#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
comparison.py
=============
Shared orbit-comparison utilities used by GNSSpy workflows.
"""
import os, datetime, glob, re, shutil, warnings
from pathlib import Path
from contextlib import contextmanager
import numpy as np




try:
    import georinex as gr
    import pandas as pd
except ImportError as exc:
    raise ImportError(
        "Orbit-comparison workflows require optional dependencies. "
        "Install them with: pip install 'gnsspy[workflows]'"
    ) from exc

from gnsspy.utils.filename import sp3FileName, clockFileName
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
    if r < r_min or r > r_max:
        return None

    return [x, y, z]





def datetime_to_gps_tow(dt):
    """datetime -> GPS Time of Week (seconds)"""
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
    """Determines product type from SP3 filenames."""
    if not sp3_files:
        return "igs"
    bn = os.path.basename(sp3_files[0]).upper()
    if bn.startswith("COD"): return "cod"
    elif bn.startswith("GFZ") or bn.startswith("GBM"): return "gfz"
    elif bn.startswith("ESA"): return "esa"
    return "igs"


def discover_files(data_dir):
    """
    Discovers nav, sp3, clk files in data directory.
    Returns: (nav_files, sp3_files, clk_files)
    """
    all_files = [f for f in glob.glob(os.path.join(data_dir, "**", "*"), recursive=True)
                 if 'temp_gnsspy' not in f and os.path.isfile(f)]

    sp3_files = [f for f in all_files if f.lower().endswith(('.sp3', '.sp3.gz'))]
    clk_files = [f for f in all_files if f.lower().endswith('.clk')]

    nav_files = []
    skip_ext = ('.sp3', '.sp3.gz', '.clk', '.crx', '.gz', '.z', '.eph')
    skip_suffix = ('o.rnx', 'd.crx')
    for f in all_files:
        fl = f.lower()
        if any(fl.endswith(e) for e in skip_ext): continue
        if any(fl.endswith(s) for s in skip_suffix): continue
        if len(fl) > 2 and fl[-1] in ['o', 'd'] and fl[-3] == '.': continue
        nav_files.append(f)

    return nav_files, sp3_files, clk_files


def filter_sp3_by_date(sp3_files, target_date):
    """Filters SP3 files for target date +/- 1 day."""
    req_doys = [(target_date + datetime.timedelta(days=d)).strftime('%Y%j') for d in [-1, 0, 1]]
    filtered = [f for f in sp3_files if any(d in os.path.basename(f) for d in req_doys)]
    return filtered if filtered else sp3_files


def setup_sp3_temp(sp3_files, clk_files, target_date, sp3_prod, base_dir, suffix=""):
    """Copies SP3/CLK files to the directory structure expected by gnsspy."""
    temp_dir = os.path.join(base_dir, f"temp_gnsspy{suffix}")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
    os.makedirs(os.path.join(temp_dir, "sp3"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "clk"), exist_ok=True)

    for delta in [-1, 0, 1]:
        dt = target_date + datetime.timedelta(days=delta)
        if isinstance(dt, datetime.datetime): dt = dt.date()
        exp = sp3FileName(dt, product=sp3_prod)
        doy = dt.strftime('%Y%j')
        for f in sp3_files:
            if doy in os.path.basename(f):
                shutil.copy2(f, os.path.join(temp_dir, "sp3", exp))
                break

    dt_tod = target_date if isinstance(target_date, datetime.date) else target_date.date()
    exp_clk = clockFileName(dt_tod, interval=30, product=sp3_prod)
    for f in clk_files:
        if dt_tod.strftime('%Y%j') in os.path.basename(f):
            shutil.copy2(f, os.path.join(temp_dir, "clk", exp_clk))
            break

    return temp_dir


@contextmanager
def pandas_freq_patch():
    """Pandas 2.2+ compatibility patch: '60S' -> '60s'"""
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
                   interval=30, poly_degree=10):
    """Runs SP3 interpolation, returns DataFrame."""
    sp3_prod = detect_sp3_product(sp3_files)
    temp_dir = setup_sp3_temp(sp3_files, clk_files, target_date, sp3_prod, base_dir)

    with pandas_freq_patch():
        sp3data = sp3_interp(target_date, interval=interval, poly_degree=poly_degree,
                             sp3_product=sp3_prod, clock_product=sp3_prod,
                             data_dir=temp_dir)
    return sp3data





def _is_healthy(eph, sys_type):
    """Check satellite health flag. Returns True if healthy.

    GPS:      'health' == 0 → healthy
    Galileo:  'health' bitmask == 0 → all signals OK
    BeiDou:   'SatH1' (or fallback 'health') == 0 → healthy
    """
    try:
        if sys_type == 'C':

            for key in ('SatH1', 'health'):
                if key in eph.data_vars if hasattr(eph, 'data_vars') else key in eph:
                    return float(eph[key]) == 0.0
            return True
        else:
            h = float(eph['health'])
            return h == 0.0
    except (KeyError, TypeError, ValueError):
        return True


def build_ephemeris_table(nav_files):
    """
    Builds a per-satellite ephemeris table from navigation files.
    Filters out unhealthy ephemeris records (health ≠ 0).
    Returns: {sv_str: [(toe_value, eph_xarray), ...]}  (sorted by Toe)
    """
    table = {}
    skipped_unhealthy = 0
    for f in nav_files:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                nav = gr.load(f, use=['G', 'E', 'C'])
            if 'sv' not in nav.coords: continue
            for sv in nav.sv.values:
                if not isinstance(sv, str) or len(sv) < 3: continue
                sys_type = sv[0]
                sv_data = nav.sel(sv=sv)
                if 'Toe' not in sv_data.data_vars: continue
                sv_data = sv_data.dropna(dim='time', subset=['Toe'])
                if sv_data.time.size == 0: continue
                if sv not in table: table[sv] = []
                for t in sv_data.time.values:
                    eph = sv_data.sel(time=t)

                    if not _is_healthy(eph, sys_type):
                        skipped_unhealthy += 1
                        continue
                    table[sv].append((float(eph['Toe']), eph))
        except Exception:
            pass

    if skipped_unhealthy > 0:
        print(f"       [FILTER] Skipped {skipped_unhealthy} unhealthy ephemeris records.")

    for sv in table:
        seen = set()
        unique = []
        for toe, eph in sorted(table[sv], key=lambda x: x[0]):
            if toe not in seen:
                seen.add(toe)
                unique.append((toe, eph))
        table[sv] = unique
    return table


def find_nearest_eph(eph_list, target_tow):
    """Midpoint rule: selects the ephemeris with the closest Toe."""
    best, best_diff = None, float('inf')
    for toe, eph in eph_list:
        diff = abs(target_tow - toe)
        if diff > 302400: diff = 604800 - diff
        if diff < best_diff:
            best_diff = diff
            best = (toe, eph)
    return best





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
