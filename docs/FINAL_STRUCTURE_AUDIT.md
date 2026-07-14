# GNSSpy v3 Final Structure Audit

Generated: 20260629_114721

## Version

- `gnsspy.__version__`: `3.0.0`

## Expected directories

- `gnsspy`: OK
- `gnsspy/atmosphere`: OK
- `gnsspy/cli`: OK
- `gnsspy/core`: OK
- `gnsspy/data`: OK
- `gnsspy/data_access`: OK
- `gnsspy/geodesy`: OK
- `gnsspy/io`: OK
- `gnsspy/io/rinex`: OK
- `gnsspy/io/rinex/converter`: OK
- `gnsspy/io/products`: OK
- `gnsspy/orbit`: OK
- `gnsspy/positioning`: OK
- `gnsspy/quality`: OK
- `gnsspy/utils`: OK
- `gnsspy/visualization`: OK
- `gnsspy/workflows`: OK

## Forbidden legacy paths

- `main.py`: absent
- `tools`: absent
- `orbit_analysis`: absent
- `gnsspy/backend`: absent
- `gnsspy/position`: absent
- `gnsspy/io/readFile.py`: absent
- `gnsspy/io/rinex_converter`: absent

## Old references

- `fix_pass10b_interpolation_readfile.py:23`
  ```python
  text = text.replace("import gnsspy.io.readFile as readFile\n", "")
  ```
- `fix_pass10b_interpolation_readfile.py:25`
  ```python
  text = text.replace("import gnsspy.io.readFile as readFile", "")
  ```

## Result

FAILED

- Old-structure references remain in text/Python files.
