# ===========================================================
# ========================= imports =========================
import numpy as _np
# ===========================================================
def clock_interp(fit, interval):
    """ 
    This function is for the interpolation of SP3 clocks.
    Inputs:
        fit: 2nd degree polynomial coefficients from numpy polyfit function
             (numpy array)
        interval: seconds (integer)
    Output:
        interpClock: interpolated clocks (numpy array)
        epoch: 
    """
    epoch = _np.linspace(0, 86400 , int(86400/interval)+1) # 86400 seconds = 24 hours
    time = _np.array([[epoch[t]**deg for deg in range(2,-1,-1)] for t in range(int(86400/interval)+1)])
    interpClock = _np.array([[sum(fit*time[t,:])] for t in range(len(time))])
    return interpClock, epoch

def coord_interp(parameter, interval):
    """ 
    This function is for the interpolation of SP3 coordinates. It fits 
    16 degree polynomial to 4 hours (14400 seconds) period of SP3 Cartesian 
    coordinates (per 15 minutes) and returns to the interpolated coordinates
    given in desired interval. NOTE: For clock interpolation refer to 'clock_interp'
    Inputs:
        fit: 16th degree polynomial coefficients from numpy polyfit function
             (numpy array)
        interval: seconds (integer)
    Output:
        interpCoord: interpolated coordinates (numpy array)
    """
    epoch = _np.linspace(1800, 12600 , int(10800/interval)+1) # 3h validity interval within 4h
    time = _np.array([epoch**deg for deg in range(len(parameter)-1,-1,-1)])
    return _np.matmul(parameter,time)
