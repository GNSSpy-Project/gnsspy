# Plotting examples — GNSSpy 3.0.2

Run from the extracted **package root**, not from inside `examples/`.
All example GNSS and TEC data are synthetic. No archive credentials or GNSS
downloads are needed. Cartopy basemap features may download on first use.

## Install and run both renderers

```bash
python -m pip install -e ".[visualization,test]"
python examples/plot_demo.py --backend both --non-geographic
```

The default output directory is `plot_demo_output/`. Six Cartopy PNG maps and
six Plotly HTML maps are requested, plus five non-geographic HTML plots with
`--non-geographic`. `demo_report.json` records each output's success, size or
error. A failed plot gives a non-zero exit code; no backend is silently skipped.
Use `--output-dir /path/to/results` to change the destination.

## Cartopy alone (the default)

```bash
python examples/plot_demo.py
```

With no basemap cache/network:

```bash
python examples/plot_demo.py --no-features
```

This still requires Cartopy. `--no-features` disables basemap geometry only.
To use an installed Matplotlib colour map instead of cmcrameri:

```bash
python examples/plot_demo.py --no-features --cmap viridis
```

## Plotly alone

```bash
python examples/plot_demo.py --backend plotly --non-geographic
```

The HTML includes plotly.js, but geographic basemap topology may need browser
internet access. File creation and visual browser inspection are separate checks.

## What to inspect

| Output stem | Expected check |
|---|---|
| `groundtracks` | Seven G/E/C satellites; no false connections across the dateline or deliberate G03/E11 gaps |
| `groundtracks_regional` | PlateCarree regional extent, same underlying satellite positions |
| `tec_12UTC` | Single synthetic native TEC map, 0–60 TECU display limits; missing region not treated as zero |
| `tec_regional` | Regional PlateCarree TEC view; Cartopy longitude/latitude labels are automatic |
| `tec_4hour_panels` | Six panels at 00, 04, 08, 12, 16, 20 UTC; one common colour scale |
| `rms_12UTC` | Synthetic RMS values rather than the TEC array; appropriate TECU label |
| Non-geographic HTML | Skyplot, azimuth/elevation, elevation/time, SNR/time and visibility remain Plotly |

To save a PNG beside any non-geographic HTML figure in your own code, pass
`png_path=True`; pass a `.png` path for a different name. This needs the
`plotly-png` extra and Chrome/Chromium (`plotly_get_chrome` can install it).

Plotly IONEX maps are grid-point views; Cartopy maps show cell-based fields.
They should agree in coordinates and values, not be assumed pixel-identical.
The deliberately invalid E11 row produces an expected warning. The generated
orbit is an illustrative circular model, not a precise or broadcast solution.

## Generate local test inputs only

```bash
python examples/plot_demo.py --generate-only
```

This writes `plot_demo_output/data/SYNTHETIC_ORBIT.SP3` and
`plot_demo_output/data/SYNTHETIC_GIM.INX`. The SP3 stores kilometres and the
IONEX uses exponent -1 with missing-value sentinels. The plotting demo reads
both through GNSSpy's existing parsers before generating its geographic plots.
The station observations for non-geographic views are constructed in memory.

Test the installed command using these files:

```bash
gnsspy-map groundtrack plot_demo_output/data/SYNTHETIC_ORBIT.SP3 --system ALL --output check_tracks.png
gnsspy-map ionosphere plot_demo_output/data/SYNTHETIC_GIM.INX --hours 0 4 8 12 16 20 --output check_tec.png
```

## Automated checks

```bash
python -m pytest tests/test_map_data.py tests/test_map_rendering.py -q -ra
python -m pytest -q -ra
```

Actual Cartopy tests are explicitly skipped when Cartopy is absent. They use
`features=False` and mostly `cmap="viridis"` to avoid network/cache dependencies;
one test checks the default batlow_r palette when cmcrameri is installed.
Do not interpret a skipped rendering test as a pass. After installing the full
visualisation extra, no map-rendering tests should be skipped. Full-size
external-product tests can still skip unless their data directories are supplied.
