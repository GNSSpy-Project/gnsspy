"""Earth-fixed VTEC interpolation and vertical first-order group delay.

These functions do not compute a satellite ionospheric pierce point or map
VTEC to slant TEC. All IONEX interpolation epochs must be UT/UTC.
"""
from __future__ import annotations

from pathlib import Path
import warnings
import numpy as np
import pandas as pd

from gnsspy.io.products.ionex import IonexDataset, read_ionex
from gnsspy.positioning.observations import _observation_picker_by_band

__all__ = ['ionosphere_interp', 'interpolate_ionosphere', 'compute_ionospheric_delay',
           'interpolate_vtec']


def _utc_epochs(values):
    if isinstance(values, (str, pd.Timestamp, np.datetime64)) or not hasattr(values, '__iter__'):
        values = [values]
    try:
        epochs = pd.DatetimeIndex(values)
        if epochs.tz is not None:
            epochs = epochs.tz_convert('UTC').tz_localize(None)
    except (TypeError, ValueError) as exc:
        raise ValueError('epochs must be datetime-like UTC values with consistent timezone information') from exc
    return epochs


def _bracket(axis, value):
    if not np.isfinite(value):
        return None
    pos = int(np.searchsorted(axis, value))
    for i in (pos, pos-1):
        if 0 <= i < len(axis) and np.isclose(axis[i], value, atol=1e-10, rtol=0):
            return i, i, 0.0
    if pos == 0 or pos == len(axis):
        return None
    return pos-1, pos, (value-axis[pos-1])/(axis[pos]-axis[pos-1])


def _weighted(values, weights):


    needed = np.asarray(weights) > 0
    values = np.asarray(values)[needed]
    weights = np.asarray(weights)[needed]
    return np.dot(values, weights) if np.isfinite(values).all() else np.nan


def interpolate_vtec(data, latitude, longitude, epochs, *, bounds='nan', max_gap=None):
    """Bilinear spatial + linear temporal interpolation of physical VTEC.

    Parameters
    ----------
    data : IonexDataset
    latitude, longitude : float or vectors of length len(epochs)
        Geocentric latitude and east-positive longitude, in degrees.
    epochs : datetime-like sequence
        UT/UTC; timezone-aware civil epochs are normalised to UTC. Unsorted
        requests and duplicate requests retain their input order.
    bounds : {'nan', 'raise'}
        Handling of out-of-coverage coordinates/times and excessive gaps.
        Missing source values remain NaN even with bounds='raise'.
    max_gap : float, optional
        Maximum map interval bridged, in seconds. Default: 1.5 times the header
        INTERVAL when positive; otherwise actual adjacent maps are used.
        Set explicitly for irregular (INTERVAL=0) products.

    This is interpolation between Earth-fixed maps, not the optional
    Sun-fixed/rotated-map interpolation described in the IONEX specification.
    """
    if not isinstance(data, IonexDataset):
        raise TypeError('data must be an IonexDataset from read_ionex')
    if bounds not in {'nan', 'raise'}:
        raise ValueError('bounds must be nan or raise')
    times = _utc_epochs(epochs)
    n = len(times)
    try:
        lat = np.broadcast_to(np.asarray(latitude, dtype=float), (n,))
        lon = np.broadcast_to(np.asarray(longitude, dtype=float), (n,))
    except ValueError as exc:
        raise ValueError('coordinates must be scalars or have one value per epoch') from exc
    if max_gap is None:
        interval = data.metadata.get('interval_seconds', 0)
        max_gap = interval*1.5 if interval else np.inf
    if isinstance(max_gap, bool) or np.isnan(max_gap) or max_gap <= 0:
        raise ValueError('max_gap must be a positive number of seconds')
    lat_order = np.argsort(data.latitudes)
    lon_order = np.argsort(data.longitudes)
    la = np.asarray(data.latitudes)[lat_order]
    lo = np.asarray(data.longitudes)[lon_order]
    grid = data.tec[:, lat_order][:, :, lon_order]
    if len(lo) > 1:
        step = lo[1]-lo[0]
        duplicate_seam = np.isclose(lo[-1]-lo[0], 360, atol=1e-6, rtol=0)
        periodic = duplicate_seam or np.isclose(lo[-1]-lo[0]+step, 360, atol=1e-6, rtol=0)
        if periodic and not duplicate_seam:
            lo = np.r_[lo, lo[0]+360]
            grid = np.concatenate([grid, grid[:, :, :1]], axis=2)
    else:
        periodic = False
    source_epochs = pd.DatetimeIndex(data.epochs)
    result = np.full(n, np.nan)

    def invalid(k, detail):
        if bounds == 'raise':
            raise ValueError(f'IONEX request {k}: {detail}')

    for k, (phi, lam, epoch) in enumerate(zip(lat, lon, times)):
        if pd.isna(epoch) or not np.isfinite(phi) or not np.isfinite(lam):
            invalid(k, 'non-finite coordinate or NaT epoch')
            continue
        if periodic:
            lam = (lam-lo[0]) % 360 + lo[0]
        else:


            lam += 360*round(((lo[0]+lo[-1])/2-lam)/360)
        a, b = _bracket(la, phi), _bracket(lo, lam)
        if a is None or b is None:
            invalid(k, 'outside the spatial grid')
            continue
        j = int(source_epochs.searchsorted(epoch))
        if j < len(source_epochs) and source_epochs[j] == epoch:
            j0 = j1 = j
            ft = 0.0
        elif j == 0 or j == len(source_epochs):
            invalid(k, 'outside the map time coverage (no extrapolation)')
            continue
        else:
            j0, j1 = j-1, j
            gap = (source_epochs[j1]-source_epochs[j0]).total_seconds()
            if gap > max_gap:
                invalid(k, 'map interval exceeds max_gap; missing scheduled maps are not bridged')
                continue
            ft = ((epoch-source_epochs[j0]) /
                  (source_epochs[j1]-source_epochs[j0]))
        a0, a1, fa = a
        b0, b1, fb = b
        weights = [(1-fa)*(1-fb), (1-fa)*fb, fa*(1-fb), fa*fb]
        spatial = []
        for jt in (j0, j1):
            spatial.append(_weighted([grid[jt, a0, b0], grid[jt, a0, b1],
                                      grid[jt, a1, b0], grid[jt, a1, b1]], weights))
        result[k] = _weighted(spatial, [1-ft, ft])
    return result


def _station_epochs(station):
    obs = station.observation
    if hasattr(obs, 'epoch'):
        return obs.epoch
    if isinstance(obs.index, pd.MultiIndex):
        if 'Epoch' not in obs.index.names:
            raise ValueError('station observation index has no Epoch level; supply epoch_list')
        return obs.index.get_level_values('Epoch').unique()
    if isinstance(obs.index, pd.DatetimeIndex):
        return obs.index.unique()
    raise ValueError('Cannot determine station epochs; supply epoch_list')


def ionosphere_interp(station, unit='meter', system='G', band='L1', epoch_list=None, *,
                      ionex_file=None, data_dir=None, product='IGS', ion_type='auto',
                      allow_download=False, frequency_hz=None, bounds='nan', max_gap=None,
                      epoch_time_system=None, gps_utc_offset=None, return_metadata=False):
    """Compute station VTEC or vertical first-order code/group delay.

    Supply an ionex_file path or search data_dir for matching local products.
    Downloads require allow_download=True. Metre output is positive vertical
    group delay, not a satellite-specific slant correction or carrier-phase delay.

    With epoch_time_system='UTC', input epochs are UTC. GPS/GPST requires an
    explicit gps_utc_offset in seconds, valid for the input interval. If neither
    a time-system argument nor station metadata is available, UTC is assumed
    with a warning. The leap-second offset is not inferred.
    """
    unit = unit.lower()
    if unit not in {'tecu', 'meter', 'meters', 'metre', 'metres', 'm'}:
        raise ValueError('unit must be tecu, meter/metre/meters/metres or m')
    times = _utc_epochs(_station_epochs(station) if epoch_list is None else epoch_list)
    if epoch_time_system is None:
        obs = getattr(station, 'observation', None)
        epoch_time_system = getattr(station, 'time_system', None) or getattr(obs, 'attrs', {}).get('time_system')
    if epoch_time_system is None:
        warnings.warn('Epoch time system is unspecified; assuming UTC for IONEX. '
                      'RINEX GPS times require epoch_time_system="GPS" and a valid gps_utc_offset.',
                      RuntimeWarning, stacklevel=2)
        epoch_time_system = 'UTC'
    time_system = str(epoch_time_system).upper()
    if time_system in {'GPS', 'GPST'}:
        if gps_utc_offset is None or isinstance(gps_utc_offset, bool) or not np.isfinite(gps_utc_offset) or gps_utc_offset < 0:
            raise ValueError('GPS epochs require a valid gps_utc_offset in seconds; it is not guessed')
        times = times-pd.Timedelta(seconds=float(gps_utc_offset))
    elif time_system not in {'UTC', 'UT'}:
        raise ValueError('Convert epochs to UTC first; supported epoch_time_system values are UTC and GPS/GPST')
    elif gps_utc_offset is not None:
        raise ValueError('gps_utc_offset is only used with GPS/GPST input epochs')
    acquisition = None
    if isinstance(ionex_file, IonexDataset):
        data = ionex_file
    elif ionex_file is not None:
        data = read_ionex(ionex_file, data_dir=data_dir)
    else:
        from gnsspy.data_access import NavigationDownloader
        from gnsspy.data_access.utils import load_credentials

        root = Path(data_dir) if data_dir is not None else Path.cwd()
        downloader = NavigationDownloader(None, None, root)
        try:
            finite_times = times[~times.isna()]
            day = finite_times[0].date() if len(finite_times) else station.epoch
            acquisition = downloader.acquire_ionosphere(day, ion_type, product=product, allow_download=False)
            if not acquisition.success and allow_download:
                user, password = load_credentials()
                downloader.session.username, downloader.session.password = user, password
                acquisition = downloader.acquire_ionosphere(day, ion_type, product=product, allow_download=True)
            if not acquisition.success:
                raise FileNotFoundError(acquisition.message)
            data = read_ionex(acquisition.path)
        finally:
            downloader.session.close()
    xyz = np.asarray(station.approx_position, dtype=float)
    if xyz.shape != (3,) or not np.isfinite(xyz).all() or np.linalg.norm(xyz) == 0:
        raise ValueError('station.approx_position must contain three finite, nonzero ECEF coordinates in metres')
    lat = np.degrees(np.arctan2(xyz[2], np.hypot(xyz[0], xyz[1])))
    lon = np.degrees(np.arctan2(xyz[1], xyz[0]))
    values = interpolate_vtec(data, lat, lon, times, bounds=bounds, max_gap=max_gap)
    frequency = None
    if unit != 'tecu':
        frequency = frequency_hz
        if frequency is None:
            frequency = _observation_picker_by_band(station, system, band)[4]
        if isinstance(frequency, bool):
            raise ValueError('frequency_hz must be a positive numeric frequency, not a Boolean')
        try:
            frequency = float(frequency)
        except (TypeError, ValueError) as exc:
            raise ValueError('supply a scalar signal frequency_hz for the vertical delay conversion') from exc
        if not np.isfinite(frequency) or frequency <= 0:
            raise ValueError('frequency_hz must be positive and finite')
        values = values * (40.3e16/frequency**2)
    if return_metadata:
        return values, {'ionex_file': str(data.source), 'product': data.metadata.get('product'),
                        'acquisition': acquisition, 'quantity': 'VTEC' if unit == 'tecu' else 'vertical_group_delay',
                        'units': 'TECU' if unit == 'tecu' else 'm', 'frequency_hz': frequency,
                        'epoch_time_system': 'UTC', 'epochs': times,
                        'missing_values': int(np.isnan(values).sum())}
    return values


interpolate_ionosphere = ionosphere_interp
compute_ionospheric_delay = ionosphere_interp
