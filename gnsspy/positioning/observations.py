"""Observation and orbit matching utilities for GNSSpy v3."""

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

from gnsspy.orbit.satellite import _reception_coord, _sagnac, _azel, _relativistic_clock
from gnsspy.atmosphere.troposphere import tropospheric_delay

def _observation_picker(station, system="G"):
    try:
        system = _SYSTEM_NAME[system.upper()]
    except KeyError:
        raise ValueError("Unknown Satellite System:", system, "OPTIONS: G-R-E-C-J-R-I-S")


    if station.version.startswith("3"):
        observation_codes = station.observation.columns.tolist()
        system_observations = getattr(station.observation_types, system)
        band_list         = set("L" + code[1] for code in observation_codes if len(code)==3)
        channel_list      = set([code[2] for code in observation_codes if len(code)==3])
        obs_codes = []
        for band in band_list:
            if band in _SYSTEM_RNX3[system]:
                for channel in channel_list:
                    if (band+channel) in _SYSTEM_RNX3[system][band]["Carrierphase"] and (band+channel) in system_observations:
                        obs_codes.append([system,band,(band+channel),("C"+band[1]+channel),_SYSTEM_RNX3[system][band]["Frequency"]])
                        break

    elif station.version.startswith("2"):
        observation_codes = station.observation.columns.tolist()
        system_observations = station.observation_types
        band_list         = set(code for code in observation_codes if code.startswith(("L")))
        obs_codes = []
        for band in band_list:
            if band in _SYSTEM_RNX2[system].keys():
                for code in _SYSTEM_RNX2[system][band]["Pseudorange"]:
                    if code in system_observations:
                        obs_codes.append([system,band,band,code,_SYSTEM_RNX2[system][band]["Frequency"]])
                        break
    obs_codes = sorted(obs_codes, key=_itemgetter(1))
    return (obs_codes[0],obs_codes[1])

def _observation_picker_by_band(station, system="G", band="L1"):

    try:
        system = _SYSTEM_NAME[system.upper()]
        if band not in _SYSTEM_RNX3[system].keys():
            raise ValueError(band,"band cannot be found in",system,"satellite system! Band options for",system,"system:",tuple(_SYSTEM_RNX3[system].keys()))
    except KeyError:
        raise ValueError("Unknown Satellite System:", system, "OPTIONS: G-R-E-C-J-R-I-S")

    

    if station.version.startswith("3"):
        observation_codes = station.observation.columns.tolist()
        system_observations = getattr(station.observation_types, system)
        channel_list      = set([code[2] for code in observation_codes if len(code)==3])
        obs_codes = []
        if band in _SYSTEM_RNX3[system]:
            for channel in channel_list:
                if (band+channel) in _SYSTEM_RNX3[system][band]["Carrierphase"] and (band+channel) in system_observations:
                    obs_codes.append([system,band,(band+channel),("C"+band[1]+channel),_SYSTEM_RNX3[system][band]["Frequency"],("D"+band[1]+channel),("S"+band[1]+channel)])
                    break

    elif station.version.startswith("2"):
        observation_codes = station.observation.columns.tolist()
        system_observations = station.observation_types
        obs_codes = []
        if band in _SYSTEM_RNX2[system].keys():
            for code in _SYSTEM_RNX2[system][band]["Pseudorange"]:
                if code in system_observations:
                    obs_codes.append([system,band,band,code,_SYSTEM_RNX2[system][band]["Frequency"],("D"+band[1]),("S"+band[1])])
                    break
    return (obs_codes[0])

def gnssDataframe(station, orbit, system="G+R+E+C+J+I+S", cut_off=7.0):
    try:
        system = _itemgetter(*system.split("+"))(_SYSTEM_NAME)
        if type(system)==str: system = tuple([system])
    except KeyError:
        raise ValueError("Unknown Satellite System:", system, "OPTIONS: G-R-E-C-J-R-I-S")
    epochMatch = station.observation.index.intersection(orbit.index)
    gnss = _pd.concat([station.observation.loc[epochMatch].copy(), orbit.loc[epochMatch]], axis=1)
    gnss = gnss[gnss['SYSTEM'].isin(system)]
    gnss["Distance"] = _distance_euclidean(station.approx_position[0], station.approx_position[1], station.approx_position[2], gnss.X, gnss.Y, gnss.Z)
    gnss["Relativistic_clock"] = _relativistic_clock(gnss.X, gnss.Y, gnss.Z, gnss.Vx, gnss.Vy, gnss.Vz)
    gnss['Azimuth'], gnss['Elevation'], gnss['Zenith'] = _azel(station.approx_position[0], station.approx_position[1], station.approx_position[2], gnss.X, gnss.Y, gnss.Z, gnss.Distance)
    gnss = gnss.loc[gnss['Elevation'] > cut_off]
    gnss["Tropo"] = tropospheric_delay(station.approx_position[0],station.approx_position[1],station.approx_position[2], gnss.Elevation, station.epoch)
    return gnss



build_gnss_dataframe = gnssDataframe
build_observation_orbit_dataframe = gnssDataframe
pick_observations = _observation_picker
pick_observation_by_band = _observation_picker_by_band

__all__ = [
    "gnssDataframe",
    "build_gnss_dataframe",
    "build_observation_orbit_dataframe",
    "_observation_picker",
    "_observation_picker_by_band",
    "pick_observations",
    "pick_observation_by_band",
]
