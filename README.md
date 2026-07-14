# GNSSpy v3

[![Version](https://img.shields.io/badge/version-3.0.1-blue.svg)](https://github.com/GNSSpy-Project/gnsspy/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-beta-orange.svg)]()

GNSSpy v3.0.1 is an open-source Python library for RINEX conversion, multi-GNSS data handling, orbit analysis, atmospheric corrections, positioning support, quality diagnostics and interactive visualisation.

Version 3 reorganises GNSSpy around scientific functions rather than the former project layout. Data access, GNSS file readers, RINEX conversion, broadcast and precise orbit tools, atmospheric models, positioning routines, quality-control functions, visualisation and executable workflows are now exposed through separate package namespaces.

Main capabilities include:

* **RINEX 2 ↔ RINEX 3 observation-file conversion**
* **Authenticated GNSS data download from NASA CDDIS**
* **RINEX observation and navigation reading**
* **SP3, CLK and IONEX product handling**
* **Broadcast-orbit computation and SP3 interpolation**
* **Ionospheric and tropospheric corrections**
* **Standard point positioning and observation–orbit matching utilities**
* **SNR, multipath and satellite-visibility diagnostics**
* **Interactive Plotly visualisation**
* **Single-epoch and full-day BRDC–SP3 orbit-comparison workflows**

> **Current orbit-comparison scope:** the packaged BRDC–SP3 workflows currently compare GPS, Galileo and BeiDou satellites. Other constellations remain available in the broader file-reading, data-handling and visualisation layers where suitable observations and orbit products are available.

---

## Table of contents

* [Installation](#installation)
* [Quick start](#quick-start)
* [Command-line interfaces](#command-line-interfaces)

  * [1) Download GNSS data](#1-download-gnss-data)
  * [2) Visualise GNSS data](#2-visualise-gnss-data)
  * [3) Orbit comparison — single epoch](#3-orbit-comparison--single-epoch)
  * [4) Orbit comparison — full-day time series](#4-orbit-comparison--full-day-time-series)
  * [5) Convert RINEX observation files](#5-convert-rinex-observation-files)
* [Python API](#python-api)
* [NASA Earthdata account](#nasa-earthdata-account)
* [Project layout](#project-layout)
* [Dependencies](#dependencies)
* [Documentation and release notes](#documentation-and-release-notes)
* [Citation](#citation)
* [License and third-party components](#license-and-third-party-components)

---

## Installation

GNSSpy v3 requires **Python 3.10 or later**.

### Recommended installation from GitHub

```bash
git clone https://github.com/GNSSpy-Project/gnsspy.git
cd gnsspy

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

python -m pip install --upgrade pip
python -m pip install -e ".[all]"
```

The `all` dependency group installs the packages needed by the visualisation, product-processing and orbit-comparison workflows. A smaller core installation is also available:

```bash
python -m pip install -e .
```

Optional groups can be installed separately:

```bash
python -m pip install -e ".[visualization]"
python -m pip install -e ".[products]"
python -m pip install -e ".[workflows]"
```

### Hatanaka decompression

GNSSpy includes the RNXCMP `CRX2RNX` executables used to decompress Hatanaka observation files (`.crx` and `.d`). The library searches for a compatible executable in the following order:

1. the system `PATH`;
2. the installed package under `gnsspy/bin/`;
3. the source-tree `bin/` directory.

The bundled files cover Linux and Windows. On macOS, install a compatible `CRX2RNX` executable and place it on the system `PATH`.

The standalone RINEX 2 ↔ 3 converter handles ordinary observation files and their `.gz` or `.Z` compression. A Hatanaka file must first be expanded with `CRX2RNX` or `gnsspy.io.manipulate.crx2rnx()`.

---

## Quick start

Run the central interface from the project root:

```bash
python -m gnsspy
```

After installation, the equivalent command is:

```bash
gnsspy
```

The main menu is:

```text
======================================================================
                 GNSSPY - CENTRAL MANAGEMENT INTERFACE
======================================================================

  1. Download GNSS Data
  2. Visualize GNSS Data (Skyplots, SNR, Groundtrack)
  3. Orbit Comparison (Single Epoch)
  4. Orbit Comparison (Full Day Time Series)
  5. RINEX Converter (2 <-> 3)
  6. Exit
```

The installed package also provides direct commands:

```bash
gnsspy-download
gnsspy-visualize
gnsspy-convert-rinex
```

The orbit-comparison workflows are currently launched through the central `gnsspy` menu or imported from `gnsspy.workflows`.

---

## Command-line interfaces

### 1) Download GNSS data

Run either:

```bash
gnsspy-download
```

or select **Option 1** from the main menu.

The interactive downloader guides you through:

1. **NASA Earthdata login** — credentials are checked before the download begins. A `credentials.txt` file in the current working directory can be used to avoid re-entering them.
2. **Date selection** — one day or an inclusive date range. Common formats such as `YYYY-MM-DD`, `DD-MM-YYYY`, slash-separated and dot-separated dates are accepted.
3. **Station selection** — comma-separated station codes such as `MATE, ANKR, ISTA`. Use `BRDC` when the task requires only a global merged broadcast file.
4. **RINEX version** — version 2 or 3. The requested version is tried first; the downloader can also test the alternative archive format when availability differs by period.
5. **File selection** — any combination of:

   * observation files;
   * station navigation files;
   * merged BRDC navigation files;
   * SP3 precise orbits and CLK clock products;
   * IONEX ionosphere products.
6. **Analysis centre** for SP3 and CLK products:

   * `CODE` — Center for Orbit Determination in Europe;
   * `GFZ` — GFZ German Research Centre for Geosciences;
   * `IGS` — International GNSS Service combination;
   * `WUM` — Wuhan University multi-GNSS products;
   * `MIT` — Massachusetts Institute of Technology products.
7. **Output directory** — use the configured `data/` directory or provide another location.

For SP3 interpolation, GNSSpy downloads the **day before**, the **target day or range**, and the **day after**. The selected centre is used in strict mode for the whole interval; the downloader does not silently mix products from different centres.

Files are organised into product-specific subdirectories such as:

```text
<output>/observation/
<output>/navigation/
<output>/brdc/
<output>/sp3/
<output>/clk/
<output>/ionosphere/
```

A per-file success or failure message is printed during the run, followed by a summary report.

---

### 2) Visualise GNSS data

Run either:

```bash
gnsspy-visualize
```

or select **Option 2** from the main menu.

The visualiser can use an existing data directory or trigger the downloader. It produces interactive HTML output with Plotly.

| # | Plot                      | Required input      | Description                                                |
| - | ------------------------- | ------------------- | ---------------------------------------------------------- |
| 1 | **Skyplot**               | Observation + orbit | Polar view of satellite tracks, optionally coloured by SNR |
| 2 | **Azimuth–Elevation**     | Observation + orbit | Azimuth and elevation through time                         |
| 3 | **Elevation Time Series** | Observation + orbit | Elevation history for the selected satellites              |
| 4 | **SNR Time Series**       | Observation         | Signal-to-noise ratio through time                         |
| 5 | **Bandplot / Visibility** | Observation         | Availability of observation bands and signals by satellite |
| 6 | **Groundtrack**           | Orbit               | Satellite ground tracks                                    |
| 7 | **All plots**             | Observation + orbit | Generates every available plot                             |

The system selector accepts:

```text
G = GPS
R = GLONASS
E = Galileo
C = BeiDou
I = IRNSS/NavIC
J = QZSS
S = SBAS
```

For GPS, GLONASS, Galileo and BeiDou visualisation, orbit-dependent plots normally use SP3 products. For IRNSS/NavIC and QZSS, the visualiser switches to broadcast navigation because these constellations are not generally included in the selected standard SP3 products.

Compressed observation files are expanded as needed. Hatanaka `.crx` or `.d` inputs are passed to `CRX2RNX` before reading.

HTML files are written to:

```text
<output>/analyses/
```

and opened in the default browser when processing finishes.

---

### 3) Orbit comparison — single epoch

Select **Option 3** from the main menu.

This workflow compares broadcast and precise satellite coordinates at one UTC epoch:

* **BRDC coordinates** are propagated from the selected broadcast ephemeris records.
* **SP3 coordinates** are obtained through GNSSpy polynomial interpolation, using adjacent-day products around the target day.

The workflow:

1. uses an existing directory or downloads navigation, BRDC, SP3 and CLK files;

2. discovers the available dates from the navigation files;

3. asks for a UTC time;

4. accepts flexible satellite filters such as:

   ```text
   all
   gps
   galileo
   beidou
   gps2-23-24
   galileo01:10
   beidou12-15
   g05,e12,c07
   gps,galileo
   ```

5. calculates ECEF coordinate differences `dX`, `dY`, `dZ` and the three-dimensional difference;

6. rejects non-finite results and differences above the current 100 m quality ceiling.

The current workflow evaluates GPS, Galileo and BeiDou broadcast ephemerides. Results are exported to:

```text
<output>/data/georinex_portable_YYYYMMDD_HHMMSS.xlsx
```

The spreadsheet contains BRDC and SP3 ECEF coordinates, component differences and the total three-dimensional difference for each retained satellite.

---

### 4) Orbit comparison — full-day time series

Select **Option 4** from the main menu.

This workflow extends the BRDC–SP3 comparison over a complete UTC day at a default **30-second interval**. SP3 coordinates are interpolated with the workflow's 16th-degree polynomial setting.

The same flexible satellite filters used by the single-epoch workflow are available. The current comparison covers GPS, Galileo and BeiDou.

Before export, the workflow applies several quality checks:

* unhealthy broadcast ephemeris records are excluded;
* epochs outside the current broadcast-ephemeris validity window are removed;
* coordinate or three-dimensional differences above 100 m are rejected;
* an additional per-satellite median-absolute-deviation filter removes isolated residual outliers.

Outputs include:

* one Excel file containing every retained satellite–epoch result;
* per-system three-dimensional RMS bar charts;
* system-wide satellite overlays for `dX`, `dY` and `dZ`;
* per-satellite BRDC and SP3 coordinate comparisons;
* per-satellite `dX`, `dY`, `dZ` and three-dimensional difference time series.

Files are saved under:

```text
<output>/data/timeseries_YYYY-MM-DD.xlsx
<output>/data/figures/
```

Figures are written as 300 DPI PNG files.

---

### 5) Convert RINEX observation files

Run either:

```bash
gnsspy-convert-rinex
```

or select **Option 5** from the main menu.

The interactive converter supports both directions:

```text
RINEX 2 -> RINEX 3.04
RINEX 3 -> RINEX 2.11
```

A source file can be supplied by:

1. pasting or dragging a local file path;
2. selecting a file discovered inside an existing directory;
3. downloading a plain RINEX 2 observation file from CDDIS for conversion to RINEX 3.

The converter engine reads ordinary observation files, gzip-compressed files and Unix-compress `.Z` files. Hatanaka `.d` and `.crx` files must be decompressed first.

When writing RINEX 2.11, the interactive tool retains the standard `G/R/E/S` group or the smaller `G/R` group. BeiDou, QZSS and IRNSS/NavIC observations cannot be represented by this RINEX 2.11 output mode and are therefore omitted.

#### Non-interactive converter

The converter also has an argument-based interface:

```bash
python -m gnsspy.io.rinex.converter \
    input_file.rnx \
    output_file.25o \
    --target 2.11 \
    --keep GRES
```

For the opposite direction:

```bash
python -m gnsspy.io.rinex.converter \
    input_file.25o \
    output_file.rnx \
    --target 3.04
```

Programmatic use is available through:

```python
from gnsspy.io.rinex.converter import convert_file

convert_file(
    "input_file.25o",
    "output_file.rnx",
    target_version=3.04,
)
```

---

## Python API

GNSSpy v3 can be used as a conventional Python library without the interactive interfaces.

### Main namespaces

```python
import gnsspy
import gnsspy.data_access
import gnsspy.io
import gnsspy.orbit
import gnsspy.atmosphere
import gnsspy.positioning
import gnsspy.quality
import gnsspy.geodesy
import gnsspy.visualization
import gnsspy.workflows

print(gnsspy.__version__)
```

### Read GNSS files

```python
from gnsspy.io.rinex.observation import read_obsFile
from gnsspy.io.rinex.navigation import read_navFile
from gnsspy.io.products.sp3 import read_sp3File
from gnsspy.io.products.clk import read_clockFile
from gnsspy.io.products.ionex import read_ionFile

observation = read_obsFile("station_file.rnx")
navigation = read_navFile("broadcast_navigation.rnx")
sp3 = read_sp3File("precise_orbit.sp3")
clock = read_clockFile("precise_clock.clk")
ionosphere = read_ionFile("ionosphere.inx")
```

The historical GNSSpy function names remain available, while the v3 namespaces also expose more explicit aliases such as `read_observation_file`, `read_navigation_file`, `read_sp3_file`, `read_clock_file` and `read_ionex_file`.

### Download data from Python

```python
from gnsspy.data_access import ObservationDownloader, NavigationDownloader

obs_downloader = ObservationDownloader(
    username="EARTHDATA_USERNAME",
    password="EARTHDATA_PASSWORD",
    output_dir="data",
)

obs_downloader.download_single(
    station="MATE",
    date="2025-11-02",
    rinex_version=3,
)

product_downloader = NavigationDownloader(
    username="EARTHDATA_USERNAME",
    password="EARTHDATA_PASSWORD",
    output_dir="data",
)

product_downloader.download_brdc_only(
    date="2025-11-02",
    rinex_version=3,
)
```

### Broadcast and precise orbits

```python
import datetime

from gnsspy.orbit.broadcast import calculate_orbit_from_nav
from gnsspy.orbit.precise import sp3_interp

broadcast = calculate_orbit_from_nav(
    navigation=navigation,
    t_start=datetime.datetime(2025, 11, 2, 0, 0, 0),
    t_end=datetime.datetime(2025, 11, 2, 23, 59, 59),
    interval=30,
    system_filter="E",
)

precise = sp3_interp(
    epoch=datetime.date(2025, 11, 2),
    interval=30,
    poly_degree=16,
    sp3_product="cod",
    clock_product="cod",
    data_dir="data",
)
```

`sp3_interp()` expects SP3 products for the previous, target and following days, together with the target-day clock product, under the corresponding `sp3/` and `clk/` directories.

### Atmosphere, positioning and diagnostics

```python
from gnsspy.atmosphere.troposphere import tropospheric_delay
from gnsspy.atmosphere.ionosphere import ionosphere_interp
from gnsspy.positioning.spp import spp
from gnsspy.quality.multipath import multipath
from gnsspy.quality.snr import standardize_snr
from gnsspy.visualization import (
    skyplot,
    azelplot,
    timelplot,
    bandplot,
    groundtrack,
)
```

---

## NASA Earthdata account

GNSSpy downloads observation and product files from the NASA CDDIS archive, which requires an Earthdata Login.

1. Create an account at [NASA Earthdata Login](https://urs.earthdata.nasa.gov/users/new).
2. Ensure that your account is authorised for CDDIS access.
3. Enter the credentials when the GNSSpy downloader requests them.

To avoid repeated prompts, create `credentials.txt` in the directory from which the command is run:

```text
username = your_username
password = your_password
```

The following two-line form is also accepted:

```text
your_username
your_password
```

The visualisation credential flow can optionally save credentials in the standard `~/.netrc` file. On Unix-like systems, GNSSpy writes that file with restricted permissions.

> **Security:** `credentials.txt` and `.netrc` contain sensitive information. Do not commit either file. The repository `.gitignore` excludes `credentials.txt`, but file permissions and repository history should still be checked before publishing changes.

---

## Project layout

```text
gnsspy/
├── pyproject.toml                   # Build metadata, dependencies and commands
├── requirements.txt                # Core runtime requirements
├── LICENSE                          # MIT licence
├── MANIFEST.in                      # Source-package inclusion rules
├── bin/                             # Source-tree RNXCMP executables and licence
├── docs/
│   ├── USER_MANUAL.md
│   ├── PACKAGE_STRUCTURE.md
│   ├── RELEASE_NOTES.md
│   └── PATCH_NOTES_v3_0_1.md
└── gnsspy/
    ├── __init__.py                  # Version and compatibility-level imports
    ├── __main__.py                  # python -m gnsspy
    ├── atmosphere/                  # Ionospheric and tropospheric corrections
    ├── bin/                         # Packaged CRX2RNX executables and licence
    ├── cli/                         # Main, download, visualisation and converter CLIs
    ├── core/                        # Shared core namespace
    ├── data/                        # Station and reference data
    ├── data_access/                 # Earthdata/CDDIS sessions and downloaders
    ├── geodesy/                     # Coordinate and projection routines
    ├── io/
    │   ├── products/                # SP3, CLK and IONEX readers
    │   └── rinex/                   # Observation/navigation readers and converter
    ├── orbit/                       # Broadcast, precise and comparison utilities
    ├── positioning/                 # SPP, adjustment and observation matching
    ├── quality/                     # SNR, multipath and visibility diagnostics
    ├── utils/                       # Dates, filenames, constants and interpolation
    ├── visualization/               # Plotly-based diagnostic figures
    └── workflows/                   # Single-epoch and daily BRDC–SP3 workflows
```

---

## Dependencies

### Core dependencies

| Package    | Used for                                    |
| ---------- | ------------------------------------------- |
| `numpy`    | Numerical arrays and GNSS calculations      |
| `pandas`   | Indexed observation, orbit and product data |
| `requests` | Authenticated CDDIS downloads               |
| `unlzw3`   | Unix-compress `.Z` decompression            |

### Optional dependency groups

| Group           | Packages                                                | Used for                                                  |
| --------------- | ------------------------------------------------------- | --------------------------------------------------------- |
| `visualization` | `matplotlib`, `plotly`, `scipy`                         | Interactive and static figures plus interpolation support |
| `products`      | `scipy`, `georinex`                                     | Precise-product and broadcast-navigation processing       |
| `workflows`     | `matplotlib`, `plotly`, `scipy`, `georinex`, `openpyxl` | Complete orbit-comparison workflows and Excel export      |
| `all`           | all optional packages above                             | Full GNSSpy v3 installation                               |

Install a group with, for example:

```bash
python -m pip install -e ".[workflows]"
```

---

## Documentation and release notes

The repository includes:

* [`docs/USER_MANUAL.md`](docs/USER_MANUAL.md) — public API and command overview;
* [`docs/PACKAGE_STRUCTURE.md`](docs/PACKAGE_STRUCTURE.md) — v3 namespace organisation;
* [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md) — major-version notes;
* [`docs/PATCH_NOTES_v3_0_1.md`](docs/PATCH_NOTES_v3_0_1.md) — fixes included in v3.0.1.

Version 3.0.1 includes packaging and stability corrections for date parsing, coordinate conversion, navigation-field parsing, multipath processing, CRX2RNX discovery, Earthdata credential handling, Plotly renderer behaviour and optional dependency management.

---

## Citation

If GNSSpy contributes to academic work, please cite the original GNSSpy publication:

> Işık, M. S., Özbey, V., Erol, S., & Tarı, E. (2021). *GNSSpy: Python Toolkit for GNSS Data*. 2021 IEEE International Geoscience and Remote Sensing Symposium (IGARSS), 8550–8553.

When using GNSSpy v3 specifically, also report the software version and repository, for example:

```text
GNSSpy v3.0.1, https://github.com/GNSSpy-Project/gnsspy
```

For Hatanaka compression and RNXCMP, cite:

> Hatanaka, Y. (2008). *A Compression Format and Tools for GNSS Observation Data*. Bulletin of the Geospatial Information Authority of Japan, 55, 21–30.

---

## License and third-party components

GNSSpy is distributed under the MIT License. See [LICENSE](LICENSE).

Third-party components include:

* **GNSSpy source code** — © Mustafa Serkan Işık and Volkan Özbey; distributed under the MIT License.
* **`CRX2RNX` and `crx2rnx.exe`** — RNXCMP software from the Geospatial Information Authority of Japan. The applicable licence is included at [`gnsspy/bin/RNX2CMP_LICENSE.txt`](gnsspy/bin/RNX2CMP_LICENSE.txt) and [`bin/RNX2CMP_LICENSE.txt`](bin/RNX2CMP_LICENSE.txt).

Use and redistribution of the bundled RNXCMP components must follow their accompanying licence terms.
