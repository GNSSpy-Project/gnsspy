#!/usr/bin/env python3
"""
rinex_converter_cli.py
======================
Interactive front-end for ``gnsspy.io.rinex.converter``.

Flow:
  1. Choose the conversion DIRECTION:  RINEX 2 -> 3   or   RINEX 3 -> 2
  2. Choose how to obtain the source file:
        a) a local file on this PC (drag-and-drop / paste)
        b) pick one from an existing folder
        c) download a fresh file from CDDIS
  3. Convert and print a short summary.

``.gz`` and ``.Z`` files are accepted directly.  Hatanaka-compressed files
(``.d`` / ``.crx``) are rejected with an explanation, per the project scope.
"""
from __future__ import annotations

import os
import sys
import datetime
from pathlib import Path


_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])


from gnsspy.cli import download as ui


from gnsspy.io.rinex.converter import convert_file
from gnsspy.io.rinex.converter.parser import parse_file



DEFAULT_OUT_DIR = Path(_PROJECT_ROOT) / "output" / "converted"
HATANAKA_HINT = (
    "Hatanaka-compressed files (.d, .crx) are not supported. "
    "Please use the plain observation form (.o / .rnx, optionally .gz)."
)





def _looks_hatanaka(path: Path) -> bool:
    """Heuristic: extension is .d/.crx (optionally .gz/.Z compressed)."""
    name = path.name.lower()
    if name.endswith(".gz"):
        name = name[:-3]
    elif name.endswith(".z"):
        name = name[:-2]
    if name.endswith(".crx"):
        return True

    if len(name) > 4 and name[-4] == "." and name[-1] == "d":
        if name[-3:-1].isdigit():
            return True
    return False


def _detect_version(path: Path) -> float:
    """Peek at the first line to read the RINEX version."""
    import gzip
    if path.suffix.lower() == ".gz":
        f = gzip.open(path, "rt", encoding="ascii", errors="replace")
    else:
        f = path.open("r", encoding="ascii", errors="replace")
    try:
        first = f.readline()
    finally:
        f.close()
    if "RINEX VERSION / TYPE" not in first:
        raise ValueError(f"{path.name}: not a RINEX file "
                         "(first line is not 'RINEX VERSION / TYPE').")
    return float(first[0:9].strip())


def _candidate_files(folder: Path, want_major: int):
    """List likely observation files of the wanted major version in *folder*.

    ``want_major`` is 2 or 3.  We pre-filter by name pattern, then confirm the
    actual version by peeking at each file header.
    """
    if not folder.is_dir():
        return []
    out = []
    for p in sorted(folder.rglob("*")):
        if not p.is_file():
            continue
        n = p.name.lower()
        if n.endswith((".sp3", ".sp3.gz", ".clk", ".clk.gz", ".sum",
                       ".nav", ".n", ".n.gz", ".g", ".g.gz")):
            continue
        if _looks_hatanaka(p):
            continue
        looks_obs = (
            n.endswith((".o", ".rnx")) or n.endswith(("o.gz", "o.z"))
            or n.endswith(".rnx.gz") or n.endswith("_mo.rnx")
            or (len(n) >= 12 and n[-1] in ("o", "z") and "." in n)
        )
        if not looks_obs:
            continue
        try:
            ver = _detect_version(p)
        except Exception:
            continue
        if (want_major == 2 and ver < 3.0) or (want_major == 3 and ver >= 3.0):
            out.append(p)
    return out





def _source_local(want_major: int) -> Path | None:
    ui.print_header(f"LOCAL FILE  (expecting RINEX {want_major})")
    ui.print_info("Paste or drag-and-drop the RINEX file path.")
    ui.print_info("Plain (.o / .rnx) and compressed (.gz / .Z) are accepted.")
    while True:
        raw = ui.get_input("File path")
        if not raw:
            return None
        raw = raw.strip().strip('"').strip("'")
        p = Path(raw)
        if not p.exists():
            ui.print_error(f"File not found: {p}")
            if not ui.get_yes_no("Try again?", True):
                return None
            continue
        if _looks_hatanaka(p):
            ui.print_error(HATANAKA_HINT)
            return None
        return p


def _source_folder(want_major: int) -> Path | None:
    ui.print_header(f"PICK A RINEX {want_major} FILE FROM A FOLDER")
    default = Path(_PROJECT_ROOT) / "output" / "observation"
    raw = ui.get_input("Folder containing observation files", str(default))
    folder = Path(raw.strip().strip('"').strip("'"))
    if not folder.is_dir():
        ui.print_error(f"Not a directory: {folder}")
        return None

    files = _candidate_files(folder, want_major)
    if not files:
        ui.print_error(f"No RINEX {want_major} observation files found there.")
        return None

    ui.print_info(f"Found {len(files)} RINEX {want_major} file(s):")
    for i, p in enumerate(files, 1):
        rel = p.relative_to(folder)
        size_kb = p.stat().st_size / 1024
        print(f"  {i:>3}. {rel}  ({size_kb:,.1f} KB)")

    while True:
        sel = ui.get_input(f"Select file number (1-{len(files)})")
        if not sel:
            return None
        try:
            idx = int(sel)
            if 1 <= idx <= len(files):
                return files[idx - 1]
        except ValueError:
            pass
        ui.print_error("Invalid selection.")


def _source_download(want_major: int) -> Path | None:


    if want_major != 2:
        ui.print_header("DOWNLOAD")
        ui.print_warning("CDDIS provides RINEX 3 observations only in Hatanaka "
                         "(.crx) form, which this tool does not process.")
        ui.print_info("For a RINEX 3 -> 2 conversion, use option 1 (local "
                      "file) with a plain .rnx file you already have.")
        return None

    ui.print_header("DOWNLOAD A PLAIN RINEX 2 (.o) FROM CDDIS")
    from gnsspy.data_access.observation import ObservationDownloader

    username, password = ui.login_flow()
    if not username:
        return None

    station = ui.get_input("Station code (4 chars, e.g. algo)")
    if not station or len(station) < 4:
        ui.print_error("Station code must be 4 characters.")
        return None

    date_str = ui.get_input("Date (YYYY-MM-DD or DD-MM-YYYY)")
    try:
        date = ui.parse_date(date_str)
    except ValueError as e:
        ui.print_error(str(e))
        return None

    out_dir = Path(_PROJECT_ROOT) / "output"
    od = ObservationDownloader(username, password, out_dir)
    yy = str(date.year)[-2:]
    doy = f"{date.timetuple().tm_yday:03d}"
    fn = f"{station.lower()[:4]}{doy}0.{yy}o.Z"
    url = od.build_url(date, fn, "o")
    fp = out_dir / "observation" / fn
    fp.parent.mkdir(parents=True, exist_ok=True)

    ui.print_info(f"Downloading {fn} ...")
    ok, msg = od.download_file(url, fp)
    if msg:
        ui.print_info(msg.splitlines()[0][:75])
    if not ok or not fp.exists() or fp.stat().st_size < 1000:
        ui.print_error("Plain RINEX 2 .o not available for that station/date. "
                       "Many modern stations only publish Hatanaka (.d).")
        ui.print_info("Tip: older IGS stations (e.g. algo, wtzr) usually have "
                      ".o files.")
        if fp.exists() and fp.stat().st_size < 1000:
            fp.unlink()
        return None

    od.extract_z(fp)
    plain = fp.with_suffix("")
    if plain.exists():
        ui.print_success(f"Downloaded & extracted: {plain.name}")
        return plain
    return fp





def _default_output_path(src: Path, target_version: float) -> Path:
    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    name = src.name
    if name.lower().endswith(".gz"):
        name = name[:-3]
    elif name.lower().endswith(".z"):
        name = name[:-2]
    stem = Path(name).stem
    if target_version >= 3.0:
        return DEFAULT_OUT_DIR / f"{stem}_v3.rnx"
    return DEFAULT_OUT_DIR / f"{stem}_v2.{datetime.datetime.now().year % 100:02d}o"


def _run_conversion(src: Path, target_version: float) -> None:
    ui.print_header("CONVERT")
    src_version = _detect_version(src)
    ui.print_success(f"Source : {src}")
    ui.print_success(f"         RINEX {src_version}  ->  RINEX {target_version}")

    keep = "GRES"
    if target_version < 3.0:
        ui.print_info("RINEX 2.11 supports GPS/GLONASS/Galileo/SBAS; "
                      "BeiDou/QZSS/IRNSS will be dropped.")
        if not ui.get_yes_no("Keep the standard set G/R/E/S? "
                             "(say no for GPS+GLONASS only)", True):
            keep = "GR"

    out_default = _default_output_path(src, target_version)
    out_raw = ui.get_input("Output file path", str(out_default))
    out = Path(out_raw.strip().strip('"').strip("'"))
    out.parent.mkdir(parents=True, exist_ok=True)

    ui.print_info("Converting ...")
    try:
        convert_file(src, out, target_version=target_version, keep_systems=keep)
    except Exception as e:
        ui.print_error(f"Conversion failed: {e}")
        import traceback
        traceback.print_exc()
        return

    ui.print_success(f"Written : {out}")
    try:
        data = parse_file(out)
        ui.print_success(f"Epochs  : {len(data.epochs)}")
        ui.print_success(f"Systems : {', '.join(data.systems()) or 'none'}")
        for s, codes in data.header.obs_types.items():
            if s in data.systems():
                ui.print_info(f"  {s}: {' '.join(codes)}")
    except Exception as e:
        ui.print_warning(f"Could not re-parse output for summary: {e}")





def main() -> None:

    ui.print_header("RINEX CONVERTER")
    print("  Which conversion do you want?")
    print("  1. RINEX 2  ->  RINEX 3")
    print("  2. RINEX 3  ->  RINEX 2")
    print("  3. Back to main menu")
    print("-" * 50)
    d = ui.get_input("Select (1-3)", "1")
    if d == "3":
        return
    if d == "1":
        want_major, target_version = 2, 3.04
    elif d == "2":
        want_major, target_version = 3, 2.11
    else:
        ui.print_error("Invalid selection.")
        return


    ui.print_header(f"RINEX {want_major}  ->  RINEX {3 if want_major == 2 else 2}")
    print(f"  Where is the RINEX {want_major} file?")
    print("  1. A file on this PC (paste / drag-and-drop)")
    print("  2. Pick from an existing folder")
    print("  3. Download a fresh file from CDDIS"
          + ("" if want_major == 2 else "  (not available for RINEX 3)"))
    print("  4. Back")
    print("-" * 50)
    s = ui.get_input("Select (1-4)", "1")
    if s == "1":
        src = _source_local(want_major)
    elif s == "2":
        src = _source_folder(want_major)
    elif s == "3":
        src = _source_download(want_major)
    elif s == "4":
        return
    else:
        ui.print_error("Invalid selection.")
        return

    if src is None:
        ui.print_warning("No file selected. Aborting.")
        return


    try:
        actual = _detect_version(src)
    except ValueError as e:
        ui.print_error(str(e))
        return
    actual_major = 2 if actual < 3.0 else 3
    if actual_major != want_major:
        ui.print_warning(f"You chose RINEX {want_major} -> "
                         f"{3 if want_major == 2 else 2}, but this file is "
                         f"RINEX {actual}.")
        if ui.get_yes_no("Convert it the other way instead?", True):
            target_version = 2.11 if actual_major == 3 else 3.04
        else:
            ui.print_info("Aborted.")
            return

    _run_conversion(src, target_version)


if __name__ == "__main__":
    main()
