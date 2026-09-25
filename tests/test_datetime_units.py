"""Regression tests for pandas datetime storage-resolution independence."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from conftest import PRECISE_DAY
from gnsspy.atmosphere.ionosphere import interpolate_vtec
from gnsspy.io.products.ionex import IonexDataset
from gnsspy.io.products.sp3 import read_sp3File
from gnsspy.orbit import precise
from gnsspy.utils._datetime import elapsed_seconds, interval_seconds
from gnsspy.visualization._observations import gap_seconds


def test_datetime_helpers_accept_all_supported_numpy_units():
    expected = np.array([0.0, 300.0, 900.0])
    labels = [
        "2025-02-11T00:00:00",
        "2025-02-11T00:05:00",
        "2025-02-11T00:15:00",
    ]
    for unit in ("s", "ms", "us", "ns"):
        epochs = pd.DatetimeIndex(np.asarray(labels, dtype=f"datetime64[{unit}]"))
        np.testing.assert_array_equal(elapsed_seconds(epochs), expected)
        np.testing.assert_array_equal(interval_seconds(epochs), np.diff(expected))


def test_vtec_interpolation_accepts_microsecond_epochs():
    epochs = pd.DatetimeIndex(np.asarray([
        "2025-02-11T00:00:00",
        "2025-02-11T01:00:00",
    ], dtype="datetime64[us]"))
    values = np.asarray([[[10.0]], [[20.0]]])
    data = IonexDataset(
        epochs=epochs,
        latitudes=np.asarray([0.0]),
        longitudes=np.asarray([0.0]),
        tec=values,
        raw_tec=values.copy(),
        source=Path("unit-test.inx"),
        height_km=450.0,
        metadata={"interval_seconds": 3600},
    )
    requested = pd.DatetimeIndex(np.asarray([
        "2025-02-11T00:00:00",
        "2025-02-11T00:30:00",
        "2025-02-11T01:00:00",
    ], dtype="datetime64[us]"))
    np.testing.assert_allclose(
        interpolate_vtec(data, 0.0, 0.0, requested),
        [10.0, 15.0, 20.0],
    )


def test_observation_gap_detection_accepts_microsecond_epochs():
    times = pd.DatetimeIndex(np.asarray([
        "2025-02-11T00:00:00",
        "2025-02-11T00:00:30",
        "2025-02-11T00:01:00",
    ], dtype="datetime64[us]"))
    assert gap_seconds(SimpleNamespace(interval=None), times, None) == 45.0


def test_sp3_interpolation_accepts_microsecond_epoch_index(
        write_product, tmp_path, monkeypatch):
    path = write_product(interval=300)
    native_reader = read_sp3File

    def read_with_microsecond_index(*args, **kwargs):
        frame = native_reader(*args, **kwargs)
        epochs = frame.index.get_level_values("Epoch").to_numpy(
            dtype="datetime64[us]"
        )
        satellites = frame.index.get_level_values("SV")
        frame.index = pd.MultiIndex.from_arrays(
            [epochs, satellites], names=["Epoch", "SV"]
        )
        return frame

    monkeypatch.setattr(precise, "read_sp3File", read_with_microsecond_index)
    with pytest.warns(RuntimeWarning, match="edge fits"):
        result = precise.sp3_interp(
            PRECISE_DAY,
            interval=300,
            poly_degree=3,
            sp3_files=[path],
            clock_product=None,
            verbose=False,
        )
    assert result[["X", "Y", "Z"]].notna().all().all()
    assert result.attrs["input_intervals_seconds"][str(path)] == 300
