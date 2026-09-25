#!/usr/bin/env python

"""
comparison.py
=============
Shared orbit-comparison utilities used by GNSSpy workflows.
"""
import os, datetime, glob, re, shutil, warnings
from pathlib import Path
from contextlib import contextmanager
import numpy as np

import pandas as pd

from gnsspy.io.rinex.navigation import _open_navigation_text
from gnsspy.orbit.ephemeris import (
    build_ephemeris_table, find_nearest_eph, find_latest_eph,
    ephemeris_age_seconds, _is_healthy,
)

from gnsspy.utils.product_files import parse_product_name, product_kind, as_date
from gnsspy.orbit.precise import sp3_interp


_ORBIT_R_BOUNDS = {
    'G': (20_000_000, 35_000_000),
    'E': (20_000_000, 35_000_000),
    'C': (20_000_000, 45_000_000),
}

_ORBIT_R_MIN = 20_000_000
_ORBIT_R_MAX = 35_000_000


_OMEGA_E_WGS84 = 7.2921151467e-5
_OMEGA_E_CGCS  = 7.2921150e-5


_BDS_GPST_OFFSET = 14.0


_BDS_GEO_INC_RAD = np.deg2rad(5.0)

_BDS_GEO_PHI_X = np.deg2rad(-5.0)


def compute_keplerian_xyz(eph, tgps, sys_type):
    """Compute ECEF (X, Y, Z) from RINEX navigation parameters.

    Supports GPS ('G'), Galileo ('E') and BeiDou ('C') — including BDS GEO
    satellites, which need an extra rotation per BDS-SIS-ICD.

    Returns [x, y, z] in metres, or None if the result fails the per-system
    orbit-radius sanity check."""
    required = ("Toe", "sqrtA", "DeltaN", "M0", "Eccentricity", "omega",
                "Cus", "Cuc", "Crs", "Crc", "Cis", "Cic", "IDOT",
                "Omega0", "OmegaDot")
    if sys_type not in {"G", "E", "C"}:
        raise ValueError("Comparison propagation supports G, E and C only")
    try:
        values = [float(eph[key]) for key in required]
        values.append(float(eph['Io'] if 'Io' in eph else eph['i0']))
        if (not np.all(np.isfinite(values)) or not np.isfinite(tgps)
                or float(eph['sqrtA']) <= 0
                or not 0 <= float(eph['Eccentricity']) < 1):
            return None
    except (KeyError, ValueError, TypeError):
        return None

    if sys_type == 'G':
        GM, OMEGA_E = 3.986005e14, _OMEGA_E_WGS84
        t = tgps
    elif sys_type == 'E':
        GM, OMEGA_E = 3.986004418e14, _OMEGA_E_WGS84
        t = tgps
    elif sys_type == 'C':
        GM, OMEGA_E = 3.986004418e14, _OMEGA_E_CGCS

        t = (tgps - _BDS_GPST_OFFSET) % 604800
    else:
        GM, OMEGA_E = 3.986005e14, _OMEGA_E_WGS84
        t = tgps

    toe_val = float(eph['Toe'])
    A = float(eph['sqrtA'])**2
    n0 = np.sqrt(GM / A**3)
    n = n0 + float(eph['DeltaN'])
    tk = t - toe_val
    if tk > 302400: tk -= 604800
    elif tk < -302400: tk += 604800
    Mk = float(eph['M0']) + n * tk
    ecc = float(eph['Eccentricity'])
    Ek = Mk
    for _ in range(15):
        Ek_new = Mk + ecc * np.sin(Ek)
        if abs(Ek_new - Ek) < 1e-12:
            Ek = Ek_new
            break
        Ek = Ek_new
    vk = np.arctan2(np.sqrt(1 - ecc**2) * np.sin(Ek), np.cos(Ek) - ecc)
    Phik = vk + float(eph['omega'])
    sin2, cos2 = np.sin(2 * Phik), np.cos(2 * Phik)
    duk = float(eph['Cus']) * sin2 + float(eph['Cuc']) * cos2
    drk = float(eph['Crs']) * sin2 + float(eph['Crc']) * cos2
    io_val = float(eph['Io']) if 'Io' in eph else float(eph['i0'])
    dik = float(eph['Cis']) * sin2 + float(eph['Cic']) * cos2
    uk = Phik + duk
    rk = A * (1 - ecc * np.cos(Ek)) + drk
    ik = io_val + dik + float(eph['IDOT']) * tk
    xk, yk = rk * np.cos(uk), rk * np.sin(uk)


    is_bds_geo = (sys_type == 'C' and float(ik) < _BDS_GEO_INC_RAD)

    if is_bds_geo:

        Om = (float(eph['Omega0']) + float(eph['OmegaDot']) * tk
              - OMEGA_E * toe_val)
        x_gk = xk * np.cos(Om) - yk * np.cos(ik) * np.sin(Om)
        y_gk = xk * np.sin(Om) + yk * np.cos(ik) * np.cos(Om)
        z_gk = yk * np.sin(ik)
        phi = OMEGA_E * tk
        c_phi, s_phi = np.cos(phi), np.sin(phi)
        c_x, s_x = np.cos(_BDS_GEO_PHI_X), np.sin(_BDS_GEO_PHI_X)

        x1 = x_gk
        y1 = y_gk * c_x + z_gk * s_x
        z1 = -y_gk * s_x + z_gk * c_x

        x = x1 * c_phi + y1 * s_phi
        y = -x1 * s_phi + y1 * c_phi
        z = z1
    else:

        Om = (float(eph['Omega0']) + (float(eph['OmegaDot']) - OMEGA_E) * tk
              - OMEGA_E * toe_val)
        x = xk * np.cos(Om) - yk * np.cos(ik) * np.sin(Om)
        y = xk * np.sin(Om) + yk * np.cos(ik) * np.cos(Om)
        z = yk * np.sin(ik)


    r = np.sqrt(x**2 + y**2 + z**2)
    r_min, r_max = _ORBIT_R_BOUNDS.get(sys_type, (_ORBIT_R_MIN, _ORBIT_R_MAX))
    if not np.isfinite(r) or r < r_min or r > r_max:
        return None

    return [x, y, z]


def datetime_to_gps_tow(dt):
    """Naive GPST calendar datetime -> GPS seconds of week (not UTC conversion)."""
    dt = pd.Timestamp(dt)
    if pd.isna(dt) or dt.tzinfo is not None:
        raise ValueError("Pass a timezone-naive GPST datetime, not a UTC datetime")
    return (dt - datetime.datetime(1980, 1, 6)).total_seconds() % 604800


def get_dates_from_nav_files(files):
    """Extracts available dates from navigation files."""
    dates = set()
    for f in files:
        bn = os.path.basename(f).upper()
        m = re.search(r'_(\d{4})(\d{3})\d{4}_', bn)
        if m:
            try: dates.add(datetime.datetime.strptime(f"{m.group(1)}{m.group(2)}", "%Y%j").date())
            except ValueError: pass
            continue
        m = re.search(r'(\d{3})0\.(\d{2})[N]', bn)
        if m:
            try: dates.add(datetime.datetime.strptime(f"{2000+int(m.group(2))}{m.group(1)}", "%Y%j").date())
            except ValueError: pass
    return sorted(dates)


def detect_sp3_product(sp3_files):
    """Return the actual centre, never substitute IGS for an unrecognised name."""
    for path in sp3_files:
        info = parse_product_name(path)
        if info:
            return info.center.lower()
    return "auto"


def discover_files(data_dir):
    """Discover products and classify navigation files by their RINEX header.

    Plain and compressed navigation files are recognised. Observation files,
    spreadsheets, logs and arbitrary directory contents are not sent to the
    navigation parser. SP3/CLK discovery accepts long/legacy names and compressed variants.
    """
    all_files = sorted(f for f in glob.glob(os.path.join(data_dir, "**", "*"), recursive=True)
                       if 'temp_gnsspy' not in f and os.path.isfile(f))
    sp3_files = [f for f in all_files if product_kind(f) == 'sp3']
    clk_files = [f for f in all_files if product_kind(f) == 'clk']
    products = set(sp3_files + clk_files)
    nav_files = []
    for filename in all_files:
        if filename in products:
            continue
        try:
            with _open_navigation_text(filename) as stream:
                for _, line in zip(range(10), stream):
                    if not line.strip():
                        continue
                    if ('RINEX VERSION / TYPE' in line[60:]
                            and line[20:21].upper() in {'N', 'G', 'H'}):
                        nav_files.append(filename)
                    break
        except ImportError as exc:
            warnings.warn(f"Cannot inspect {filename}: {exc}", RuntimeWarning, stacklevel=2)
        except (OSError, UnicodeError, ValueError, EOFError):
            continue
    return nav_files, sp3_files, clk_files


def filter_sp3_by_date(sp3_files, target_date):
    """Select nominal coverage of target +/- one day, including weekly products."""
    day = as_date(target_date)
    start = datetime.datetime.combine(day-datetime.timedelta(days=1), datetime.time())
    stop = start+datetime.timedelta(days=3)
    return [p for p in sp3_files if (parse_product_name(p) is None
                                    or parse_product_name(p).overlaps(start,stop))]


def setup_sp3_temp(sp3_files, clk_files, target_date, sp3_prod, base_dir, suffix=""):
    """Deprecated staging helper that preserves product names and compression."""
    import tempfile
    warnings.warn('Temporary SP3 staging is deprecated; pass product paths directly to '
                  'sp3_interp.',DeprecationWarning,stacklevel=2)
    temp_dir = Path(tempfile.mkdtemp(prefix='temp_gnsspy'+suffix+'_',dir=base_dir))
    for kind,paths in [('sp3',sp3_files),('clk',clk_files)]:
        dest = temp_dir/kind
        dest.mkdir()
        for path in paths:
            target = dest/Path(path).name
            if target.exists():
                if target.read_bytes() != Path(path).read_bytes():
                    raise ValueError(f'Conflicting source files named {target.name}')
                continue
            shutil.copy2(path,target)
    return str(temp_dir)


@contextmanager
def pandas_freq_patch():
    """Temporarily normalise second-frequency suffixes for pandas date_range."""
    _orig = pd.date_range
    def _patched(*a, **kw):
        if 'freq' in kw and isinstance(kw['freq'], str):
            kw['freq'] = re.sub(r'(\d+)S$', r'\1s', kw['freq'])
        return _orig(*a, **kw)
    pd.date_range = _patched
    try:
        yield
    finally:
        pd.date_range = _orig


def run_sp3_interp(target_date, sp3_files, clk_files, base_dir,
                   interval=30, poly_degree=10, *, edge_policy="one-sided"):
    """Interpolate original products directly, with no staging or renaming."""
    return sp3_interp(target_date, interval=interval, poly_degree=poly_degree,
                      sp3_product="auto", clock_product="auto", data_dir=base_dir,
                      sp3_files=sp3_files, clk_files=clk_files, allow_download=False,
                      edge_policy=edge_policy)


SYSTEM_NAMES = {'G': 'GPS', 'E': 'Galileo', 'C': 'BeiDou'}
SYSTEMS = ('G', 'E', 'C')


_SYSTEM_ALIASES = {
    'G': 'G', 'GPS': 'G',
    'E': 'E', 'GAL': 'E', 'GALILEO': 'E',
    'C': 'C', 'BDS': 'C', 'BEIDOU': 'C',
}


def parse_sv_filter(expr):
    """Parse a user-supplied satellite selection expression.

    Accepted forms (case insensitive, any mix):
        ""                       -> None  (no filter)
        "all"                    -> None
        "gps"                    -> all GPS satellites
        "gps2-23-24"             -> {G02, G23, G24}
        "gps2,23,24"             -> {G02, G23, G24}   (commas equivalent)
        "gps02-05"               -> {G02, G03, G04, G05}   (ranges with ':'  or '..')
        "gps2:5"                 -> {G02, G03, G04, G05}
        "gps2..5"                -> same
        "galileo01-05,beidou12"  -> {E01..E05, C12}
        "g12,e03,c07"            -> {G12, E03, C07}
        "gps,beidou"             -> all GPS + all BeiDou
        "-gps05"                 -> NOT-supported (reserved)

    Returns a tuple (systems, svs) where:
        systems : set of 1-letter codes that are fully selected (no PRN list)
        svs     : set of explicit PRN strings like 'G12', 'E03'
    If the expression is empty or "all", returns None meaning "include all".
    """
    if expr is None:
        return None
    s = str(expr).strip().lower()
    if not s or s == 'all' or s == '*':
        return None

    selected_systems = set()
    selected_svs = set()


    import re as _re
    terms = [t for t in _re.split(r'[,\s;]+', s) if t]

    last_sys = None
    for term in terms:

        m = _re.match(r'^([a-z]+)(.*)$', term)
        if m:
            prefix, rest = m.group(1), m.group(2)
            sys_letter = _SYSTEM_ALIASES.get(prefix.upper())
            if sys_letter is None:

                continue
            last_sys = sys_letter
        else:

            if last_sys is None:
                continue
            sys_letter = last_sys
            rest = term

        if not rest:

            selected_systems.add(sys_letter)
            continue


        rest_norm = rest.replace('..', ':').replace('/', '-')

        chunks = [c for c in rest_norm.split('-') if c]
        for chunk in chunks:
            if ':' in chunk:
                try:
                    a, b = chunk.split(':', 1)
                    a_i, b_i = int(a), int(b)
                    lo, hi = min(a_i, b_i), max(a_i, b_i)
                    for prn in range(lo, hi + 1):
                        selected_svs.add(f"{sys_letter}{prn:02d}")
                except ValueError:
                    continue
            else:
                try:
                    prn = int(chunk)
                    selected_svs.add(f"{sys_letter}{prn:02d}")
                except ValueError:
                    continue


    if not selected_systems and not selected_svs:
        return None
    return (selected_systems, selected_svs)


def sv_matches_filter(sv, sv_filter):
    """Return True if the satellite ID (e.g. 'G12') passes sv_filter."""
    if sv_filter is None:
        return True
    if not sv or len(sv) < 2:
        return False
    systems, svs = sv_filter
    if sv[0] in systems:
        return True

    try:
        key = f"{sv[0]}{int(sv[1:]):02d}"
    except ValueError:
        return sv in svs
    return key in svs or sv in svs
