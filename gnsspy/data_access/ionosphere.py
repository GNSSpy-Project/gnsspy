"""Local-first GIM acquisition with explicit provenance and bounded retries."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import warnings

from gnsspy.utils.date import parse_date
from gnsspy.utils.ionex_files import (
    TRANSITION_DATE, LEGACY, IonexName, find_ionex_files, ionex_filename,
    ionex_request, local_ionex_paths, parse_ionex_name, token_seconds,
)
from gnsspy.data_access.config import IONOSPHERE_URL


@dataclass(frozen=True)
class IonosphereResult:
    path: Path | None = None
    action: str = 'missing'
    url: str | None = None
    product: IonexName | None = None
    attempted_urls: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    detail: str = ''

    @property
    def success(self):
        return self.path is not None

    @property
    def message(self):
        if self.success:
            verb = 'reused locally (no download)' if self.action == 'reused' else 'downloaded'
            series = f' [{self.product.series}]' if self.product else ''
            return f'IONEX {verb}{series}: {self.path}' + (f'\n  IONEX LINK: {self.url}' if self.url else '')
        message = 'IONEX missing: '+(self.detail or 'no valid matching GIM product was found')
        if self.errors:
            message += '\nLast acquisition error: '+self.errors[-1]
        return message


def validate_ionex_payload(path, expected_name=None):
    """Full structural parsing, including compressed CRC and content-date checks."""
    from gnsspy.io.products.ionex import read_ionex
    data = read_ionex(path)
    info = parse_ionex_name(expected_name or path)
    if info and (info.content != 'GIM' or data.epochs[0].to_pydatetime() != info.start):
        raise ValueError('IONEX content type/start epoch does not match the requested filename')
    return data


def ionex_candidates(day, product='IGS', ion_type='auto', sampling=None):
    """Generate a bounded sequence of archive candidates.

    Modern products use year/day-of-year and GPS-week directory candidates.
    Legacy products use year/day-of-year directories. The product date controls
    candidate order. Predicted products require an explicit request.
    """
    day = parse_date(day)
    req = ionex_request(product, ion_type)
    center = req.center or 'IGS'
    week = (day-parse_date('1980-01-06')).days // 7
    rates = [sampling.upper()] if sampling else (['01H', '02H', '15M', '30M'] if center == 'COD' else ['02H', '01H', '15M', '30M'])
    for rate in rates:
        if token_seconds(rate) == 0:
            raise ValueError('sampling must not be zero')
    output = []
    for solution in req.solutions:
        modern, old = [], []
        if solution in {'FIN', 'RAP'} and req.prefix is None:
            series = center+(req.version or '0')+(req.project or 'OPS')+solution
            for rate in rates:
                name = ionex_filename(day, series, solution='auto', sampling=rate, legacy=False, zipped=True)
                for directory in (f'{day:%Y/%j}', str(week)):
                    modern.append((name, f'{IONOSPHERE_URL}/{directory}/{name}'))
        if req.project in {None, 'OPS'} and req.version in {None, '0'}:
            prefix = req.prefix or next((p for p, family in LEGACY.items() if family == (center, solution)), None)
            if prefix:
                base = f'{prefix}{day:%j}0.{day:%y}i'
                for suffix in ('.Z', '.gz', ''):
                    name = base+suffix
                    old.append((name, f'{IONOSPHERE_URL}/{day:%Y/%j}/{name}'))
        output.extend(old+modern if day < TRANSITION_DATE else modern+old)
    return list(dict.fromkeys(output))


def acquire_ionosphere(downloader, day, ion_type='auto', *, product='IGS',
                       allow_download=True, sampling=None, max_attempts=None):
    """Find/download one valid TEC GIM. Never substitutes ROT or a prediction."""
    day = parse_date(day)
    ionex_request(product, ion_type)
    if sampling is not None:
        sampling = sampling.upper()
        if token_seconds(sampling) == 0:
            raise ValueError('sampling must not be zero')
    limit = max_attempts if max_attempts is not None else downloader.ionosphere_max_attempts
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError('max_attempts must be a positive integer')
    errors, attempted = [], []

    def finish(**kwargs):
        result = IonosphereResult(attempted_urls=tuple(attempted), errors=tuple(errors), **kwargs)
        downloader.last_ionosphere_result = result
        return result

    paths = local_ionex_paths(downloader.output_dir) + local_ionex_paths()
    for info in find_ionex_files(day, product, ion_type, files=paths):
        if sampling and info.sampling != '00U' and info.sampling != sampling:
            continue
        try:
            data = validate_ionex_payload(info.path)
            if sampling and info.sampling == '00U' and data.metadata['interval_seconds'] != token_seconds(sampling):
                continue
        except (OSError, ValueError, ImportError, EOFError) as exc:
            errors.append(f'Invalid IONEX cache entry {info.path}: {exc}')
            warnings.warn(errors[-1], RuntimeWarning, stacklevel=2)
            continue
        return finish(path=info.path.resolve(), action='reused', product=info)
    if not allow_download:
        return finish(detail=f'no valid local {product}/{ion_type} GIM for {day}; downloads are disabled')
    candidates = ionex_candidates(day, product, ion_type, sampling)
    if not candidates:
        return finish(detail='no remote filename mapping for the requested series; supply the original local GIM path')
    target = downloader.output_dir/'ionosphere'
    target.mkdir(parents=True, exist_ok=True)
    for name, url in candidates:
        if len(attempted) >= limit:
            return finish(detail=f'reached the {limit}-request limit; supply a manually downloaded GIM or check archive availability')
        path = target/name


        attempted.append(url)
        success, message = downloader.download_file(url, path)
        if success:
            try:
                validate_ionex_payload(path)
            except (OSError, ValueError, ImportError, EOFError) as exc:
                errors.append(f'{url}: downloaded response is not a valid matching GIM: {exc}')
                return finish(detail='invalid product response; not reported as a successful acquisition')
            reused = message.lower().startswith('reused locally')
            if reused:
                attempted.pop()
            return finish(path=path.resolve(), action='reused' if reused else 'downloaded',
                          url=None if reused else url, product=parse_ionex_name(path))
        errors.append(f'{url}: {message}')


        if '404' not in message:
            return finish(detail='search stopped after an access/transport/validation failure; inspect the error before retrying')
    return finish(detail=f'no available matching {product}/{ion_type} GIM for {day}; all candidates returned 404')
