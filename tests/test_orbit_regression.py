"""Deterministic broadcast-orbit regression tests."""
import json
from pathlib import Path

import numpy as np
import pytest

from gnsspy.orbit.comparison import compute_keplerian_xyz

CASES = json.loads((Path(__file__).parent / "orbit_regression_baseline.json").read_text())["cases"]


@pytest.mark.parametrize("case", CASES, ids=[case["label"] for case in CASES])
def test_original_keplerian_numerics_preserved(case):
    actual = compute_keplerian_xyz(case["ephemeris"], case["gps_tow"], case["system"])
    np.testing.assert_allclose(actual, case["expected_original_xyz_m"], rtol=0, atol=1e-7)
