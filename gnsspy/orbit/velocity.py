"""Satellite velocity utilities for GNSSpy v3.

Velocity estimates are currently produced inside existing orbit and
product-reading workflows. This module is reserved for the consolidated
velocity API that will be introduced after the structural refactor.

Current behaviour:
- BRDC-derived orbit workflows can include velocity columns.
- SP3 readers/interpolation workflows can derive velocity estimates.
- A dedicated Remondi-style implementation should be added here only
  after the formula and reference are explicitly documented and tested.
"""

__all__ = []
