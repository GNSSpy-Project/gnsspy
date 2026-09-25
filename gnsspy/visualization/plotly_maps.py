"""Optional interactive geographic renderers. Cartopy is not imported here."""
from math import ceil
import numpy as np

from gnsspy.visualization._maps import (map_style, validate_extent, colour_limits,
                                        positive,
                                        coordinate_labels as _coordinate_labels)


def _imports():
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise ImportError("Interactive plots require Plotly. Install with "
                          "python -m pip install 'gnsspy[plotly]' or, from source, "
                          "python -m pip install '.[plotly]'.") from exc
    return go


def _css(value):
    try:
        grey = float(value)
    except (ValueError, TypeError):
        return value
    if 0 <= grey <= 1:
        n = round(255*grey)
        return f"rgb({n},{n},{n})"
    return value


def _geo(fig, projection, centre, extent, style, features, gridlines,
         label_coordinates=False):
    if not isinstance(projection, str):
        raise TypeError("The Plotly backend requires a projection name, not a Cartopy object")
    name = projection.lower().replace("-", "_")
    aliases = {"platecarree": "equirectangular", "plate_carree": "equirectangular",
               "naturalearth": "natural earth", "equalearth": "equal earth"}
    name = aliases.get(name, name)
    if name not in {"robinson", "equirectangular", "mollweide", "natural earth",
                    "equal earth", "mercator"}:
        raise ValueError("Unknown geographic projection")
    centre = float(centre)
    if not np.isfinite(centre):
        raise ValueError("central_longitude must be finite")
    show_grid = bool(gridlines or label_coordinates)
    kwargs = dict(projection_type=name, projection_rotation_lon=centre,
                  showland=features, landcolor=_css(style.land_colour),
                  showocean=features, oceancolor=_css(style.ocean_colour),
                  showcountries=features, countrycolor=_css(style.border_colour),
                  countrywidth=style.border_width,
                  showcoastlines=features, coastlinecolor=_css(style.coastline_colour),
                  coastlinewidth=style.coastline_width,
                  bgcolor=_css(style.ocean_colour),
                  lonaxis_showgrid=show_grid, lataxis_showgrid=show_grid,
                  lonaxis_gridcolor=_css(style.grid_colour),
                  lonaxis_gridwidth=style.grid_width, lataxis_gridwidth=style.grid_width,
                  lataxis_gridcolor=_css(style.grid_colour))
    if extent is not None:
        kwargs.update(lonaxis_range=extent[:2], lataxis_range=extent[2:])
    fig.update_geos(**kwargs)


def _finish(fig, path, show):
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(path), include_plotlyjs=True, full_html=True)
    if show:
        fig.show()
    return fig


def groundtrack(tracks, *, projection="robinson", central_longitude=0.0,
                extent=None, style=None, features=True, gridlines=True,
                title="Satellite ground tracks", legend=True, start_markers=True,
                save_path=None, show=False):
    go = _imports()
    from plotly.colors import qualitative
    style, extent = map_style(style), validate_extent(extent)
    fig = go.Figure()
    for i, (sv, track) in enumerate(tracks.items()):
        colour = qualitative.Plotly[i % len(qualitative.Plotly)]
        lon, lat, text = [], [], []
        for x, y, times in track["segments"]:
            lon.extend([*x, None])
            lat.extend([*y, None])
            text.extend([*[str(t) for t in times], None])
        fig.add_trace(go.Scattergeo(
            lon=lon, lat=lat, text=text, mode="lines+markers", name=sv,
            line=dict(color=colour, width=style.track_width),
            marker=dict(color=colour, size=2), connectgaps=False,
            hovertemplate=sv+"<br>Epoch: %{text}<br>Lon: %{lon:.3f}°<br>Lat: %{lat:.3f}°<extra></extra>"))
        if start_markers:
            x, y = track["start"]
            fig.add_trace(go.Scattergeo(lon=[x], lat=[y], mode="markers", showlegend=False,
                                       marker=dict(symbol="diamond", color=colour, size=7),
                                       hovertext=f"{sv}: first valid epoch", hoverinfo="text"))
    _geo(fig, projection, central_longitude, extent, style, features, gridlines)
    fig.update_layout(title=dict(text=title or "", x=0.5, font=dict(size=style.title_size)), template="plotly_white",
                      height=600, showlegend=legend, margin=dict(l=20, r=20, t=60, b=30))
    return _finish(fig, save_path, show)


def _colourscale(cmap):
    if cmap is None:
        return "Viridis"
    from plotly.colors import get_colorscale
    if isinstance(cmap, str):
        try:
            return get_colorscale(cmap)
        except Exception:
            pass
    try:
        from matplotlib.colors import Colormap, to_hex
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError("Use a Plotly colourscale name, or install Matplotlib for a Matplotlib colour map") from exc
    if not isinstance(cmap, Colormap):
        try:
            cmap = plt.get_cmap(cmap)
        except ValueError:
            try:
                from cmcrameri import cm
            except ImportError as exc:
                raise ImportError("Install cmcrameri to use batlow_r, or set cmap='Viridis'") from exc
            if not hasattr(cm, str(cmap)):
                raise ValueError(f"Unknown colour map: {cmap}")
            cmap = getattr(cm, str(cmap))
    return [[float(x), to_hex(cmap(x))] for x in np.linspace(0, 1, 64)]


def ionosphere_maps(grid, epochs, *, field="tec", projection="robinson",
                    central_longitude=0.0, extent=None, style=None, features=True,
                    gridlines=False, coordinate_labels=None, cmap=None,
                    vmin=None, vmax=None, ncols=2,
                    title=None, marker_size=3, norm=None, save_path=None, show=False):
    go = _imports()
    from plotly.subplots import make_subplots
    style, extent = map_style(style), validate_extent(extent)
    label_coordinates = _coordinate_labels(coordinate_labels, extent)
    if norm is not None:
        raise ValueError("Plotly IONEX maps use linear limits; use vmin/vmax or select Cartopy for norm")
    if isinstance(ncols, bool) or int(ncols) != ncols or ncols < 1:
        raise ValueError("ncols must be a positive integer")
    marker_size = positive(marker_size, "marker_size")
    ncols = min(int(ncols), len(epochs))
    nrows = ceil(len(epochs)/ncols)
    lon, lat, lon_edges, lat_edges, maps = grid
    lo, hi = colour_limits(maps, vmin, vmax)
    labels = [e.strftime("%Y-%m-%d  %H:%M UTC") for e in epochs]
    specs = [[{"type": "geo"} if r*ncols+c < len(epochs) else None
              for c in range(ncols)] for r in range(nrows)]
    fig = make_subplots(rows=nrows, cols=ncols, specs=specs, subplot_titles=labels,
                        horizontal_spacing=0.04, vertical_spacing=min(0.10, 0.25/nrows))
    xx, yy = np.meshgrid(lon, lat)
    for i, values in enumerate(maps):
        valid = ~np.ma.getmaskarray(values)
        fig.add_trace(go.Scattergeo(
            lon=xx[valid], lat=yy[valid], mode="markers", showlegend=False,
            marker=dict(size=marker_size, color=np.asarray(values)[valid], coloraxis="coloraxis"),
            hovertemplate="Lon: %{lon:.2f}°<br>Lat: %{lat:.2f}°<br>%{marker.color:.2f} TECU<extra></extra>"),
            row=i//ncols+1, col=i%ncols+1)
    _geo(fig, projection, central_longitude, extent, style, features, gridlines,
         label_coordinates)
    fig.update_layout(template="plotly_white", height=340*nrows,
                      title=dict(text=title or "", x=0.5, font=dict(size=style.title_size)),
                      coloraxis=dict(cmin=lo, cmax=hi, colorscale=_colourscale(cmap),
                                     colorbar=dict(title="VTEC [TECU]" if field == "tec" else "RMS [TECU]")),
                      margin=dict(l=15, r=90, t=75 if title else 45, b=20))
    return _finish(fig, save_path, show)
