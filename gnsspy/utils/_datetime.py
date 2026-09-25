"""Datetime calculations that do not depend on pandas' storage resolution."""
from __future__ import annotations

import numpy as np
import pandas as pd


def elapsed_seconds(values, reference=None):
    """Return seconds from *reference* for datetime-like values.

    Pandas datetime indexes may use second, millisecond, microsecond or
    nanosecond storage. Timedelta arithmetic keeps this conversion independent
    of that internal unit.
    """
    index = pd.DatetimeIndex(values)
    if len(index) == 0:
        return np.empty(0, dtype=float)
    origin = index[0] if reference is None else pd.Timestamp(reference)
    return np.asarray((index - origin).total_seconds(), dtype=float)


def interval_seconds(values):
    """Return consecutive datetime intervals in seconds."""
    index = pd.DatetimeIndex(values)
    if len(index) < 2:
        return np.empty(0, dtype=float)
    return np.asarray((index[1:] - index[:-1]).total_seconds(), dtype=float)


__all__ = ["elapsed_seconds", "interval_seconds"]
