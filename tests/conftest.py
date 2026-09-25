"""Small, deliberately synthetic navigation records; no external downloads."""
from datetime import datetime
from pathlib import Path

import pytest


GPS_EPOCH = datetime(1980, 1, 6)
BDT_EPOCH = datetime(2006, 1, 1)


def header(version="3.04", system="M", file_type="N"):
    first = f"{version:>9s}" + " " * 11 + f"{file_type}: GNSS NAV DATA".ljust(20) + system.ljust(20)
    return (first + "RINEX VERSION / TYPE\n"
            + "Synthetic GNSSpy test".ljust(60) + "COMMENT\n"
            + " ".ljust(60) + "END OF HEADER\n")


def field(value, exponent="D"):
    if value is None:
        return " " * 19
    if isinstance(value, str):
        assert len(value) <= 19
        return value.rjust(19)
    return f"{value:19.12E}".replace("E", exponent)


def elements(system="G", epoch=datetime(2025, 11, 2), *, toe=None,
             health=0.0, overrides=None):
    origin = BDT_EPOCH if system == "C" else GPS_EPOCH
    seconds = (epoch - origin).total_seconds()
    week, tow = divmod(seconds, 604800)
    if toe is not None:
        tow = toe

    values = [None] * 31
    values[0:3] = [-2.123456789e-4, -3.4e-12, 1.25e-20]
    values[3:20] = [12, -56.25, 4.5e-9, -1.2, 1e-6, .01, -2e-6,
                     5282.0 if system == "C" else 5440.0 if system == "E" else 5153.7,
                     tow, 3e-8, -2.4, -4e-8, .95, 250.0, .7, -8e-9, 1e-10]
    values[21] = week
    values[23:28] = [2.0, health, -2e-9, 3e-9, tow + 60]
    if system in "GJ":
        values[20], values[22], values[26], values[28] = 1, 0, 12, 4
    elif system == "E":
        values[20] = 513
    elif system == "C":
        values[28] = 7
    elif system == "I":
        values[26] = None
    if overrides:
        for index, value in overrides.items():
            values[index] = value
    return values


def kepler_record(sv="G01", epoch=datetime(2025, 11, 2), *, version="3.04",
                   values=None, exponent="D", trim=False):
    values = elements(sv[0], epoch) if values is None else list(values)
    major = int(float(version))
    if major == 3:
        first = f"{sv} {epoch:%Y %m %d %H %M %S}"
        assert len(first) == 23
        prefix = " " * 4
    else:
        second = epoch.second + epoch.microsecond / 1e6
        first = (f"{int(sv[1:]):2d} {epoch.year%100:02d} {epoch.month:2d} {epoch.day:2d} "
                 f"{epoch.hour:2d} {epoch.minute:2d}{second:5.1f}")
        assert len(first) == 22
        prefix = " " * 3
    lines = [first + "".join(field(v, exponent) for v in values[:3])]
    for start in range(3, 31, 4):
        lines.append(prefix + "".join(field(v, exponent) for v in values[start:start+4]))
    if trim:
        lines = [line.rstrip() for line in lines]
    return "\n".join(lines) + "\n"


def state_record(sv="R01", epoch=datetime(2025, 11, 2), *, version="3.04"):
    values = [-1e-4, 2e-10, 12345.0, 19000.0, -1.2, 1e-9, 0,
              -13000.0, 2.2, -2e-9, -7 if sv[0] == "R" else 4,
              11000.0, .5, 3e-9, 12]
    base = kepler_record(sv, epoch, version=version, values=values+[None]*16)
    lines = base.splitlines()[:4]
    if sv[0] == "R" and float(version) >= 3.05:
        lines.append(" "*4 + "".join(field(v) for v in [257, -1e-9, 3, 7]))
    return "\n".join(lines) + "\n"


@pytest.fixture
def write_nav(tmp_path):
    def write(records=None, *, name="test.rnx", version="3.04", system="M", file_type="N"):
        path = tmp_path / name
        path.write_text(header(version, system, file_type) + (
            kepler_record(version=version) if records is None else records), encoding="ascii")
        return path
    return write


import gzip
import numpy as np
from datetime import timedelta

PRECISE_DAY = datetime(2024,8,8)


def precise_xyz(seconds, satellite_index=0):
    t = np.asarray(seconds,dtype=float)
    return np.stack((2.1e7+100*t+1e-4*t*t-1e-9*t**3,
                     -1.3e7+20*t-2e-4*t*t+2e-9*t**3,
                     1.8e7-50*t+5e-5*t*t-3e-10*t**3),axis=-1) + satellite_index*1000


def precise_velocity(seconds):
    t = np.asarray(seconds,dtype=float)
    return np.stack((100+2e-4*t-3e-9*t*t,
                     20-4e-4*t+6e-9*t*t,
                     -50+1e-4*t-9e-10*t*t),axis=-1)


def sp3_text(start=PRECISE_DAY, *, interval=300, length=86400, satellites=('G01',),
             include_endpoint=True, missing=(), time_system='GPS', offset=0.):
    times = np.arange(0,length+(interval/2 if include_endpoint else 0),interval)
    first = (f'#dP{start.year:4d} {start.month:2d} {start.day:2d} {start.hour:2d} '
             f'{start.minute:2d} {start.second:11.8f} ')
    first = first[:32].ljust(32)+f'{len(times):7d} SYNTH IGS20 FIT TEST\n'
    text = first+f'## 2326 345600.00000000 {interval:14.8f} 60530 0.0000000000000\n'
    text += f'%c M  cc {time_system} ccc cccc cccc cccc cccc ccccc ccccc ccccc ccccc\n'
    text += '/* Synthetic cubic coordinates, not measured GNSS orbits.\n'
    for second in times:
        if any(a <= second <= b for a,b in missing):
            continue
        epoch = start+timedelta(seconds=float(second))
        sec = epoch.second+epoch.microsecond/1e6
        text += f'*  {epoch:%Y %m %d %H %M} {sec:11.8f}\n'
        for i,sv in enumerate(satellites):
            xyz = (precise_xyz((epoch-PRECISE_DAY).total_seconds(),i)+offset)/1000.
            text += 'P'+sv+''.join(f'{value:14.6f}' for value in [*xyz,123.456789])+'\n'
    return text+'EOF\n'


def clk_text(start=PRECISE_DAY, *, interval=30, length=86400, satellites=('G01',),
             missing=(), time_system='GPS'):
    text = ('     3.04           C'.ljust(60)+'RINEX VERSION / TYPE\n'
            +f'   {time_system}'.ljust(60)+'TIME SYSTEM ID\n'
            +' '.ljust(60)+'END OF HEADER\n')
    for second in np.arange(0,length,interval):
        epoch = start+timedelta(seconds=float(second))
        for sv in satellites:
            if (float(second),sv) in missing:
                continue
            sec = epoch.second+epoch.microsecond/1e6
            text += f'AS {sv} {epoch:%Y %m %d %H %M} {sec:9.6f}  2  {1e-4+second*1e-12:.12E}  1.0000E-12\n'
    return text


@pytest.fixture
def write_product(tmp_path):
    def write(name='COD0MGXFIN_20242210000_01D_05M_ORB.SP3', text=None, **kwargs):
        path = tmp_path/name
        path.parent.mkdir(parents=True,exist_ok=True)
        if text is None:
            text = clk_text(**kwargs) if '.clk' in name.lower() else sp3_text(**kwargs)
        data = text.encode('ascii')
        if path.suffix.lower() == '.gz':
            data = gzip.compress(data)
        elif path.suffix.lower() == '.bz2':
            import bz2
            data = bz2.compress(data)
        elif path.suffix.lower() == '.xz':
            import lzma
            data = lzma.compress(data)
        path.write_bytes(data)
        return path
    return write
