"""Interactive observation availability, optionally coloured by measured SNR."""
from gnsspy.visualization._optional import plotly_backend

def bandplot(station, system='G', sv_list=None, save_path=None, *, color_mode=None,
             snr_code='auto', color_range=None, png_path=None, png_scale=2.0):
    """Plot observation availability, optionally writing HTML and a PNG."""
    return plotly_backend().bandplot(station, system, sv_list, save_path,
                                     color_mode=color_mode, snr_code=snr_code,
                                     color_range=color_range, png_path=png_path,
                                     png_scale=png_scale)

visibility_plot = bandplot
__all__ = ['bandplot', 'visibility_plot']
