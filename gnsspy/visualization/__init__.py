"""Visualization tools for GNSSpy v3.

Geographic maps use Cartopy by default, with Plotly available explicitly.
Non-geographic skyplots, geometry, SNR and visibility plots retain Plotly.
Optional plotting libraries are imported only when a renderer is called.
"""

from gnsspy.visualization.skyplot import skyplot
from gnsspy.visualization.azel import (
    azelplot,
    azimuth_elevation_plot,
)
from gnsspy.visualization.time_elevation import (
    timelplot,
    time_elevation_plot,
    snr_time_series_plot,
)
from gnsspy.visualization.visibility import (
    bandplot,
    visibility_plot,
)
from gnsspy.visualization.groundtrack import (
    groundtrack,
    ground_track,
)

from gnsspy.visualization.ionosphere import ionosphere_map, ionosphere_maps, tec_map, tec_maps
from gnsspy.visualization._maps import MapStyle

__all__ = [
    "MapStyle", "ionosphere_map", "ionosphere_maps", "tec_map", "tec_maps",
    "skyplot",
    "azelplot",
    "azimuth_elevation_plot",
    "timelplot",
    "time_elevation_plot",
    "snr_time_series_plot",
    "bandplot",
    "visibility_plot",
    "groundtrack",
    "ground_track",
]
