# GNSSpy 3.0.2

GNSSpy is an open-source Python library for RINEX conversion, multi-GNSS data handling, orbit analysis, atmospheric modelling and visualisation.

## Capabilities

- RINEX 2/3 observation reading, navigation reading and observation-file conversion.
- GNSS archive access and local SP3, CLK and IONEX product handling.
- Broadcast-orbit calculations, precise-orbit interpolation and orbit comparisons.
- Ionospheric and tropospheric calculations, single-point positioning utilities and observation quality checks.
- Cartopy geographic maps for satellite ground tracks and native IONEX TEC/RMS, with Plotly as an explicit alternative.
- Plotly skyplots, azimuth/elevation, signal-strength, elevation/time and visibility plots, with optional PNG export alongside HTML; existing quality and orbit-comparison routines.

## Installation

Python 3.10 or later is required. From the extracted source directory:

```bash
python -m pip install ".[all]"
```

For an editable installation with tests:

```bash
python -m pip install -e ".[all,test]"
python -m pytest -q
```

A base installation uses `python -m pip install .`. Optional dependency groups are `products`, `cartopy`, `plotly`, `plotly-png`, `visualization`, `workflows`, `all` and `test`. Install `.[visualization]` for both plotting backends plus Plotly's PNG exporter, `.[plotly-png]` for Plotly PNG support alone, or `.[cartopy]` for geographic maps alone. Modern Kaleido PNG export also needs Chrome or Chromium; run `plotly_get_chrome` if no compatible browser is installed.

## Command-line interface

```bash
gnsspy
```

The same interface is available with `python -m gnsspy`. Dedicated entry points are `gnsspy-download`, `gnsspy-visualize`, `gnsspy-map` and `gnsspy-convert-rinex`.

## Python interface

```python
import gnsspy

navigation = gnsspy.read_navFile("broadcast.rnx")
print(navigation.navigation.head())
```

```python
from datetime import date
import gnsspy

orbit = gnsspy.sp3_interp(
    date(2024, 8, 8),
    data_dir="/path/to/products",
    sp3_product="COD0MGXFIN",
    clock_product="auto",
    interval=30,
    allow_download=False,
)
```

```python
import gnsspy

gim = gnsspy.read_ionex("/path/to/product_GIM.INX")
vtec = gim.interpolate(40.0, 30.0, ["2024-01-14T12:00:00"])
```

The user manual describes units, time systems, product selection and interpolation coverage. Check these conventions before combining outputs from different routines.

## Maps and plotting examples

```python
from gnsspy import read_sp3File, read_ionex
from gnsspy.visualization import groundtrack, ionosphere_map, ionosphere_maps, skyplot

orbit = read_sp3File("orbit.SP3", verbose=False)
fig = groundtrack(orbit, system=None, save_path="tracks.png")  # Cartopy default
interactive = groundtrack(orbit, system=None, backend="plotly", save_path="tracks.html")

gim = read_ionex("product_GIM.INX")
fig = ionosphere_maps(gim, save_path="tec_4hour.png")
regional = ionosphere_map(
    gim, epoch=gim.epochs[0], projection="platecarree",
    extent=(20, 45, 30, 50), save_path="tec_regional.png",
)  # Regional longitude/latitude labels are automatic.

# Given a parsed station and matching orbit, keep HTML and add a PNG.
sky = skyplot(station, orbit, save_path="skyplot.html", png_path=True)
```

Cartopy maps default to Robinson projection, light-grey oceans and white land.
IONEX maps use batlow_r and a shared linear TECU colour scale. Four-hour panels
select exact 00/04/08/12/16/20 UTC source epochs; missing epochs raise an error.
Skyplots and other non-geographic observation plots retain Plotly. Geographic
HTML output requires `backend="plotly"` explicitly; maps do not silently switch
backends based on an extension or a missing dependency. Regional TEC maps with
an explicit `extent` show coordinate labels automatically; global TEC maps do
not add them by default.

Run the synthetic examples from the package root:

```bash
python examples/plot_demo.py --backend both --non-geographic
```

The examples generate their own SP3/IONEX files. Cartopy's first basemap use may
require a Natural Earth download. Use `--no-features` for a cache-independent
rendering check (Cartopy is still required). See the plotting guide for cache,
units, output formats, optional backends and exact input conventions.

## Documentation

- [User manual](docs/USER_MANUAL.md)
- [Package structure](docs/PACKAGE_STRUCTURE.md)
- [Plotting guide](docs/PLOTTING.md)
- [Synthetic plotting examples](examples/README.md)

## Licence

GNSSpy source code is distributed under the [MIT licence](LICENSE). Bundled CRX2RNX executables have separate [RNXCMP licence terms](gnsspy/bin/RNX2CMP_LICENSE.txt).

The bundled executables target Linux x86-64 and Windows x86-64. On macOS, install a compatible CRX2RNX executable and make it available on `PATH` for Hatanaka decompression.

RNXCMP reference: Hatanaka, Y. (2008). A Compression Format and Tools for GNSS Observation Data. *Bulletin of the Geospatial Information Authority of Japan*, 55, 21–30.
