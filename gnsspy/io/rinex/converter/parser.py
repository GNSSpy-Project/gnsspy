"""Parsers for RINEX 2 and RINEX 3 observation files.

Auto-detects the version from the first line and dispatches to the right
routine.  Both routines populate the same
:class:`~gnsspy.io.rinex.converter.models.ObsData` structure.

Supports transparently:
  * plain text     (.o, .25o, .rnx, ...)
  * gzip           (.gz)
  * Unix compress  (.Z)  - requires the ``unlzw3`` package
"""
from __future__ import annotations

import gzip
import io
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .models import ObsData, ObsEpoch, ObsHeader, ObsValue



OBS_FIELD_WIDTH = 16





def parse_file(path: str | Path) -> ObsData:
    """Parse a RINEX 2 or RINEX 3 observation file.

    Recognises plain text, ``.gz`` (gzip) and ``.Z`` (Unix compress)
    automatically.  ``.Z`` files require the ``unlzw3`` package, which is
    already a dependency of the gnsspy downloader.
    """
    path = Path(path)
    lines = _read_all_lines(path)
    if not lines:
        raise ValueError(f"{path}: file is empty")
    first = lines[0]
    if "RINEX VERSION / TYPE" not in first:
        raise ValueError(
            f"{path}: first line is not 'RINEX VERSION / TYPE' "
            "(is this really a RINEX observation file?)"
        )
    version = float(first[0:9].strip())
    if version < 3.0:
        header, body_start = _parse_rinex2_header(lines)
        epochs = _parse_rinex2_body(lines, body_start, header)
    else:
        header, body_start = _parse_rinex3_header(lines)
        epochs = _parse_rinex3_body(lines, body_start, header)
    return ObsData(header=header, epochs=epochs)


def _read_all_lines(path: Path) -> List[str]:
    """Read a file's lines, transparently handling .gz and .Z."""
    suffix = path.suffix.lower()
    if suffix == ".gz":
        with gzip.open(path, "rt", encoding="ascii", errors="replace") as f:
            return f.readlines()
    if suffix == ".z":
        try:
            import unlzw3
        except ImportError as exc:
            raise RuntimeError(
                f"{path}: cannot read .Z file without the 'unlzw3' package "
                "(pip install unlzw3)."
            ) from exc
        with path.open("rb") as fh:
            data = unlzw3.unlzw(fh.read())
        text = data.decode("ascii", errors="replace")
        return io.StringIO(text).readlines()
    with path.open("r", encoding="ascii", errors="replace") as f:
        return f.readlines()





def _label(line: str) -> str:
    """Return the 20-char descriptor at columns 61-80, stripped."""
    return line[60:80].rstrip() if len(line) >= 61 else ""


def _data(line: str) -> str:
    """Return the 60-char data field at columns 1-60."""
    return line[:60]


def _safe_float(s: str) -> Optional[float]:
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _safe_int(s: str) -> Optional[int]:
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _parse_xyz(line: str) -> Tuple[float, float, float]:
    d = _data(line)
    return (
        _safe_float(d[0:14]) or 0.0,
        _safe_float(d[14:28]) or 0.0,
        _safe_float(d[28:42]) or 0.0,
    )


def _parse_time_of_obs(line: str) -> Tuple[Optional[datetime], str]:
    d = _data(line)
    y = _safe_int(d[0:6])
    mo = _safe_int(d[6:12])
    da = _safe_int(d[12:18])
    h = _safe_int(d[18:24])
    mi = _safe_int(d[24:30])
    se = _safe_float(d[30:43])
    time_sys = d[48:51].strip() or "GPS"
    if None in (y, mo, da, h, mi, se):
        return None, time_sys
    whole = int(se)
    micro = int(round((se - whole) * 1_000_000))
    dt = datetime(y, mo, da, h, mi, whole, micro)
    return dt, time_sys


def _decode_obs_field(s: str) -> ObsValue:
    if len(s) < 16:
        s = s.ljust(16)
    val = _safe_float(s[0:14])
    lli = _safe_int(s[14:15])
    ss = _safe_int(s[15:16])
    return val, lli, ss





def _parse_rinex2_header(lines: List[str]) -> Tuple[ObsHeader, int]:
    h = ObsHeader(version=2.11, sat_system="M")
    h.obs_types = {}
    obs_types_flat: List[str] = []
    n_obs_total = 0

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        label = _label(line)
        data = _data(line)

        if label == "RINEX VERSION / TYPE":
            h.version = float(data[0:9].strip())
            h.file_type = data[20:21].strip() or "O"
            sys_str = data[40:41].strip()
            h.sat_system = sys_str if sys_str else "G"
        elif label == "PGM / RUN BY / DATE":
            h.program = data[0:20].rstrip()
            h.run_by = data[20:40].rstrip()
            h.date_str = data[40:60].rstrip()
        elif label == "COMMENT":
            h.comments.append(data.rstrip())
        elif label == "MARKER NAME":
            h.marker_name = data.rstrip()
        elif label == "MARKER NUMBER":
            h.marker_number = data.rstrip()
        elif label == "OBSERVER / AGENCY":
            h.observer = data[0:20].rstrip()
            h.agency = data[20:60].rstrip()
        elif label == "REC # / TYPE / VERS":
            h.receiver_number = data[0:20].rstrip()
            h.receiver_type = data[20:40].rstrip()
            h.receiver_version = data[40:60].rstrip()
        elif label == "ANT # / TYPE":
            h.antenna_number = data[0:20].rstrip()
            h.antenna_type = data[20:40].rstrip()
        elif label == "APPROX POSITION XYZ":
            h.approx_xyz = _parse_xyz(line)
        elif label == "ANTENNA: DELTA H/E/N":
            h.antenna_delta_hen = _parse_xyz(line)
        elif label == "WAVELENGTH FACT L1/2":
            l1 = _safe_int(data[0:6]) or 1
            l2 = _safe_int(data[6:12]) or 1
            h.wavelength_fact = (l1, l2)
        elif label == "# / TYPES OF OBSERV":
            if n_obs_total == 0:
                n_obs_total = _safe_int(data[0:6]) or 0
            start = 6
            for k in range(9):
                code = data[start + k * 6 : start + k * 6 + 6].strip()
                if code:
                    obs_types_flat.append(code)
                if len(obs_types_flat) >= n_obs_total:
                    break
        elif label == "INTERVAL":
            h.interval = _safe_float(data[0:10])
        elif label == "TIME OF FIRST OBS":
            h.time_first_obs, h.time_system = _parse_time_of_obs(line)
        elif label == "TIME OF LAST OBS":
            h.time_last_obs, _ = _parse_time_of_obs(line)
        elif label == "LEAP SECONDS":
            h.leap_seconds = _safe_int(data[0:6])
        elif label == "RCV CLOCK OFFS APPL":
            h.rcv_clock_offs_appl = _safe_int(data[0:6]) or 0
        elif label == "END OF HEADER":
            i += 1
            break
        i += 1

    for sys_letter in "GRECSJI":
        h.obs_types[sys_letter] = list(obs_types_flat)
    return h, i


def _parse_rinex2_epoch_line(line: str):
    yy = _safe_int(line[0:3])
    mo = _safe_int(line[3:6])
    da = _safe_int(line[6:9])
    h = _safe_int(line[9:12])
    mi = _safe_int(line[12:15])
    se = _safe_float(line[15:26])
    flag = _safe_int(line[26:29]) or 0
    n = _safe_int(line[29:32]) or 0
    clk = _safe_float(line[68:80]) if len(line) > 68 else None
    if None in (yy, mo, da, h, mi, se):
        return None, flag, n, [], clk
    year = yy + 2000 if yy < 80 else yy + 1900
    whole = int(se)
    micro = int(round((se - whole) * 1_000_000))
    dt = datetime(year, mo, da, h, mi, whole, micro)
    sats = _read_sat_chunk(line[32:68])
    return dt, flag, n, sats, clk


def _read_sat_chunk(s: str) -> List[str]:
    out: List[str] = []
    for i in range(0, len(s), 3):
        tok = s[i : i + 3]
        if not tok.strip():
            continue
        sys_letter = tok[0] if tok[0] != " " else "G"
        num = tok[1:].strip()
        if not num.isdigit():
            continue
        out.append(f"{sys_letter}{int(num):02d}")
    return out


def _parse_rinex2_body(lines, start, header) -> List[ObsEpoch]:
    epochs: List[ObsEpoch] = []
    n_obs = len(next(iter(header.obs_types.values()), []))
    obs_codes_per_sys = header.obs_types

    i = start
    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        i += 1
        if not line.strip():
            continue

        dt, flag, nsats, sats, clk = _parse_rinex2_epoch_line(line)
        if dt is None:
            if flag in (2, 3, 4, 5) and nsats > 0:
                i += nsats
            continue

        while len(sats) < nsats and i < len(lines):
            cont = lines[i].rstrip("\r\n")
            i += 1
            sats.extend(_read_sat_chunk(cont[32:68]))
        sats = sats[:nsats]

        lines_per_sat = (n_obs + 4) // 5
        epoch_obs = {}
        for sat in sats:
            values: List[ObsValue] = []
            for _ in range(lines_per_sat):
                if i >= len(lines):
                    break
                obs_line = lines[i].rstrip("\r\n")
                i += 1
                if len(obs_line) < 80:
                    obs_line = obs_line.ljust(80)
                for k in range(5):
                    if len(values) >= n_obs:
                        break
                    chunk = obs_line[k * 16 : k * 16 + 16]
                    values.append(_decode_obs_field(chunk))
            sys_letter = sat[0]
            codes = obs_codes_per_sys.get(sys_letter, [])
            epoch_obs[sat] = {
                codes[idx]: values[idx]
                for idx in range(min(len(codes), len(values)))
                if values[idx][0] is not None
            }

        epochs.append(
            ObsEpoch(epoch=dt, flag=flag, rcv_clock_offset=clk, obs=epoch_obs)
        )
    return epochs





def _parse_rinex3_header(lines: List[str]) -> Tuple[ObsHeader, int]:
    h = ObsHeader(version=3.04, sat_system="M")
    pending_obs_sys: Optional[str] = None
    pending_obs_count = 0

    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        label = _label(line)
        data = _data(line)

        if label == "RINEX VERSION / TYPE":
            h.version = float(data[0:9].strip())
            h.file_type = data[20:21].strip() or "O"
            sys_str = data[40:41].strip()
            h.sat_system = sys_str if sys_str else "M"
        elif label == "PGM / RUN BY / DATE":
            h.program = data[0:20].rstrip()
            h.run_by = data[20:40].rstrip()
            h.date_str = data[40:60].rstrip()
        elif label == "COMMENT":
            h.comments.append(data.rstrip())
        elif label == "MARKER NAME":
            h.marker_name = data.rstrip()
        elif label == "MARKER NUMBER":
            h.marker_number = data.rstrip()
        elif label == "MARKER TYPE":
            h.marker_type = data.rstrip()
        elif label == "OBSERVER / AGENCY":
            h.observer = data[0:20].rstrip()
            h.agency = data[20:60].rstrip()
        elif label == "REC # / TYPE / VERS":
            h.receiver_number = data[0:20].rstrip()
            h.receiver_type = data[20:40].rstrip()
            h.receiver_version = data[40:60].rstrip()
        elif label == "ANT # / TYPE":
            h.antenna_number = data[0:20].rstrip()
            h.antenna_type = data[20:40].rstrip()
        elif label == "APPROX POSITION XYZ":
            h.approx_xyz = _parse_xyz(line)
        elif label == "ANTENNA: DELTA H/E/N":
            h.antenna_delta_hen = _parse_xyz(line)
        elif label == "SYS / # / OBS TYPES":
            if data[0:1].strip():
                pending_obs_sys = data[0:1]
                pending_obs_count = _safe_int(data[1:6]) or 0
                h.obs_types[pending_obs_sys] = []
            start = 7
            if pending_obs_sys is not None:
                codes_here: List[str] = []
                for k in range(13):
                    code = data[start + k * 4 : start + k * 4 + 3].strip()
                    if code:
                        codes_here.append(code)
                h.obs_types[pending_obs_sys].extend(codes_here)
                if len(h.obs_types[pending_obs_sys]) >= pending_obs_count:
                    pending_obs_sys = None
        elif label == "SIGNAL STRENGTH UNIT":
            h.signal_strength_unit = data[0:20].strip() or "DBHZ"
        elif label == "INTERVAL":
            h.interval = _safe_float(data[0:10])
        elif label == "TIME OF FIRST OBS":
            h.time_first_obs, h.time_system = _parse_time_of_obs(line)
        elif label == "TIME OF LAST OBS":
            h.time_last_obs, _ = _parse_time_of_obs(line)
        elif label == "LEAP SECONDS":
            h.leap_seconds = _safe_int(data[0:6])
        elif label == "RCV CLOCK OFFS APPL":
            h.rcv_clock_offs_appl = _safe_int(data[0:6]) or 0
        elif label == "SYS / PHASE SHIFT":
            sys_letter = data[0:1]
            code = data[2:5].strip()
            corr = _safe_float(data[6:14])
            nsats = _safe_int(data[16:18])
            sats = None
            if nsats:
                sats = []
                for k in range(min(nsats, 10)):
                    s = data[18 + k * 4 : 18 + k * 4 + 3].strip()
                    if s:
                        sats.append(s)
            if sys_letter.strip():
                h.phase_shifts.append((sys_letter, code, corr, sats))
        elif label == "GLONASS SLOT / FRQ #":
            text = data[4:]
            off = 0
            while off + 7 <= len(text):
                chunk = text[off : off + 7]
                sat = chunk[0:3].strip()
                fnum = chunk[3:7].strip()
                if sat and fnum:
                    try:
                        h.glonass_slots[sat] = int(fnum)
                    except ValueError:
                        pass
                off += 7
        elif label == "GLONASS COD/PHS/BIS":
            for k in range(4):
                seg = data[k * 13 + 1 : k * 13 + 13]
                code = seg[0:3].strip()
                bias = _safe_float(seg[3:13])
                if code:
                    h.glonass_cod_phs_bis[code] = bias if bias is not None else 0.0
        elif label == "END OF HEADER":
            i += 1
            break
        i += 1
    return h, i


def _parse_rinex3_epoch_line(line):
    if not line.startswith(">"):
        return None, 0, 0, None
    y = _safe_int(line[2:6])
    mo = _safe_int(line[7:9])
    da = _safe_int(line[10:12])
    h = _safe_int(line[13:15])
    mi = _safe_int(line[16:18])
    se = _safe_float(line[19:29])
    flag = _safe_int(line[31:32]) or 0
    n = _safe_int(line[32:35]) or 0
    clk = _safe_float(line[41:56]) if len(line) > 41 else None
    if None in (y, mo, da, h, mi, se):
        return None, flag, n, clk
    whole = int(se)
    micro = int(round((se - whole) * 1_000_000))
    dt = datetime(y, mo, da, h, mi, whole, micro)
    return dt, flag, n, clk


def _parse_rinex3_body(lines, start, header) -> List[ObsEpoch]:
    epochs: List[ObsEpoch] = []
    obs_codes_per_sys = header.obs_types

    i = start
    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        i += 1
        if not line.strip() or not line.startswith(">"):
            continue

        dt, flag, nsats, clk = _parse_rinex3_epoch_line(line)
        if dt is None:
            if flag in (2, 3, 4, 5) and nsats > 0:
                i += nsats
            continue

        epoch_obs = {}
        for _ in range(nsats):
            if i >= len(lines):
                break
            obs_line = lines[i].rstrip("\r\n")
            i += 1
            sat = obs_line[0:3]
            sys_letter = sat[0]
            codes = obs_codes_per_sys.get(sys_letter, [])
            n_obs = len(codes)
            need = 3 + 16 * n_obs
            if len(obs_line) < need:
                obs_line = obs_line.ljust(need)
            obs_dict = {}
            for k, code in enumerate(codes):
                chunk = obs_line[3 + k * 16 : 3 + k * 16 + 16]
                val = _decode_obs_field(chunk)
                if val[0] is not None:
                    obs_dict[code] = val
            epoch_obs[sat] = obs_dict

        epochs.append(
            ObsEpoch(epoch=dt, flag=flag, rcv_clock_offset=clk, obs=epoch_obs)
        )
    return epochs
