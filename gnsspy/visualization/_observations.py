"""Non-mutating observation selection for plots; no synthetic signal aliases."""
from __future__ import annotations

from collections.abc import Mapping
import re
import warnings
import numpy as np
import pandas as pd

from gnsspy.utils._datetime import interval_seconds

SNR_CODE = re.compile(r'^S[1-9][A-Z]?$')
PRIORITY = {
    'G': ('S1C', 'S1', 'S1W', 'S2W', 'S2L', 'S5Q'),
    'E': ('S1C', 'S1X', 'S1', 'S5Q', 'S7Q', 'S8Q'),
    'C': ('S2I', 'S1P', 'S1D', 'S1X', 'S2X', 'S7I', 'S6I'),
    'R': ('S1C', 'S1P', 'S1', 'S2C', 'S2P'),
    'J': ('S1C', 'S1', 'S2L', 'S5Q'),
    'I': ('S5A', 'S5', 'S9A'),
    'S': ('S1C', 'S1', 'S5I'),
}


def systems(value):
    if value is None or (isinstance(value, str) and value.upper().strip() in {'AUTO', 'ALL', 'M', ''}):
        return None
    tokens = list(value.upper().replace('+', '').replace(',', '').replace(' ', '')) if isinstance(value, str) else [str(x).upper() for x in value]
    if not tokens or any(x not in 'GRECJIS' or len(x) != 1 for x in tokens):
        raise ValueError('system must be auto/all, a constellation letter, or a combination such as G+E+C')
    return tuple(dict.fromkeys(tokens))


def satellites(value):
    if value is None or (isinstance(value, str) and value.strip().upper() in {'AUTO', 'ALL', ''}):
        return None
    if isinstance(value, str):
        value = re.split(r'[,;+\s]+', value.strip().upper())
    result = [str(x).upper() for x in value]
    if not result or any(re.fullmatch(r'[GRECJIS]\d{2,3}', x) is None for x in result):
        raise ValueError('sv_list must be auto/all, a satellite ID, or a list of satellite IDs')
    return result


def indexed(frame):
    if not isinstance(frame, pd.DataFrame):
        raise TypeError('observations/orbits must be pandas DataFrames')
    if {'Epoch', 'SV'}.issubset(frame.index.names):
        result = frame.reorder_levels(['SV', 'Epoch']).sort_index().copy()
    elif {'Epoch', 'SV'}.issubset(frame.columns):
        result = frame.set_index(['SV', 'Epoch']).sort_index().copy()
    else:
        raise ValueError('a named (Epoch, SV) index or these two columns is required')
    if result.index.has_duplicates:
        raise ValueError('duplicate (Epoch, SV) rows must be resolved before plotting')
    if not isinstance(result.index.get_level_values('Epoch'), pd.DatetimeIndex):
        raise TypeError('Epoch must contain pandas datetime values')
    return result


def observations(station, system='G', sv_list=None):
    if station is None or not hasattr(station, 'observation'):
        raise TypeError('station must have an observation DataFrame')
    frame = indexed(station.observation)
    selected, svs = systems(system), satellites(sv_list)
    ids = frame.index.get_level_values('SV')
    if selected is not None:
        frame = frame[ids.str[0].isin(selected)]
    if svs is not None:
        frame = frame[frame.index.get_level_values('SV').isin(svs)]
    if frame.empty:
        raise ValueError('No observations match the requested constellation/satellites')
    return frame


def snr_columns(frame):


    aliases = frame.attrs.get('gnsspy_snr_aliases', {})
    return sorted(c for c in frame.columns if isinstance(c, str) and SNR_CODE.fullmatch(c) and c not in aliases)


def select_snr(frame, snr_code='auto'):
    """Select one measured signal per SV, fixed for the selected observation span.

    Auto maximises finite positive sample coverage, then uses constellation
    priority and lexical order to resolve ties. It NEVER fills a missing epoch
    from another signal. Explicit codes are strict; a mapping can key by SV or
    constellation (an optional 'default' key may be used).
    """
    if snr_code is None:
        snr_code = 'auto'
    if not isinstance(snr_code, (str, Mapping)):
        raise TypeError('snr_code must be auto, a RINEX S-code, or a mapping')
    candidates = snr_columns(frame)
    chosen, details, missing = {}, {}, {}
    for sv, group in frame.groupby(level='SV', sort=True):
        request = snr_code
        if isinstance(request, Mapping):
            request = request.get(sv, request.get(sv[0], request.get('default', 'auto')))
        request = str(request).strip().upper()
        if request != 'AUTO' and SNR_CODE.fullmatch(request) is None:
            raise ValueError(f'Invalid SNR code {request!r}; use auto or a measured S-code such as S1C')
        counts = {}
        for code in candidates:
            vals = pd.to_numeric(group[code], errors='coerce').to_numpy(dtype=float)
            counts[code] = int((np.isfinite(vals) & (vals > 0)).sum())
        if request != 'AUTO':
            if counts.get(request, 0) == 0:
                raise ValueError(f'{sv}: requested {request} has no finite positive observations; available: {counts}')
            code = request
        else:
            available = [code for code, count in counts.items() if count > 0]
            if not available:
                missing[sv] = 'no finite positive measured SNR values'
                continue
            order = PRIORITY.get(sv[0], ())
            code = min(available, key=lambda c: (-counts[c], order.index(c) if c in order else len(order), c))
        chosen[sv] = code
        details[sv] = {'code': code, 'valid_samples': counts[code], 'total_samples': len(group), 'candidate_counts': counts}
    if missing:
        warnings.warn('No usable SNR for: ' + ', '.join(missing) + '; omitted from SNR plots (no elevation substitution).', RuntimeWarning, stacklevel=2)
    if not chosen:
        raise RuntimeError('No plottable SNR observations; select elevation explicitly or provide measured SNR data')
    return chosen, details, missing


def snr_values(group, code):
    vals = pd.to_numeric(group[code], errors='coerce').to_numpy(dtype=float)
    return np.where(np.isfinite(vals) & (vals > 0), vals, np.nan)


def geometry(station, orbit, frame, cut_off=0.0):
    """Use GNSSpy's existing ECEF-to-azimuth/elevation formula, without clocks.

    Geometry-only visualisation does not require Doppler, velocities, satellite
    clocks, relativistic clock terms or tropospheric delays.
    """
    from gnsspy.orbit.satellite import _azel
    if orbit is None:
        raise ValueError('orbit data are required for sky/elevation plots')
    cut_off = float(cut_off)
    if not np.isfinite(cut_off) or not 0 <= cut_off < 90:
        raise ValueError('cut_off must be finite in [0, 90) degrees')
    xyz = indexed(orbit)
    if not {'X', 'Y', 'Z'}.issubset(xyz.columns):
        raise ValueError('orbit must contain X, Y and Z')
    unit = str(orbit.attrs.get('position_unit', 'm')).lower()
    if unit not in {'m', 'km'}:
        raise ValueError('orbit position_unit must be m or km')
    obs_time = str(frame.attrs.get('time_system', '')).upper()
    orb_time = str(orbit.attrs.get('time_system', '')).upper()
    synonyms = {'GPST': 'GPS'}
    if obs_time and orb_time and synonyms.get(obs_time, obs_time) != synonyms.get(orb_time, orb_time):
        raise ValueError(f'Observation time system {obs_time} differs from orbit {orb_time}; convert explicitly first')
    receiver = np.asarray(station.approx_position, dtype=float)
    if receiver.shape != (3,) or not np.isfinite(receiver).all() or not 6e6 <= np.linalg.norm(receiver) <= 7e6:
        raise ValueError('station.approx_position must be a plausible terrestrial ECEF position in metres')
    aligned = xyz[['X', 'Y', 'Z']].reindex(frame.index).to_numpy(
        dtype=float, copy=True
    )
    aligned *= 1000.0 if unit == 'km' else 1.0
    norm = np.linalg.norm(aligned, axis=1)
    valid = np.isfinite(aligned).all(axis=1) & (norm > 6.4e6)
    out = frame.copy()
    out['Azimuth'] = np.nan
    out['Elevation'] = np.nan
    if valid.any():
        positions = aligned[valid]
        dist = np.linalg.norm(positions - receiver, axis=1)
        az, el, _ = _azel(*receiver, *positions.T, dist)
        out.loc[valid, 'Azimuth'] = (np.asarray(az) + 360.0) % 360.0
        out.loc[valid, 'Elevation'] = el
    missing = int((~valid).sum())
    if missing:
        warnings.warn(f'{missing} observation rows have no valid orbit at the exact epoch; geometry is left missing.', RuntimeWarning, stacklevel=2)
    out.loc[out['Elevation'] <= cut_off, ['Azimuth', 'Elevation']] = np.nan
    if not out['Elevation'].notna().any():
        raise RuntimeError('No plottable observations above cut_off with matching orbit epochs')
    return out


def gap_seconds(station, times, max_gap):
    if max_gap is not None:
        value = float(max_gap)
        if not np.isfinite(value) or value <= 0:
            raise ValueError('max_gap must be positive finite seconds')
        return value
    nominal = getattr(station, 'interval', None)
    try:
        nominal = nominal.total_seconds() if hasattr(nominal, 'total_seconds') else float(nominal)
    except (TypeError, ValueError):
        nominal = np.nan
    if not np.isfinite(nominal) or nominal <= 0:
        diff = interval_seconds(times)
        nominal = np.median(diff[diff > 0]) if np.any(diff > 0) else 30.0
    return 1.5 * nominal


def labels(station):
    attrs = station.observation.attrs
    scale = attrs.get('time_system', 'RINEX epoch')
    if scale == 'GPS':
        scale = 'GPST'
    unit = attrs.get('signal_strength_unit', 'RINEX units')
    if str(unit).upper() in {'DBHZ', 'DB-HZ'}:
        unit = 'dB-Hz'
    return f'Time ({scale})', f'SNR ({unit})'
