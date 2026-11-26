"""RINEX 3 observation epoch parsing; synthetic input, no external downloads."""
import datetime

import pytest

from gnsspy.io.rinex.observation import read_obsFile_v3


HEADER = (
    "     3.03           OBSERVATION DATA    M                   RINEX VERSION / TYPE\n"
    "gnsspy              TEST                20230101 000000 UTC PGM / RUN BY / DATE\n"
    "0000                TEST                                        REC # / TYPE / VERS\n"
    "                                                            ANT # / TYPE\n"
    "  4075460.0000  -100000.0000  4000000.0000                  APPROX POSITION XYZ\n"
    "G    4 C1C L1C D1C S1C                                      SYS / # / OBS TYPES\n"
    "                                                            END OF HEADER\n"
)

SV_LINE = "G01  20000000.000 100000000.000  1000.000  40.000\n"


def write_obs(tmp_path, seconds):
    body = "".join(
        f"> 2023 01 01 00 00 {second:11.7f}  0  1\n{SV_LINE}" for second in seconds
    )
    path = tmp_path / "epoch_fraction.23o"
    path.write_text(HEADER + body)
    return str(path)


def test_epoch_keeps_fractional_seconds(tmp_path):
    obs = read_obsFile_v3(write_obs(tmp_path, [14.996, 15.001, 16.0]))

    epochs = obs.observation.index.get_level_values("Epoch")

    assert list(epochs) == [
        datetime.datetime(2023, 1, 1, 0, 0, 14, 996000),
        datetime.datetime(2023, 1, 1, 0, 0, 15, 1000),
        datetime.datetime(2023, 1, 1, 0, 0, 16),
    ]


def test_subsecond_sampling_interval_is_not_rounded_to_zero(tmp_path):
    obs = read_obsFile_v3(write_obs(tmp_path, [14.996, 15.001]))

    assert obs.interval == pytest.approx(0.005)