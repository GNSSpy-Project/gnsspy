# ===========================================================
# ========================= imports =========================
import numpy as _np
from gnsspy.funcs.constants import _CLIGHT
from gnsspy.funcs.constants import _OMEGA
from gnsspy.geodesy.coordinate import cart2ell, ell2topo
# ===========================================================

def _relativistic_clock(x, y, z, vx, vy, vz):
    """ Calculate relativistic clock correction
    Input: Coordinates [m] (x,y,z) and Velocities (vx,vy,vz) [m/s]
           of satellites in ECEF frame
    Output: Relativistic clock correction in seconds unit
    """
    return -2*(x*vx + y*vy + z*vz)/_CLIGHT**2

def _reception_coord(x_t, y_t, z_t, vx, vy, vz, travel_time):
    """ Calculates satellite coordinates at signal reception time
    Input:
        satellite coordinates at transmission time (x_t, y_t, z_t) [m]
        satellite velocity in ECEF frame [m/s]
        signal travel time calculated from pseudorange [s]
    Output:
        satellite coordinates at signal reception time
    """
    x_r = x_t-vx*travel_time
    y_r = y_t-vy*travel_time
    z_r = z_t-vz*travel_time
    return x_r, y_r, z_r

def _sagnac(x_rec, y_rec, z_rec, x_sat, y_sat, z_sat):
    sagnac_cor = _OMEGA*(x_sat*y_rec-y_sat*x_rec) / _CLIGHT
    return sagnac_cor

def _azel(x_rec,y_rec,z_rec, x_sat, y_sat, z_sat, distance):
    lat_rec, lon_rec, h_rec = cart2ell(x_rec,y_rec,z_rec)
    east, north, up = ell2topo(lat_rec, lon_rec, h_rec) 
    unit_p = _np.matrix([(x_sat-x_rec)/distance, 
                         (y_sat-y_rec)/distance,
                         (z_sat-z_rec)/distance])
    elevation = []
    azimuth = []
    for i in range(len(_np.transpose(unit_p))):
        elevation.append((_np.arcsin(_np.matmul(_np.transpose(unit_p[:,i]),up))))
        azimuth.append(_np.arctan2(_np.matmul(_np.transpose(unit_p[:,i]),east), _np.matmul(_np.transpose(unit_p[:,i]),north)))
        elevation[i] = elevation[i].item()
        azimuth[i]   = azimuth[i].item()
    
    elevation = _np.degrees(elevation)
    azimuth = _np.degrees(azimuth)
    zenith = _np.degrees(_np.pi/2)-elevation
    return (azimuth, elevation, zenith)

def posvel():
    raise Warning("This function will be available in the next release...")