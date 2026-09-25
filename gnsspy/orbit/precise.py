"""Local-first, filename-independent interpolation of precise orbit products."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import time
import warnings

import numpy as np
import pandas as pd
from numpy.polynomial import Polynomial

from gnsspy.io.products.sp3 import read_sp3File
from gnsspy.io.products.clk import read_clockFile
from gnsspy.utils._datetime import elapsed_seconds
from gnsspy.utils.product_files import (
    as_date, find_product_files, local_product_paths, parse_product_name,
    product_spec, resolve_product_path, validate_product_file,
)

__all__ = ['sp3_interp','interpolate_sp3','sp3_interpolation']


def _paths(files, data_dir, kind):
    if files is None:
        return local_product_paths(data_dir,kind)
    if isinstance(files,(str,Path)):
        files = [files]
    return list(dict.fromkeys(resolve_product_path(p,kind,data_dir) for p in files))


def _select_orbits(day, paths, product, orbit_type):
    candidates = find_product_files(day,'sp3',product,orbit_type,files=paths)
    valid = []
    for info in candidates:
        if validate_product_file(info.path,'sp3'):
            valid.append(info)
        else:
            warnings.warn(f"Ignoring invalid SP3 cache entry: {info.path}",RuntimeWarning,stacklevel=3)
    if not valid:
        return [], None
    primary = valid[0]
    selected = [primary.path]


    family = ''.join((primary.center,primary.version,primary.project,primary.solution))
    for offset in (-1,1):
        neighbours = find_product_files(day+timedelta(days=offset),'sp3',family,files=paths)
        for info in neighbours:
            if validate_product_file(info.path,'sp3'):
                selected.append(info.path)
                break
    return list(dict.fromkeys(selected)), primary


def _same_time_system(frames):
    systems = {frame.attrs.get('time_system') for frame in frames}
    systems.discard(None)


    if systems - {'GPS'}:
        raise ValueError(f"SP3/CLK time system {sorted(systems)} is not GPS. Convert time scales explicitly first.")


def sp3_interp(epoch, interval=30, poly_degree=16, sp3_product='auto', clock_product='auto',
               data_dir=None, *, sp3_files=None, clk_files=None, orbit_type='auto',
               allow_download=False, require_clock=False, verbose=True,
               edge_policy='one-sided'):
    """Interpolate a day of precise satellite positions and velocities.

    Local selection prioritises FIN, RAP, then ULT and respects an explicit
    centre or series. sp3_files and clk_files accept paths or lists of paths,
    including compressed inputs. Explicit paths need not use standard names.

    Four-hour polynomial fits supply three-hour output blocks. Velocities are
    polynomial derivatives. The output spans [00:00, next 00:00) in GPST, with
    positions in metres and velocities in metres per second.

    Fits do not extrapolate beyond satellite coverage or across manoeuvre flags
    or gaps exceeding 1.5 input intervals. edge_policy='strict' excludes outputs
    within 30 minutes of an actual fit-support boundary. The default 'one-sided'
    retains in-coverage edge fits with a warning. Matching neighbouring-day files
    provide support at day boundaries. Unsupported values are NaN.

    CLK biases in seconds are joined at exact epochs, without interpolation or
    SP3-clock substitution. clock_product=None disables clocks. Downloads require
    allow_download=True and are attempted only when the target-day SP3 is absent.
    """
    day = as_date(epoch)
    if isinstance(interval,bool) or not isinstance(interval,(int,float,np.integer,np.floating)) or not np.isfinite(interval) or interval <= 0 or interval > 86400:
        raise ValueError('interval must be a finite number of seconds in (0, 86400]')
    if isinstance(poly_degree,bool) or not isinstance(poly_degree,(int,np.integer)) or not 1 <= poly_degree <= 16:
        raise ValueError('poly_degree must be an integer from 1 to 16')
    if edge_policy not in ('one-sided','strict'):
        raise ValueError('edge_policy must be one-sided or strict')
    if require_clock and clock_product is None:
        raise ValueError('require_clock=True conflicts with clock_product=None')
    started = time.monotonic()
    paths = _paths(sp3_files,data_dir,'sp3')
    selected, primary = _select_orbits(day,paths,sp3_product,orbit_type)
    unnamed = [p for p in paths if parse_product_name(p) is None]
    if not selected and sp3_files is not None and unnamed:


        selected = unnamed
    if not selected and allow_download and sp3_files is None:
        from gnsspy.data_access.products import NavigationDownloader
        from gnsspy.data_access.utils import load_credentials
        user,password = load_credentials()
        center = product_spec(sp3_product)[0]
        downloader = NavigationDownloader(user,password,data_dir or Path.cwd())
        ok,message,mode = downloader.download_sp3_with_fallback(
            center=center or 'CODE',date=day,orbit_type=orbit_type,
            strict_center=center is not None,fallback_to_broadcast=False,
            download_clk=clock_product is not None)
        if not ok:
            raise FileNotFoundError(message)
        paths = _paths(None,data_dir,'sp3')
        selected,primary = _select_orbits(day,paths,sp3_product,orbit_type)
    if not selected:
        raise FileNotFoundError(
            f'No matching local SP3 for {day} (product={sp3_product!r}, orbit_type={orbit_type!r}). '
            'Use the correct data_dir, pass sp3_files=[actual_path], or download explicitly. '
            'Long 05M/15M names are accepted; renaming is unnecessary. No network request was made.'
            if not allow_download else f'No matching SP3 found for {day} after the requested download.')
    if verbose:
        print('[SP3] Using original file(s): '+', '.join(p.name for p in selected))
    frames = [read_sp3File(p,verbose=False) for p in selected]
    _same_time_system(frames)
    input_intervals = {}
    for frame in frames:
        nominal = frame.attrs.get('interval_seconds')
        observed = frame.attrs.get('observed_intervals_seconds',())
        if nominal is None or nominal <= 0:
            nominal = float(np.median(observed)) if observed else 900.
        frame['_input_interval'] = nominal
        input_intervals[frame.attrs['source_path']] = nominal

    positions = pd.concat(frames)
    positions = positions[~positions.index.duplicated(keep='first')].sort_index()
    start = pd.Timestamp(day)
    stop = start+pd.Timedelta(days=1)
    times = pd.date_range(start,stop,freq=pd.Timedelta(seconds=float(interval)),inclusive='left')
    target_seconds = elapsed_seconds(times,start)
    satellites = sorted(positions.index.get_level_values('SV').unique())
    index = pd.MultiIndex.from_product([times,satellites],names=['Epoch','SV'])
    output = pd.DataFrame(np.nan,index=index,columns=['X','Y','Z','Vx','Vy','Vz'])
    xyz_columns = ['X','Y','Z']
    manoeuvre_boundaries = []
    edge_rows = 0
    for sv in satellites:
        group = positions.xs(sv,level='SV').sort_index()
        group = group.loc[np.isfinite(group[xyz_columns].to_numpy()).all(axis=1)]
        seconds = elapsed_seconds(group.index,start)
        if len(group) <= poly_degree:
            continue
        xyz = group[xyz_columns].to_numpy(dtype=float)*1000.
        rates = group['_input_interval'].to_numpy(dtype=float)
        gap_breaks = np.diff(seconds) > 1.5*np.maximum(rates[:-1],rates[1:])
        manoeuvres = group['orbit_manoeuvre'].to_numpy(dtype=bool)
        manoeuvre_boundaries.extend((sv,stamp.isoformat()) for stamp in group.index[manoeuvres])


        boundaries = np.flatnonzero(gap_breaks | manoeuvres[1:])+1
        segments = np.split(np.arange(len(group)),boundaries)
        result = np.full((len(times),6),np.nan)
        for segment in segments:
            if len(segment) <= poly_degree:
                continue
            tx, coords = seconds[segment],xyz[segment]
            for block in range(8):
                begin,end = block*10800.,(block+1)*10800.
                mask = ((target_seconds >= begin) & (target_seconds < end)
                        & (target_seconds >= tx[0]) & (target_seconds <= tx[-1]))
                if not mask.any():
                    continue
                fit_begin = max(tx[0],min(begin-1800.,tx[-1]-14400.))
                fit_end = min(tx[-1],fit_begin+14400.)
                support = (tx >= fit_begin-1e-8) & (tx <= fit_end+1e-8)
                if support.sum() <= poly_degree:
                    continue


                edge = mask & ((target_seconds < tx[support][0]+1800.-1e-8)
                               | (target_seconds > tx[support][-1]-1800.+1e-8))
                edge_rows += int(edge.sum())
                if edge_policy == 'strict':
                    mask &= ~edge
                if not mask.any():
                    continue


                for axis in range(3):
                    fit = Polynomial.fit(tx[support],coords[support,axis],int(poly_degree))
                    result[mask,axis] = fit(target_seconds[mask])
                    result[mask,axis+3] = fit.deriv()(target_seconds[mask])
        output.loc[pd.IndexSlice[:,sv],:] = result
    valid_rows = output[xyz_columns].notna().all(axis=1)
    if not valid_rows.any():
        raise ValueError(f'No interpolatable SP3 coordinates for {day}. Check actual file dates, '
                         f'gaps and the {poly_degree+1} samples required for degree {poly_degree}.')
    missing_orbits = int((~valid_rows).sum())
    if edge_rows and edge_policy == 'one-sided':
        warnings.warn(f'{edge_rows} orbit rows use edge fits with less than a 30-minute support '
                      'buffer on one side. These can be less accurate; supply matching neighbouring '
                      'files or set edge_policy="strict" to leave those rows as NaN.',
                      RuntimeWarning,stacklevel=2)
    if missing_orbits:
        warnings.warn(f'{missing_orbits} orbit rows have no supported interpolation (file edges, gaps, manoeuvres, strict edge filtering or '
                      'insufficient samples); left as NaN. Supply matching neighbouring SP3 files '
                      'for complete edge coverage. No extrapolation was performed.',RuntimeWarning,stacklevel=2)
    selected_clocks = []
    if clock_product is not None:
        clock_paths = _paths(clk_files,data_dir,'clk')
        clock_spec = clock_product
        if clock_product == 'auto' and primary:
            clock_spec = ''.join((primary.center,primary.version,primary.project,primary.solution))
        candidates = find_product_files(day,'clk',clock_spec,files=clock_paths)
        if candidates:
            selected_clocks = [candidates[0].path]
        elif clk_files is not None:
            selected_clocks = [p for p in clock_paths if parse_product_name(p) is None]
        if selected_clocks:
            clocks = [read_clockFile(p,verbose=False,missing='raise') for p in selected_clocks]
            _same_time_system(frames+clocks)
            clock = pd.concat(clocks).reset_index().set_index(['Epoch','SV']).sort_index()
            clock = clock[~clock.index.duplicated()]
            if primary and clock_product != 'auto':
                for path in selected_clocks:
                    info = parse_product_name(path)
                    if info and info.family != primary.family:
                        warnings.warn('Explicit CLK series differs from the selected SP3 series; '
                                      'the caller is responsible for orbit/clock consistency.',RuntimeWarning,stacklevel=2)
            output = output.join(clock[['DeltaTSV']],how='left')
        else:
            output['DeltaTSV'] = np.nan
            if require_clock:
                raise FileNotFoundError(f'No matching CLK for {day}; orbit file names do not need changing.')
            warnings.warn(f'No matching CLK for {day}; orbits retained and DeltaTSV is NaN. '
                          'Set clock_product=None to request orbit-only processing.',RuntimeWarning,stacklevel=2)
    else:
        output['DeltaTSV'] = np.nan
    missing_clocks = int(output['DeltaTSV'].isna().sum())
    if require_clock and output.loc[valid_rows,'DeltaTSV'].isna().any():
        raise ValueError('CLK does not cover all valid orbit rows at the requested epochs. '
                         'Clock interpolation is not performed; select an appropriate output interval.')
    output.attrs.update(
        sp3_files=[str(p) for p in selected],clk_files=[str(p) for p in selected_clocks],
        product_family=primary.family if primary else None,input_intervals_seconds=input_intervals,
        target_date=day.isoformat(),position_unit='m',velocity_unit='m/s',clock_unit='seconds',
        time_system='GPS',missing_orbit_rows=missing_orbits,missing_clock_rows=missing_clocks,
        extrapolated=False,clock_interpolation=False,manoeuvre_boundaries=manoeuvre_boundaries,
        edge_policy=edge_policy,edge_fit_rows=edge_rows if edge_policy == 'one-sided' else 0,
        strict_edge_rows_removed=edge_rows if edge_policy == 'strict' else 0,
        interpolation='scaled polynomial, 4h support / 3h output blocks')
    if verbose:
        print(f'[OK] SP3 interpolation completed in {time.monotonic()-started:.2f} seconds; '
              f'{int(valid_rows.sum())}/{len(output)} supported orbit rows.')
    return output


interpolate_sp3 = sp3_interp
sp3_interpolation = sp3_interp
