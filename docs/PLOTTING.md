# Geographic plotting

## Installation and scope

From the GNSSpy source directory, install both plotting backends and the tests:

```bash
python -m pip install -e ".[visualization,test]"
```

For geographic maps alone, use `.[cartopy]`. For interactive Plotly plots alone,
use `.[plotly]`. Use `.[plotly-png]` when Plotly figures must also be exported
to PNG. The `visualization`, `workflows` and `all` extras include both backends
and Kaleido. Modern Kaleido requires Chrome or Chromium; run
`plotly_get_chrome` if a compatible browser is not already installed. The
package version remains 3.0.2.

| Function | Default renderer | Alternative | Coordinates |
|---|---|---|---|
| `groundtrack` / `ground_track` | Cartopy | `backend="plotly"` | ECEF converted to longitude/latitude |
| `ionosphere_map` / `tec_map` | Cartopy | `backend="plotly"` | Native IONEX grid, one epoch |
| `ionosphere_maps` / `tec_maps` | Cartopy | `backend="plotly"` | Native IONEX grid, multiple epochs |
| `skyplot`, `azelplot`, `timelplot`, `bandplot` | Plotly | No geographic backend switch | Receiver sky or observation time |
| Orbit-comparison time-series figures | Existing Matplotlib routines | Unchanged | Time and orbit differences |

Cartopy is used only for geographic maps. Skyplots are receiver-centred polar
plots, not geographic maps. No projection has been imposed on those plots.

Geographic calls return a Matplotlib `Figure` with Cartopy, or a Plotly `Figure`
with Plotly. The non-geographic functions also return their Plotly figure.
`save_path=None` returns the map without opening a window or writing a file.
Use `show=True` to display a map. Close Matplotlib figures after batch use.
Importing `gnsspy.visualization` does not import either optional renderer.

Non-geographic Plotly functions accept `png_path`. Keep the normal HTML and add
a same-stem PNG with `png_path=True`, or provide a separate `.png` path. The
optional `png_scale` controls image resolution and defaults to 2.0.

```python
fig = skyplot(station, orbit, save_path="skyplot.html", png_path=True)
fig = azelplot(station, orbit, save_path="azel.html",
               png_path="publication/azel.png", png_scale=3)
```

PNG export never replaces the HTML file. If the static renderer is unavailable,
the call reports how to install it; an HTML file already written remains valid.

## Satellite ground tracks

```python
import matplotlib.pyplot as plt
from gnsspy import read_sp3File
from gnsspy.visualization import groundtrack

orbit = read_sp3File("orbit.SP3", verbose=False)
fig = groundtrack(orbit, system=None, save_path="groundtracks.png")
plt.close(fig)

interactive = groundtrack(
    orbit, system=None, backend="plotly", save_path="groundtracks.html"
)
```

The first four positional parameters are retained:
`groundtrack(orbit, system="G", sv_list=None, save_path=None, ...)`.
To retain HTML in an existing map script, add `backend="plotly"` explicitly.
An HTML suffix does **not** silently override the default renderer.

Accepted map extensions are `.png`, `.pdf`, `.svg`, `.jpg`, `.jpeg`, `.tif`,
`.tiff`, `.eps` and `.ps` for Cartopy, and `.html`/`.htm` for Plotly. A path with
no suffix receives `.png` or `.html`, respectively. Invalid combinations raise
an error. The interactive menu offers PNG, PDF and SVG for Cartopy maps.

`system=None`, `"auto"`, `"ALL"` or `"M"` selects all systems. A combination such as
`"G+E+C"` selects GPS, Galileo and BeiDou. `sv_list=["G01", "E11"]` restricts
satellites within the selected systems. Set `system=None` when the list spans
constellations. An empty selection is an error.

The orbit must have `Epoch` and `SV` index levels, in either order, or equivalent
columns, plus `X`, `Y`, `Z`. Position units are read from
`orbit.attrs["position_unit"]` with `position_unit="auto"`. The native SP3 reader
sets kilometres; interpolated positions use metres. Without metadata, metres
are assumed. Use `position_unit="km"` for a kilometre table without metadata.
Do not multiply native SP3 output by 1000 while leaving its `km` metadata intact.

The default latitude is WGS84 geodetic latitude, preserving the existing
coordinate convention. Set `latitude_type="geocentric"` for the Earth-centred
radial latitude. Source epoch labels are retained; plotting does not perform a
GPST/UTC conversion.

Tracks retain native sampling. Lines break at missing/invalid coordinates, the
geographic antimeridian, the selected projection seam and long time gaps. The
default gap threshold is the greater of 600 seconds and 1.5 times the median
positive sampling interval for each satellite. Set `max_gap=900` to use an
explicit threshold in seconds. Invalid coordinate rows are reported and never
bridged; all-invalid input raises an error. Duplicate satellite/epoch records
also raise an error. A diamond marks each satellite's first valid epoch.

## IONEX maps

```python
import matplotlib.pyplot as plt
from gnsspy import read_ionex
from gnsspy.visualization import ionosphere_map, ionosphere_maps

gim = read_ionex("product_GIM.INX")
print(gim.epochs)

# One exact source epoch; first available epoch when epoch is omitted.
fig = ionosphere_map(gim, epoch=gim.epochs[0], save_path="tec.png")
plt.close(fig)

# Six panels at 00, 04, 08, 12, 16 and 20 UTC on the first source date.
fig = ionosphere_maps(gim, save_path="tec_4hour.png")
plt.close(fig)

# An explicit subset handles products with different coverage.
fig = ionosphere_maps(gim, epochs=gim.epochs[:4], ncols=2,
                      save_path="tec_subset.svg")
plt.close(fig)

# RMS, when present in the source IONEX product.
fig = ionosphere_map(gim, field="rms", save_path="tec_rms.png")
plt.close(fig)

# Regional coordinate labels are enabled automatically by an explicit extent.
fig = ionosphere_map(gim, epoch=gim.epochs[0], projection="platecarree",
                     extent=(20, 45, 30, 50), save_path="tec_regional.png")
plt.close(fig)
```

A local IONEX path can replace `gim` directly. Compressed formats supported by
the existing reader are accepted. Raw arrays are deliberately not accepted:
`gim.tec` and `gim.rms` already contain TECU and must not be rescaled again.

The selected epochs must exist exactly in the product. Requested missing
four-hour epochs are an error, not a nearest-epoch substitution. IONEX epochs
are UTC; timezone-aware requested timestamps are converted to UTC for matching.
All panels share a single colour normalisation and colour bar. Set `vmin` and
`vmax` explicitly to compare figures from different files or days.

The Cartopy renderer draws native cells using `pcolormesh` with explicit cell
edges. It does not spatially smooth or temporally interpolate the values.
Descending axes are reordered together with their data. One duplicated global
longitude endpoint is removed. Complete global grids span 360 degrees through
their cell edges; regional grids are not artificially made cyclic. Inconsistent
values at duplicate seam endpoints trigger a warning; the western endpoint is
retained without averaging. Missing cells are white by default.

For Cartopy TEC/RMS maps, `coordinate_labels=None` (the default) labels the
longitude and latitude axes when `extent=(west, east, south, north)` is supplied,
and leaves global plots unlabelled. Use `coordinate_labels=False` to suppress
regional labels or `coordinate_labels=True` to request them explicitly. Panel
figures show latitude labels only in the left column and longitude labels only
on the bottom row. Plotly regional maps enable coordinate graticules; exact
coordinates are also available in hover text.

These are native-grid maps, not the bi-quadratically interpolated display used
by some earlier figure scripts. Captions for figures regenerated with these
functions should describe the native grid, not claim an interpolation that is
not performed.

With `backend="plotly"`, IONEX output is an interactive, colour-coded **grid-point
view**, not a projected raster or a cell-for-cell reproduction of the Cartopy
map. Missing points are omitted. It uses a shared linear colour scale and
supports hover inspection. For raster-style paper figures, use Cartopy.

## Appearance and projections

Defaults are Robinson projection centred at 0 degrees, light-grey oceans,
white land, black coastlines and thin borders. Cartopy TEC/RMS maps use
`batlow_r` from cmcrameri. The default normalisation is **linear**, with common
limits derived from the selected finite values. No vegetation-specific 0–10
range or square-root scaling is imposed on TEC. Plotly IONEX maps default to
Viridis; `cmap="batlow_r"` also works when Matplotlib and cmcrameri are installed.

```python
from gnsspy.visualization import MapStyle, groundtrack, ionosphere_map
from matplotlib.colors import PowerNorm

style = MapStyle(ocean_colour="lightgray", land_colour="white",
                 coastline_width=0.65, border_width=0.5, title_size=12)

fig = groundtrack(orbit, system=None, style=style,
                  projection="platecarree", extent=(20, 45, 30, 50),
                  save_path="regional.png", dpi=300)

# Optional nonlinear visual scaling; does not change the underlying TECU.
fig = ionosphere_map(gim, style=style,
                      norm=PowerNorm(gamma=0.5, vmin=0, vmax=80),
                      save_path="tec_power_scale.png")
```

Normalisation objects are Cartopy-only. Do not pass both `norm` and `vmin/vmax`.
A caller's normalisation and colour map are copied before modification.

Both renderers accept `projection="robinson"`, `"platecarree"`, `"mollweide"`,
`"equalearth"` and `"mercator"`, plus `central_longitude`, `extent=(W,E,S,N)`,
`style`, `features`, `gridlines`, `coordinate_labels`, `title` and `show` for
IONEX maps. Extents require west < east
with a span no greater than 360 degrees, and -90 <= south < north <= 90.
Cartopy also accepts a Cartopy projection object, a supplied `ax` (GeoAxes),
`figsize`, `resolution`, `dpi` and `rasterized` for TEC maps. A supplied IONEX
axis supports only one epoch. Ground tracks also accept `legend` and
`start_markers`. Unsupported backend-specific arguments raise, rather than being
silently discarded. Longitude/latitude data are explicitly passed with a
PlateCarree data transform independently of the map projection.
Plotly additionally accepts `"naturalearth"`; Cartopy does not provide a
Natural Earth projection class and reports that `"equalearth"` should be used.

PDF/SVG exports preserve line/text geometry while rasterising the IONEX mesh by
default to control file size. Set `rasterized=False` for vector mesh cells.
The function does not force a Matplotlib backend; command-line tools use Agg.

## Basemap data and disconnected operation

Cartopy downloads Natural Earth data on first use when its cache is empty.
This is separate from GNSS data acquisition and does not require Earthdata
credentials. `resolution="110m"` is the default; `"50m"` and `"10m"` require
separate cached datasets. The cache must be writable for downloads.

```python
from pathlib import Path
import cartopy
cartopy.config["data_dir"] = Path.home() / ".local/share/cartopy"
```

Copy an already populated Cartopy cache to a disconnected computer, or use
`features=False` to explicitly omit land polygons, coastlines and borders.
`features=False` does not remove the Cartopy dependency. Failed basemap loading
raises an explanatory error; the library does not silently produce an incomplete
basemap. The automated rendering tests use `features=False`; the example run
without `--no-features` is the additional basemap check.

Map HTML embeds plotly.js, but Plotly geographic topology can still require
network access in the browser. An HTML file being written successfully is not
proof of offline browser rendering. Use Cartopy exports for self-contained
static maps after basemap resources have been cached.

## Command-line maps

```bash
gnsspy-map groundtrack orbit.SP3 --system ALL --output tracks.png
gnsspy-map groundtrack orbit.SP3 --backend plotly --output tracks.html
gnsspy-map ionosphere product_GIM.INX --hours 0 4 8 12 16 20 --output tec.png
gnsspy-map ionosphere product_GIM.INX --hours 12 --field rms --output rms.svg
gnsspy-map ionosphere product_GIM.INX --epochs 2024-01-14T12:00:00 --output tec12.png
```

`python -m gnsspy.cli.maps` accepts the same arguments. Use `--help` after the
command or subcommand. `--date YYYY-MM-DD` selects the date for `--hours`;
otherwise the first source date is used. `--no-features`, `--projection`,
`--extent`, `--central-longitude`, `--cmap`, `--vmin`, `--vmax` and `--dpi` expose
the corresponding plotting options. IONEX commands also provide
`--coordinate-labels` / `--no-coordinate-labels`; their default is automatic
from `--extent`. The command returns a non-zero exit code
when input reading or plotting fails.

`gnsspy-visualize` retains its observation-based interactive flow. Choosing a
ground track also offers the map backend, defaulting to Cartopy, and a static
format. It can optionally add PNG copies of the non-geographic HTML outputs. A
local ground-track-only SP3 call
does not require observations. Saved outputs are reported individually; only
newly generated HTML files are offered for browser opening.

## Reproducible examples and checks

See [examples/README.md](../examples/README.md) for synthetic SP3/IONEX generation,
map rendering and tests. Synthetic examples demonstrate software behaviour; they
are not real satellite or ionosphere observations and are not a scientific
accuracy validation. Real-product integration tests remain separate.

## Implementation references

- Cartopy, *Understanding the transform and projection keywords*:
  https://cartopy.readthedocs.io/stable/tutorials/understanding_transform.html
- Cartopy, *Configuration* (data cache and downloads):
  https://cartopy.readthedocs.io/stable/reference/config.html
- Cartopy, *Adding a cyclic point to help with wrapping of global data*:
  https://cartopy.readthedocs.io/stable/gallery/scalar_data/wrapping_global.html

The wrapping reference explains the periodic-grid issue. This implementation
uses explicit native cell edges rather than adding a duplicate plotted column.


## Observation signal selection and real-data checks

`skyplot` and `azelplot` now accept `snr_code="auto"`, an explicit RINEX S-code,
or a mapping by constellation/satellite. Automatic selection uses a native
measured signal per satellite, maximises finite positive coverage over the
selected span, and never fills missing epochs from another signal. Source codes
appear in legends, hover labels and `fig.layout.meta["snr_selection"]`.
`color_mode="auto"` means SNR; use `"elevation"` explicitly for elevation colouring.
Unknown modes and unavailable explicit codes raise errors. `system="auto"` and
`sv_list="auto"` select available systems/satellites, independently of SNR choice.

`time_elevation_plot` defaults to elevation; `snr_time_series_plot` and legacy
`timelplot` default to SNR. Elevation/time and visibility accept SNR colouring.
SNR values remain unsmoothed, missing samples/gaps are preserved and a shared
colour axis uses the actual plotted range unless `color_range=(low, high)` is set.
Do not interpret different auto-selected codes as the same physical signal.

All five observation views (`skyplot`, `azelplot`, `timelplot`, its named
aliases, and `bandplot`) support the same `png_path` and `png_scale` arguments.

Plots no longer call `standardize_snr`. Its compatibility aliases are deprecated,
explicitly marked, and excluded from selection of native measured codes. Existing
measured observation columns are not overwritten.

Use the matching companion `run_real_plots.py` for RINEX/product retrieval,
reading, interpolation and plotting. The previous `test_all_plots.py` remains
synthetic. See [REAL_PLOT_CHECKS.md](REAL_PLOT_CHECKS.md) for installation, actual
station/date commands, optional BRDC/CLK checks and acceptance limitations.
