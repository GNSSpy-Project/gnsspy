"""Interactive receiver-sky plots with native RINEX signal selection."""
from gnsspy.visualization._optional import plotly_backend

def skyplot(station, orbit, system='G', sv_list=None, color_mode='snr', save_path=None,
            *, snr_code='auto', cut_off=0.0, max_gap=None, color_range=None,
            png_path=None, png_scale=2.0):
    """Colour by SNR/elevation; snr_code='auto' selects a measured code per SV.

    system/sv_list accept 'auto' for all available observations. No missing SNR
    is replaced by elevation or another signal; selection is in layout.meta.
    Set png_path=True to add a same-stem PNG beside save_path's HTML, or supply
    an explicit .png path. png_scale controls static-image resolution.
    """
    return plotly_backend().skyplot(station, orbit, system, sv_list, color_mode, save_path,
                                    snr_code=snr_code, cut_off=cut_off, max_gap=max_gap,
                                    color_range=color_range, png_path=png_path,
                                    png_scale=png_scale)

__all__ = ['skyplot']
