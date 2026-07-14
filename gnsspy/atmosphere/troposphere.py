"""Tropospheric delay models for GNSSpy v3.

This module contains atmospheric corrections as standalone GNSS
functionality. The functions can be used by positioning routines,
diagnostic workflows, visualization examples and teaching notebooks.
"""

import numpy as _np

from gnsspy.geodesy.coordinate import cart2ell as _cart2ell
from gnsspy.utils.date import datetime2doy as _datetime2doy

__all__ = [
    "tropospheric_delay",
    "compute_tropospheric_delay",
]


def tropospheric_delay(x, y, z, elevation, epoch):
    """Calculate tropospheric delay using the Collins model.

    Parameters
    ----------
    x, y, z : float
        Receiver coordinates in the Earth-Centred Earth-Fixed frame.
    elevation : float or array-like
        Satellite elevation angle in degrees.
    epoch : datetime-like
        Observation epoch used to model seasonal atmospheric variation.

    Returns
    -------
    float or array-like
        Tropospheric delay in metres.

    Notes
    -----
    The implementation follows the Collins tropospheric model retained
    from the earlier GNSSpy release. Ellipsoidal height is used as an
    approximation for orthometric height.
    """
    lat, lon, ellHeight = _cart2ell(x, y, z)
    ortHeight = ellHeight


    k1 = 77.604
    k2 = 382000
    Rd = 287.054
    g = 9.80665
    gm = 9.784



    ave_params = _np.array([
        [1013.25, 299.65, 26.31, 6.30e-3, 2.77],
        [1017.25, 294.15, 21.79, 6.05e-3, 3.15],
        [1015.75, 283.15, 11.66, 5.58e-3, 2.57],
        [1011.75, 272.15,  6.78, 5.39e-3, 1.81],
        [1013.00, 263.65,  4.11, 4.53e-3, 1.55],
    ])


    sea_params = _np.array([
        [ 0.00,  0.00, 0.00, 0.00e-3, 0.00],
        [-3.75,  7.00, 8.85, 0.25e-3, 0.33],
        [-2.25, 11.00, 7.24, 0.32e-3, 0.46],
        [-1.75, 15.00, 5.36, 0.81e-3, 0.74],
        [-0.50, 14.50, 3.39, 0.62e-3, 0.30],
    ])

    latitude_grid = _np.linspace(15, 75, 5)

    if abs(lat) <= 15.0:
        indexLat = 0
    elif 15 < abs(lat) <= 30:
        indexLat = 1
    elif 30 < abs(lat) <= 45:
        indexLat = 2
    elif 45 < abs(lat) <= 60:
        indexLat = 3
    elif 60 < abs(lat) < 75:
        indexLat = 4
    else:
        indexLat = 5

    if indexLat == 0:
        ave_meteo = ave_params[indexLat, :]
        svar_meteo = sea_params[indexLat - 1, :]
    elif indexLat == 5:
        ave_meteo = ave_params[indexLat - 1, :]
        svar_meteo = sea_params[indexLat - 1, :]
    else:
        ave_meteo = (
            ave_params[indexLat - 1, :]
            + (ave_params[indexLat, :] - ave_params[indexLat - 1, :])
            * (abs(lat) - latitude_grid[indexLat - 1])
            / (latitude_grid[indexLat] - latitude_grid[indexLat - 1])
        )
        svar_meteo = (
            sea_params[indexLat - 1, :]
            + (sea_params[indexLat, :] - sea_params[indexLat - 1, :])
            * (abs(lat) - latitude_grid[indexLat - 1])
            / (latitude_grid[indexLat] - latitude_grid[indexLat - 1])
        )

    doy = _datetime2doy(epoch, string=False)
    doy_min = 28 if lat >= 0.0 else 211

    param_meteo = ave_meteo - svar_meteo * _np.cos(
        (2 * _np.pi * (doy - doy_min)) / 365.25
    )

    pressure, temperature, e, beta, lamda = (
        param_meteo[0],
        param_meteo[1],
        param_meteo[2],
        param_meteo[3],
        param_meteo[4],
    )

    ave_dry = 1e-6 * k1 * Rd * pressure / gm
    ave_wet = 1e-6 * k2 * Rd / (gm * (lamda + 1) - beta * Rd) * e / temperature

    d_dry = ave_dry * (1 - beta * ortHeight / temperature) ** (g / Rd / beta)
    d_wet = ave_wet * (
        1 - beta * ortHeight / temperature
    ) ** (((lamda + 1) * g / Rd / beta) - 1)

    mapping = 1.001 / _np.sqrt(
        0.002001 + _np.sin(_np.deg2rad(elevation)) ** 2
    )

    return (d_dry + d_wet) * mapping



compute_tropospheric_delay = tropospheric_delay
