"""Geographic maps of native IONEX vertical TEC and RMS values."""
from gnsspy.visualization._maps import (backend_name, output_path, read_gim,
                                        select_epochs, prepare_grid)


def ionosphere_map(gim, epoch=None, save_path=None, *, backend="cartopy",
                   field="tec", **kwargs):
    """Plot one IONEX epoch (default: first), returning the backend's Figure.

    gim is an IonexDataset or a local IONEX path. Only already-scaled TECU
    values are used; raw arrays are rejected. Epoch selection is exact, not
    nearest-neighbour or temporal interpolation. field may be 'tec' or 'rms'.
    See ionosphere_maps for styling and layout arguments.
    """
    dataset = read_gim(gim)
    epochs, indices = select_epochs(dataset, epoch)
    if len(epochs) != 1:
        raise ValueError("ionosphere_map accepts one epoch; use ionosphere_maps for multiple epochs")
    return _render(dataset, epochs, indices, save_path, backend, field, kwargs)


def ionosphere_maps(gim, epochs=None, save_path=None, *, backend="cartopy",
                    field="tec", **kwargs):
    """Plot multiple native IONEX epochs with a shared colour scale.

    With epochs=None select 00, 04, 08, 12, 16 and 20 UTC on the first source
    date. Missing requested epochs raise an error; supply an explicit subset of
    gim.epochs for products with different coverage. There is no spatial or
    temporal interpolation, exponent reapplication or modification of gim.

    Cartopy maps default to Robinson, batlow_r, linear scaling, a two-column
    layout, white land/missing cells and light-grey oceans. Set vmin/vmax for a
    fixed range; or pass a Matplotlib norm (e.g. PowerNorm) explicitly. All
    panels use the same norm. Options include projection, central_longitude,
    extent, style (MapStyle/mapping), features, resolution, gridlines,
    coordinate_labels, cmap, ncols, figsize, dpi, title, rasterized and show.
    Coordinate labels default to automatic: on for an explicit regional extent
    and off for global maps. ax is single-map only.

    Plotly produces an interactive grid-point view (not a projected raster),
    using Viridis unless a Plotly colourscale or Matplotlib cmap is provided.
    Its shared limits are linear; a Matplotlib norm is not accepted.
    """
    dataset = read_gim(gim)
    chosen, indices = select_epochs(dataset, epochs, panels=True)
    return _render(dataset, chosen, indices, save_path, backend, field, kwargs)


def _render(dataset, epochs, indices, save_path, backend, field, kwargs):
    backend = backend_name(backend)
    path = output_path(save_path, backend)
    grid = prepare_grid(dataset, indices, field)
    if backend == "cartopy":
        from gnsspy.visualization import cartopy_backend as renderer
    else:
        from gnsspy.visualization import plotly_maps as renderer
    return renderer.ionosphere_maps(grid, epochs, field=field, save_path=path, **kwargs)


tec_map = ionosphere_map
tec_maps = ionosphere_maps
__all__ = ["ionosphere_map", "ionosphere_maps", "tec_map", "tec_maps"]
