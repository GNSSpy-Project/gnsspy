"""Fixed-width RINEX 2/3 navigation reader.

Epochs and Toe use the time system of each record. Navigation state vectors
use kilometres, kilometres per second and kilometres per second squared.
Orbit-comparison adapters handle their own time-system conversion.

Field definitions follow RINEX 2.11 and RINEX 3.05, section 6.8 and
Tables A6-A18.
"""
from __future__ import annotations

import bz2
from contextlib import contextmanager
from datetime import datetime, timedelta
import gzip
import io
import lzma
from pathlib import Path
import re
import time
from typing import Iterable, Iterator, TextIO

import numpy as np
import pandas as pd

from gnsspy.io.io import Navigation


class RinexNavigationError(ValueError):
    """A malformed or unsupported navigation file, with file/line context."""


_SYSTEMS = frozenset("GRECJIS")
_TIME_SYSTEMS = {"G": "GPS", "E": "GAL", "C": "BDT", "J": "QZS",
                 "I": "IRN", "R": "UTC", "S": "GPS"}
_LEGACY_COLUMNS = [
    "SV", "clockBias", "relFeqBias", "transmissionTime", "roota", "toe",
    "m0", "eccentricity", "delta_n", "smallomega", "cus", "cuc", "crs",
    "crc", "cis", "cic", "idot", "i0", "bigomega0", "bigomegadot", "x",
    "y", "z", "vx", "vy", "vz", "ax", "ay", "az", "health", "freqNumber",
    "operationDay", "epoch",
]
_EXTRA_COLUMNS = [
    "clockDriftRate", "messageTime", "week", "iode", "iodc", "aode", "aodc",
    "iodnav", "iodec", "dataSources", "codesL2", "l2Pflag", "accuracy",
    "fitInterval", "tgd", "tgd1", "tgd2", "bgdE5aE1", "bgdE5bE1", "iodn",
    "statusFlags", "groupDelay", "urai", "healthFlags", "system", "timeSystem",
    "recordNumber", "sourceLine",
]

_COMMON_KEPLER = {
    0: "clockBias", 1: "relFeqBias", 2: "clockDriftRate", 4: "crs",
    5: "delta_n", 6: "m0", 7: "cuc", 8: "eccentricity", 9: "cus",
    10: "roota", 11: "toe", 12: "cic", 13: "bigomega0", 14: "cis",
    15: "i0", 16: "crc", 17: "smallomega", 18: "bigomegadot", 19: "idot",
    21: "week", 23: "accuracy", 24: "health", 27: "messageTime",
}
_SYSTEM_FIELDS = {
    "G": {3: "iode", 20: "codesL2", 22: "l2Pflag", 25: "tgd",
          26: "iodc", 28: "fitInterval"},
    "J": {3: "iode", 20: "codesL2", 22: "l2Pflag", 25: "tgd",
          26: "iodc", 28: "fitInterval"},
    "E": {3: "iodnav", 20: "dataSources", 25: "bgdE5aE1", 26: "bgdE5bE1"},
    "C": {3: "aode", 25: "tgd1", 26: "tgd2", 28: "aodc"},
    "I": {3: "iodec", 25: "tgd"},
}
_STATE_FIELDS = {
    0: "clockBias", 1: "relFeqBias", 2: "messageTime", 3: "x", 4: "vx",
    5: "ax", 6: "health", 7: "y", 8: "vy", 9: "ay", 11: "z", 12: "vz",
    13: "az",
}


def _error(path, line_number: int, message: str) -> RinexNavigationError:
    return RinexNavigationError(f"{path}: line {line_number}: {message}")


@contextmanager
def _open_navigation_text(filename) -> Iterator[TextIO]:
    """Open plain or compressed navigation text without modifying the input.

    Compression is detected by magic bytes. Unix-compress input requires unlzw3.
    """
    path = Path(filename).expanduser()
    with path.open("rb") as raw:
        magic = raw.read(6)
    opener = (gzip.open if magic.startswith(b"\x1f\x8b") else
              bz2.open if magic.startswith(b"BZh") else
              lzma.open if magic.startswith(b"\xfd7zXZ\x00") else None)
    if magic.startswith(b"\x1f\x9d"):
        try:
            from unlzw3 import unlzw
        except ImportError as exc:
            raise ImportError("Reading Unix-compress (.Z) files requires "
                              "GNSSpy's core dependency: pip install unlzw3") from exc
        with io.StringIO(unlzw(path.read_bytes()).decode("ascii")) as stream:
            yield stream
    elif opener is not None:
        with opener(path, "rt", encoding="ascii", errors="strict") as stream:
            yield stream
    else:
        with path.open("rt", encoding="ascii", errors="strict") as stream:
            yield stream


def _read_header(lines, path):
    first = None
    header = {}
    for number, line in lines:
        if first is None:
            if not line.strip():
                continue
            if "RINEX VERSION / TYPE" not in line[60:]:
                raise _error(path, number, "missing RINEX VERSION / TYPE header")
            first = line.rstrip("\r\n").ljust(80)
            version = first[:9].strip()
            try:
                value = float(version)
            except ValueError as exc:
                raise _error(path, number, f"invalid RINEX version {version!r}") from exc
            if not (2.0 <= value < 3.0 or 3.0 <= value <= 3.05):
                raise _error(path, number, f"RINEX {version} navigation is unsupported; "
                             "this reader accepts RINEX 2.x and 3.00--3.05")
            file_type = first[20].upper()
            if file_type not in ("N", "G", "H") or (value >= 3 and file_type != "N"):
                raise _error(path, number, "not a RINEX navigation file")
            if file_type == "G":
                system = "R"
            elif file_type == "H":
                system = "S"
            else:
                system = first[40].upper().strip() or "G"
                if system not in _SYSTEMS | {"M"}:
                    system = "G" if value < 3 else "M"
        label = line[60:80].strip()
        header.setdefault(label, []).append(line[:60].rstrip("\r\n"))
        if label == "END OF HEADER":
            return version, value, system, header
    raise _error(path, number if first is not None else 1, "missing END OF HEADER")


def _number(text: str, path, line_number: int, field: str) -> float:
    value = text.strip()
    if not value:
        return np.nan
    value = value.replace("d", "E").replace("D", "E").replace("e", "E")

    value = re.sub(r"E\s*([+-]?)\s*(\d+)$", r"E\1\2", value)
    if "E" not in value:
        value = re.sub(r"^([+-]?(?:\d+\.?\d*|\.\d+))([+-]\d{2,3})$",
                       r"\1E\2", value)
    try:
        result = float(value)
    except ValueError as exc:
        raise _error(path, line_number, f"invalid numeric field {field}: {text!r}") from exc
    if not np.isfinite(result):
        raise _error(path, line_number, f"non-finite numeric field {field}: {text!r}")
    return result


def _read_epoch(line: str, major: int, default_system: str, path, number: int):
    try:
        if major == 3:
            system = line[0]
            if system not in _SYSTEMS:
                raise ValueError(f"unknown satellite system {system!r}")
            prn = int(line[1:3])
            year, month, day, hour, minute = (int(line[a:b]) for a, b in
                ((4, 8), (9, 11), (12, 14), (15, 17), (18, 20)))
            second = float(line[21:23])
        else:
            system = default_system
            if system not in _SYSTEMS:
                raise ValueError("RINEX 2 navigation needs a single-system header")
            prn = int(line[:2])
            year, month, day, hour, minute = (int(line[a:b]) for a, b in
                ((3, 5), (6, 8), (9, 11), (12, 14), (15, 17)))
            year += 1900 if year >= 80 else 2000
            second = float(line[17:22])
        if not (1 <= prn <= 99 and 0 <= second < 61):
            raise ValueError("satellite number or seconds are out of range")
        epoch = datetime(year, month, day, hour, minute) + timedelta(seconds=second)
    except (ValueError, IndexError, OverflowError) as exc:
        raise _error(path, number, f"invalid satellite/epoch record: {exc}") from exc
    return f"{system}{prn:02d}", epoch


def read_navFile(navigationFile, *, use: str | Iterable[str] | None = None,
                 verbose: bool = True) -> Navigation:
    """Read a RINEX navigation file into a Navigation object.

    Parameters
    ----------
    navigationFile : str or os.PathLike
        Plain or compressed (.gz, .bz2, .xz, .Z) navigation file.
    use : iterable of str, optional
        Constellation letters, for example 'GEC'. All systems are read by default.
    verbose : bool, default True
        Print elapsed reading time.

    Notes
    -----
    The navigation DataFrame is indexed by (Epoch, SV). Distinct messages can
    share an index. Missing numeric fields are NaN; health filtering is applied
    by the comparison routines, not by this reader. Reading a constellation does
    not imply that its broadcast propagator is implemented.

    clockDriftRate is the third clock-polynomial coefficient. messageTime is the
    message time. transmissionTime is a compatibility alias for the third field
    on the first record line; use the explicit field names in calculations.
    """
    started = time.perf_counter()
    selected = None if use is None else {str(s).upper() for s in use}
    if selected is not None and (not selected or not selected <= _SYSTEMS):
        raise ValueError("use must contain constellation letters from G, R, E, C, J, I, S")
    path = Path(navigationFile).expanduser()
    records = []
    record_number = 0
    with _open_navigation_text(path) as stream:
        lines = iter(enumerate(stream, start=1))
        version, version_value, default_system, header = _read_header(lines, path)
        major = int(version_value)
        for number, first in lines:
            if not first.strip():
                continue
            sv, epoch = _read_epoch(first, major, default_system, path, number)
            system = sv[0]
            record_number += 1
            length = (5 if system == "R" and version_value >= 3.05 else
                      4 if system in "RS" else 8)
            block = [(number, first.rstrip("\r\n"))]
            prefix = 4 if major == 3 else 3
            for _ in range(length - 1):
                try:
                    n, line = next(lines)
                except StopIteration as exc:
                    raise _error(path, number, f"truncated {sv} record; expected {length} lines") from exc
                if line[:prefix].strip():
                    raise _error(path, n, f"invalid continuation/truncated {sv} record")
                block.append((n, line.rstrip("\r\n")))
            if selected is not None and system not in selected:
                continue
            fields = dict(_STATE_FIELDS if system in "RS" else _COMMON_KEPLER)
            if system in "RS":
                fields.update({10: "freqNumber", 14: "operationDay"} if system == "R"
                              else {10: "accuracy", 14: "iodn"})
                if length == 5:
                    fields.update({15: "statusFlags", 16: "groupDelay", 17: "urai", 18: "healthFlags"})
            else:
                fields.update(_SYSTEM_FIELDS[system])
            row = {name: np.nan for name in _LEGACY_COLUMNS + _EXTRA_COLUMNS}
            row.update(SV=sv, Epoch=epoch, epoch=epoch, system=system,
                       timeSystem=_TIME_SYSTEMS[system], recordNumber=record_number,
                       sourceLine=number)
            for index, name in fields.items():
                line_index = 0 if index < 3 else 1 + (index - 3) // 4
                field_index = index if index < 3 else (index - 3) % 4
                start = (23 if major == 3 else 22) if index < 3 else prefix
                n, text = block[line_index]
                field = text[start + field_index * 19:start + (field_index + 1) * 19]
                row[name] = _number(field, path, n, name)
            row["transmissionTime"] = row["messageTime" if system in "RS" else "clockDriftRate"]
            if system == "S":

                row["freqNumber"] = row["accuracy"]
                row["operationDay"] = row["iodn"]
            records.append(row)
    columns = _LEGACY_COLUMNS + _EXTRA_COLUMNS
    if records:
        frame = pd.DataFrame.from_records(records)
        frame = frame.set_index(["Epoch", "SV"], drop=False).drop(columns="Epoch")
        frame = frame[columns].sort_index(kind="mergesort")
        file_epoch = frame.index.get_level_values("Epoch").min().date()
    else:
        index = pd.MultiIndex.from_arrays([pd.DatetimeIndex([]), pd.Index([], dtype="object")],
                                         names=["Epoch", "SV"])
        frame = pd.DataFrame(index=index, columns=columns)
        file_epoch = None
    metadata = {"filename": str(path), "header": header, "system": default_system,
                "time_systems": dict(_TIME_SYSTEMS), "state_vector_units": "km, km/s, km/s^2",
                "records_in_file": record_number, "records_selected": len(frame)}
    if verbose:
        print(f"Navigation file {path} is read in {time.perf_counter() - started:.2f} seconds.")
    return Navigation(file_epoch, frame, version, metadata=metadata)


read_navigation_file = read_navFile
__all__ = ["read_navFile", "read_navigation_file", "RinexNavigationError"]
