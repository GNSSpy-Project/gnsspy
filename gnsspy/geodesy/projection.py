# ===========================================================
# ========================= imports =========================
import numpy as _np
from gnsspy.geodesy.coordinate import _ellipsoid
# ===========================================================

__all__ = ["ell2tm","tm2utm","scale_tm"]

def ell2tm(latitude, longitude, longitude_CM, ellipsoid = 'GRS80'):
    """
    Convert ellipsoidal coordinates to 3 degree Transversal Mercator 
    projection coordinates
    Input:
        latitude: latitude of a point in degrees
        longitude: longitude of a point in degrees
        longitude_CM: central meridian  in degrees
        ellipsoid: name of ellipsoid in string format
    Output:
        Easting, Northing [unit:meters]
    """
    Phi     = _np.deg2rad(latitude) # degree to radian
    Lambda  = _np.deg2rad(longitude) # degree to radian
    Lambda_CM  = _np.deg2rad(longitude_CM) # degree to radian
    dlambda = Lambda - Lambda_CM
    # -----------------------------------------------------------------------------
    # Define Ellipsoid
    ell = _ellipsoid(ellipsoid)
    # -----------------------------------------------------------------------------
    # Some parameters
    N = ell.a/_np.sqrt(1-ell.e1**2*_np.sin(Phi)**2)
    t = _np.tan(Phi)
    n = ell.e2 * _np.cos(Phi)
    # -----------------------------------------------------------------------------
    # Easting Computation
    easting = N*(dlambda*_np.cos(Phi)+((dlambda**3*_np.cos(Phi)**3)/6)*(1-t**2+n**2) +
        ((dlambda**5*_np.cos(Phi)**5)/120)*(5-18*t**2+t**4+14*n**2-58*t**2*n**2+13*n**4+4*n**6-64*n**4*t**2-24*n**6*t**2) +
        ((dlambda**7*_np.cos(Phi)**7)/5040)*(61-479*t**2+179*t**4-t**6))
    
    easting += 500000 # false easting
    # -----------------------------------------------------------------------------
    # Meridian Arc Computation
    # Meridian Arc Computation
    A0 = 1 - ell.e1**2/4 - (3/64)*ell.e1**4 - (5/256)*ell.e1**6 - (175/16384)*ell.e1**8
    A2 = (3/8) * (ell.e1**2 + ell.e1**4/4 + (15/128)*ell.e1**6 - (455/4096)*ell.e1**8)
    A4 = (15/256) * (ell.e1**4 + (3/4)*ell.e1**6 - (77/128)*ell.e1**8)
    A6 = (35/3072) * (ell.e1**6 - (41/32)*ell.e1**8)
    A8 = (-315/131072) * ell.e1**8
    S_phi = ell.a * ( A0 * Phi - A2*_np.sin(2*Phi) + A4*_np.sin(4*Phi) - A6*_np.sin(6*Phi) + A8*_np.sin(8*Phi))
    # -----------------------------------------------------------------------------
    # Northing Computation
    northing = S_phi + N * ( (dlambda**2/2) * _np.sin(Phi) * _np.cos(Phi) + (dlambda**4/24) * _np.sin(Phi) * _np.cos(Phi)**3 * (5 - t**2 + 9*n**2 + 4*n**4) +
        (dlambda**6/720) * _np.sin(Phi) * _np.cos(Phi)**5 * (61 - 58*t**2 + t**4 + 270*n**2 - 330*t**2*n**2 + 445*n**4 + 324*n**6 - 680*n**4*t**2 + 88*n**8 -
        600*n**6*t**2 - 192*n**8*t**2) + (dlambda**8/40320) * _np.sin(Phi) * _np.cos(Phi)**7 * (1385 - 311*t**2 + 543*t**4 - t**6))
    return easting, northing

def tm2utm(easting,northing, scale = 0.9996):
    """ Convert TM (3 degree zone) to UTM (6 degree zone)"""
    x = easting - 500000 # remove false easting
    x *= scale # scale TM to UTM
    easting = x + 500000 # restore false easting
    northing *= scale # In case of Southern hemisphere, false northing may required
    return easting, northing


def scale_tm(latitude, longitude, longitude_CM, ellipsoid = 'GRS80'):
    """ Scale factor in TM projection """
    dlambda = _np.deg2rad(longitude) - _np.deg2rad(longitude_CM)
    ell = _ellipsoid(ellipsoid)
    e1, e2 = ell.e1, ell.e2
    t = _np.tan(_np.deg2rad(latitude))
    n = e2 * _np.cos(_np.deg2rad(latitude))
    # -----------------------------------------------------------------------------
    # Scale formula in terms of ellipsoidal coordinates
    scale = 1 + dlambda**2 / 2 * _np.cos(_np.deg2rad(latitude))**2 * (1 + n**2) + (dlambda**4 * _np.cos(_np.deg2rad(latitude))**4) / 24 * (5 - 4*t**2)
    return scale
