"""Satellite ground tracks: Cartopy by default, Plotly on request."""
from gnsspy.visualization._maps import backend_name, output_path, prepare_tracks


def groundtrack(orbit, system="G", sv_list=None, save_path=None, *,
                backend="cartopy", position_unit="auto", latitude_type="geodetic",
                max_gap=None, projection="robinson", central_longitude=0.0,
                **kwargs):
    """Plot ECEF satellite positions without changing their sampling.

    Parameters
    ----------
    orbit : pandas.DataFrame
        Epoch/SV index levels or columns and X/Y/Z ECEF coordinates.
    system : str or None
        G by default; also accepts 'G+E+C', 'GEC', or None for all systems.
    sv_list : sequence of str, optional
        Satellite selection; an empty selection is an error.
    backend : {'cartopy', 'plotly'}
        Cartopy returns a Matplotlib Figure; Plotly returns a Plotly Figure.
    position_unit : {'auto', 'm', 'km'}
        Auto reads orbit.attrs['position_unit']; without metadata assumes metres.
        Raw read_sp3File output carries 'km'; sp3_interp output uses metres.
    latitude_type : {'geodetic', 'geocentric'}
        WGS84 geodetic latitude preserves the previous ground-track convention.
        Geocentric latitude gives the radial Earth-centred sub-satellite latitude.
    max_gap : float, optional
        Break lines across longer time gaps (seconds). Default: the larger of
        600 s and 1.5 times each satellite's median epoch spacing.
    projection : str or Cartopy Projection
        Default Robinson. Cartopy Projection objects are Cartopy-only.

    Additional options common to both renderers: extent=(W,E,S,N), style,
    features, gridlines, title, legend, start_markers and show. Cartopy also
    accepts resolution, figsize, dpi and ax. Use PNG/PDF/SVG paths for Cartopy,
    HTML for Plotly. With no path the figure is returned without showing it.
    Plotly HTML embeds plotly.js, but geographic basemaps may require network
    access in the browser. No backend fallback happens silently.
    """
    backend = backend_name(backend)
    path = output_path(save_path, backend)
    if backend == "cartopy":
        from gnsspy.visualization import cartopy_backend as renderer

        target = getattr(kwargs.get("ax"), "projection", projection)
        if hasattr(target, "proj4_params"):
            central_longitude = target.proj4_params.get("lon_0", central_longitude)
    else:
        from gnsspy.visualization import plotly_maps as renderer
    tracks = prepare_tracks(orbit, system, sv_list, position_unit=position_unit,
                            latitude_type=latitude_type, max_gap=max_gap,
                            central_longitude=central_longitude)
    return renderer.groundtrack(tracks, projection=projection,
                               central_longitude=central_longitude,
                               save_path=path, **kwargs)


ground_track = groundtrack
__all__ = ["groundtrack", "ground_track"]
