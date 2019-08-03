"""
Atmopspheric corrections

"""
import numpy as _np
from gnsspy.geodesy.coordinate import cart2ell as _cart2ell
from gnsspy.funcs.date import datetime2doy as _datetime2doy

__all__ = ["tropospheric_delay"]

def tropospheric_delay(x, y, z, elevation, epoch):
    """
    Calculates tropospheric delay using Colins(1999) method
    Input:
        Cartesian coordinates of receiver in ECEF frame (x,y,z)
        Elevation Angle [unit: degree] of satellite vehicle
    Output:
        Tropospheric delay [unit: m]
    
    Reference: 
    Collins, J. P. (1999). Assessment and Development of a Tropospheric Delay Model for
    Aircraft Users of the Global Positioning System. M.Sc.E. thesis, Department of
    Geodesy and Geomatics Engineering Technical Report No. 203, University of
    New Brunswick, Fredericton, New Brunswick, Canada, 174 pp
    """
    lat,lon,ellHeight = _cart2ell(x,y,z)
    ortHeight = ellHeight # Using elliposidal height for now
    # --------------------
    # constants
    k1 = 77.604  # K/mbar
    k2 = 382000  # K^2/mbar
    Rd = 287.054 # J/Kg/K
    g  = 9.80665 # m/s^2
    gm = 9.784   # m/s^2
    # --------------------
    # linear interpolation of meteorological values
    # Average values
    ave_params = _np.array([
                           [1013.25,299.65,26.31,6.30e-3,2.77],
                           [1017.25,294.15,21.79,6.05e-3,3.15],
                           [1015.75,283.15,11.66,5.58e-3,2.57],
                           [1011.75,272.15, 6.78,5.39e-3,1.81],
                           [1013.00,263.65, 4.11,4.53e-3,1.55]
                           ])
    # seasonal variations
    sea_params = _np.array([
                           [ 0.00, 0.00,0.00,0.00e-3,0.00],
                           [-3.75, 7.00,8.85,0.25e-3,0.33],
                           [-2.25,11.00,7.24,0.32e-3,0.46],
                           [-1.75,15.00,5.36,0.81e-3,0.74],
                           [-0.50,14.50,3.39,0.62e-3,0.30]
                           ])
    # Latitude index 
    Latitude = _np.linspace(15,75,5)
    if abs(lat)<=15.0:
        indexLat=0
    elif 15<abs(lat)<=30:
        indexLat=1
    elif 30<abs(lat)<=45:
        indexLat=2
    elif 45<abs(lat)<=60:
        indexLat=3
    elif 60<abs(lat)<75:
        indexLat=4
    elif 75<=abs(lat):
        indexLat=5
    # ----------------
    if indexLat == 0:
        ave_meteo  = ave_params[indexLat,:]
        svar_meteo = sea_params[indexLat-1,:]
    elif indexLat == 5:
        ave_meteo  = ave_params[indexLat-1,:]
        svar_meteo = sea_params[indexLat-1,:]
    else:
        ave_meteo  = ave_params[indexLat-1,:]+(ave_params[indexLat,:]-ave_params[indexLat-1,:])*(abs(lat)-Latitude[indexLat-1])/(Latitude[indexLat]-Latitude[indexLat-1])
        svar_meteo = sea_params[indexLat-1,:]+(sea_params[indexLat,:]-sea_params[indexLat-1,:])*(abs(lat)-Latitude[indexLat-1])/(Latitude[indexLat]-Latitude[indexLat-1])
    #
    doy = _datetime2doy(epoch, string = False)
    if lat >= 0.0: # northern hemisphere
        doy_min=28
    else: # southern latitudes
        doy_min=211
    param_meteo = ave_meteo - svar_meteo*_np.cos((2*_np.pi*(doy-doy_min))/365.25)
    pressure, temperature, e, beta, lamda = param_meteo[0],param_meteo[1],param_meteo[2],param_meteo[3],param_meteo[4]
    # --------------------
    ave_dry = 1e-6*k1*Rd*pressure/gm 
    ave_wet = 1e-6*k2*Rd/(gm*(lamda+1)-beta*Rd)*e/temperature
    d_dry = ave_dry*(1-beta*ortHeight/temperature)**(g/Rd/beta)
    d_wet = ave_wet*(1-beta*ortHeight/temperature)**(((lamda+1)*g/Rd/beta)-1)
    m_elev = 1.001/_np.sqrt(0.002001+_np.sin(_np.deg2rad(elevation))**2)
    dtropo = (d_dry + d_wet) * m_elev
    return dtropo
