"""Time-series visualization for satellite elevation and SNR."""

from gnsspy.visualization.plotly_backend import (
    timelplot,
    time_elevation_plot,
)


snr_time_series_plot = timelplot

__all__ = [
    "timelplot",
    "time_elevation_plot",
    "snr_time_series_plot",
]
