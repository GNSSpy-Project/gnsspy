# GNSSpy 3.0.2 User Manual

## Installation

Use Python 3.10 or later. From the source directory:

```bash
python -m pip install ".[all]"
```

For development:

```bash
python -m pip install -e ".[all,test]"
python -m pytest -q
```

The base dependencies are NumPy, pandas, requests and unlzw3. Optional groups provide SciPy (`products`), Cartopy maps (`cartopy`), interactive plots (`plotly`), Plotly PNG export (`plotly-png`), both plotting backends plus PNG export (`visualization`), analysis and Excel-output dependencies (`workflows`), or all application dependencies (`all`). Plotly PNG export also needs Chrome or Chromium. The `test` group provides pytest.

## Command-line use

```bash
gnsspy
```

The interactive menu provides data acquisition, visualisation, single-epoch and daily orbit comparisons, and RINEX conversion. `python -m gnsspy` opens the same menu. Dedicated commands are `gnsspy-download`, `gnsspy-visualize`, `gnsspy-map` and `gnsspy-convert-rinex`.

## RINEX observations and navigation

```python
import gnsspy

station = gnsspy.read_obsFile("station.rnx")
nav = gnsspy.read_navFile("broadcast.rnx.gz", use="GEC", verbose=False)
```

`read_obsFile` takes an uncompressed RINEX observation file. Navigation input supports plain text, gzip, bzip2, xz and Unix-compress `.Z` files.

`nav.navigation` is a pandas DataFrame indexed by `(Epoch, SV)`. Distinct messages can share an index. Navigation epochs retain each record's time system. GLONASS and SBAS state-vector positions, velocities and accelerations use kilometres, kilometres per second and kilometres per second squared.

For clock parameters, use `clockDriftRate` for the third polynomial coefficient and `messageTime` for the message time. The compatibility column `transmissionTime` must not be assumed to contain the message transmission time for Keplerian records.

The GPS, Galileo and BeiDou orbit-comparison routines take GPST calendar epochs. Reading other constellations does not establish broadcast-propagation support for them.

## RINEX observation conversion

```python
from gnsspy.io.rinex.converter import convert_file

convert_file("station_v2.24o", "station_v3.rnx", target_version=3.04)
convert_file("station_v3.rnx", "station_v2.24o", target_version=2.11)
```

RINEX 3-to-2 conversion can discard unsupported constellations and merge observation codes. Check that the output retains the signals required for the analysis.

Hatanaka decompression is available through `gnsspy.crx2rnx`. It searches for CRX2RNX on `PATH` and then for a compatible bundled executable. macOS requires an external CRX2RNX installation. The executable licence and reference are included in `gnsspy/bin/RNX2CMP_LICENSE.txt`.

## SP3 and CLK products

```python
import gnsspy

sp3 = gnsspy.read_sp3File("/path/to/orbit.SP3")
clk = gnsspy.read_clockFile("/path/to/clock.CLK")
```

Readers accept original product paths and supported compressed files. SP3 reader positions are in kilometres, clock offsets in microseconds and velocities in kilometres per second. CLK `DeltaTSV` values are in seconds.

```python
from datetime import date
import gnsspy

orbit = gnsspy.sp3_interp(
    date(2024, 8, 8),
    data_dir="/path/to/products",
    sp3_product="COD0MGXFIN",
    clock_product="auto",
    interval=30,
    edge_policy="strict",
    allow_download=False,
)

print(orbit.attrs["sp3_files"])
print(orbit.attrs["clk_files"])
print(orbit.attrs["missing_orbit_rows"])
print(orbit.attrs["missing_clock_rows"])
```

`sp3_files` and `clk_files` can specify individual paths or lists of paths instead of directory discovery. Automatic local selection prioritises final, rapid and ultra-rapid products. An explicit series constrains the centre, project, solution and version. Modern sampling tokens such as `05M` and `15M` are accepted; interpolation uses source epochs.

The output covers one day in GPST, excluding the following midnight. Positions and velocities are in metres and metres per second. Clock biases are matched at exact epochs, without clock interpolation; `clock_product=None` disables clocks.

Supply matching neighbouring-day SP3 files for buffered day-boundary coverage. Unsupported samples, gaps and manoeuvre intervals remain missing. The default `edge_policy="one-sided"` retains in-coverage edge fits with a warning; `"strict"` excludes outputs within 30 minutes of a fit-support boundary. Neither policy extrapolates beyond satellite coverage. Inspect warnings and missing values before further analysis.

## IONEX TEC maps

```python
import gnsspy

gim = gnsspy.read_ionex("/path/to/COD0OPSFIN_20240140000_01D_01H_GIM.INX")
print(gim.tec.shape)
print(gim.epochs)

vtec = gim.interpolate(40.0, 30.0, ["2024-01-14T12:00:00"])
```

Legacy names and modern `GIM.INX` names are supported, including compressed input. `gim.tec` and `gim.rms` are in TECU. Do not apply another exponent or `0.1` scale factor. Maps are stored as `(epoch, latitude, longitude)` and preserve the source grid and epochs.

Interpolation coordinates are geocentric latitude and east-positive longitude in degrees. Epochs are UTC. Spatial interpolation is bilinear and temporal interpolation is linear between Earth-fixed maps. Required missing values and requests outside coverage return `NaN`; `bounds="raise"` raises for out-of-coverage requests. ROTI products and three-dimensional electron-density maps are not accepted as VTEC maps.

`read_ionFile` and `read_ionex_file` return raw arrays unless `return_dataset=True`. Physical TECU conversion of raw arrays requires the source exponent.

`gnsspy.ionosphere_interp` evaluates VTEC or vertical first-order code/group delay at a station. Set `epoch_time_system` explicitly. GPST input requires a valid `gps_utc_offset` in seconds. Metre output is vertical group delay, not satellite-specific slant delay or a carrier-phase correction. The routine does not compute an ionospheric pierce point or a slant mapping function.

## Product acquisition

```python
from datetime import date
from gnsspy.data_access import NavigationDownloader

manager = NavigationDownloader(None, None, "/path/to/products")
try:
    precise = manager.acquire_precise_products(
        center="CODE",
        date=date(2024, 8, 8),
        orbit_type="auto",
        allow_download=False,
    )
    print(precise.message)

    ionosphere = manager.acquire_ionosphere(
        date(2024, 1, 14),
        product="CODE",
        ion_type="auto",
        allow_download=False,
    )
    print(ionosphere.message)
finally:
    manager.session.close()
```

Local acquisition does not require credentials. For authenticated downloads, provide NASA Earthdata credentials to the downloader or use the interactive download interface. Keep credentials out of source control.

Acquisition results distinguish `reused`, `downloaded` and `missing`; CLK can also be `disabled`. A successful availability check does not necessarily indicate a network transfer. Check the per-file actions and paths. Explicit provider and solution requests constrain selection. Predicted ionosphere products require an explicit request.

For observation downloads, use `gnsspy.data_access.ObservationDownloader` or the command-line interface.

## Geographic and observation plots

Geographic plots use Cartopy by default. `backend="plotly"` explicitly selects
interactive HTML. Skyplots and non-geographic observation plots retain Plotly.

```python
from gnsspy.visualization import (groundtrack, ionosphere_map, ionosphere_maps,
                                  skyplot)

fig = groundtrack(sp3, system=None, save_path="groundtracks.png")
fig = ionosphere_map(gim, epoch=gim.epochs[0], save_path="tec.png")
fig = ionosphere_maps(gim, save_path="tec_4hour.png")
fig = ionosphere_map(gim, epoch=gim.epochs[0], projection="platecarree",
                     extent=(20, 45, 30, 50), save_path="tec_regional.png")
fig = skyplot(station, orbit, save_path="skyplot.html", png_path=True)
```

The native SP3 reader's kilometre metadata is honoured. IONEX TECU values are
not rescaled or interpolated by the plotting layer. Four-hour panels require
exact source epochs. Cartopy figures use PNG/PDF/SVG or another supported static
format; Plotly maps use HTML. Regional TEC plots with an explicit extent label
longitude and latitude automatically, while global maps remain uncluttered.
Observation plots can write HTML and a matching PNG with `png_path=True`, or an
explicit PNG destination with `png_path="figure.png"`. PNG export uses Kaleido
and a Chrome/Chromium installation. The returned figure remains available for
further customisation. Close Matplotlib figures after batch plotting.

See the [plotting guide](PLOTTING.md) for the full API, examples, map styling,
coordinate conventions, basemap caching and command-line use. The
[synthetic examples](../examples/README.md) generate local inputs and report
plot failures without requiring GNSS archive downloads.

## Other interfaces

```python
from gnsspy.atmosphere import tropospheric_delay
from gnsspy.positioning.spp import spp
from gnsspy.positioning.observations import gnssDataframe
from gnsspy.quality import multipath
from gnsspy.geodesy import coordinate, projection
from gnsspy.visualization import skyplot, azelplot, timelplot, bandplot, groundtrack
```

Use the callable docstrings for argument definitions. Inspect observation availability, product coverage and numerical warnings before positioning or orbit analysis.

## Tests

The default suite generates synthetic fixtures without live archive access. Full-size integration tests are enabled by setting `GNSSPY_TEST_PRODUCT_DIR` and `GNSSPY_TEST_IONEX_DIR` to directories containing the files listed in `tests/test_precise_samples.py` and `tests/test_ionex_samples.py`. Those external data files are not distributed with the package.
