"""IONEX naming and local paths, separate from orbit/clock naming.

Filename metadata describe provenance, not the TEC array geometry. Both naming
styles are accepted on either side of the operational transition. No network
requests or renaming occur in this module.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import bz2
import gzip
import io
import lzma
from pathlib import Path
import re
import shutil
import subprocess

from gnsspy.utils.date import parse_date
from gnsspy.utils.product_files import strip_compression, token_seconds, search_directories

TRANSITION_DATE = date(1980, 1, 6) + timedelta(weeks=2238)
LONG = re.compile(
    r'^(?P<center>[A-Z0-9]{3})(?P<version>\d)(?P<project>[A-Z0-9]{3})'
    r'(?P<solution>[A-Z0-9]{3})_(?P<stamp>\d{11})_'
    r'(?P<duration>\d{2}[DHMSU])_(?P<sampling>\d{2}[DHMSU])_'
    r'(?P<content>GIM|ROT)\.INX$', re.I)
SHORT = re.compile(r'^(?P<prefix>[A-Z0-9]{4})(?P<doy>\d{3})(?P<session>\d)'
                   r'\.(?P<year>\d{2})(?P<kind>[IF])$', re.I)
LEGACY = {'igsg': ('IGS', 'FIN'), 'igrg': ('IGS', 'RAP'),
          'igpg': ('IGS', 'PRE'), 'codg': ('COD', 'FIN'),
          'jplg': ('JPL', 'FIN'), 'jplq': ('JPL', 'QCK'),
          'esag': ('ESA', 'FIN'), 'upcg': ('UPC', 'FIN'),
          'casg': ('CAS', 'FIN'), 'whug': ('WHU', 'FIN'),
          'emrg': ('EMR', 'FIN'), 'uqrg': ('UQR', 'RAP')}
SOLUTION_RANK = {'FIN': 0, 'RAP': 1, 'QCK': 2, 'PRE': 3}


@dataclass(frozen=True)
class IonexName:
    path: Path
    center: str
    solution: str
    start: datetime
    content: str = 'GIM'
    project: str = 'OPS'
    version: str = '0'
    duration: str = '01D'
    sampling: str = '00U'
    prefix: str | None = None

    @property
    def series(self):
        return self.prefix.upper() if self.prefix else self.center+self.version+self.project+self.solution


@dataclass(frozen=True)
class IonexRequest:
    center: str | None
    solutions: tuple[str, ...]
    project: str | None = None
    version: str | None = None
    prefix: str | None = None

    def matches(self, info):
        return (info.content == 'GIM' and info.solution in self.solutions
                and (self.center is None or info.center == self.center)
                and (self.project is None or info.project == self.project)
                and (self.version is None or info.version == self.version)
                and (self.prefix is None or info.prefix == self.prefix))


def parse_ionex_name(path) -> IonexName | None:
    """Case-insensitive names; JPLQ is retained as a distinct quick-look stream."""
    path = Path(path)
    name, _ = strip_compression(path)
    m = LONG.fullmatch(name)
    try:
        if m:
            g = {k: v.upper() for k, v in m.groupdict().items()}
            start = datetime.strptime(g['stamp'], '%Y%j%H%M')
            if start.strftime('%Y%j%H%M') != g['stamp']:
                return None
            if token_seconds(g['duration']) == 0 or token_seconds(g['sampling']) == 0:
                return None
            return IonexName(path, g['center'], g['solution'], start, g['content'],
                             g['project'], g['version'], g['duration'], g['sampling'])
        m = SHORT.fullmatch(name)
        if not m:
            return None
        g = m.groupdict()
        year = int(g['year']) + (1900 if int(g['year']) >= 80 else 2000)
        start = datetime(year, 1, 1) + timedelta(days=int(g['doy'])-1)
        if start.year != year or int(g['doy']) < 1:
            return None
        prefix = g['prefix'].lower()
        content = 'ROT' if g['kind'].upper() == 'F' or prefix == 'roti' else 'GIM'
        center, solution = LEGACY.get(prefix, (prefix[:3].upper(), 'UNKNOWN'))
        return IonexName(path, center, solution, start, content, prefix=prefix)
    except (ValueError, OverflowError):
        return None


def is_ionex_path(path):
    name, _ = strip_compression(path)
    return name.lower().endswith('.inx') or SHORT.fullmatch(name) is not None


def ionex_request(product='IGS', ion_type='auto') -> IonexRequest:
    text = str(product or 'auto').upper()
    typ = str(ion_type).lower()
    typ = {'fin': 'final', 'rap': 'rapid', 'pre': 'predicted'}.get(typ, typ)
    if typ not in {'auto', 'final', 'rapid', 'predicted'}:
        raise ValueError('ion_type must be auto, final, rapid or predicted')
    selected = {'final': 'FIN', 'rapid': 'RAP', 'predicted': 'PRE'}.get(typ)
    project = version = prefix = pinned = None
    if text in {'AUTO', 'ANY'}:
        center = None
    elif text.lower() in LEGACY:
        prefix = text.lower()
        center, pinned = LEGACY[prefix]


        if prefix in {'igsg', 'igrg', 'codg', 'jplg', 'esag', 'upcg', 'casg', 'whug', 'emrg'}:
            prefix = None
            project, version = 'OPS', '0'
    elif text in {'IGR', 'IGP'}:
        center, pinned = 'IGS', {'IGR': 'RAP', 'IGP': 'PRE'}[text]
        project, version = 'OPS', '0'
    elif re.fullmatch(r'[A-Z0-9]{3}\d[A-Z0-9]{6}', text):
        center, version, project, pinned = text[:3], text[3], text[4:7], text[7:]
    else:
        center = {'CODE': 'COD'}.get(text, text)
        project = 'OPS'
        if not re.fullmatch(r'[A-Z0-9]{3}', center):
            raise ValueError(f'Invalid ionosphere product {product!r}; use IGS, CODE, JPLQ or a full series')
    if selected and pinned and selected != pinned:
        raise ValueError('ion_type conflicts with the explicitly requested ionosphere series')
    solutions = (selected or pinned,) if selected or pinned else ('FIN', 'RAP')
    return IonexRequest(center, solutions, project, version, prefix)


def ionex_filename(day, product='IGS', *, solution='final', sampling=None, legacy=None, zipped=False):
    """Generate an IONEX filename candidate without checking availability.

    Predicted products use supported legacy prefixes; automatic generation of
    modern predicted-product names is not supported.
    """
    day = parse_date(day)
    req = ionex_request(product, solution)
    if req.center is None or len(req.solutions) != 1:
        raise ValueError('One centre and solution are required to generate a filename')
    sol = req.solutions[0]
    legacy = (day < TRANSITION_DATE or req.prefix is not None or sol in {'PRE', 'QCK'}) if legacy is None else legacy
    if legacy:
        prefix = req.prefix or next((p for p, family in LEGACY.items() if family == (req.center, sol)), None)
        if prefix is None:
            raise ValueError('No verified legacy prefix for this series; use a long filename or an explicit path')
        if req.project not in {None, 'OPS'} or req.version not in {None, '0'}:
            raise ValueError('A legacy name cannot preserve this project/version')
        name = f'{prefix}{day:%j}0.{day:%y}i'
        return name + ('.Z' if zipped else '')
    if sol not in {'FIN', 'RAP'}:
        raise ValueError('No modern filename mapping is defined here for predicted/quick-look products; supply an actual path')
    sampling = (sampling or ('01H' if req.center == 'COD' else '02H')).upper()
    if token_seconds(sampling) == 0:
        raise ValueError('Sampling must not be zero')
    return f'{req.center}{req.version or "0"}{req.project or "OPS"}{sol}_{day:%Y%j}0000_01D_{sampling}_GIM.INX' + ('.gz' if zipped else '')


def ionex_directories(data_dir=None):
    roots = search_directories(data_dir, 'ionosphere')
    root = Path(data_dir).expanduser() if data_dir is not None else Path.cwd()
    roots += [root/'ionex', root/'data'/'ionex']
    return list(dict.fromkeys(p.resolve() for p in roots))


def local_ionex_paths(data_dir=None):
    out = []
    for directory in ionex_directories(data_dir):
        if directory.is_dir():
            out.extend(p.resolve() for p in sorted(directory.iterdir()) if p.is_file() and is_ionex_path(p))
    return list(dict.fromkeys(out))


def find_ionex_files(day, product='IGS', ion_type='auto', *, data_dir=None, files=None):
    """Nominal day/series filtering. Call the reader to validate actual content."""
    day = parse_date(day)
    req = ionex_request(product, ion_type)
    paths = local_ionex_paths(data_dir) if files is None else files
    result = []
    for path in dict.fromkeys(Path(p).resolve() for p in paths):
        info = parse_ionex_name(path)
        if not info or not path.is_file() or not req.matches(info):
            continue
        duration = token_seconds(info.duration) or 86400
        if info.start < datetime.combine(day+timedelta(days=1), datetime.min.time()) and info.start+timedelta(seconds=duration) > datetime.combine(day, datetime.min.time()):
            result.append(info)
    return sorted(result, key=lambda p: (SOLUTION_RANK.get(p.solution, 9),
        0 if p.center == (req.center or 'IGS') else 1, p.center, p.project, p.version,
        token_seconds(p.sampling) or float('inf'), bool(strip_compression(p.path)[1]), str(p.path)))


def resolve_ionex_path(filename, data_dir=None):
    path = Path(filename).expanduser()
    if path.is_file():
        return path.resolve()
    directories = list(dict.fromkeys([path.parent.resolve()] + ionex_directories(data_dir)))
    requested, _ = strip_compression(path)
    paths = []
    for directory in directories:
        if not directory.is_dir():
            continue
        paths += [p for p in sorted(directory.iterdir()) if p.is_file() and is_ionex_path(p)]
        exact = [p for p in directory.iterdir() if p.is_file() and strip_compression(p)[0].lower() == requested.lower()]
        if exact:
            return sorted(exact, key=lambda p: (bool(strip_compression(p)[1]), str(p)))[0].resolve()
    info = parse_ionex_name(path)
    if info and info.content == 'GIM' and info.solution in SOLUTION_RANK:
        matches = find_ionex_files(info.start.date(), info.series, files=paths)
        if matches:
            return matches[0].path
    raise FileNotFoundError(f'IONEX file not found: {filename}. Supply its actual path or use acquire_ionosphere(); no file was renamed or downloaded.')


@contextmanager
def open_ionex_text(path):
    """Non-destructive decompression; Latin-1 preserves non-ASCII header comments.

    Numeric fields are still parsed strictly. The optional system gzip fallback
    supports .Z on machines where the declared unlzw3 dependency is unavailable.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == '.z':
        try:
            from unlzw3 import unlzw
        except ImportError:
            executable = shutil.which('gzip')
            if executable is None:
                raise ImportError('Reading .Z IONEX requires unlzw3 or a gzip executable; install unlzw3 or decompress the file') from None
            try:
                result = subprocess.run([executable, '-cd', '--', str(path.resolve())],
                                        capture_output=True, check=True, timeout=30)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ValueError(f'Cannot decompress .Z IONEX {path}: {exc}') from exc
            data = result.stdout
        else:
            data = unlzw(path.read_bytes())
        with io.StringIO(data.decode('latin1')) as stream:
            yield stream
    else:
        opener = {'.gz': gzip.open, '.bz2': bz2.open, '.xz': lzma.open}.get(suffix, open)
        with opener(path, 'rt', encoding='latin1') as stream:
            yield stream
