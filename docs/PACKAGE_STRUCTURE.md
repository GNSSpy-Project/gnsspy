# GNSSpy v3 Package Structure

GNSSpy v3 is organised by scientific function.

```text
gnsspy/
├── atmosphere/       # ionospheric and tropospheric corrections
├── cli/              # command-line interfaces
├── core/             # shared core utilities
├── data_access/      # authenticated archive access and downloads
├── data/             # station/reference data
├── geodesy/          # coordinate and projection utilities
├── io/               # RINEX readers, converters and product readers
├── orbit/            # broadcast orbits, SP3 interpolation and orbit comparison
├── positioning/      # SPP and observation/orbit matching utilities
├── quality/          # SNR and multipath diagnostics
├── visualization/    # Plotly-based diagnostic plots
└── workflows/        # reproducible analysis workflows
```

The public API is intended to follow this structure.
