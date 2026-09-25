"""Header-driven IONEX 1.x reader for two-dimensional TEC maps.

read_ionex returns TECU, coordinates and epochs. read_ionFile and
read_ionex_file return raw arrays unless return_dataset=True.
Reading does not download or modify the input file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from gnsspy.utils._datetime import interval_seconds
from gnsspy.utils.ionex_files import open_ionex_text, parse_ionex_name, resolve_ionex_path


class IonexFormatError(ValueError):
    """An invalid, truncated or inconsistent IONEX file."""


class IonexProductError(IonexFormatError):
    """An ionospheric product which is not a vertical TEC map."""


@dataclass
class IonexDataset:
    """Two-dimensional maps, in file order: (epoch, latitude, longitude).

    TEC/RMS are in TECU, coordinates in degrees, height in kilometres. Epochs
    are timezone-naive UT/UTC labels, NOT automatically converted from GPST.
    The duplicate longitude seam, where supplied, is retained in this object.
    """
    epochs: pd.DatetimeIndex
    latitudes: np.ndarray
    longitudes: np.ndarray
    tec: np.ndarray
    raw_tec: np.ndarray
    source: Path
    height_km: float
    rms: np.ndarray | None = None
    height_maps_km: np.ndarray | None = None
    metadata: dict = field(default_factory=dict)

    @property
    def shape(self):
        return self.tec.shape

    def interpolate(self, latitude, longitude, epochs, *, bounds='nan', max_gap=None):
        """Bilinear + linear-in-time VTEC; latitude is geocentric, time is UTC."""
        from gnsspy.atmosphere.ionosphere import interpolate_vtec
        return interpolate_vtec(self, latitude, longitude, epochs, bounds=bounds, max_gap=max_gap)


_LABELS = [
    'IONEX VERSION / TYPE', 'EPOCH OF FIRST MAP', 'EPOCH OF LAST MAP',
    '# OF MAPS IN FILE', 'MAP DIMENSION', 'HGT1 / HGT2 / DHGT',
    'LAT1 / LAT2 / DLAT', 'LON1 / LON2 / DLON', 'BASE RADIUS',
    'INTERVAL', 'EXPONENT', 'END OF HEADER', 'END OF FILE',
    'EPOCH OF CURRENT MAP', 'LAT/LON1/LON2/DLON/H',
    'START OF TEC MAP', 'END OF TEC MAP', 'START OF RMS MAP', 'END OF RMS MAP',
    'START OF HEIGHT MAP', 'END OF HEIGHT MAP', 'COMMENT', 'DESCRIPTION',
]


def _label(line):


    tail = line.rstrip()
    return next((label for label in _LABELS if tail.endswith(label)), '')


def _body(line, label):
    return line.rstrip()[:-len(label)] if label else line


def _epoch(text):
    parts = text.split()
    if len(parts) != 6:
        raise ValueError('expected six epoch fields')
    y, m, d, h, minute = map(int, parts[:5])
    sec = float(parts[5])
    if not 0 <= h <= 24 or not 0 <= minute < 60 or not 0 <= sec < 60:
        raise ValueError('invalid epoch time')
    if h == 24 and (minute or sec):
        raise ValueError('24-hour epoch must be midnight')
    return datetime(y, m, d) + timedelta(hours=h, minutes=minute, seconds=sec)


def _fields(text, count):

    out = [float(text[2+6*i:8+6*i]) for i in range(count)]
    if not np.all(np.isfinite(out)):
        raise ValueError('non-finite coordinate')
    return out


def _axis(values, label):
    first, last, step = values
    if first == last:
        return np.array([first], dtype=float)
    if step == 0 or (last-first)/step < 0:
        raise ValueError(f'invalid {label} increment')
    n = (last-first)/step
    if not np.isclose(n, round(n), atol=1e-7, rtol=0) or n > 100000:
        raise ValueError(f'inconsistent or excessive {label} grid')
    return first + np.arange(round(n)+1)*step


def read_ionex(filename, *, data_dir=None) -> IonexDataset:
    """Read a complete 2-D GIM from its original name, including .Z/.gz.

    Header exponent and per-block exponent changes are applied once. Sentinel
    9999 is NaN in both raw and scaled arrays. RMS maps are aligned by map number
    and epoch. AUX bias text is retained in metadata, not used as a correction.
    Three-dimensional electron-density maps are rejected explicitly.
    """
    path = resolve_ionex_path(filename, data_dir)
    info = parse_ionex_name(path)
    if info and info.content == 'ROT':
        raise IonexProductError(f'{path.name}: ROT/ROTI is a TEC-fluctuation index in magnetic coordinates, not a GIM/VTEC map; it cannot be used for ionospheric delay conversion.')
    with open_ionex_text(path) as stream:
        lines = stream.read().splitlines()
    if any('ROTIPOLARMAP' in line.upper() or 'IGS ROTI MAPS' in line.upper() for line in lines[:35]):
        raise IonexProductError(f'{path.name}: ROTI polar-map content is not a GIM/VTEC map; use a TEC product, not ROT.INX.')

    def fail(i, message):
        raise IonexFormatError(f'{path}: line {i+1}: {message}')

    if not lines or _label(lines[0]) != 'IONEX VERSION / TYPE':
        fail(0, 'missing IONEX VERSION / TYPE (possibly an HTML/login page or wrong product)')
    try:
        version = float(lines[0][:8])
    except ValueError:
        fail(0, 'invalid IONEX version')
    if not 1 <= version < 2:
        fail(0, f'unsupported IONEX version {version}')
    header = {'EXPONENT': -1, 'INTERVAL': 0, 'BASE RADIUS': None}
    header_lines = []
    end = None
    for i, line in enumerate(lines[1:], 1):
        label = _label(line)
        text = _body(line, label).strip()
        header_lines.append(line)
        try:
            if label == 'END OF HEADER':
                end = i+1
                break
            if label in {'EXPONENT', '# OF MAPS IN FILE', 'MAP DIMENSION', 'INTERVAL'}:
                header[label] = int(text)
            elif label in {'EPOCH OF FIRST MAP', 'EPOCH OF LAST MAP'}:
                header[label] = _epoch(text)
            elif label == 'BASE RADIUS':
                header[label] = float(text)
            elif label in {'HGT1 / HGT2 / DHGT', 'LAT1 / LAT2 / DLAT', 'LON1 / LON2 / DLON'}:
                header[label] = _fields(_body(line, label), 3)
        except (ValueError, OverflowError) as exc:
            fail(i, f'invalid {label}: {exc}')
    if end is None:
        fail(len(lines)-1, 'missing END OF HEADER')
    required = {'# OF MAPS IN FILE', 'MAP DIMENSION', 'HGT1 / HGT2 / DHGT',
                'LAT1 / LAT2 / DLAT', 'LON1 / LON2 / DLON', 'EPOCH OF FIRST MAP', 'EPOCH OF LAST MAP'}
    if required - header.keys():
        fail(end-1, 'missing header fields: '+', '.join(sorted(required-header.keys())))
    if header['MAP DIMENSION'] != 2:
        fail(end-1, 'only 2-D VTEC maps are supported; 3-D maps must not be treated as vertical TEC')
    try:
        lats = _axis(header['LAT1 / LAT2 / DLAT'], 'latitude')
        lons = _axis(header['LON1 / LON2 / DLON'], 'longitude')
        hgts = _axis(header['HGT1 / HGT2 / DHGT'], 'height')
        if len(hgts) != 1 or len(lats)*len(lons) > 10000000 or np.max(np.abs(lats)) > 90 or np.ptp(lons) > 360+1e-6:
            raise ValueError('invalid or excessive 2-D grid')
        if header['# OF MAPS IN FILE'] < 1 or header['# OF MAPS IN FILE'] > 100000:
            raise ValueError('invalid map count')
        if header['INTERVAL'] < 0:
            raise ValueError('negative map interval')
        if not -20 <= header['EXPONENT'] <= 20:
            raise ValueError('invalid exponent')
    except (ValueError, OverflowError) as exc:
        fail(end-1, str(exc))

    maps = {'TEC': {}, 'RMS': {}, 'HEIGHT': {}}
    exponent = header['EXPONENT']
    i = end
    eof = False
    while i < len(lines):
        label = _label(lines[i])
        text = _body(lines[i], label).strip()
        if not lines[i].strip() or label in {'COMMENT', 'DESCRIPTION'}:
            i += 1
            continue
        if label == 'END OF FILE':
            eof = True
            if any(line.strip() for line in lines[i+1:]):
                fail(i+1, 'unexpected data after END OF FILE')
            break
        if label == 'EXPONENT':
            try:
                exponent = int(text)
                if not -20 <= exponent <= 20:
                    raise ValueError('exponent outside supported range')
            except ValueError as exc:
                fail(i, str(exc))
            i += 1
            continue
        if label not in {'START OF TEC MAP', 'START OF RMS MAP', 'START OF HEIGHT MAP'}:
            fail(i, 'expected START OF TEC/RMS/HEIGHT MAP, EXPONENT or END OF FILE')
        kind = label.split()[2]
        try:
            number = int(text)
        except ValueError:
            fail(i, 'invalid map number')
        if number < 1 or number in maps[kind]:
            fail(i, 'invalid or duplicate map number')
        raw = np.full((len(lats), len(lons)), np.nan)
        scaled = raw.copy()
        seen = np.zeros(len(lats), dtype=bool)
        epoch = None
        used_exponents = set()
        i += 1
        while i < len(lines):
            label = _label(lines[i])
            text = _body(lines[i], label).strip()
            if label == f'END OF {kind} MAP':
                try:
                    matches = int(text) == number
                except ValueError:
                    matches = False
                if not matches:
                    fail(i, 'START/END map numbers disagree')
                if not seen.all():
                    fail(i, f'incomplete {kind} map; missing latitude rows')
                if epoch is None:
                    if kind != 'TEC' and number in maps['TEC']:
                        epoch = maps['TEC'][number][0]
                    else:
                        fail(i, 'missing EPOCH OF CURRENT MAP')
                maps[kind][number] = (epoch, raw, scaled, sorted(used_exponents))
                i += 1
                break
            try:
                if label == 'EPOCH OF CURRENT MAP':
                    current = _epoch(text)
                    if epoch is not None and current != epoch:
                        raise ValueError('conflicting map epochs')
                    epoch = current
                elif label == 'EXPONENT':
                    exponent = int(text)
                    if not -20 <= exponent <= 20:
                        raise ValueError('exponent outside supported range')
                elif label == 'LAT/LON1/LON2/DLON/H':
                    lat, lo1, lo2, dlon, height = _fields(_body(lines[i], label), 5)
                    row = _axis([lo1, lo2, dlon], 'row longitude')
                    indices = np.flatnonzero(np.isclose(lats, lat, atol=1e-6, rtol=0))
                    if len(indices) != 1 or len(row) != len(lons) or not np.allclose(row, lons, atol=1e-6, rtol=0):
                        raise ValueError('map row does not match the header grid')
                    j = indices[0]
                    if seen[j] or not np.isclose(height, hgts[0], atol=1e-6, rtol=0):
                        raise ValueError('duplicate latitude or inconsistent layer height')
                    values = []
                    while len(values) < len(lons):
                        i += 1
                        if i >= len(lines) or _label(lines[i]):
                            fail(min(i, len(lines)-1), 'truncated numeric row')
                        row_text = lines[i].rstrip()
                        fields = [row_text[k:k+5] for k in range(0, len(row_text), 5)]
                        expected = min(16, len(lons)-len(values))
                        if len(fields) != expected or any(not f.strip() for f in fields):
                            raise ValueError(f'expected {expected} fixed-width I5 values')
                        values.extend(int(f) for f in fields)
                    data = np.asarray(values, dtype=float)
                    data[data == 9999] = np.nan
                    raw[j] = data
                    scaled[j] = data * (10.0**exponent)
                    seen[j] = True
                    used_exponents.add(exponent)
                elif label not in {'COMMENT', 'DESCRIPTION'} and lines[i].strip():
                    raise ValueError(f'unexpected record inside {kind} map')
            except (ValueError, OverflowError) as exc:
                if isinstance(exc, IonexFormatError):
                    raise
                fail(i, str(exc))
            i += 1
        else:
            fail(len(lines)-1, f'truncated {kind} map')
    if not eof:
        fail(len(lines)-1, 'missing END OF FILE; possibly truncated')
    if len(maps['TEC']) != header['# OF MAPS IN FILE']:
        fail(end-1, f"header declares {header['# OF MAPS IN FILE']} TEC maps, found {len(maps['TEC'])}")
    if set(maps['TEC']) != set(range(1, header['# OF MAPS IN FILE']+1)):
        fail(end-1, 'TEC map numbers must be 1 through the declared map count')
    entries = list(maps['TEC'].items())
    epochs = pd.DatetimeIndex([m[0] for _, m in entries], name='Epoch')
    if not epochs.is_monotonic_increasing or epochs.has_duplicates:
        fail(end-1, 'TEC map epochs must be unique and increasing')
    if epochs[0] != header['EPOCH OF FIRST MAP'] or epochs[-1] != header['EPOCH OF LAST MAP']:
        fail(end-1, 'actual first/last map epoch disagrees with header')


    step = header['INTERVAL']
    if step and len(epochs) > 1 and np.any(interval_seconds(epochs) != step):
        warnings.warn(f'{path.name}: actual map spacing differs from header INTERVAL; actual epochs are retained', RuntimeWarning, stacklevel=2)
    tec = np.stack([m[2] for _, m in entries])
    raw_tec = np.stack([m[1] for _, m in entries])
    auxiliary = {}
    for kind in ('RMS', 'HEIGHT'):
        if not maps[kind]:
            auxiliary[kind] = None
            continue
        data = np.full_like(tec, np.nan)
        by_number = {number: (j, m[0]) for j, (number, m) in enumerate(entries)}
        for number, m in maps[kind].items():
            if number not in by_number or m[0] != by_number[number][1]:
                fail(end-1, f'{kind} map has no matching TEC number/epoch')
            data[by_number[number][0]] = m[2]
        auxiliary[kind] = data + hgts[0] if kind == 'HEIGHT' else data
    metadata = {'version': version, 'time_system': 'UTC', 'units': 'TECU',
                'interval_seconds': step, 'header_exponent': header['EXPONENT'],
                'tec_exponents': [m[3] for _, m in entries],
                'base_radius_km': header['BASE RADIUS'], 'map_numbers': [n for n, _ in entries],
                'header_lines': tuple(header_lines), 'product': info,
                'missing_tec_values': int(np.isnan(tec).sum()),
                'missing_rms_values': int(np.isnan(auxiliary['RMS']).sum()) if auxiliary['RMS'] is not None else None}
    return IonexDataset(epochs, lats, lons, tec, raw_tec, path, float(hgts[0]),
                        auxiliary['RMS'], auxiliary['HEIGHT'], metadata)


def read_ionFile(IonFile, *, return_dataset=False, data_dir=None, verbose=False):
    """Read raw IONEX numbers, removing a duplicate longitude endpoint.

    The raw array requires the file's declared exponent to obtain TECU.
    Use read_ionex(...).tec or return_dataset=True for physical units and
    coordinates. Array dimensions follow the source maps.
    """
    data = read_ionex(IonFile, data_dir=data_dir)
    if verbose:
        print(f'IONEX read locally: {data.source} ({len(data.epochs)} maps)')
    if return_dataset:
        return data
    warnings.warn('read_ionFile/read_ionex_file array mode returns RAW IONEX numbers, not TECU. '
                  'Use read_ionex(...).tec or return_dataset=True for scaled values and coordinates.',
                  FutureWarning, stacklevel=2)
    raw = data.raw_tec
    if len(data.longitudes) > 1 and np.isclose(abs(data.longitudes[-1]-data.longitudes[0]), 360):
        raw = raw[:, :, :-1]
    return raw.copy()


read_ionex_file = read_ionFile
__all__ = ['read_ionFile', 'read_ionex_file', 'read_ionex', 'IonexDataset',
           'IonexFormatError', 'IonexProductError']
