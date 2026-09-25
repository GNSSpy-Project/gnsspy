"""Static geographic plots using Cartopy and Matplotlib.

No pyplot backend is selected here. Applications may choose Agg before calling
these functions, while notebooks and desktop applications retain their backend.
"""
from __future__ import annotations

from math import ceil
import copy
import numpy as np

from gnsspy.visualization._maps import (map_style, positive, validate_extent,
                                        colour_limits,
                                        coordinate_labels as _coordinate_labels)


def _imports():
    try:
        import cartopy.crs as ccrs
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ImportError("Cartopy maps require the map dependencies. Install with "
                          "python -m pip install 'gnsspy[cartopy]' or, from source, "
                          "python -m pip install '.[cartopy]'. "
                          "For interactive maps select backend='plotly'.") from exc
    return ccrs, plt


def _projection(value, centre):
    ccrs, _ = _imports()
    if isinstance(value, ccrs.Projection):
        return value
    names = {"robinson": ccrs.Robinson, "platecarree": ccrs.PlateCarree,
             "plate_carree": ccrs.PlateCarree, "equirectangular": ccrs.PlateCarree,
             "mollweide": ccrs.Mollweide, "equalearth": ccrs.EqualEarth,
             "equal earth": ccrs.EqualEarth, "mercator": ccrs.Mercator}
    name = str(value).lower().replace("-", "_")
    if name in {"naturalearth", "natural earth"}:
        raise ValueError("Cartopy has no Natural Earth projection; use equalearth")
    if name not in names:
        raise ValueError("Unknown projection; use robinson, platecarree, mollweide, "
                         "equalearth, mercator or a Cartopy Projection instance")
    return names[name](central_longitude=float(centre))


def _add_features(ax, style, resolution):
    import cartopy.feature as cf
    if resolution not in {"110m", "50m", "10m"}:
        raise ValueError("resolution must be '110m', '50m' or '10m'")
    entries = [
        (cf.LAND, {"facecolor": style.land_colour, "edgecolor": "none", "zorder": 0}),
        (cf.COASTLINE, {"facecolor": "none", "edgecolor": style.coastline_colour,
                        "linewidth": style.coastline_width, "zorder": 4}),
        (cf.BORDERS, {"facecolor": "none", "edgecolor": style.border_colour,
                     "linewidth": style.border_width, "zorder": 4}),
    ]
    for feature, kwargs in entries:
        feature = feature.with_scale(resolution)
        try:
            geometries = tuple(feature.geometries())
        except Exception as exc:
            raise RuntimeError(
                "Natural Earth basemap data are unavailable. Allow Cartopy's first-use "
                "download, configure cartopy.config['data_dir'] with a prepared cache, "
                "or pass features=False for an explicit basemap-free plot."
            ) from exc
        ax.add_geometries(geometries, crs=feature.crs, **kwargs)


def _decorate(ax, style, extent, features, resolution, gridlines,
              label_coordinates=False, label_left=True, label_bottom=True):
    ccrs, _ = _imports()
    ax.set_facecolor(style.ocean_colour)
    if extent is None:
        ax.set_global()
    else:
        ax.set_extent(extent, crs=ccrs.PlateCarree())
    if features:
        _add_features(ax, style, resolution)
    if gridlines or label_coordinates:
        labels = bool(label_coordinates)
        lines = ax.gridlines(
            crs=ccrs.PlateCarree(), draw_labels=labels,
            linewidth=style.grid_width if gridlines else 0.0,
            color=style.grid_colour, alpha=0.6,
            linestyle=":" if gridlines else "-", zorder=5,
            x_inline=False, y_inline=False,
        )
        if labels:
            lines.top_labels = False
            lines.right_labels = False
            lines.left_labels = bool(label_left)
            lines.bottom_labels = bool(label_bottom)
            lines.xlabel_style = {"size": 9, "color": "black"}
            lines.ylabel_style = {"size": 9, "color": "black"}


def _finish(fig, path, dpi, show):
    _, plt = _imports()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
    if show:
        plt.show()
    return fig


def groundtrack(tracks, *, projection="robinson", central_longitude=0.0,
                extent=None, style=None, features=True, resolution="110m",
                gridlines=True, ax=None, figsize=(12, 6.5), dpi=200,
                title="Satellite ground tracks", legend=True,
                start_markers=True, save_path=None, show=False):
    ccrs, plt = _imports()
    style, extent = map_style(style), validate_extent(extent)
    dpi = positive(dpi, "dpi")
    owns_figure = ax is None
    if owns_figure:
        projection_object = _projection(projection, central_longitude)
        fig = plt.figure(figsize=figsize, layout="constrained")
        ax = fig.add_subplot(1, 1, 1, projection=projection_object)
    else:
        if not hasattr(ax, "projection"):
            raise TypeError("ax must be a Cartopy GeoAxes")
        fig = ax.figure
    try:
        _decorate(ax, style, extent, features, resolution, gridlines)
        colours = plt.rcParams["axes.prop_cycle"].by_key().get("color", ["C0"])
        for i, (sv, track) in enumerate(tracks.items()):
            colour = colours[i % len(colours)]
            for j, (lon, lat, times) in enumerate(track["segments"]):
                ax.plot(lon, lat, color=colour, linewidth=style.track_width,
                        marker="." if len(lon) == 1 else None,
                        label=sv if j == 0 else "_nolegend_",
                        transform=ccrs.PlateCarree(), zorder=3)
            if start_markers:
                ax.plot(*track["start"], marker="D", markersize=4, color=colour,
                        linestyle="none", transform=ccrs.PlateCarree(), zorder=4)
        if title:
            ax.set_title(title, fontsize=style.title_size, pad=10)
        if legend:
            ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.025),
                      ncol=min(len(tracks), 8), frameon=False, fontsize=9)
        return _finish(fig, save_path, dpi, show)
    except Exception:
        if owns_figure:
            plt.close(fig)
        raise


def _colormap(name):
    _, plt = _imports()
    from matplotlib.colors import Colormap
    if isinstance(name, Colormap):
        cmap = copy.copy(name)
    else:
        name = "batlow_r" if name is None else name
        try:
            cmap = copy.copy(plt.get_cmap(name))
        except ValueError:
            try:
                from cmcrameri import cm
            except ImportError as exc:
                raise ImportError("The default batlow_r colour map requires cmcrameri. "
                                  "Install gnsspy[cartopy] or pass cmap='viridis'.") from exc
            if not hasattr(cm, str(name)):
                raise ValueError(f"Unknown colour map: {name}")
            cmap = copy.copy(getattr(cm, str(name)))


    cmap.set_bad((1.0, 1.0, 1.0, 0.0))
    return cmap


def ionosphere_maps(grid, epochs, *, field="tec", projection="robinson",
                    central_longitude=0.0, extent=None, style=None,
                    features=True, resolution="110m", gridlines=False,
                    coordinate_labels=None,
                    cmap=None, vmin=None, vmax=None, norm=None, ncols=2,
                    figsize=None, dpi=200, title=None, ax=None,
                    rasterized=True, save_path=None, show=False):
    ccrs, plt = _imports()
    from matplotlib.colors import ListedColormap, Normalize
    style, extent = map_style(style), validate_extent(extent)
    label_coordinates = _coordinate_labels(coordinate_labels, extent)
    dpi = positive(dpi, "dpi")
    lon, lat, lon_edges, lat_edges, maps = grid
    if isinstance(ncols, bool) or int(ncols) != ncols or ncols < 1:
        raise ValueError("ncols must be a positive integer")
    ncols = min(int(ncols), len(epochs))
    nrows = ceil(len(epochs)/ncols)
    if ax is not None and len(epochs) != 1:
        raise ValueError("A supplied ax can hold only one IONEX map")
    if norm is not None and (vmin is not None or vmax is not None):
        raise ValueError("Supply either norm or vmin/vmax, not both")
    if norm is None:
        lo, hi = colour_limits(maps, vmin, vmax)
        norm = Normalize(vmin=lo, vmax=hi)
    else:
        if not isinstance(norm, Normalize):
            raise TypeError("norm must be a matplotlib.colors.Normalize instance")
        norm = copy.copy(norm)
        norm.autoscale_None(maps)
        if norm.vmin is None or norm.vmax is None or norm.vmin >= norm.vmax:
            raise ValueError("norm must span a non-zero finite range")
        if not np.isfinite([norm.vmin, norm.vmax]).all():
            raise ValueError("norm limits must be finite")
    palette = _colormap(cmap)
    underlay = ListedColormap([style.missing_colour])
    underlay.set_bad((1, 1, 1, 0))
    owns_figure = ax is None
    if owns_figure:
        if figsize is None:
            figsize = (7*ncols, 3.8*nrows)
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize, squeeze=False,
                                 subplot_kw={"projection": _projection(projection, central_longitude)},
                                 layout="constrained")
        axes = list(axes.flat)
    else:
        if not hasattr(ax, "projection"):
            raise TypeError("ax must be a Cartopy GeoAxes")
        fig, axes = ax.figure, [ax]
    active = axes[:len(epochs)]
    try:
        for a in axes[len(epochs):]:
            a.remove()
        for i, (a, epoch, values) in enumerate(zip(active, epochs, maps)):
            column = i % ncols
            _decorate(
                a, style, extent, features, resolution, gridlines,
                label_coordinates=label_coordinates,
                label_left=column == 0,
                label_bottom=i + ncols >= len(active),
            )
            a.pcolormesh(lon_edges, lat_edges, np.ones(values.shape),
                         transform=ccrs.PlateCarree(), cmap=underlay, shading="flat",
                         rasterized=rasterized, zorder=1)
            image = a.pcolormesh(lon_edges, lat_edges, values,
                                transform=ccrs.PlateCarree(), cmap=palette, norm=norm,
                                shading="flat", rasterized=rasterized, zorder=2)
            a.set_title(epoch.strftime("%Y-%m-%d  %H:%M UTC"),
                        fontsize=style.title_size, pad=7)
        label = "Vertical TEC [TECU]" if field == "tec" else "TEC RMS [TECU]"
        cbar = fig.colorbar(image, ax=active, orientation="vertical", fraction=0.032,
                            pad=0.025, shrink=0.82)
        cbar.set_label(label, fontsize=11)
        if title:
            fig.suptitle(title, fontsize=style.title_size+2)
        return _finish(fig, save_path, dpi, show)
    except Exception:
        if owns_figure:
            plt.close(fig)
        raise
