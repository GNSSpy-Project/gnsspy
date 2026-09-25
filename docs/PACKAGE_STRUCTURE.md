# GNSSpy 3.0.2 Package Structure

| Namespace | Purpose |
|---|---|
| `gnsspy.data_access` | Archive access and observation, navigation and product acquisition |
| `gnsspy.io` | RINEX readers, observation conversion and SP3/CLK/IONEX readers |
| `gnsspy.orbit` | Broadcast orbits, precise interpolation and orbit comparisons |
| `gnsspy.atmosphere` | Ionospheric and tropospheric calculations |
| `gnsspy.positioning` | Single-point positioning and observation/orbit matching |
| `gnsspy.quality` | Signal-strength, multipath and visibility diagnostics |
| `gnsspy.geodesy` | Coordinate and projection utilities |
| `gnsspy.visualization` | Cartopy/Plotly geographic maps and Plotly observation plots with optional PNG export |
| `gnsspy.cli` | Command-line interfaces |
| `gnsspy.workflows` | Single-epoch and daily orbit-comparison applications |
| `gnsspy.utils` | Time, filename and product-selection utilities |
| `gnsspy.data` | Station reference data |

`gnsspy/bin` contains CRX2RNX executables and their licence notice. The root `bin` directory provides a source-tree fallback. `tests` contains synthetic and optional external-data tests. `docs` contains the user manual and package reference.

## Visualisation internals

`groundtrack.py` and `ionosphere.py` provide backend-selecting public functions.
`_maps.py` validates inputs and prepares coordinates, gaps and native map grids
without a rendering dependency. `cartopy_backend.py` draws geographic static
maps; `plotly_maps.py` supplies explicit interactive alternatives.
`plotly_backend.py` retains the non-geographic plotting functions and the
explicit legacy Plotly ground-track entry point. The small public wrappers
import that optional backend only when called.

`gnsspy.cli.maps` implements `gnsspy-map` for local SP3/IONEX products.
`examples/plot_demo.py` and `examples/synthetic_data.py` provide reproducible
rendering checks and input generation. `tests/test_map_data.py` checks data
preparation and dispatch; `tests/test_map_rendering.py` checks available
renderers, CLI integration and non-geographic plots.
