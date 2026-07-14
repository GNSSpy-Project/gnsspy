"""Least-squares adjustment helpers for GNSSpy v3."""

import time
from datetime import timedelta as _timedelta
import numpy as _np
import pandas as _pd
from operator import itemgetter as _itemgetter
from gnsspy.geodesy.coordinate import _distance_euclidean
from gnsspy.atmosphere.troposphere import tropospheric_delay
from gnsspy.orbit.satellite import _reception_coord, _sagnac, _azel, _relativistic_clock
from gnsspy.utils.constants import (_SYSTEM_RNX2, _SYSTEM_RNX3,
                                    _SYSTEM_NAME, _CLIGHT)
import datetime
import numpy as np
import pandas as pd

def _adjustment(coeffMatrix,LMatrix):
    NMatrix = _np.linalg.inv(_np.dot(_np.transpose(coeffMatrix), coeffMatrix))
    nMatrix = _np.matmul(_np.transpose(coeffMatrix), LMatrix)
    XMatrix = _np.dot(NMatrix, nMatrix)
    vMatrix = _np.dot(coeffMatrix, XMatrix) - LMatrix
    m0 = _np.sqrt(_np.dot(_np.transpose(vMatrix), vMatrix)/(len(LMatrix)-len(NMatrix)))
    diagN = _np.diag(NMatrix)
    rmse = m0*_np.sqrt(diagN)
    _mp = _np.sqrt(rmse[0]**2+rmse[1]**2+rmse[2]**2)
    return XMatrix, rmse



least_squares_adjustment = _adjustment

__all__ = [
    "_adjustment",
    "least_squares_adjustment",
]
