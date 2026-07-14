"""High-level conversion API."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from .parser import parse_file
from .writer import write_rinex2, write_rinex3


def rinex2_to_rinex3(
    in_path: str | Path,
    out_path: str | Path,
    version: float = 3.04,
) -> None:
    """Convert a RINEX 2.x observation file to RINEX 3.x."""
    data = parse_file(in_path)
    if data.header.version >= 3.0:
        raise ValueError(f"{in_path}: source file is already RINEX 3.")
    write_rinex3(data, out_path, version=version)


def rinex3_to_rinex2(
    in_path: str | Path,
    out_path: str | Path,
    version: float = 2.11,
    keep_systems: str = "GRES",
) -> None:
    """Convert a RINEX 3.x observation file to RINEX 2.x.

    Only the constellations RINEX 2.11 officially supports are kept by
    default (``keep_systems="GRES"`` = GPS, GLONASS, Galileo, SBAS).  BeiDou,
    QZSS and IRNSS have no valid RINEX 2.11 form and are dropped.  Note that
    R3 -> R2 is inherently lossy: a band tracked in several RINEX 3 modes
    (e.g. C2W/C2L/C2X) collapses to the single RINEX 2 code for that band,
    keeping the mode with the most observations.
    """
    data = parse_file(in_path)
    if data.header.version < 3.0:
        raise ValueError(f"{in_path}: source file is already RINEX 2.")
    write_rinex2(data, out_path, version=version, keep_systems=keep_systems)


def convert_file(
    in_path: str | Path,
    out_path: str | Path,
    target_version: Optional[float] = None,
    keep_systems: str = "GRES",
) -> None:
    """Convert a RINEX observation file to the *opposite* version.

    If *target_version* is omitted, the destination is chosen automatically:
    a RINEX 2 input is converted to RINEX 3.04 and vice versa.
    """
    data = parse_file(in_path)
    src_v = data.header.version
    if target_version is None:
        target_version = 3.04 if src_v < 3.0 else 2.11
    if target_version >= 3.0:
        write_rinex3(data, out_path, version=target_version)
    else:
        write_rinex2(data, out_path, version=target_version, keep_systems=keep_systems)
