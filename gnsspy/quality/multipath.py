"""Multipath-related diagnostic utilities for GNSSpy v3."""

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

from gnsspy.positioning.observations import _observation_picker

def multipath(station, system="G"):
    if len(system)>1:
        raise ValueError("Multiple satellite system is not applicable for multipath | This feature will be implemented in next version.")
    observation_list = _observation_picker(station, system=system)
    observation = station.observation.dropna(subset=[observation_list[0][2],observation_list[1][2],observation_list[0][3],observation_list[1][3]])
    observation = observation.loc[observation.SYSTEM==_SYSTEM_NAME[system]].copy(deep=True)
    carrierPhase1 = getattr(observation,observation_list[0][2])
    carrierPhase2 = getattr(observation,observation_list[1][2])
    pseudorange1  = getattr(observation,observation_list[0][3])
    pseudorange2  = getattr(observation,observation_list[1][3])
    frequency1 = observation_list[0][4]
    frequency2 = observation_list[1][4]
    lam1 = _CLIGHT/frequency1 
    lam2 = _CLIGHT/frequency2 
    ioncoeff = (frequency1/frequency2)**2
    observation["Multipath1"] = pseudorange1 - (2/(ioncoeff-1)+1)*(carrierPhase1*lam1) + (2/(ioncoeff-1))*(carrierPhase2*lam2)
    observation["Multipath2"] = pseudorange2 - (2*ioncoeff/(ioncoeff-1))*(carrierPhase1*lam1) + (2*ioncoeff/(ioncoeff-1)-1)*(carrierPhase2*lam2)
    observation = observation.reorder_levels(['SV','Epoch'])
    observation = observation.sort_index()
    sv_list = observation.index.get_level_values('SV').unique()

    Multipath1 = []
    Multipath2 = []
    for sv in sv_list:
        ObsSV = observation.loc[sv]
        multipathSV1 = []
        multipathSV2 = []
        j = 0
        for i in range(1, len(ObsSV)):
            if (ObsSV.iloc[i].epoch - ObsSV.iloc[i-1].epoch) > _pd.Timedelta('0 days 00:15:00'):
                multipath1 = ObsSV.iloc[j:i].Multipath1.values - _np.nanmean(ObsSV.iloc[j:i].Multipath1.values)
                multipath2 = ObsSV.iloc[j:i].Multipath2.values - _np.nanmean(ObsSV.iloc[j:i].Multipath2.values)
                multipathSV1.extend(multipath1)
                multipathSV2.extend(multipath2)
                j=i
        multipath1 = ObsSV.iloc[j:].Multipath1.values - _np.nanmean(ObsSV.iloc[j:].Multipath1.values)
        multipath2 = ObsSV.iloc[j:].Multipath2.values - _np.nanmean(ObsSV.iloc[j:].Multipath2.values)
        multipathSV1.extend(multipath1)
        multipathSV2.extend(multipath2)
        Multipath1.extend(multipathSV1)
        Multipath2.extend(multipathSV2)

    observation["Multipath1"] = Multipath1
    observation["Multipath2"] = Multipath2
    return observation



compute_multipath = multipath

__all__ = [
    "multipath",
    "compute_multipath",
]
