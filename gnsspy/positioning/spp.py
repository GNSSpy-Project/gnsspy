"""Standard Point Positioning routines for GNSSpy v3."""

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

from gnsspy.positioning.observations import (
    gnssDataframe,
    _observation_picker,
    _observation_picker_by_band,
)
from gnsspy.positioning.adjustment import _adjustment
from gnsspy.orbit.satellite import _reception_coord, _sagnac, _azel, _relativistic_clock
from gnsspy.atmosphere.troposphere import tropospheric_delay

def spp(station, orbit, system="G", cut_off=7.0):
    start = time.time()
    if len(system)>1:
        raise ValueError("SPP does not support multiple satellite system | This feature will be implemented in the next version")
    observation_list = _observation_picker(station, system)
    gnss = gnssDataframe(station, orbit, system, cut_off)

    if len(observation_list) >=2:
        _carrierPhase1 = getattr(gnss,observation_list[0][2])
        _carrierPhase2 = getattr(gnss,observation_list[1][2])
        pseudorange1  = getattr(gnss,observation_list[0][3])
        pseudorange2  = getattr(gnss,observation_list[1][3])
        frequency1 = observation_list[0][4]
        frequency2 = observation_list[1][4]
    else:
        raise ValueError("Ionosphere-free combination is not available")

    gnss["Ionosphere_Free"] = (frequency1**2*pseudorange1-frequency2**2*pseudorange2)/(frequency1**2-frequency2**2)
    gnss = gnss.dropna(subset = ['Ionosphere_Free'])
    gnss["Travel_time"] = gnss["Ionosphere_Free"] / _CLIGHT
    gnss["X_Reception"],gnss["Y_Reception"],gnss["Z_Reception"] = _reception_coord(gnss.X, gnss.Y, gnss.Z, gnss.Vx, gnss.Vy, gnss.Vz, gnss.Travel_time)
    epochList =gnss.index.get_level_values("Epoch").unique().sort_values()
    epoch_start = epochList[0] 
    epoch_offset= _timedelta(seconds=300) 
    epoch_interval = _timedelta(seconds=station.interval-0.000001)
    epoch_stop  = epochList[-1] + _timedelta(seconds=0.000001)
    approx_position = [station.approx_position[0], station.approx_position[1], station.approx_position[2]]
    receiver_clock = station.receiver_clock
    position_list = []
    while True:
        epoch_step = epoch_start + epoch_interval
        gnss_temp = gnss.xs((slice(epoch_start,epoch_step))).copy()
        for iter in range(6):
            distance = _distance_euclidean(approx_position[0],approx_position[1],approx_position[2], gnss_temp.X_Reception, gnss_temp.Y_Reception, gnss_temp.Z_Reception)
            gnss_temp["Distance"] = distance + _sagnac(approx_position[0],approx_position[1],approx_position[2], gnss_temp.X_Reception, gnss_temp.Y_Reception, gnss_temp.Z_Reception)
            gnss_temp["Azimuth"], gnss_temp["Elevation"], gnss_temp["Zenith"] = _azel(station.approx_position[0], station.approx_position[1], station.approx_position[2], gnss_temp.X, gnss_temp.Y, gnss_temp.Z, gnss_temp.Distance)
            gnss_temp["Tropo"] = tropospheric_delay(station.approx_position[0],station.approx_position[1],station.approx_position[2], gnss_temp.Elevation, station.epoch)
            coeffMatrix = _np.zeros([len(gnss_temp),4]) 
            coeffMatrix[:,0] = (approx_position[0] - gnss_temp.X_Reception) / gnss_temp.Distance
            coeffMatrix[:,1] = (approx_position[1] - gnss_temp.Y_Reception) / gnss_temp.Distance
            coeffMatrix[:,2] = (approx_position[2] - gnss_temp.Z_Reception) / gnss_temp.Distance
            coeffMatrix[:,3] =  1
            lMatrix = gnss_temp.Ionosphere_Free - gnss_temp.Distance + _CLIGHT * (gnss_temp.DeltaTSV + gnss_temp.Relativistic_clock - receiver_clock) - gnss_temp.Tropo
            lMatrix = _np.array(lMatrix)
            try:
                linearEquationSolution = _np.linalg.lstsq(coeffMatrix,lMatrix,rcond=None)
                xMatrix = linearEquationSolution[0]
                pos = [approx_position[0] + xMatrix[0], approx_position[1] + xMatrix[1], approx_position[2] + xMatrix[2], receiver_clock + xMatrix[3] / _CLIGHT]
                approx_position[0], approx_position[1] , approx_position[2], receiver_clock = pos[0], pos[1], pos[2], pos[3]
            except:
                print("Cannot solve normal equations for epoch", epoch_start,"| Skipping...")
        position_list.append(pos)
        epoch_start += epoch_offset
        epoch_step  += epoch_offset
        if (epoch_step - epoch_stop) > _timedelta(seconds=station.interval):
            break
    x_coordinate = _np.mean([pos[0] for pos in position_list])
    y_coordinate = _np.mean([pos[1] for pos in position_list])
    z_coordinate = _np.mean([pos[2] for pos in position_list])
    rec_clock    = _np.mean([pos[3] for pos in position_list])
    finish = time.time()
    print("Pseudorange calculation is done in", "{0:.2f}".format(finish-start), "seconds.")
    return (x_coordinate, y_coordinate, z_coordinate, rec_clock)



standard_point_positioning = spp

__all__ = [
    "spp",
    "standard_point_positioning",
]
