"""Native navigation-to-orbit adapter and ephemeris selection.

Times passed to the comparison functions are naive GPST calendar times, not
UTC. The RINEX reader itself retains each record's native time system.
"""
from __future__ import annotations

from pathlib import Path
import warnings

import numpy as np
import pandas as pd

from gnsspy.io.rinex.navigation import read_navFile

_WEEK = 604800.0
_HALF_WEEK = _WEEK / 2
_GPS_EPOCH = pd.Timestamp("1980-01-06")
_BDT_EPOCH = pd.Timestamp("2006-01-01")
_BDT_TO_GPST = 14.0
_KEYS = {
    "sqrtA": "roota", "Toe": "toe", "M0": "m0", "Eccentricity": "eccentricity",
    "DeltaN": "delta_n", "omega": "smallomega", "Cus": "cus", "Cuc": "cuc",
    "Crs": "crs", "Crc": "crc", "Cis": "cis", "Cic": "cic", "IDOT": "idot",
    "Io": "i0", "Omega0": "bigomega0", "OmegaDot": "bigomegadot",
    "SVclockBias": "clockBias", "SVclockDrift": "relFeqBias",
    "SVclockDriftRate": "clockDriftRate", "health": "health", "Week": "week",
    "DataSrc": "dataSources", "TransTime": "messageTime", "FitIntvl": "fitInterval",
    "IODE": "iode", "IODC": "iodc", "IODnav": "iodnav", "AODE": "aode",
    "AODC": "aodc", "TGD": "tgd", "TGD1": "tgd1", "TGD2": "tgd2",
    "BGDe5a": "bgdE5aE1", "BGDe5b": "bgdE5bE1", "SVacc": "accuracy",
}
_ORBIT_KEYS = tuple(list(_KEYS)[:16])


def _gpst_timestamp(value) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if pd.isna(stamp) or stamp.tzinfo is not None:
        raise ValueError("Use a finite, timezone-naive GPST datetime; UTC is not converted implicitly")
    return stamp


def _is_healthy(eph, sys_type):
    """Conservative legacy policy: zero health, otherwise reject.

    For Galileo, requiring a zero bitmask is not a signal-specific assessment.
    Missing/unknown health is never silently classified as healthy.
    """
    keys = ("SatH1", "health") if sys_type == "C" else ("health",)
    for key in keys:
        try:
            value = float(eph[key])
        except (KeyError, TypeError, ValueError):
            continue
        if np.isfinite(value):
            return value == 0.0
    return False


def _native_record(row, epoch, sv: str, filename) -> dict:
    eph = {key: float(row[name]) for key, name in _KEYS.items()}
    system = sv[0]
    toc = pd.Timestamp(epoch)
    toe = eph["Toe"]
    if (not all(np.isfinite(eph[k]) for k in _ORBIT_KEYS)
            or eph["sqrtA"] <= 0 or not 0 <= eph["Eccentricity"] < 1
            or not 0 <= toe <= _WEEK):
        raise ValueError("missing or invalid Keplerian orbit parameters")
    offset = _BDT_TO_GPST if system == "C" else 0.0
    origin = _BDT_EPOCH if system == "C" else _GPS_EPOCH
    week = eph["Week"]
    if np.isfinite(week):
        if week < 0 or abs(week - round(week)) > 1e-6:
            raise ValueError("navigation week must be a non-negative continuous integer")
        toe_native = origin + pd.to_timedelta(round(week) * _WEEK + toe, unit="s")


        if abs((toe_native - toc).total_seconds()) > _HALF_WEEK:
            raise ValueError("continuous navigation week/Toe is inconsistent with Toc")
    else:

        toc_seconds = (toc - origin).total_seconds()
        toe_seconds = np.floor(toc_seconds / _WEEK) * _WEEK + toe
        toe_seconds += round((toc_seconds - toe_seconds) / _WEEK) * _WEEK
        toe_native = origin + pd.to_timedelta(toe_seconds, unit="s")
    eph.update(
        _system=system, _sv=sv, _toc_native=toc,
        _toc_gpst=toc + pd.to_timedelta(offset, unit="s"),
        _toe_gpst=toe_native + pd.to_timedelta(offset, unit="s"),
        _source_file=str(filename), _source_line=int(row["sourceLine"]),
    )
    if system == "C":
        eph["SatH1"] = eph["health"]
        eph["BDTWeek"] = week
    elif system == "E":
        eph["GALWeek"] = week
        eph["SISA"] = eph["SVacc"]
    else:
        eph["GPSWeek"] = week
    return eph


def _signature(eph):
    """All meaningful numeric fields and native Toc, excluding file provenance."""
    return (eph["_sv"], eph["_toc_native"], tuple(
        (key, value if np.isfinite(value) else None)
        for key, value in sorted(eph.items()) if not key.startswith("_")
    ))


def _sort_key(item):
    _, eph = item

    values = tuple((eph[key] if np.isfinite(eph[key]) else float("inf"))
                   for key in sorted(eph) if not key.startswith("_"))
    return eph["_toe_gpst"], eph["_toc_gpst"], values


def build_ephemeris_table(nav_files, *, use=("G", "E", "C"), healthy_only=True,
                          errors="raise"):
    """Return ``{SV: [(native_Toe_seconds, plain_dict), ...]}``.

    The default comparison systems remain GPS, Galileo and BeiDou. Distinct
    messages at the same Toc or Toe are preserved; only exact duplicates are
    removed. Absolute week/date information is carried in each record.

    Invalid files raise with context by default. ``errors='warn'`` explicitly
    permits skipping a bad file; it never suppresses the reason. Incomplete
    orbit records are excluded and counted separately from health filtering.
    """
    systems = {str(s).upper() for s in use}
    if not systems or not systems <= {"G", "E", "C"}:
        raise ValueError("orbit comparisons currently support G, E and C only")
    if errors not in {"raise", "warn"}:
        raise ValueError("errors must be 'raise' or 'warn'")
    table, seen = {}, set()
    skipped_health = skipped_invalid = 0
    invalid_examples = []
    paths = sorted({str(Path(f).expanduser()) for f in nav_files})
    for filename in paths:
        try:
            nav = read_navFile(filename, use=systems, verbose=False)
        except (OSError, ValueError, ImportError) as exc:
            if errors == "raise":
                raise
            warnings.warn(f"Skipping navigation file {filename}: {exc}", RuntimeWarning,
                          stacklevel=2)
            continue
        for (epoch, sv), row in nav.navigation.iterrows():
            if healthy_only and not _is_healthy(row, sv[0]):
                skipped_health += 1
                continue
            try:
                eph = _native_record(row, epoch, sv, filename)
            except (ValueError, OverflowError) as exc:
                skipped_invalid += 1
                if len(invalid_examples) < 3:
                    invalid_examples.append(f"{filename}: line {int(row['sourceLine'])}: {exc}")
                continue
            signature = _signature(eph)
            if signature in seen:
                continue
            seen.add(signature)
            table.setdefault(sv, []).append((eph["Toe"], eph))
    if skipped_health:
        print(f"       [FILTER] Skipped {skipped_health} unhealthy/unknown-health ephemeris records.")
    if skipped_invalid:
        warnings.warn(f"Excluded {skipped_invalid} incomplete/invalid ephemeris records. "
                      + "; ".join(invalid_examples), RuntimeWarning, stacklevel=2)
    return {sv: sorted(records, key=_sort_key) for sv, records in sorted(table.items())}


def ephemeris_age_seconds(eph, target_tow, *, target_epoch=None, sys_type=None):
    """Signed target-minus-Toe seconds, on one time scale.

    Supply target_epoch for absolute (week-aware) comparison. The legacy
    TOW-only path handles a week boundary but cannot identify an arbitrary week.
    """
    if target_epoch is not None and "_toe_gpst" in eph:
        return (_gpst_timestamp(target_epoch) - eph["_toe_gpst"]).total_seconds()
    system = sys_type or eph.get("_system", "G")
    native_tow = float(target_tow) - (_BDT_TO_GPST if system == "C" else 0)
    if not np.isfinite(native_tow):
        raise ValueError("target_tow must be finite GPST seconds of week")
    return (native_tow - float(eph["Toe"]) + _HALF_WEEK) % _WEEK - _HALF_WEEK


def find_nearest_eph(eph_list, target_tow, *, target_epoch=None, sys_type=None,
                     max_age=None):
    """Select the closest Toe with an optional age limit.

    Multi-week tables require target_epoch to disambiguate the calendar week.
    Two-argument calls are supported for single-week tables.
    """
    if max_age is not None and (not np.isfinite(max_age) or max_age < 0):
        raise ValueError("max_age must be a finite, non-negative number of seconds")
    if target_epoch is None:
        times = [eph["_toe_gpst"] for _, eph in eph_list if "_toe_gpst" in eph]
        if times and (max(times) - min(times)).total_seconds() >= _HALF_WEEK:
            raise ValueError("target_epoch is required for a multi-week ephemeris table")
    best, best_rank = None, None
    for toe, eph in eph_list:
        age = ephemeris_age_seconds(eph, target_tow, target_epoch=target_epoch,
                                    sys_type=sys_type)
        if not np.isfinite(age) or (max_age is not None and abs(age) > max_age):
            continue

        rank = (abs(age), age < 0)
        if best_rank is None or rank < best_rank:
            best_rank, best = rank, (toe, eph)
    return best


def find_latest_eph(eph_list, target_epoch, *, max_age=14400.0):
    """Select the latest Toc at or before the target, otherwise the earliest future.

    Both Toc and Toe must satisfy the age limit in GPST. The default limit is
    four hours. This offline comparison policy does not establish real-time
    message availability.
    """
    target = _gpst_timestamp(target_epoch)
    if not np.isfinite(max_age) or max_age < 0:
        raise ValueError("max_age must be finite and non-negative")
    candidates = [(toe, eph) for toe, eph in eph_list
                  if abs((target - eph["_toc_gpst"]).total_seconds()) <= max_age
                  and abs((target - eph["_toe_gpst"]).total_seconds()) <= max_age]
    previous = [item for item in candidates if item[1]["_toc_gpst"] <= target]
    if previous:
        latest = max(item[1]["_toc_gpst"] for item in previous)
        candidates = [item for item in previous if item[1]["_toc_gpst"] == latest]
    elif candidates:
        earliest = min(item[1]["_toc_gpst"] for item in candidates)
        candidates = [item for item in candidates if item[1]["_toc_gpst"] == earliest]
    else:
        return None
    return min(candidates, key=_sort_key)


__all__ = ["build_ephemeris_table", "find_nearest_eph", "find_latest_eph",
           "ephemeris_age_seconds"]
