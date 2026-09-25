"""Raw, unsmoothed elevation/SNR time series with correctly named defaults."""
from gnsspy.visualization._optional import plotly_backend

def timelplot(station, orbit=None, system='G', sv_list=None, mode='snr', save_path=None,
              *, snr_code='auto', color_mode=None, cut_off=0.0, max_gap=None,
              color_range=None, png_path=None, png_scale=2.0):
    """Plot raw time series, optionally writing HTML and a PNG together."""
    return plotly_backend().timelplot(station, orbit, system, sv_list, mode, save_path,
                                      snr_code=snr_code, color_mode=color_mode, cut_off=cut_off,
                                      max_gap=max_gap, color_range=color_range,
                                      png_path=png_path, png_scale=png_scale)

def time_elevation_plot(station, orbit=None, system='G', sv_list=None, mode='elevation', save_path=None, **kwargs):
    return timelplot(station, orbit, system, sv_list, mode, save_path, **kwargs)

def snr_time_series_plot(station, orbit=None, system='G', sv_list=None, mode='snr', save_path=None, **kwargs):
    return timelplot(station, orbit, system, sv_list, mode, save_path, **kwargs)

__all__ = ['timelplot', 'time_elevation_plot', 'snr_time_series_plot']
