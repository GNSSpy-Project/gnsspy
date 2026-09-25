"""SP3 orbit and clock reader.

Positions are returned in kilometres, clock offsets in microseconds and
velocities in kilometres per second. sp3_interp uses metres for positions.
The sigma columns contain SP3 exponent fields, not decoded uncertainties.
"""
from datetime import datetime, timedelta
import time

import numpy as np
import pandas as pd

from gnsspy.utils._datetime import elapsed_seconds, interval_seconds
from gnsspy.utils.product_files import open_product_text, resolve_product_path


def _epoch(parts):
    return datetime(*map(int,parts[:5])) + timedelta(seconds=float(parts[5]))


def read_sp3File(sp3file, *, data_dir=None, verbose=True):
    """Read a plain or compressed SP3 file without network access or renaming."""
    started = time.monotonic()
    path = resolve_product_path(sp3file, "sp3", data_dir)
    rows, velocities = [], {}
    current = None
    time_system = None
    declared_interval = None
    declared_epochs = None
    with open_product_text(path) as stream:
        first = stream.readline()
        if len(first) < 3 or first[0] != '#' or first[1].lower() not in 'abcd' or first[2].upper() not in 'PV':
            raise ValueError(f"{path}:1: not an SP3 file (expected #a/#b/#c/#d header)")
        try:
            declared_epochs = int(first[32:39])
        except ValueError:
            pass
        for line_number,line in enumerate(stream,2):
            try:
                if line.startswith("##"):
                    declared_interval = float(line.split()[3])
                elif line.startswith("%c") and time_system is None:
                    value = line[9:12].strip().upper()
                    if value and value != "CCC":
                        time_system = value
                elif line.startswith("*"):
                    current = _epoch(line[1:].split())
                elif line[:1] in {"P","V"}:
                    if current is None:
                        raise ValueError("position/velocity before first epoch")
                    if len(line.rstrip('\r\n')) < 60:
                        raise ValueError("truncated position/velocity record")
                    sv = line[1:4].strip()
                    if sv.isdigit():
                        sv = f"G{int(sv):02d}"
                    if not sv:
                        raise ValueError("missing satellite identifier")
                    values = [float(line[a:b].replace('D','E').replace('d','e'))
                              for a,b in ((4,18),(18,32),(32,46),(46,60))]
                    if line.startswith("V"):
                        velocities[(current,sv)] = np.asarray(values[:3]) * 1e-4
                        continue
                    if all(v == 0 for v in values[:3]):
                        values[:3] = [np.nan]*3
                    if abs(values[3]) >= 999999:
                        values[3] = np.nan
                    sigma = [float(line[a:b]) if line[a:b].strip() else np.nan
                             for a,b in ((61,63),(64,66),(67,69),(70,73))]
                    padded = line.rstrip('\r\n').ljust(80)
                    rows.append((current,sv,*values,*sigma,
                                 padded[74]=='E',padded[75]=='P',padded[78]=='M',padded[79]=='P'))
                elif line.startswith("EOF"):
                    break

            except (ValueError, IndexError, OverflowError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid SP3 record: {exc}") from exc
    if not rows:
        raise ValueError(f"{path}: no SP3 position records found")
    columns = ['Epoch','SV','X','Y','Z','deltaT','sigmaX','sigmaY','sigmaZ','sigmadeltaT',
               'clock_event','clock_predicted','orbit_manoeuvre','orbit_predicted']
    data = pd.DataFrame(rows,columns=columns).set_index(['Epoch','SV']).sort_index()
    if data.index.has_duplicates:
        for key,group in data[data.index.duplicated(keep=False)].groupby(level=['Epoch','SV']):
            if len(group.drop_duplicates()) != 1:
                raise ValueError(f"{path}: conflicting SP3 records for {key}")
        data = data[~data.index.duplicated()]
    data[['Vx','Vy','Vz']] = np.nan
    for sv,group in data.groupby(level='SV',sort=False):
        seconds = elapsed_seconds(group.index.get_level_values('Epoch'))
        xyz = group[['X','Y','Z']].to_numpy()
        if len(seconds) > 1:
            vel = np.diff(xyz,axis=0) / np.diff(seconds)[:,None]
            vel = np.vstack([vel[0],vel])
            data.loc[group.index,['Vx','Vy','Vz']] = vel
    for key,values in velocities.items():
        if key in data.index:
            data.loc[key,['Vx','Vy','Vz']] = values
    epochs = data.index.get_level_values('Epoch').unique().sort_values()
    intervals = tuple(float(v) for v in np.unique(interval_seconds(epochs)))
    data.attrs.update(source_path=str(path), position_unit='km', velocity_unit='km/s',
                      clock_unit='microseconds', time_system=time_system,
                      interval_seconds=declared_interval, observed_intervals_seconds=intervals,
                      declared_epochs=declared_epochs, first_epoch=epochs[0].isoformat(),
                      last_epoch=epochs[-1].isoformat(), sigma_fields='SP3 exponent fields')
    if verbose:
        print(f"{path} file is read in {time.monotonic()-started:.2f} seconds")
    return data


read_sp3_file = read_sp3File
__all__ = ['read_sp3File','read_sp3_file']
