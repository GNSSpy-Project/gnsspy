"""Writers for RINEX 2.11 and RINEX 3.04 observation files.

A writer takes an :class:`~rinex_converter.models.ObsData` and emits text.
The internal ObsData carries codes in their original width (2-char for a
file that was originally RINEX 2, 3-char for RINEX 3).  When writing to a
*different* version, code remapping is applied here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .models import ObsData, ObsEpoch, ObsHeader, ObsValue
from .obs_codes import (
    GLONASS_FREQ_CHANNELS,
    build_r2_to_r3_map,
    build_r3_to_r2_map,
)





def _pad60(data: str, label: str) -> str:
    """Compose a 80-char header line from a 60-char data field + label."""
    return f"{data:<60s}{label:<20s}\n"


def _fmt_obs(val: ObsValue) -> str:
    """Format one observation as F14.3 + I1 LLI + I1 SS (16 chars)."""
    value, lli, ss = val
    if value is None:
        return " " * 16
    s = f"{value:14.3f}"
    if len(s) > 14:


        s = s[-14:]
    lli_c = "" if lli is None or lli == 0 else str(lli)
    lli_c = " " if not lli_c else lli_c
    ss_c = "" if ss is None or ss == 0 else str(ss)
    ss_c = " " if not ss_c else ss_c
    return f"{s}{lli_c[:1]}{ss_c[:1]}"


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d %H%M%S UTC")





def write_rinex3(data: ObsData, out_path: str | Path, version: float = 3.04) -> None:
    """Write *data* to *out_path* in RINEX 3 format.

    If the source codes are 2-char (RINEX 2 origin) they are remapped to
    3-char codes using the rules in :mod:`obs_codes`.
    """
    out_path = Path(out_path)


    code_maps: Dict[str, Dict[str, str]] = {}
    for sys_letter, codes in data.header.obs_types.items():
        if codes and len(codes[0]) == 2:
            code_maps[sys_letter] = build_r2_to_r3_map(sys_letter, codes)
        else:
            code_maps[sys_letter] = {c: c for c in codes}


    final_codes: Dict[str, List[str]] = {}
    for sys_letter, codes in data.header.obs_types.items():
        out_codes: List[str] = []
        seen = set()
        for c in codes:
            mapped = code_maps[sys_letter].get(c)
            if mapped and mapped not in seen:
                out_codes.append(mapped)
                seen.add(mapped)
        if out_codes:
            final_codes[sys_letter] = out_codes


    systems_present = set(data.systems())
    final_codes = {s: v for s, v in final_codes.items() if s in systems_present}







    used: Dict[str, set] = {s: set() for s in final_codes}
    for ep in data.epochs:
        for sat, sat_obs in ep.obs.items():
            sys_letter = sat[0]
            if sys_letter not in final_codes:
                continue
            cmap = code_maps.get(sys_letter, {})
            seen_codes = used[sys_letter]
            for src_code, val in sat_obs.items():
                if val[0] is None:
                    continue
                out_code = cmap.get(src_code, src_code)
                seen_codes.add(out_code)
    final_codes = {
        s: [c for c in codes if c in used[s]]
        for s, codes in final_codes.items()
    }
    final_codes = {s: codes for s, codes in final_codes.items() if codes}





    glonass_slots: Dict[str, int] = {}
    if "R" in systems_present:
        if data.header.glonass_slots:
            glonass_slots = dict(data.header.glonass_slots)
        else:
            for sat in data.satellites("R"):
                if sat in GLONASS_FREQ_CHANNELS:
                    glonass_slots[sat] = GLONASS_FREQ_CHANNELS[sat]

    with out_path.open("w", encoding="ascii", newline="\n") as f:
        _write_rinex3_header(f, data.header, final_codes, version, glonass_slots)
        _write_rinex3_body(f, data, code_maps, final_codes)


def _write_rinex3_header(f, h: ObsHeader, final_codes, version: float,
                         glonass_slots: Optional[Dict[str, int]] = None) -> None:


    systems = sorted(final_codes.keys())
    sys_char = systems[0] if len(systems) == 1 else "M"
    sys_str = {
        "G": "G: GPS", "R": "R: GLONASS", "E": "E: GALILEO",
        "C": "C: BDS",  "J": "J: QZSS",    "I": "I: IRNSS",
        "S": "S: SBAS", "M": "M: MIXED",
    }.get(sys_char, "M: MIXED")
    line = f"{version:9.2f}           {'OBSERVATION DATA':<20s}{sys_str:<20s}"
    f.write(_pad60(line, "RINEX VERSION / TYPE"))

    f.write(_pad60(
        f"{(h.program or 'rinex_converter'):<20s}"
        f"{(h.run_by or 'user'):<20s}"
        f"{_now_stamp():<20s}",
        "PGM / RUN BY / DATE",
    ))

    for c in h.comments:
        f.write(_pad60(c[:60], "COMMENT"))

    if h.marker_name:
        f.write(_pad60(h.marker_name[:60], "MARKER NAME"))
    if h.marker_number:
        f.write(_pad60(h.marker_number[:60], "MARKER NUMBER"))
    if h.marker_type:
        f.write(_pad60(h.marker_type[:60], "MARKER TYPE"))
    else:
        f.write(_pad60("GEODETIC", "MARKER TYPE"))

    f.write(_pad60(
        f"{h.observer[:20]:<20s}{h.agency[:40]:<40s}",
        "OBSERVER / AGENCY",
    ))
    f.write(_pad60(
        f"{h.receiver_number[:20]:<20s}{h.receiver_type[:20]:<20s}{h.receiver_version[:20]:<20s}",
        "REC # / TYPE / VERS",
    ))
    f.write(_pad60(
        f"{h.antenna_number[:20]:<20s}{h.antenna_type[:20]:<20s}{'':<20s}",
        "ANT # / TYPE",
    ))

    x, y, z = h.approx_xyz
    f.write(_pad60(f"{x:14.4f}{y:14.4f}{z:14.4f}{'':18s}", "APPROX POSITION XYZ"))
    dh, de, dn = h.antenna_delta_hen
    f.write(_pad60(f"{dh:14.4f}{de:14.4f}{dn:14.4f}{'':18s}", "ANTENNA: DELTA H/E/N"))





    _sys_order = "GRECJIS"
    ordered_systems = [s for s in _sys_order if s in final_codes]
    ordered_systems += [s for s in final_codes if s not in ordered_systems]
    for sys_letter in ordered_systems:
        codes = final_codes[sys_letter]
        first = True
        idx = 0
        while idx < len(codes):
            chunk = codes[idx : idx + 13]
            if first:
                head = f"{sys_letter}  {len(codes):3d}"
                first = False
            else:
                head = f"{'':6s}"
            body = " " + " ".join(f"{c:>3s}" for c in chunk)
            line = f"{head}{body}"
            f.write(_pad60(line, "SYS / # / OBS TYPES"))
            idx += 13

    f.write(_pad60(f"{h.signal_strength_unit:<20s}", "SIGNAL STRENGTH UNIT"))

    if h.interval is not None:
        f.write(_pad60(f"{h.interval:10.3f}{'':50s}", "INTERVAL"))

    if h.time_first_obs is not None:
        f.write(_pad60(_fmt_time_of_obs(h.time_first_obs, h.time_system), "TIME OF FIRST OBS"))
    if h.time_last_obs is not None:
        f.write(_pad60(_fmt_time_of_obs(h.time_last_obs, h.time_system), "TIME OF LAST OBS"))

    f.write(_pad60(f"{h.rcv_clock_offs_appl:6d}{'':54s}", "RCV CLOCK OFFS APPL"))


    if h.phase_shifts:
        for sys_letter, code, corr, sats in h.phase_shifts:
            corr_s = f"{corr:8.5f}" if corr is not None else "        "
            line = f"{sys_letter} {code:<3s} {corr_s}"
            f.write(_pad60(line, "SYS / PHASE SHIFT"))
    else:



        for sys_letter, codes in final_codes.items():
            for c in codes:
                if c.startswith("L"):
                    f.write(_pad60(f"{sys_letter} {c:<3s}", "SYS / PHASE SHIFT"))



    slots = h.glonass_slots or (glonass_slots or {})
    if "R" in final_codes and slots:
        items = sorted(slots.items())
        idx = 0
        n = len(items)
        first = True
        while idx < n:
            chunk = items[idx : idx + 8]
            head = f"{n:3d} " if first else "    "
            body = "".join(f"{s:>3s}{f:>3d} " for s, f in chunk)
            f.write(_pad60(f"{head}{body}", "GLONASS SLOT / FRQ #"))
            first = False
            idx += 8

    if "R" in final_codes:
        if h.glonass_cod_phs_bis:
            items = list(h.glonass_cod_phs_bis.items())
            line = " " + " ".join(f"{c:<3s} {v:8.3f}" for c, v in items[:4])
            f.write(_pad60(line, "GLONASS COD/PHS/BIS"))
        else:
            f.write(_pad60(" C1C    0.000 C1P    0.000 C2C    0.000 C2P    0.000",
                           "GLONASS COD/PHS/BIS"))

    if h.leap_seconds is not None:
        f.write(_pad60(f"{h.leap_seconds:6d}{'':54s}", "LEAP SECONDS"))

    f.write(_pad60("", "END OF HEADER"))


def _fmt_time_of_obs(dt: datetime, time_sys: str) -> str:
    sec = dt.second + dt.microsecond / 1_000_000
    return (
        f"{dt.year:6d}{dt.month:6d}{dt.day:6d}"
        f"{dt.hour:6d}{dt.minute:6d}{sec:13.7f}"
        f"     {time_sys:<3s}{'':9s}"
    )


def _write_rinex3_body(f, data: ObsData, code_maps, final_codes) -> None:
    for ep in data.epochs:
        sec = ep.epoch.second + ep.epoch.microsecond / 1_000_000
        nsats = len(ep.obs)
        head = (
            f"> {ep.epoch.year:4d} {ep.epoch.month:02d} {ep.epoch.day:02d} "
            f"{ep.epoch.hour:02d} {ep.epoch.minute:02d}{sec:11.7f}"
            f"  {ep.flag:1d}{nsats:3d}"
        )
        if ep.rcv_clock_offset is not None:
            head += f"      {ep.rcv_clock_offset:15.12f}"
        f.write(head + "\n")

        for sat, sat_obs in ep.obs.items():
            sys_letter = sat[0]
            codes = final_codes.get(sys_letter, [])
            if not codes:
                continue
            cmap = code_maps.get(sys_letter, {})

            out_obs: Dict[str, ObsValue] = {}
            for src_code, val in sat_obs.items():
                out_code = cmap.get(src_code, src_code)


                if out_code not in out_obs or out_obs[out_code][0] is None:
                    out_obs[out_code] = val
            parts = [sat[:3]]
            for c in codes:
                parts.append(_fmt_obs(out_obs.get(c, (None, None, None))))
            f.write("".join(parts).rstrip() + "\n")





def write_rinex2(
    data: ObsData,
    out_path: str | Path,
    version: float = 2.11,
    keep_systems: str = "GRES",
) -> None:
    """Write *data* to *out_path* in RINEX 2.11 format.

    Parameters
    ----------
    keep_systems : str
        Systems to retain in the output.  The default "GRES" is exactly the
        set RINEX 2.11 officially supports - GPS (G), GLONASS (R), Galileo
        (E) and SBAS (S).  BeiDou (C), QZSS (J) and IRNSS (I) have no valid
        RINEX 2.11 representation and are dropped by default; pass them
        explicitly only if a downstream tool is known to tolerate them.
        (RINEX 2 observation files never contain C/J/I anyway, so this never
        affects a RINEX 2 -> RINEX 3 -> RINEX 2 round-trip.)
    """
    out_path = Path(out_path)
    keep_set = set(keep_systems)





    raw_maps: Dict[str, Dict[str, str]] = {}
    for sys_letter in list(data.header.obs_types.keys()):
        if sys_letter not in keep_set:
            continue
        codes = data.header.obs_types[sys_letter]
        if codes and len(codes[0]) == 3:
            mapping, _unmapped = build_r3_to_r2_map(sys_letter, codes)
            raw_maps[sys_letter] = mapping
        else:
            raw_maps[sys_letter] = {c: c for c in codes}






    counts: Dict[str, Dict[str, int]] = {s: {} for s in raw_maps}
    for ep in data.epochs:
        for sat, sat_obs in ep.obs.items():
            sys_letter = sat[0]
            if sys_letter not in counts:
                continue
            cc = counts[sys_letter]
            for src_code, val in sat_obs.items():
                if val[0] is not None:
                    cc[src_code] = cc.get(src_code, 0) + 1


    code_maps: Dict[str, Dict[str, str]] = {s: {} for s in raw_maps}
    for sys_letter, mapping in raw_maps.items():
        src_order = data.header.obs_types[sys_letter]
        by_target: Dict[str, List[str]] = {}
        for src in src_order:
            dst = mapping.get(src)
            if dst is None:
                continue
            by_target.setdefault(dst, []).append(src)
        cc = counts[sys_letter]
        for dst, srcs in by_target.items():

            best = max(srcs, key=lambda s: (cc.get(s, 0), -src_order.index(s)))
            code_maps[sys_letter][best] = dst



    union_codes: List[str] = []
    seen = set()
    for sys_letter in data.header.obs_types:
        if sys_letter not in keep_set:
            continue
        for src in data.header.obs_types[sys_letter]:
            dst = code_maps[sys_letter].get(src)
            if dst is None:
                continue
            if dst not in seen:
                seen.add(dst)
                union_codes.append(dst)

    with out_path.open("w", encoding="ascii", newline="\n") as f:
        _write_rinex2_header(f, data.header, union_codes, keep_set, version)
        _write_rinex2_body(f, data, code_maps, union_codes, keep_set)


def _write_rinex2_header(f, h: ObsHeader, union_codes, keep_set, version: float) -> None:
    sys_char = "M" if len(keep_set) > 1 else next(iter(keep_set))
    sys_str = {
        "G": "G (GPS)", "R": "R (GLONASS)", "M": "M (MIXED)",
    }.get(sys_char, "M (MIXED)")
    line = f"{version:9.2f}           OBSERVATION DATA    {sys_str:<20s}"
    f.write(_pad60(line, "RINEX VERSION / TYPE"))

    f.write(_pad60(
        f"{(h.program or 'rinex_converter'):<20s}"
        f"{(h.run_by or 'user'):<20s}"
        f"{_now_stamp():<20s}",
        "PGM / RUN BY / DATE",
    ))

    for c in h.comments:
        f.write(_pad60(c[:60], "COMMENT"))

    if h.marker_name:
        f.write(_pad60(h.marker_name[:60], "MARKER NAME"))
    if h.marker_number:
        f.write(_pad60(h.marker_number[:60], "MARKER NUMBER"))

    f.write(_pad60(
        f"{h.observer[:20]:<20s}{h.agency[:40]:<40s}",
        "OBSERVER / AGENCY",
    ))
    f.write(_pad60(
        f"{h.receiver_number[:20]:<20s}{h.receiver_type[:20]:<20s}{h.receiver_version[:20]:<20s}",
        "REC # / TYPE / VERS",
    ))
    f.write(_pad60(
        f"{h.antenna_number[:20]:<20s}{h.antenna_type[:20]:<20s}{'':<20s}",
        "ANT # / TYPE",
    ))

    x, y, z = h.approx_xyz
    f.write(_pad60(f"{x:14.4f}{y:14.4f}{z:14.4f}{'':18s}", "APPROX POSITION XYZ"))
    dh, de, dn = h.antenna_delta_hen
    f.write(_pad60(f"{dh:14.4f}{de:14.4f}{dn:14.4f}{'':18s}", "ANTENNA: DELTA H/E/N"))

    f.write(_pad60(f"{h.wavelength_fact[0]:6d}{h.wavelength_fact[1]:6d}{'':48s}",
                   "WAVELENGTH FACT L1/2"))


    n = len(union_codes)
    idx = 0
    first = True
    while idx < n or first:
        chunk = union_codes[idx : idx + 9]
        if first:
            head = f"{n:6d}"
            first = False
        else:
            head = f"{'':6s}"
        body = "".join(f"{c:>6s}" for c in chunk)
        f.write(_pad60(f"{head}{body}", "# / TYPES OF OBSERV"))
        idx += 9
        if idx >= n:
            break

    if h.interval is not None:
        f.write(_pad60(f"{h.interval:10.3f}{'':50s}", "INTERVAL"))

    if h.time_first_obs is not None:
        f.write(_pad60(_fmt_time_of_obs(h.time_first_obs, h.time_system), "TIME OF FIRST OBS"))
    if h.time_last_obs is not None:
        f.write(_pad60(_fmt_time_of_obs(h.time_last_obs, h.time_system), "TIME OF LAST OBS"))

    if h.leap_seconds is not None:
        f.write(_pad60(f"{h.leap_seconds:6d}{'':54s}", "LEAP SECONDS"))

    f.write(_pad60("", "END OF HEADER"))


def _write_rinex2_body(f, data: ObsData, code_maps, union_codes, keep_set) -> None:
    for ep in data.epochs:

        sats = [s for s in ep.obs.keys() if s[0] in keep_set]
        if not sats:
            continue


        yy = ep.epoch.year % 100
        sec = ep.epoch.second + ep.epoch.microsecond / 1_000_000
        head = (
            f" {yy:2d}"
            f"{ep.epoch.month:3d}{ep.epoch.day:3d}"
            f"{ep.epoch.hour:3d}{ep.epoch.minute:3d}"
            f"{sec:11.7f}"
            f"  {ep.flag:1d}"
            f"{len(sats):3d}"
        )


        first_chunk = sats[:12]
        head += "".join(first_chunk)
        if ep.rcv_clock_offset is not None and len(sats) <= 12:
            head += f"{ep.rcv_clock_offset:12.9f}"
        f.write(head + "\n")

        idx = 12
        while idx < len(sats):
            cont = " " * 32 + "".join(sats[idx : idx + 12])
            f.write(cont + "\n")
            idx += 12


        for sat in sats:
            sys_letter = sat[0]
            cmap = code_maps.get(sys_letter, {})
            sat_obs = ep.obs[sat]

            out_obs: Dict[str, ObsValue] = {}
            for src_code, val in sat_obs.items():
                out_code = cmap.get(src_code, src_code if len(src_code) == 2 else None)
                if out_code is None:
                    continue
                if out_code not in out_obs or out_obs[out_code][0] is None:
                    out_obs[out_code] = val
            for k in range(0, len(union_codes), 5):
                chunk = union_codes[k : k + 5]
                line = "".join(
                    _fmt_obs(out_obs.get(c, (None, None, None))) for c in chunk
                )
                f.write(line.rstrip() + "\n" if line.strip() else line + "\n")
