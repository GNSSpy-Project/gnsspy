# GNSSpy v3 User Manual

This manual describes the public GNSSpy v3 API and command-line workflows.

## 1. Installation

Recommended editable installation from the project root:

```bash
pip install -e .
```

Run the command-line interface with:

```bash
python -m gnsspy
```

or, after installation:

```bash
gnsspy
```

## 2. Main package structure

GNSSpy v3 is organised by function:

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
```

## 3. Data download

Use the data-access namespace for authenticated archive access:

```python
from gnsspy.data_access.observation import ObservationDownloader
from gnsspy.data_access.products import NavigationDownloader
```

## 4. RINEX conversion

Use the RINEX converter namespace:

```python
from gnsspy.io.rinex.converter import convert_file
```

## 5. Reading GNSS files

```python
from gnsspy.io.rinex.observation import read_obsFile
from gnsspy.io.rinex.navigation import read_navFile
from gnsspy.io.products.sp3 import read_sp3File
from gnsspy.io.products.clk import read_clockFile
from gnsspy.io.products.ionex import read_ionFile
```

## 6. Orbit computation and interpolation

```python
from gnsspy.orbit.broadcast import calculate_orbit_from_nav
from gnsspy.orbit.precise import sp3_interp
from gnsspy.orbit.comparison import compute_keplerian_xyz
```

## 7. Atmospheric corrections

```python
from gnsspy.atmosphere.troposphere import tropospheric_delay
from gnsspy.atmosphere.ionosphere import ionosphere_interp
```

## 8. Positioning and quality diagnostics

```python
from gnsspy.positioning.spp import spp
from gnsspy.positioning.observations import gnssDataframe
from gnsspy.quality.multipath import multipath
from gnsspy.quality.snr import standardize_snr
```

## 9. Visualization

```python
from gnsspy.visualization import skyplot, azelplot, timelplot, bandplot, groundtrack
```

## 10. Workflows

```python
from gnsspy.workflows.orbit_compare_single import integrated_main
from gnsspy.workflows.brdc_sp3_timeseries import main
```

Detailed executable examples will be added after the manuscript figures and validation examples are finalised.
