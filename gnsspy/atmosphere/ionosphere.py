"""Ionospheric delay utilities for GNSSpy v3.

The current implementation uses IONEX global ionosphere maps and
interpolates the total electron content at the station location and
observation epochs.
"""

import numpy as _np
import pandas as _pd

from gnsspy.io.products.ionex import read_ionFile
from gnsspy.geodesy.coordinate import cart2ell, geocentric_latitude
from gnsspy.utils.filename import ionFileName
from gnsspy.positioning.observations import _observation_picker_by_band

__all__ = [
    "ionosphere_interp",
    "interpolate_ionosphere",
    "compute_ionospheric_delay",
]


def ionosphere_interp(station, unit="meter", system="G", band="L1", epoch_list=None):
    """Interpolate IONEX values and compute ionospheric delay.

    Parameters
    ----------
    station : object
        GNSSpy station-like object containing epoch, observation epochs and
        approximate receiver coordinates.
    unit : {"meter", "meters", "m", "tecu"}, optional
        Output unit. The default is metres.
    system : str, optional
        Satellite-system code. The default is "G" for GPS.
    band : str, optional
        Frequency band used for the delay conversion. The default is "L1".
    epoch_list : sequence of datetime-like, optional
        Epochs at which the ionosphere values are interpolated. If omitted,
        station observation epochs are used.

    Returns
    -------
    numpy.ndarray
        Interpolated ionospheric delay values.
    """
    ionosphereFile = ionFileName(station.epoch)
    tec = read_ionFile(ionosphereFile)

    obsList = _observation_picker_by_band(station, system, band)

    lat, lon, ellHeight = cart2ell(
        station.approx_position[0],
        station.approx_position[1],
        station.approx_position[2],
    )

    geocentric_lat = geocentric_latitude(lat)
    geocentric_lon = lon

    if epoch_list is None:
        observationEpochList = station.observation.epoch
    else:
        observationEpochList = epoch_list

    Latitude = _np.linspace(87.5, -87.5, 71)
    Longitude = _np.linspace(-180, 180, 72)

    IndexLat = None
    IndexLon = None

    for i in range(len(Latitude) - 1):
        if Latitude[i] > geocentric_lat > Latitude[i + 1]:
            IndexLat = i
            break

    for i in range(len(Longitude) - 1):
        if Longitude[i] < geocentric_lon < Longitude[i + 1]:
            IndexLon = i
            break

    if IndexLat is None or IndexLon is None:
        raise ValueError(
            "Station location is outside the supported IONEX interpolation grid."
        )

    dlat = 2.5
    dlon = 5.0

    p = (geocentric_lon - Longitude[IndexLon]) / dlon
    q = (geocentric_lat - Latitude[IndexLat + 1]) / dlat

    E = (
        (1 - p) * (1 - q) * tec[:, IndexLat + 1, IndexLon]
        + p * (1 - q) * tec[:, IndexLat + 1, IndexLon + 1]
        + q * (1 - p) * tec[:, IndexLat, IndexLon]
        + p * q * tec[:, IndexLat, IndexLon + 1]
    )

    tecFinal = _np.zeros(len(observationEpochList))
    epochStart = _pd.Timestamp(station.epoch)
    j = 0

    for i in range(12):
        epochEnd = epochStart + _pd.Timedelta(hours=2)

        while j < len(observationEpochList) and observationEpochList[j] < epochEnd:
            tecFinal[j] = (
                ((epochEnd - observationEpochList[j]) / (epochEnd - epochStart)) * E[i]
                + ((observationEpochList[j] - epochStart) / (epochEnd - epochStart))
                * E[i + 1]
            )
            j += 1

        epochStart += _pd.Timedelta(hours=2)

        if j == len(observationEpochList):
            break

    if unit.lower() == "tecu":
        ionDelay = 0.1 * tecFinal
    elif unit.lower() in {"meter", "meters", "m"}:
        ionDelay = (0.1 * tecFinal * 40.3 * 1e16) / obsList[4] ** 2
    else:
        raise ValueError("unit must be one of 'tecu', 'meter', 'meters' or 'm'.")

    return ionDelay



interpolate_ionosphere = ionosphere_interp
compute_ionospheric_delay = ionosphere_interp
