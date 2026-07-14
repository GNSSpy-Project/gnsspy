




"""
Calculate satellite positions from Broadcast Ephemeris (Navigation) data.
Supports Keplerian broadcast-orbit computation for the implemented multi-GNSS systems.

References:
- Poliastro: https://github.com/poliastro/poliastro
- GPS Interface Control Document (ICD-GPS-200)
- Vallado, David. "Fundamentals of Astrodynamics and Applications"
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta


GM = 3.986005e14
OMEGA_E = 7.2921151467e-5


PI = np.pi
TWO_PI = 2.0 * np.pi

__all__ = ["calculate_orbit_from_nav", "compute_broadcast_orbit", "broadcast_orbit_from_navigation"]


def _kepler_equation(E, M, ecc):
    """Kepler equation: f(E) = E - e*sin(E) - M"""
    return E - ecc * np.sin(E) - M


def _kepler_equation_prime(E, ecc):
    """Derivative of Kepler equation: f'(E) = 1 - e*cos(E)"""
    return 1.0 - ecc * np.cos(E)


def _solve_kepler_newton(M, ecc, tol=1e-14, max_iter=50):
    """
    Solve Kepler's equation using Newton-Raphson method.
    
    Based on poliastro's implementation with improved initial guess.
    
    Parameters:
    -----------
    M : float
        Mean anomaly in radians
    ecc : float
        Eccentricity (0 <= ecc < 1 for elliptic orbits)
    tol : float
        Convergence tolerance
    max_iter : int
        Maximum number of iterations
        
    Returns:
    --------
    E : float
        Eccentric anomaly in radians
    """

    M = np.fmod(M, TWO_PI)
    if M > PI:
        M -= TWO_PI
    elif M < -PI:
        M += TWO_PI
    


    if -PI < M < 0 or M > PI:
        E = M - ecc
    else:
        E = M + ecc
    

    for _ in range(max_iter):
        f_val = _kepler_equation(E, M, ecc)
        f_prime = _kepler_equation_prime(E, ecc)
        

        if abs(f_prime) < 1e-15:
            break
            
        delta_E = f_val / f_prime
        E = E - delta_E
        
        if abs(delta_E) < tol:
            return E
    

    return E


def _E_to_nu(E, ecc):
    """
    Convert eccentric anomaly to true anomaly using half-angle formula.
    
    From poliastro: uses the numerically stable half-angle formula.
    
    Parameters:
    -----------
    E : float
        Eccentric anomaly in radians
    ecc : float
        Eccentricity
        
    Returns:
    --------
    nu : float
        True anomaly in radians, in range (-π, π]
    """


    beta = ecc / (1.0 + np.sqrt(1.0 - ecc * ecc))
    nu = E + 2.0 * np.arctan2(beta * np.sin(E), 1.0 - beta * np.cos(E))
    return nu


def _compute_satellite_position(eph, t_transmit):
    """
    Compute satellite ECEF position from Keplerian elements.
    
    Implements the GPS ICD algorithm for satellite position calculation.
    
    Parameters:
    -----------
    eph : dict-like
        Ephemeris record with Kepler elements (roota, toe, m0, eccentricity, etc.)
    t_transmit : float
        GPS time of transmission [seconds of week]
    
    Returns:
    --------
    tuple: (x, y, z, dt_sv) in meters and seconds
    """

    try:
        roota = float(eph['roota'])
        toe = float(eph['toe'])
        m0 = float(eph['m0'])
        e = float(eph['eccentricity'])
        delta_n = float(eph['delta_n'])
        omega = float(eph['smallomega'])
        cus = float(eph['cus'])
        cuc = float(eph['cuc'])
        crs = float(eph['crs'])
        crc = float(eph['crc'])
        cis = float(eph['cis'])
        cic = float(eph['cic'])
        i0 = float(eph['i0'])
        idot = float(eph['idot'])
        omega0 = float(eph['bigomega0'])
        omega_dot = float(eph['bigomegadot'])
    except (KeyError, TypeError, ValueError) as ex:
        raise ValueError(f"Invalid ephemeris data: {ex}")
    

    if e < 0 or e >= 1:
        raise ValueError(f"Invalid eccentricity: {e}")
    

    if roota <= 0:
        raise ValueError(f"Invalid sqrt(a): {roota}")
    

    a = roota ** 2
    

    n0 = np.sqrt(GM / (a ** 3))
    n = n0 + delta_n
    

    tk = t_transmit - toe
    

    if tk > 302400:
        tk -= 604800
    elif tk < -302400:
        tk += 604800
    

    Mk = m0 + n * tk
    

    Ek = _solve_kepler_newton(Mk, e)
    

    nu_k = _E_to_nu(Ek, e)
    

    phi_k = nu_k + omega
    

    sin_2phi = np.sin(2.0 * phi_k)
    cos_2phi = np.cos(2.0 * phi_k)
    
    delta_uk = cus * sin_2phi + cuc * cos_2phi
    delta_rk = crs * sin_2phi + crc * cos_2phi
    delta_ik = cis * sin_2phi + cic * cos_2phi
    

    uk = phi_k + delta_uk
    rk = a * (1.0 - e * np.cos(Ek)) + delta_rk
    ik = i0 + delta_ik + idot * tk
    

    xk_prime = rk * np.cos(uk)
    yk_prime = rk * np.sin(uk)
    

    omega_k = omega0 + (omega_dot - OMEGA_E) * tk - OMEGA_E * toe
    

    cos_omega_k = np.cos(omega_k)
    sin_omega_k = np.sin(omega_k)
    cos_ik = np.cos(ik)
    sin_ik = np.sin(ik)
    
    x = xk_prime * cos_omega_k - yk_prime * cos_ik * sin_omega_k
    y = xk_prime * sin_omega_k + yk_prime * cos_ik * cos_omega_k
    z = yk_prime * sin_ik
    

    try:
        clock_bias = float(eph['clockBias'])
        clock_drift = float(eph['relFeqBias']) if pd.notna(eph.get('relFeqBias')) else 0.0
    except:
        clock_bias = 0.0
        clock_drift = 0.0
    
    dt_sv = clock_bias + clock_drift * tk
    
    return x, y, z, dt_sv


def _datetime_to_gps_week_sec(dt):
    """Convert datetime to GPS week and seconds of week."""
    gps_epoch = datetime(1980, 1, 6)
    delta = dt - gps_epoch
    total_seconds = delta.total_seconds()
    week = int(total_seconds // 604800)
    sow = total_seconds - week * 604800
    return week, sow


def calculate_orbit_from_nav(navigation, t_start, t_end, interval=30, system_filter=None):
    """
    Calculate satellite orbits from Navigation (BRDC) data.
    
    Parameters:
    -----------
    navigation : Navigation object
        Parsed navigation file from read_navFile
    t_start : datetime.date or datetime.datetime
        Start time for orbit calculation
    t_end : datetime.date or datetime.datetime  
        End time for orbit calculation
    interval : int
        Time interval in seconds (default: 30)
    system_filter : str or None
        Single letter filter for satellite system ('G', 'R', 'E', 'C', 'J', 'I')
        If None, all systems are included
    
    Returns:
    --------
    pd.DataFrame
        DataFrame with columns [X, Y, Z, Vx, Vy, Vz, DeltaTSV] indexed by (Epoch, SV)
    """
    nav_df = navigation.navigation
    

    if isinstance(t_start, datetime):
        start_dt = t_start
    else:
        start_dt = datetime(t_start.year, t_start.month, t_start.day, 0, 0, 0)
    
    if isinstance(t_end, datetime):
        end_dt = t_end
    else:
        end_dt = datetime(t_end.year, t_end.month, t_end.day, 23, 59, 59)
    

    epochs = pd.date_range(start=start_dt, end=end_dt, freq=f'{interval}s')
    

    sv_list = nav_df.index.get_level_values('SV').unique().tolist()
    

    if system_filter:
        sv_list = [sv for sv in sv_list if sv.startswith(system_filter.upper())]
    

    sv_list = [sv for sv in sv_list if not sv.startswith('R')]
    
    if not sv_list:
        print(f"   [!] No satellites found for system filter: {system_filter}")
        return pd.DataFrame()
    
    results = []
    processed_sats = set()
    error_sats = set()
    
    for sv in sv_list:
        try:

            sv_eph = nav_df.xs(sv, level='SV')
            
            if sv_eph.empty:
                continue
            
            for epoch in epochs:
                try:

                    eph_epochs = sv_eph.index.get_level_values('Epoch')
                    

                    valid_eph = sv_eph[eph_epochs <= epoch]
                    if valid_eph.empty:
                        valid_eph = sv_eph
                    

                    eph_record = valid_eph.iloc[-1]
                    

                    if pd.isna(eph_record['roota']):
                        continue
                    

                    _, sow = _datetime_to_gps_week_sec(epoch)
                    

                    x, y, z, dt_sv = _compute_satellite_position(eph_record, sow)
                    
                    results.append({
                        'Epoch': epoch,
                        'SV': sv,
                        'X': x,
                        'Y': y,
                        'Z': z,
                        'DeltaTSV': dt_sv
                    })
                    processed_sats.add(sv)
                    
                except Exception as e:
                    if sv not in error_sats:
                        error_sats.add(sv)
                    continue
                
        except Exception as e:
            if sv not in error_sats:
                error_sats.add(sv)
            continue
    
    if not results:
        print("[!] Warning: No valid ephemeris found for orbit calculation.")
        if error_sats:
            print(f"    Satellites with errors: {', '.join(sorted(error_sats))}")
        return pd.DataFrame()
    

    orbit_df = pd.DataFrame(results)
    orbit_df.set_index(['Epoch', 'SV'], inplace=True)
    orbit_df.sort_index(inplace=True)
    

    orbit_df['Vx'] = 0.0
    orbit_df['Vy'] = 0.0
    orbit_df['Vz'] = 0.0
    
    for sv in orbit_df.index.get_level_values('SV').unique():
        try:
            sv_data = orbit_df.xs(sv, level='SV')
            if len(sv_data) > 1:
                vx = np.gradient(sv_data['X'].values, interval)
                vy = np.gradient(sv_data['Y'].values, interval)
                vz = np.gradient(sv_data['Z'].values, interval)
                

                sv_mask = orbit_df.index.get_level_values('SV') == sv
                orbit_df.loc[sv_mask, 'Vx'] = vx
                orbit_df.loc[sv_mask, 'Vy'] = vy
                orbit_df.loc[sv_mask, 'Vz'] = vz
        except Exception:
            continue
    
    print(f"   [OK] Orbit calculated from BRDC: {len(processed_sats)} satellites, {len(epochs)} epochs.")
    if error_sats:
        print(f"   [!] Skipped satellites with invalid data: {', '.join(sorted(error_sats))}")
    
    return orbit_df



compute_broadcast_orbit = calculate_orbit_from_nav
broadcast_orbit_from_navigation = calculate_orbit_from_nav
