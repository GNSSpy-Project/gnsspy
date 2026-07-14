# GNSSpy v3.0.1 stabilisation patch

This patch focuses on bug fixes and packaging stability before preparing the full LaTeX user manual.

## Fixed

- Corrected `gnsspy.geodesy.coordinate.ell2cart()` to use the first eccentricity squared in the prime-vertical radius of curvature.
- Reworked `gnsspy.utils.date` with a shared `parse_date()` helper supporting ISO dates, legacy `DD-MM-YYYY` dates, slash/dot variants and `datetime` objects.
- Replaced the approximate day-of-year calculation with Python calendar-based day-of-year handling.
- Updated `BaseDownloader.parse_date()` and CLI date parsing to use the shared date parser.
- Improved `crx2rnx()` executable discovery: system PATH, package data under `gnsspy/bin`, and source-tree fallback are now searched.
- Added bundled CRX2RNX files under `gnsspy/bin` for package-data inclusion.
- Fixed RINEX navigation seconds parsing, which previously read only the first character of the seconds field.
- Fixed `Multipath2` arc de-meaning to use the `Multipath2` series rather than `Multipath1`.
- Removed import-time `pip install` calls from orbit-comparison modules and workflows. Optional dependencies now raise an informative `ImportError`.
- Avoided forcing the global Plotly renderer at import time.
- Improved Earthdata password prompting in the download CLI using `getpass`.
- Updated credential loading to use Python's `netrc` parser with a legacy fallback.
- Added a `.gitignore` for cache files, build artefacts, credentials and local data/output directories.
- Included `gnsspy.workflows` in package discovery and added explicit project dependencies / optional dependency groups in `pyproject.toml`.

## Version

- Package version changed from `3.0.0` to `3.0.1`.
