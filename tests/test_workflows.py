"""Integration tests with analytically generated, synthetic SP3 substitutes.

The real interpolation entry point is replaced at the product boundary.
These tests do NOT validate archive downloads or real SP3 interpolation.
"""
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from conftest import elements, kepler_record, state_record
from gnsspy.orbit import comparison as utils
from gnsspy.workflows.orbit_compare_single import compare_orbits, integrated_main
from gnsspy.workflows.brdc_sp3_timeseries import compute_day_timeseries

START = datetime(2025, 11, 2)
SVS = ("G01", "E11", "C11")
DELTA = np.array([1., -2., .5])


def circular_parameters(system):
    radius = {"G":26560000.,"E":29600000.,"C":27900000.}[system]
    mu = 3.986005e14 if system == "G" else 3.986004418e14
    rotation = 7.2921150e-5 if system == "C" else 7.2921151467e-5
    return radius, np.sqrt(mu/radius**3), rotation


def analytical_xyz(system, seconds):
    """Independent circular-orbit trigonometry, not the GNSSpy propagator."""
    radius, n, rotation = circular_parameters(system)
    phase = 1.1 + n*seconds
    node = -.2 + (-8e-9-rotation)*seconds
    inclination = .95
    return np.array([
        radius*(np.cos(phase)*np.cos(node)-np.sin(phase)*np.cos(inclination)*np.sin(node)),
        radius*(np.cos(phase)*np.sin(node)+np.sin(phase)*np.cos(inclination)*np.cos(node)),
        radius*np.sin(phase)*np.sin(inclination),
    ])


def synthetic_navigation(write_nav, *, unhealthy_extra=False):
    text = state_record(version="3.05")
    for sv in SVS + (("G02",) if unhealthy_extra else ()):
        system = sv[0]
        radius, n, rotation = circular_parameters(system)
        for hours in range(0,25,2):
            absolute_seconds = 3600*hours
            gps_epoch = START + timedelta(seconds=absolute_seconds)
            native_epoch = gps_epoch - timedelta(seconds=14 if system == "C" else 0)
            values = elements(system,native_epoch,health=1 if sv == "G02" else 0)
            toe = values[11]
            wrap = lambda angle: (angle+np.pi) % (2*np.pi)-np.pi

            values[4:11] = [0.,0.,wrap(1.1+n*absolute_seconds),0.,0.,0.,np.sqrt(radius)]
            values[12:20] = [0.,wrap(-.2+(-8e-9-rotation)*absolute_seconds+rotation*toe),
                             0.,.95,0.,0.,-8e-9,0.]
            text += kepler_record(sv,native_epoch,version="3.05",values=values)
    return write_nav(text,version="3.05")


def synthetic_precise(epochs, satellites=SVS):
    rows=[]
    for epoch in epochs:
        seconds = (epoch-START).total_seconds()
        for sv in satellites:
            xyz = analytical_xyz(sv[0],seconds) - DELTA
            rows.append(dict(Epoch=epoch,SV=sv,X=xyz[0],Y=xyz[1],Z=xyz[2],Vx=0.,Vy=0.,Vz=0.))
    return pd.DataFrame(rows).set_index(["Epoch","SV"]).sort_index()


def test_full_day_three_constellations_30_seconds(write_nav,monkeypatch):
    nav = synthetic_navigation(write_nav)
    epochs = pd.date_range(START,periods=2880,freq="30s")
    precise = synthetic_precise(epochs)
    monkeypatch.setattr(utils,"run_sp3_interp",lambda *args,**kwargs: precise)
    results = compute_day_timeseries([nav],[],[],START.date())
    assert set(results) == set(SVS)
    for sv in SVS:
        frame = results[sv]
        assert len(frame) == 2880
        assert (frame["epoch"].iloc[0],frame["epoch"].iloc[-1]) == (epochs[0],epochs[-1])
        np.testing.assert_allclose(frame[["dx","dy","dz"]].values,
                                   np.tile(DELTA,(2880,1)),rtol=0,atol=.002)
        np.testing.assert_allclose(frame.d3d.values,np.linalg.norm(DELTA),rtol=0,atol=.002)


def test_single_epoch_native_reader_health_and_excel_output(write_nav,monkeypatch,tmp_path):
    pytest.importorskip("openpyxl")
    nav = synthetic_navigation(write_nav,unhealthy_extra=True)
    target = START+timedelta(hours=12)
    precise = synthetic_precise([target],SVS+("G02",))
    monkeypatch.setattr(utils,"run_sp3_interp",lambda *args,**kwargs: precise)
    output = tmp_path/"new_output_directory"
    result = compare_orbits([nav],[],[],target,save_dir=output)
    assert set(result.PRN) == set(SVS) and "G02" not in set(result.PRN)
    np.testing.assert_allclose(result[["Diff_X (m)","Diff_Y (m)","Diff_Z (m)"]].values,
                               np.tile(DELTA,(3,1)),rtol=0,atol=.002)
    files = list(output.glob("gnsspy_orbit_comparison_*.xlsx"))
    assert len(files) == 1
    assert set(pd.read_excel(files[0]).PRN) == set(SVS)


def test_single_epoch_satellite_filter(write_nav,monkeypatch,tmp_path):
    pytest.importorskip("openpyxl")
    nav = synthetic_navigation(write_nav)
    target = START+timedelta(hours=2)
    monkeypatch.setattr(utils,"run_sp3_interp",lambda *args,**kwargs: synthetic_precise([target]))
    result = compare_orbits([nav],[],[],target,save_dir=tmp_path,sv_filter=utils.parse_sv_filter("galileo"))
    assert list(result.PRN) == ["E11"]


def test_interactive_entry_no_undefined_gnsspy_name(tmp_path):

    assert integrated_main(out_dir=str(tmp_path),skip_download=True) is None


def test_missing_navigation_inputs_have_clear_errors():
    with pytest.raises(ValueError,match="navigation file"):
        compare_orbits([],[],[],START)
    with pytest.raises(ValueError,match="navigation file"):
        compute_day_timeseries([],[],[],START.date())


def test_reader_and_workflows_with_both_external_imports_blocked(write_nav):
    nav = write_nav()
    script = r'''
import importlib.abc
import sys
class BlockExternalRinex(importlib.abc.MetaPathFinder):
    def find_spec(self,fullname,path=None,target=None):
        if fullname.split(".")[0] in {"georinex","xarray"}:
            raise AssertionError("Forbidden import: "+fullname)
sys.meta_path.insert(0,BlockExternalRinex())
import gnsspy
from gnsspy.workflows.orbit_compare_single import compare_orbits
from gnsspy.workflows.brdc_sp3_timeseries import compute_day_timeseries
from gnsspy.orbit.comparison import build_ephemeris_table
assert len(gnsspy.read_navFile(sys.argv[1],verbose=False).navigation) == 1
assert "G01" in build_ephemeris_table([sys.argv[1]])
assert not any(m.split(".")[0] in {"georinex","xarray"} for m in sys.modules)
print("native imports and navigation computation succeeded")
'''
    done = subprocess.run([sys.executable,"-c",script,str(nav)],
                          cwd=Path(__file__).resolve().parents[1],text=True,
                          capture_output=True,timeout=30)
    assert done.returncode == 0, done.stdout+done.stderr
    assert "succeeded" in done.stdout
