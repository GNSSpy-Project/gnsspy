import bz2
from datetime import datetime
import gzip
import importlib.util
import lzma
import warnings

import numpy as np
import pandas as pd
import pytest

from gnsspy.io.rinex.navigation import read_navFile, read_navigation_file, RinexNavigationError
from conftest import header, elements, field, kepler_record, state_record


def test_public_shape_and_metadata(write_nav):
    path = write_nav()
    nav = read_navigation_file(path, verbose=False)
    assert read_navigation_file is read_navFile
    assert nav.version == "3.04"
    assert nav.epoch == datetime(2025, 11, 2).date()
    assert nav.navigation.index.names == ["Epoch", "SV"]
    row = nav.navigation.iloc[0]
    assert row.SV == "G01"
    assert row.roota == 5153.7
    assert row.crs == -56.25
    assert row.clockDriftRate == 1.25e-20
    assert row.transmissionTime == row.clockDriftRate
    assert row.messageTime == 60
    assert row.health == 0
    assert nav.metadata["records_in_file"] == 1
    assert nav.metadata["header"]["COMMENT"][0].strip() == "Synthetic GNSSpy test"


@pytest.mark.parametrize("system", list("GECJI"))
def test_kepler_system_fields(write_nav, system):
    path = write_nav(kepler_record(system+"02"))
    row = read_navFile(path, verbose=False).navigation.iloc[0]
    assert row.system == system
    assert row.health == 0
    assert row.week == elements(system)[21]
    assert row.clockBias == -2.123456789e-4
    if system == "E":
        assert row.dataSources == 513 and row.bgdE5aE1 == -2e-9 and row.iodnav == 12
        assert np.isnan(row.iodc) and np.isnan(row.codesL2)
    elif system == "C":
        assert row.aode == 12 and row.aodc == 7 and row.tgd2 == 3e-9
        assert np.isnan(row.dataSources) and row.timeSystem == "BDT"
    elif system == "I":
        assert row.iodec == 12 and row.tgd == -2e-9
    else:
        assert row.iode == 12 and row.iodc == 12 and row.fitInterval == 4


@pytest.mark.parametrize("exponent", ["D", "d", "E", "e"])
def test_exponents_adjacent_negative_numbers_and_blank_spares(write_nav, exponent):
    values = elements("C", overrides={20: None, 22: None, 23: 2.4, 24: 1})
    path = write_nav(kepler_record("C12", values=values, exponent=exponent, trim=True))
    row = read_navFile(path, verbose=False).navigation.iloc[0]
    assert row.accuracy == 2.4 and row.health == 1 and row.week == values[21]
    assert row.smallomega == .7 and row.bigomegadot == -8e-9


def test_blank_defined_field_does_not_shift_columns(write_nav):
    values = elements("E", overrides={20: None, 24: None, 25: -2.2e-9})
    path = write_nav(kepler_record("E11", values=values, trim=True))
    row = read_navFile(path, verbose=False).navigation.iloc[0]
    assert np.isnan(row.dataSources) and np.isnan(row.health)
    assert row.week == values[21] and row.bgdE5aE1 == -2.2e-9


def test_spare_fields_are_ignored_not_misinterpreted(write_nav):
    path = write_nav(kepler_record("C01", values=elements("C", overrides={20: "RESERVED", 22: "N/A"})))
    row = read_navFile(path, verbose=False).navigation.iloc[0]
    assert row.health == 0 and np.isnan(row.codesL2)


@pytest.mark.parametrize("version", ["2.10", "2.11", "3.00", "3.01", "3.02", "3.03", "3.04", "3.05"])
def test_supported_versions(write_nav, version):
    nav = read_navFile(write_nav(version=version, system="G"), verbose=False)
    assert nav.version == version and nav.navigation.iloc[0].roota == 5153.7


@pytest.mark.parametrize("year", [1980, 1999, 2000, 2025, 2079])
def test_rinex2_year_pivot_and_fractional_seconds(write_nav, year):
    epoch = datetime(year, 11, 2, 1, 2, 3, 500000)
    path = write_nav(kepler_record(epoch=epoch, version="2.11"), version="2.11", system="G")
    assert read_navFile(path, verbose=False).navigation.iloc[0].epoch == epoch


@pytest.mark.parametrize("system,file_type", [("R", "G"), ("S", "H")])
def test_rinex2_state_vector_system_from_header(write_nav, system, file_type):
    path = write_nav(state_record(system+"01", version="2.11"),
                     version="2.11", system=" ", file_type=file_type)
    row = read_navFile(path, verbose=False).navigation.iloc[0]
    assert row.SV == system+"01" and row.x == 19000.0
    assert row.vx == -1.2 and row.messageTime == 12345
    assert np.isnan(row.clockDriftRate) and np.isnan(row.roota)
    if system == "R":
        assert row.freqNumber == -7 and row.operationDay == 12
    else:
        assert row.accuracy == 4 and row.iodn == 12


@pytest.mark.parametrize("version", ["3.04", "3.05"])
def test_mixed_glonass_length_does_not_desynchronise_reader(write_nav, version):
    text = state_record(version=version) + kepler_record("G02", version=version)
    text += state_record("S22", version=version) + kepler_record("E11", version=version)
    path = write_nav(text, version=version)
    frame = read_navFile(path, verbose=False).navigation
    assert sorted(frame.SV) == ["E11", "G02", "R01", "S22"]
    assert frame[frame.SV == "G02"].iloc[0].roota == 5153.7
    glo = frame[frame.SV == "R01"].iloc[0]
    assert glo.x == 19000
    if version == "3.05":
        assert glo.statusFlags == 257 and glo.healthFlags == 7 and glo.urai == 3
    else:
        assert np.isnan(glo.statusFlags)
    selected = read_navFile(path, use="GE", verbose=False).navigation
    assert sorted(selected.SV) == ["E11", "G02"]


def test_duplicate_epochs_not_overwritten(write_nav):
    records = kepler_record("E11") + kepler_record("E11", values=elements("E", overrides={20: 258}))
    frame = read_navFile(write_nav(records), verbose=False).navigation
    assert len(frame) == 2 and not frame.index.is_unique
    assert set(frame.dataSources) == {258, 513}


def test_empty_navigation_has_valid_empty_index(write_nav):
    nav = read_navFile(write_nav(""), verbose=False)
    assert nav.navigation.empty and nav.epoch is None
    assert nav.navigation.index.names == ["Epoch", "SV"]
    assert "roota" in nav.navigation


def test_leading_and_inter_record_blank_lines(write_nav):
    path = write_nav("\n" + kepler_record() + "\n\n" + kepler_record("G02") + "\n")
    path.write_text("\n" + path.read_text())
    assert len(read_navFile(path, verbose=False).navigation) == 2


@pytest.mark.parametrize("compress,suffix", [(gzip.compress,".gz"), (bz2.compress,".bz2"), (lzma.compress,".xz")])
def test_compressed_equivalence_and_magic_detection(write_nav, compress, suffix):
    path = write_nav()
    expected = read_navFile(path, verbose=False).navigation
    for name in ("nav.rnx"+suffix, "no_extension"):
        compressed = path.parent / name
        compressed.write_bytes(compress(path.read_bytes()))
        pd.testing.assert_frame_equal(read_navFile(compressed, verbose=False).navigation, expected)


def _literal_z(payload):

    assert len(payload) < 256
    buffer = sum(value << (9 * i) for i, value in enumerate(payload))
    return b"\x1f\x9d\x09" + buffer.to_bytes((9*len(payload)+7)//8, "little")


def test_unix_compress_has_clear_missing_dependency_error(tmp_path):
    if importlib.util.find_spec("unlzw3") is not None:
        pytest.skip("unlzw3 is installed; covered by positive decompression test")
    path = tmp_path / "empty.n.Z"
    path.write_bytes(_literal_z(header().encode("ascii")))
    with pytest.raises(ImportError, match="unlzw3"):
        read_navFile(path, verbose=False)


def test_unix_compress_positive_when_core_dependency_installed(tmp_path):
    pytest.importorskip("unlzw3", reason=".Z positive test needs the existing core dependency")
    path = tmp_path / "empty.n.Z"
    path.write_bytes(_literal_z(header().encode("ascii")))
    assert read_navFile(path, verbose=False).navigation.empty


@pytest.mark.parametrize("version", ["1.00", "3.06", "4.00", "4.02"])
def test_unsupported_navigation_version_fails_explicitly(write_nav, version):
    with pytest.raises(RinexNavigationError, match="unsupported"):
        read_navFile(write_nav("", version=version), verbose=False)


def test_observation_file_rejected(write_nav):
    with pytest.raises(RinexNavigationError, match="not a RINEX navigation"):
        read_navFile(write_nav("", file_type="O"), verbose=False)


@pytest.mark.parametrize("content,match", [("garbage\n", "RINEX VERSION"), ("", "END OF HEADER"),
                                          (header().split("COMMENT")[0], "END OF HEADER")])
def test_broken_header_has_actionable_error(tmp_path, content, match):
    path = tmp_path / "broken.rnx"
    path.write_text(content)
    with pytest.raises(RinexNavigationError, match=match) as exc:
        read_navFile(path, verbose=False)
    assert "broken.rnx: line" in str(exc.value)


def test_truncated_record_not_silently_dropped(write_nav):
    record = "\n".join(kepler_record().splitlines()[:5]) + "\n"
    with pytest.raises(RinexNavigationError, match="truncated G01"):
        read_navFile(write_nav(record), verbose=False)


def test_missing_continuation_cannot_consume_next_satellite(write_nav):
    record = "\n".join(kepler_record().splitlines()[:7]) + "\n" + kepler_record("G02")
    with pytest.raises(RinexNavigationError, match="continuation/truncated G01"):
        read_navFile(write_nav(record), verbose=False)


@pytest.mark.parametrize("value", ["INVALID", "NaN", "Inf", "-Inf"])
def test_malformed_or_nonfinite_defined_number(write_nav, value):
    record = kepler_record(values=elements(overrides={10: value}))
    with pytest.raises(RinexNavigationError, match="roota"):
        read_navFile(write_nav(record), verbose=False)


@pytest.mark.parametrize("use", ["", "X", "GPS", ["G", "bad"]])
def test_invalid_constellation_filter(write_nav, use):
    with pytest.raises(ValueError, match="use must"):
        read_navFile(write_nav(), use=use, verbose=False)
