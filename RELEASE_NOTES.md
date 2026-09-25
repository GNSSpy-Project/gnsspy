# GNSSpy 3.0.2 refined support build

## Added

- Regional IONEX TEC/RMS maps automatically show longitude and latitude labels
  when an explicit `extent=(west, east, south, north)` is supplied. Global maps
  remain unlabelled by default. Use `coordinate_labels=True` or `False` to
  override the automatic behaviour.
- `skyplot`, `azelplot`, `timelplot`, its named aliases, and `bandplot` accept
  `png_path` and `png_scale`. `png_path=True` writes a same-stem PNG beside the
  normal HTML output; a `.png` path selects another destination.
- `gnsspy-visualize` can request PNG copies of its observation plots.
- The `plotly-png` optional dependency group installs modern Plotly and Kaleido.

## Compatibility retained

- pandas 2.3 and pandas 3 datetime resolutions.
- Cartopy static maps, including Equal Earth projection support.
- Plotly/AUTO/SNR signal selection and HTML output.

## Examples

```python
from gnsspy.visualization import ionosphere_map, skyplot

ionosphere_map(
    gim,
    epoch=gim.epochs[0],
    projection="platecarree",
    extent=(20, 45, 30, 50),
    save_path="tec_regional.png",
)

skyplot(
    station,
    orbit,
    save_path="skyplot.html",
    png_path=True,
    png_scale=2,
)
```

Plotly PNG export requires Kaleido and a compatible Chrome/Chromium browser.
Run `plotly_get_chrome` if the browser is not already installed.
