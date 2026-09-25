from datetime import datetime, timedelta
import gzip
import warnings

import numpy as np
import pandas as pd
import pytest

from gnsspy.orbit.comparison import (build_ephemeris_table, find_nearest_eph,
    find_latest_eph, ephemeris_age_seconds, compute_keplerian_xyz,
    datetime_to_gps_tow, discover_files, _is_healthy)
from conftest import elements, kepler_record, state_record


def test_native_table_plain_dict_and_field_mapping(write_nav):
    table = build_ephemeris_table([write_nav(kepler_record()+kepler_record("E11")+kepler_record("C11"))])
    assert set(table) == {"G01", "E11", "C11"}
    eph = table["E11"][0][1]
    assert isinstance(eph, dict) and eph["sqrtA"] == 5440
    assert eph["DataSrc"] == 513 and eph["SVclockDriftRate"] == 1.25e-20
    assert eph["TransTime"] == 60 and eph["_sv"] == "E11"
    assert eph["_source_line"] > 0


@pytest.mark.parametrize("system", ["G", "E", "C"])
@pytest.mark.parametrize("health", [1, 512, None])
def test_health_filter_preserved_for_all_comparison_systems(write_nav, system, health):
    text = kepler_record(system+"01")
    text += kepler_record(system+"02", values=elements(system, health=health))
    path = write_nav(text)
    assert set(build_ephemeris_table([path])) == {system+"01"}
    assert len(build_ephemeris_table([path], healthy_only=False)) == 2


def test_health_unknown_is_not_healthy():
    assert not _is_healthy({}, "G")
    assert not _is_healthy({"health": np.nan}, "E")
    assert _is_healthy({"SatH1": np.nan, "health": 0}, "C")
    assert not _is_healthy({"SatH1": 1, "health": 0}, "C")


def test_true_duplicates_removed_but_coincident_distinct_messages_preserved(write_nav):
    one = kepler_record("E11")
    alternate = kepler_record("E11", values=elements("E", overrides={20: 258}))
    changed_clock = kepler_record("E11", values=elements("E", overrides={0: .001}))
    a = write_nav(one+alternate+one+changed_clock, name="a.rnx")
    b = write_nav(one, name="b.rnx")
    table = build_ephemeris_table([a,b])
    assert list(table) == ["E11"]
    assert len(table["E11"]) == 3
    reverse = build_ephemeris_table([b,a])
    assert [(e["DataSrc"], e["SVclockBias"]) for _, e in table["E11"]] == [
            (e["DataSrc"], e["SVclockBias"]) for _, e in reverse["E11"]]


def test_same_toe_in_different_weeks_not_deduplicated_or_selected_as_current(write_nav):
    old = datetime(2025,10,26)
    current = datetime(2025,11,2)
    path = write_nav(kepler_record(epoch=old) + kepler_record(epoch=current))
    entries = build_ephemeris_table([path])["G01"]
    assert len(entries) == 2
    assert find_nearest_eph(entries, 0, target_epoch=current)[1]["_toc_native"] == current
    assert find_nearest_eph(entries, 0, target_epoch=old)[1]["_toc_native"] == old
    with pytest.raises(ValueError, match="target_epoch"):
        find_nearest_eph(entries, 0)
    assert find_nearest_eph(entries[:1], 0, target_epoch=current, max_age=7200) is None


def test_week_boundary_uses_absolute_epochs(write_nav):
    before = datetime(2025,11,1,23,59)
    after = datetime(2025,11,2,0,1)
    path = write_nav(kepler_record(epoch=before) + kepler_record(epoch=after))
    entries = build_ephemeris_table([path])["G01"]
    target = datetime(2025,11,2)
    chosen = find_nearest_eph(entries, 0, target_epoch=target)
    assert chosen[1]["_toc_native"] == before
    assert ephemeris_age_seconds(chosen[1], 0, target_epoch=target) == 60


def test_beidou_toc_toe_and_midpoint_selection_use_bdt_to_gpst(write_nav):
    native0 = datetime(2025,11,2)
    native2h = native0 + timedelta(hours=2)
    path = write_nav(kepler_record("C11", native0) + kepler_record("C11", native2h))
    entries = build_ephemeris_table([path])["C11"]
    eph = entries[0][1]
    assert eph["_toe_gpst"] == pd.Timestamp(native0) + pd.Timedelta(seconds=14)
    assert eph["_toc_gpst"] == eph["_toe_gpst"]
    target = native0 + timedelta(seconds=3612)
    chosen = find_nearest_eph(entries, 3612, target_epoch=target, sys_type="C")
    assert chosen[0] == 0
    assert ephemeris_age_seconds(eph, 3612, target_epoch=target) == 3598
    assert ephemeris_age_seconds(eph, 3612, sys_type="C") == 3598
    assert ephemeris_age_seconds(eph, 14, target_epoch=native0+timedelta(seconds=14)) == 0


@pytest.mark.parametrize("system", ["G", "E", "C"])
def test_missing_week_is_inferred_from_native_toc(write_nav, system):
    path = write_nav(kepler_record(system+"01", values=elements(system, overrides={21: None})))
    eph = build_ephemeris_table([path])[system+"01"][0][1]
    expected = pd.Timestamp("2025-11-02") + pd.Timedelta(seconds=14 if system == "C" else 0)
    assert eph["_toe_gpst"] == expected


def test_bad_week_is_not_silently_reinterpreted(write_nav):
    path = write_nav(kepler_record(values=elements(overrides={21: 5})))
    with pytest.warns(RuntimeWarning, match="inconsistent with Toc"):
        assert build_ephemeris_table([path]) == {}


def test_bad_files_raise_or_warn_explicitly(write_nav):
    good = write_nav()
    bad = good.parent / "bad.txt"
    bad.write_text("not RINEX\n")
    with pytest.raises(ValueError, match="bad.txt: line"):
        build_ephemeris_table([good,bad])
    with pytest.warns(RuntimeWarning, match="bad.txt"):
        assert set(build_ephemeris_table([bad,good], errors="warn")) == {"G01"}


def test_missing_kepler_parameter_is_counted_and_rejected(write_nav):
    path = write_nav(kepler_record(values=elements(overrides={10: None})))
    with pytest.warns(RuntimeWarning, match="invalid Keplerian"):
        assert build_ephemeris_table([path]) == {}


def test_single_epoch_latest_toc_policy_and_exact_age_limit(write_nav):
    start = datetime(2025,11,2)
    path = write_nav(kepler_record(epoch=start) + kepler_record(epoch=start+timedelta(hours=2)))
    records = build_ephemeris_table([path])["G01"]
    target = start + timedelta(minutes=110)
    assert find_latest_eph(records,target)[0] == 0
    assert find_nearest_eph(records,6600,target_epoch=target)[0] == 7200
    assert find_latest_eph(records[:1],start+timedelta(hours=4)) is not None
    assert find_latest_eph(records[:1],start+timedelta(hours=4,seconds=1)) is None
    assert find_latest_eph(records[:1],start-timedelta(seconds=1)) is not None


def test_bds_single_epoch_selection_does_not_treat_future_toc_as_past(write_nav):
    start = datetime(2025,11,2)
    path = write_nav(kepler_record("C11", start) + kepler_record("C11",start+timedelta(seconds=30)))
    records = build_ephemeris_table([path])["C11"]

    assert find_latest_eph(records,start+timedelta(seconds=35))[0] == 0


def test_legacy_tow_only_api_and_week_wrap():
    before = {"Toe":604790}
    after = {"Toe":30}
    assert find_nearest_eph([(604790,before),(30,after)],0)[1] is before


@pytest.mark.parametrize("time", [pd.Timestamp("2025-11-02",tz="UTC"), pd.NaT])
def test_ambiguous_or_missing_input_time_rejected(time):
    with pytest.raises(ValueError,match="GPST"):
        datetime_to_gps_tow(time)


def test_file_discovery_uses_header_not_every_file(write_nav):
    plain = write_nav(name="arbitrary_name.txt")
    gz = plain.parent/"nav.rnx.gz"
    gz.write_bytes(gzip.compress(plain.read_bytes()))
    (plain.parent/"paper.txt").write_text("not navigation")
    write_nav("", name="observations.rnx", file_type="O")
    (plain.parent/"out.xlsx").write_bytes(b"PK\x03\x04junk")
    (plain.parent/"orbit.sp3").write_text("SP3 dummy")
    (plain.parent/"clock.clk").write_text("CLK dummy")
    nav,sp3,clk = discover_files(plain.parent)
    assert set(nav) == {str(plain),str(gz)}
    assert len(sp3) == len(clk) == 1


@pytest.mark.parametrize("change", [{"sqrtA":0}, {"Eccentricity":1}, {"M0":np.nan}, {"Toe":np.inf}])
def test_invalid_orbit_inputs_do_not_return_nan_coordinates(write_nav, change):
    eph = build_ephemeris_table([write_nav()])["G01"][0][1]
    eph.update(change)
    assert compute_keplerian_xyz(eph,0,"G") is None


def test_unsupported_comparison_constellation_does_not_use_gps_formula(write_nav):
    eph = build_ephemeris_table([write_nav()])["G01"][0][1]
    with pytest.raises(ValueError,match="G, E and C"):
        compute_keplerian_xyz(eph,0,"R")


def test_analytical_circular_equatorial_orbit():
    eph = dict(Toe=0,sqrtA=np.sqrt(26560000),DeltaN=0,M0=0,Eccentricity=0,omega=0,
               Cus=0,Cuc=0,Crs=0,Crc=0,Io=0,Cis=0,Cic=0,IDOT=0,Omega0=0,OmegaDot=0)
    np.testing.assert_allclose(compute_keplerian_xyz(eph,0,"G"),[26560000,0,0],atol=1e-8)
