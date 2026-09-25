"""Interactive azimuth/elevation plots using the same SNR selector as skyplot."""
from gnsspy.visualization._optional import plotly_backend

def azelplot(station, orbit, system='G', sv_list=None, color_mode='snr', save_path=None,
             *, snr_code='auto', cut_off=0.0, max_gap=None, color_range=None,
             png_path=None, png_scale=2.0):
    """Plot azimuth/elevation, optionally writing HTML and a PNG together."""
    return plotly_backend().azelplot(station, orbit, system, sv_list, color_mode, save_path,
                                     snr_code=snr_code, cut_off=cut_off, max_gap=max_gap,
                                     color_range=color_range, png_path=png_path,
                                     png_scale=png_scale)

azimuth_elevation_plot = azelplot
__all__ = ['azelplot', 'azimuth_elevation_plot']
