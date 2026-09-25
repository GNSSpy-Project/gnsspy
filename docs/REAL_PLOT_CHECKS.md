# GNSSpy 3.0.2 — real station download-to-plot checks

## What changed

The old `test_all_plots.py` exercises generated observations/orbits/IONEX files.
It is still useful for regression, but is NOT an archive-download or real-station
acceptance test. It now includes separate SNR codes for GPS, Galileo and BeiDou.

The new `run_real_plots.py` uses GNSSpy's actual observation, precise-product and
IONEX downloaders; native RINEX/SP3/IONEX readers; native SP3 interpolation; and
public plotting functions. It never replaces an unavailable real file with
synthetic observations, a fabricated orbit, or a generated TEC field.

Use the supplied **gnsspy-3.0.2-cartopy-refined.zip** and
**gnsspy-3.0.2-real-plot-tests.zip** together. The library is still version 3.0.2.
Installing only the revised test scripts does not fix the old plotting library.

## 1. Update the existing environment, without overwriting the previous checkout

Assuming both downloads are in ~/Downloads and the gnsspy302 environment from
our previous setup exists:

```bash
conda activate gnsspy302
mkdir -p "$HOME/software/gnsspy302_realcheck"
cd "$HOME/software/gnsspy302_realcheck"
unzip -n "$HOME/Downloads/gnsspy-3.0.2-cartopy-refined.zip"
unzip -n "$HOME/Downloads/gnsspy-3.0.2-real-plot-tests.zip"
cd gnsspy-3.0.2
python -m pip install -e ".[all,test]"
python -m pip check
cd ../gnsspy_plot_tests
python check_installation.py
```

The source directory must remain in place for an editable installation. Check
the printed GNSSpy import path, not only its unchanged 3.0.2 version.

For a new environment, see the environment creation command in README.md.

### Hatanaka conversion on macOS

GNSSpy searches PATH for CRX2RNX/crx2rnx before its bundled executable. The
bundled Unix executable in this archive is Linux ELF, not a macOS binary.
One way to install a platform-appropriate `crx2rnx` is:

```bash
python -m pip install hatanaka
command -v crx2rnx
```

The Hatanaka project's documented installation provides that original executable
alongside its Python interface. GNSSpy still calls its own `crx2rnx()` wrapper;
this is not a silent alternative conversion route inside the runner. Installation
of Hatanaka/macOS conversion was not tested in the current runtime.

## 2. First real run: download and plot

The default example is **ISTA, 11 February 2025**. This is a requested test case,
not a claim that archive access or file availability has already been verified.
The station's long identifier is resolved by GNSSpy's existing station table.
An unavailable station/date remains a failure; another station is not substituted.

```bash
python run_real_plots.py \
  --station ISTA --date 2025-02-11 \
  --data-dir "$PWD/real_data/ISTA_20250211" \
  --output "$PWD/results_ISTA_first" \
  --systems G E C \
  --backend both \
  --with-cli \
  --require-download
```

`--require-download` is specifically for testing network retrieval. It fails
when an input was already cached, including when a native product selector finds
an existing file elsewhere in its local search. It never deletes your cache.
For a second run, omit it, or choose an empty data directory when intentionally
testing downloads again. Downloading only an HTTP response is not the final
acceptance criterion: the all-stage run must also parse and plot the products.

By default, the real runner requests an observation file, one same-day SP3
product and one same-day IONEX GIM. SP3 product/solution selection remains
`auto`; use `--center CODE` to constrain the centre. Use `--systems auto` to plot
whatever constellations are actually observed, instead of requiring G/E/C.
The runner does not silently discard an explicitly requested absent constellation.

### Credentials

CDDIS HTTPS uses NASA Earthdata authentication. The runner reads the standard
`urs.earthdata.nasa.gov` entry in ~/.netrc, or EARTHDATA_USERNAME and
EARTHDATA_PASSWORD, or prompts in an interactive terminal. The password prompt
is hidden; passwords are not written to the result JSON or scripts. Do not send
credentials in chat. Protect an existing ~/.netrc with `chmod 600 ~/.netrc`.

`--no-prompt` makes unattended runs use only environment/.netrc. Without usable
credentials it may receive an authentication error; this is not a plotting failure.
Access/authorisation failures, archive 404s, missing software and rendering failures
are recorded separately in stage logs. A generic native observation error is
augmented with the actual attempted transfer errors.

### Sampling

The full observation file is read. For the initial plot gallery, the default
`--plot-step 300` retains exact five-minute epochs without averaging. Source
values are unchanged. To check every native observation epoch, use:

```bash
python run_real_plots.py \
  --station ISTA --date 2025-02-11 \
  --data-dir "$PWD/real_data/ISTA_20250211" \
  --output "$PWD/results_ISTA_native" \
  --offline --plot-step 0 --backend both
```

The daily IONEX maps are independent of the station. Station RINEX observations
are not used to estimate the plotted global TEC field. IONEX is read in native
TECU, with exact requested map epochs; there is no added interpolation or exponent
rescaling. The single-map time is 12 UTC; panels are 00,04,08,12,16,20 UTC.
An absent map epoch or RMS block is reported, not invented.

## 3. Repeat only plotting, without downloading GNSS products again

```bash
python run_real_plots.py \
  --stage plot \
  --station ISTA --date 2025-02-11 \
  --data-dir "$PWD/real_data/ISTA_20250211" \
  --output "$PWD/results_ISTA_repeat" \
  --systems G E C --per-system --backend both --with-cli
```

`--stage plot` implies offline GNSS-product acquisition. Cartopy may still fetch
missing Natural Earth basemaps. Add `--no-features` for a run without those
feature downloads. It does not remove the requirement for Cartopy itself.
Use `prepare_cartopy_cache.py` from the previous kit to prepare the feature cache.

The `--per-system` flag repeats observation plots separately for each requested,
available constellation as well as the mixed-constellation plot.

### Focus on the auto-SNR problems

```bash
python run_real_plots.py \
  --stage plot --station ISTA --date 2025-02-11 \
  --data-dir "$PWD/real_data/ISTA_20250211" \
  --output "$PWD/results_ISTA_auto_SNR" \
  --systems G E C --per-system --backend plotly \
  --only skyplot_snr azel_snr snr_time elevation_snr visibility_snr explicit_snr
```

### Focus on IONEX maps

```bash
python run_real_plots.py \
  --stage plot --station ISTA --date 2025-02-11 \
  --data-dir "$PWD/real_data/ISTA_20250211" \
  --output "$PWD/results_ISTA_ionosphere" \
  --backend both --only tec tec_panels tec_regional rms rms_panels
```

The runner still checks the common input-reading stages when `--only` limits
plot selections. A failing observation stage does not prevent an independently
available IONEX map from being attempted.

## 4. Native observation-plot behaviour

The following are separate selections, not interchangeable meanings of auto:

- `system='auto'` selects all constellations present in the observations;
- `sv_list='auto'` selects all available satellites in those constellations;
- `snr_code='auto'` selects a native measured S-code per satellite;
- `color_mode='auto'` means SNR colouring, not an unlabelled switch to elevation;
- `sp3_product='auto'` selects an orbit product, not an observation signal.

**Auto-SNR policy:** select the code with the largest number of finite positive
samples for that satellite over the selected observation span. Resolve ties by
a deterministic constellation priority, then lexical order. NaN, infinity and
nonpositive values are excluded; SYSTEM/SSI/LLI are not SNR measurements. RINEX 2
S1/S2 and RINEX 3 codes such as S1C/S1X/S2I are recognised. Missing epochs are not
filled from a different code. Selection is fixed for the given satellite/span.
A different time subset can legitimately produce a different selection.

Different satellites may therefore use different signals. The actual code is
included in legends, hover labels and `fig.layout.meta['snr_selection']`. Use
an explicit code to compare the same signal; auto does not assert that different
codes represent an equivalent physical signal. An explicit unavailable/all-empty
code raises an error rather than silently selecting another one.

```python
from gnsspy.visualization import skyplot, time_elevation_plot, bandplot

# station and orbit are already read/prepared GNSSpy objects.
fig = skyplot(station, orbit, system='auto', sv_list='auto', snr_code='auto')
print(fig.layout.meta['snr_selection'])

# Strict native signal on a selected satellite; substitute a code actually
# listed for this satellite in signal_selection.csv.
fig = skyplot(station, orbit, system='G', sv_list=['G01'], snr_code='S1C')

# Elevation on the ordinate, measured SNR on the colour scale.
fig = time_elevation_plot(station, orbit, system='E', color_mode='snr')
fig = bandplot(station, system='auto', color_mode='snr')
```

A mapping can also be passed to `snr_code`, for example
`{'G':'S1C','E':'S1X','C':'S2I'}`. These codes are examples, not a claim about
ISTA's actual receiver observations on this date. In the command-line runner,
use `--snr-code '{"G":"S1C","E":"S1X","C":"S2I"}'` after checking availability.

`time_elevation_plot()` now defaults to elevation. `snr_time_series_plot()`
defaults to SNR. The legacy `timelplot()` still defaults to SNR. None of these
silently smooths measurements. Geometry uses actual matched epoch coordinates;
no velocity or satellite clock product is needed solely to draw an azimuth or
elevation. It uses GNSSpy's existing ECEF geometry formula.

One shared colour scale is used for all satellites in a figure. The default
uses the full finite plotted range rather than always clipping at 15–50. Pass
`color_range=(low, high)` for a fixed cross-figure range. A grey geometry track
can exist through missing SNR epochs; there is no coloured SNR marker there.
Lines break at missing data and time gaps; SNR values remain raw.

Time labels come from the RINEX header in the runner. GPST is not labelled UTC.
If the header time system is absent, station-only plots use UNKNOWN and geometry
will reject a mismatch with GPS-labelled SP3. Use `--obs-time-system GPS` only
when you have established that convention. It asserts a label, not a conversion.
SNR units similarly use the header; absent units are labelled RINEX units.

## 5. Real broadcast–SP3 plots and clock-download test

The main plotting run does not need CLK or broadcast navigation. To test those
retrieval paths and all five original orbit-comparison plot functions:

```bash
python run_real_plots.py \
  --station ISTA --date 2025-02-11 \
  --data-dir "$PWD/real_data/ISTA_20250211" \
  --output "$PWD/results_ISTA_extended" \
  --systems G E C --backend both --with-cli \
  --with-clk --orbit-comparison
```

This downloads/reads BRDC and CLK, computes broadcast-versus-SP3 tables through
the existing package routine, and calls `plot_satellite`, `plot_system_rms`,
`plot_all_satellites_overlay`, `plot_all_coords_compare` and `plot_all_diffs`.
Those functions retain Matplotlib. **No residuals are fabricated.** Existing
broadcast age limits, hard difference limits and MAD filtering are unchanged;
their messages remain in the compute-stage log. This is not an independent
validation of orbit accuracy. Broadcast comparisons remain limited to G/E/C.
The number of figures depends on actual satellite/product coverage.

## 6. Explicit existing files

```bash
python run_real_plots.py \
  --offline --station ISTA --date 2025-02-11 \
  --obs /absolute/path/to/your_observation.crx.gz \
  --sp3 /absolute/path/to/your_orbit.SP3.gz \
  --ionex /absolute/path/to/your_ionosphere.INX.gz \
  --output "$PWD/results_explicit_files" --backend both
```

Use your exact original paths; there is no filename-renaming requirement.
`--sp3` accepts multiple paths to supply matching neighbouring-day support.
Without neighbours, the native interpolator can use one-sided edge fits and
reports that warning. The runner does not turn that warning into a claim of
precise orbit accuracy. Native interpolation excludes unsupported epochs.

## 7. Outputs and acceptance

- `report.json`: stage outcomes, original source paths, SHA-256, bytes, download
  versus reuse, requested parameters and warnings. Hashes identify local bytes;
  they are not a comparison with an archive-provided checksum.
- `index.html`: links to figures, sidecar metadata and logs.
- `signal_inventory_full_day.csv`: finite positive count for every native
  S-code and satellite before plot thinning.
- `signal_selection.csv`: actual per-satellite code used on the plot grid.
- `selected_snr_samples.csv`: raw selected values, including missing epochs.
- `geometry_coverage.csv`: observation count, exact orbit matches and above-mask
  count for each satellite. Satellites with no SP3 matches fail the coverage stage.
- `plots/`: HTML observation plots, chosen-backend maps and optional orbit PNGs.
- `logs/`: one log per acquisition/read/plot stage. Individual failures do not
  suppress unrelated plots.

`failed: 0`, `blocked: 0` and `real_data_acceptance_passed: true` mean the requested
real-input pipeline stages passed. They do not certify positioning/orbit accuracy
or visual publication quality. A download-only run never earns full plot
acceptance. RMS absence and missing exact requested map epochs are explicitly
reported. A requested constellation absent from the RINEX/SP3 product is not
reported as a full success. A labelled synthetic integration fixture cannot
earn real-data acceptance even when its internal pipeline checks pass.

The runner verifies numeric SNR marker/ordinate values against the selected
RINEX records, not only whether an HTML file exists. Inspect actual maps for
colourbar placement, label overlap, basemap downloads and projection appearance.
A downloaded invalid/unsupported RINEX file remains a reading failure; the script
does not repair or silently replace scientific inputs.

## 8. Regression checks and limits of current verification

```bash
# In the package source directory:
python -m pytest tests/test_plot_auto.py -q
python -m pytest -q -ra

# In gnsspy_plot_tests:
python -m pytest tests/test_real_runner.py -q
python test_all_plots.py --backend both --systems G E C --with-cli
```

See VALIDATION.md for actual local results. Live authenticated CDDIS downloads
and Cartopy rendering were not verified here. A genuine native-download attempt
failed at the network stage in this runtime. Synthetic native-file checks and
mocked transport tests are recorded separately and are not presented as real
station validation. Original RINEX parser limitations remain in place.

## Public documentation consulted

- NASA Earthdata CDDIS daily data:
  https://www.earthdata.nasa.gov/data/space-geodesy-techniques/gnss/daily-30-second-data-product
- Earthdata Python authentication:
  https://urs.earthdata.nasa.gov/documentation/for_users/data_access/python
- Plotly shared colour axes:
  https://plotly.com/python/colorscales/
- Hatanaka platform executables:
  https://github.com/valgur/hatanaka

These sources describe archive/software conventions, not successful execution
of this particular ISTA run.
