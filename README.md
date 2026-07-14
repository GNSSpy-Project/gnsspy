# GNSSpy v3

GNSSpy v3 is an open-source Python library for RINEX conversion, multi-GNSS data handling, orbit analysis, atmospheric corrections and diagnostic visualization.

The package is organised by scientific function. Data access, RINEX and product I/O, orbit computation, atmospheric corrections, positioning support, quality diagnostics and visualization are exposed through separate namespaces.

## Main capabilities

- RINEX 2<->3 observation-file conversion
- Authenticated GNSS data acquisition
- RINEX observation and navigation reading
- SP3, CLK and IONEX product handling
- Broadcast-orbit computation
- SP3 interpolation
- Atmospheric corrections
- SPP-related utilities
- SNR, multipath and visibility diagnostics
- Plotly-based visualization tools
- BRDC-SP3 orbit-comparison workflows

## Main namespaces

```text
gnsspy.data_access      # authenticated archive access and downloads
gnsspy.io               # RINEX readers, converter and product readers
gnsspy.orbit            # broadcast orbits, SP3 interpolation and orbit comparison
gnsspy.atmosphere       # ionospheric and tropospheric corrections
gnsspy.positioning      # SPP and observation/orbit matching utilities
gnsspy.quality          # SNR and multipath diagnostics
gnsspy.geodesy          # coordinate and projection utilities
gnsspy.visualization    # Plotly-based diagnostic plots
gnsspy.cli              # command-line interfaces
gnsspy.workflows        # reproducible analysis workflows
```

## Command-line use

From the project root:

```bash
python -m gnsspy
```

After installation:

```bash
gnsspy
```

## Documentation

A practical user manual will be maintained in `docs/USER_MANUAL.md`.
