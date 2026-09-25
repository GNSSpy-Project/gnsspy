"""Shared, local-first SP3/CLK filename handling (no network side effects).

Names describe products; they are not a prerequisite for reading their contents.
The metadata here are nominal filename metadata, not a validation of orbit quality.
"""
from __future__ import annotations

import bz2
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
import gzip
import io
import lzma
from pathlib import Path
import re
from typing import Iterable

COMPRESSION = (".gz", ".z", ".bz2", ".xz")
SOLUTION_CODES = {"final": "FIN", "rapid": "RAP", "ultra-rapid": "ULT"}
SOLUTION_NAMES = {v: k for k, v in SOLUTION_CODES.items()}
SOLUTION_RANK = {"FIN": 0, "RAP": 1, "ULT": 2}
ALIASES = {"CODE": "COD", "COM": "COD", "GBM": "GFZ", "IGR": "IGS", "IGU": "IGS"}
MGEX_CENTRES = {"COD", "GFZ", "WUM", "GRG", "JAX", "IAC", "SHA"}
LONG = re.compile(
    r"^(?P<center>[A-Z0-9]{3})(?P<version>\d)(?P<project>[A-Z0-9]{3})"
    r"(?P<solution>[A-Z0-9]{3})_(?P<stamp>\d{11})_"
    r"(?P<duration>\d{2}[DHMSU])_(?P<sampling>\d{2}[DHMSU])_"
    r"(?P<content>ORB|CLK)\.(?P<kind>SP3|CLK)$", re.I)
LEGACY = re.compile(r"^(?P<center>[A-Z]{3})(?P<week>\d{4})(?P<day>[0-7])"
                    r"(?:_(?P<hour>\d{2}))?\.(?P<kind>sp3|clk)(?:_(?P<rate>\d{2})s)?$", re.I)


def as_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError("epoch must be datetime.date or datetime.datetime")


def normalise_center(value: str) -> str:
    text = str(value).upper()
    text = ALIASES.get(text, text)
    if not re.fullmatch(r"[A-Z0-9]{3}", text):
        raise ValueError(f"Invalid analysis centre {value!r}; use e.g. CODE, COD, GFZ, EMR or IGS")
    return text


def normalise_orbit_type(value: str) -> str:
    text = str(value).lower().replace("_", "-")
    text = {"fin": "final", "rap": "rapid", "ult": "ultra-rapid",
            "ultrarapid": "ultra-rapid"}.get(text, text)
    if text not in {"auto", *SOLUTION_CODES}:
        raise ValueError(f"Unknown orbit_type {value!r}; choose auto, final, rapid or ultra-rapid")
    return text


def token_seconds(token: str) -> float | None:
    token = token.upper()
    if not re.fullmatch(r"\d{2}[DHMSU]", token):
        raise ValueError(f"Invalid duration/sampling token: {token!r}")
    return None if token[-1] == "U" else int(token[:2]) * {"D":86400, "H":3600, "M":60, "S":1}[token[-1]]


def strip_compression(path) -> tuple[str, str]:
    name = Path(path).name
    for suffix in COMPRESSION:
        if name.lower().endswith(suffix):
            return name[:-len(suffix)], name[-len(suffix):]
    return name, ""


def product_kind(path) -> str | None:
    name, _ = strip_compression(path)
    if name.lower().endswith(".sp3"):
        return "sp3"
    if re.search(r"\.clk(?:_\d+s)?$", name, re.I):
        return "clk"
    return None


@dataclass(frozen=True)
class ProductName:
    path: Path
    center: str
    project: str
    solution: str
    start: datetime
    duration: str
    sampling: str
    kind: str
    version: str = "0"
    legacy: bool = False

    @property
    def end(self) -> datetime:
        seconds = token_seconds(self.duration)
        return self.start + timedelta(seconds=seconds or 86400)

    @property
    def family(self) -> tuple[str, str, str, str]:
        return self.center, self.project, self.solution, self.version

    def overlaps(self, start: datetime, end: datetime) -> bool:
        return self.start < end and self.end > start


def parse_product_name(path) -> ProductName | None:
    """Parse long and legacy SP3/CLK names, case-insensitively.

    Legacy IGS ultra-rapid labels refer to prediction start (one day after
    the observed-data start); modern names refer to the content start.
    """
    path = Path(path)
    name, _ = strip_compression(path)
    match = LONG.fullmatch(name)
    try:
        if match:
            fields = {k: v.upper() for k,v in match.groupdict().items()}
            if (fields["content"], fields["kind"]) not in {("ORB","SP3"),("CLK","CLK")}:
                return None
            stamp = fields["stamp"]
            start = datetime.strptime(stamp, "%Y%j%H%M")
            if start.strftime("%Y%j%H%M") != stamp:
                return None
            return ProductName(path, normalise_center(fields["center"]), fields["project"],
                               fields["solution"], start, fields["duration"], fields["sampling"],
                               fields["kind"].lower(), fields["version"])
        match = LEGACY.fullmatch(name)
        if not match:
            return None
        raw = match["center"].upper()
        day = int(match["day"])
        start = datetime(1980,1,6) + timedelta(weeks=int(match["week"]), days=min(day,6))
        duration = "07D" if day == 7 else "01D"
        if day == 7:
            start -= timedelta(days=6)
        solution = {"IGR":"RAP", "IGU":"ULT"}.get(raw,"FIN")
        if solution == "ULT":
            hour = int(match["hour"] or 0)
            if hour > 23:
                return None
            start += timedelta(hours=hour, days=-1)
            duration = "02D"
        center = normalise_center(raw)
        project = "MGX" if raw in {"COM","GBM","WUM","GRG","JAX"} else "OPS"
        kind = match["kind"].lower()
        sampling = (f'{match["rate"]}S' if match["rate"] else "30S") if kind == "clk" else "15M"
        return ProductName(path, center, project, solution, start, duration, sampling, kind, legacy=True)
    except (ValueError, OverflowError):
        return None


def product_spec(product="auto") -> tuple[str | None, str | None, str | None, str | None]:
    """A centre, legacy alias, or full series identifier (e.g. COD0MGXFIN)."""
    if product is None or str(product).lower() in {"auto", "any"}:
        return None, None, None, None
    text = str(product).upper()
    if re.fullmatch(r"[A-Z0-9]{3}\d[A-Z0-9]{6}", text):
        return normalise_center(text[:3]), text[4:7], text[7:10], text[3]
    return normalise_center(text), None, {"IGR":"RAP", "IGU":"ULT"}.get(text), None


def matches_product(info: ProductName, product="auto", orbit_type="auto") -> bool:
    center, project, solution, version = product_spec(product)
    orbit_type = normalise_orbit_type(orbit_type)
    required_solution = SOLUTION_CODES.get(orbit_type, solution)
    return (all(expected is None or expected == actual for expected,actual in
                zip((center,project,solution,version), info.family))
            and (required_solution is None or required_solution == info.solution))


def search_directories(data_dir=None, kind="sp3") -> list[Path]:
    root = Path(data_dir).expanduser() if data_dir is not None else Path.cwd()
    roots = [root, root/kind, root/"data", root/"data"/kind,
             root/"output", root/"output"/kind, root/"output"/"data"/kind]
    if root.name.lower() == kind:
        roots += [root.parent, root.parent/kind]
    return list(dict.fromkeys(p.resolve() for p in roots))


def local_product_paths(data_dir=None, kind="sp3") -> list[Path]:
    result = []
    for directory in search_directories(data_dir, kind):
        if directory.is_dir():
            result.extend(p for p in sorted(directory.iterdir()) if p.is_file() and product_kind(p) == kind)
    return list(dict.fromkeys(p.resolve() for p in result))


def product_sort_key(info: ProductName, preferred_center=None):
    return (SOLUTION_RANK.get(info.solution,9),
            0 if preferred_center is None or info.center == preferred_center else 1,
            info.center,
            0 if info.project == ("MGX" if info.center in MGEX_CENTRES else "OPS") else 1,
            info.project, info.version,
            token_seconds(info.duration) or float("inf"),
            token_seconds(info.sampling) or float("inf"),
            -info.start.timestamp(),
            bool(strip_compression(info.path)[1]), str(info.path))


def find_product_files(epoch, kind="sp3", product="auto", orbit_type="auto", data_dir=None,
                       files: Iterable | None = None) -> list[ProductName]:
    """Return existing named products whose nominal spans overlap a day.

    Selection does not depend on today's date or publication-latency estimates.
    Use file headers and actual epochs when deciding interpolation coverage.
    """
    day = as_date(epoch)
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    candidates = local_product_paths(data_dir,kind) if files is None else [Path(p).resolve() for p in files]
    output = []
    for path in dict.fromkeys(candidates):
        info = parse_product_name(path)
        if (path.is_file() and path.stat().st_size and info and info.kind == kind
                and info.overlaps(start,end) and matches_product(info,product,orbit_type)):
            output.append(info)
    center = product_spec(product)[0]
    return sorted(output, key=lambda info: product_sort_key(info,center))


@contextmanager
def open_product_text(path):
    """Read text without extracting/renaming. .Z requires the declared unlzw3 dependency."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".z":
        try:
            from unlzw3 import unlzw
        except ImportError as exc:
            raise ImportError("Reading .Z products requires unlzw3; install it or decompress the file first") from exc
        with io.StringIO(unlzw(path.read_bytes()).decode("ascii")) as stream:
            yield stream
    else:
        opener = {".gz":gzip.open, ".bz2":bz2.open, ".xz":lzma.open}.get(suffix,open)
        with opener(path,"rt",encoding="ascii") as stream:
            yield stream


def validate_product_file(path, kind=None) -> bool:
    """Lightweight cache check: header plus a first usable data record, not full QC."""
    kind = kind or product_kind(path)
    try:
        with open_product_text(path) as stream:
            first = stream.readline()
            if kind == "sp3":
                if not re.match(r"#[a-dA-D][PVpv]",first):
                    return False
                for line in stream:
                    if line.startswith("P") and len(line) >= 60:
                        for a,b in [(4,18),(18,32),(32,46),(46,60)]:
                            float(line[a:b].replace("D","E"))
                        return True
            elif kind == "clk":
                if "RINEX VERSION / TYPE" not in first or "C" not in first[:40]:
                    return False
                for line in stream:
                    if line.startswith("AS "):
                        parts = line.split()
                        float(parts[9].replace("D","E"))
                        return True
    except (OSError, ValueError, UnicodeError, EOFError, IndexError, ImportError):
        return False
    return False


def resolve_product_path(filename, kind=None, data_dir=None) -> Path:
    """Resolve an existing path, its compression variant, or a sampling variant.

    An existing explicitly supplied path is authoritative. A missing recognised
    filename may resolve only to the same centre/project/solution whose nominal
    span overlaps the requested day (including a weekly product).
    No download, rename, centre switch, or final-to-ultra-rapid substitution.
    """
    path = Path(filename).expanduser()
    if path.is_file():
        return path.resolve()
    kind = kind or product_kind(path)
    if kind not in {"sp3","clk"}:
        raise FileNotFoundError(f"Product file not found: {filename}")
    directories = [path.parent.resolve()] + search_directories(data_dir,kind)
    requested, _ = strip_compression(path)
    for directory in dict.fromkeys(directories):
        if not directory.is_dir():
            continue
        matches = [p for p in directory.iterdir() if p.is_file()
                   and strip_compression(p)[0].lower() == requested.lower()]
        if matches:
            return sorted(matches,key=lambda p:(bool(strip_compression(p)[1]),str(p)))[0].resolve()
    info = parse_product_name(path)
    if info:
        candidates = []
        for directory in dict.fromkeys(directories):
            if directory.is_dir():
                candidates += [p for p in directory.iterdir() if p.is_file() and product_kind(p) == kind]
        product = info.center if info.legacy else ''.join((info.center,info.version,info.project,info.solution))
        matches = find_product_files(info.start.date(),kind,product,
                                     SOLUTION_NAMES.get(info.solution,"auto"),files=candidates)
        if matches:
            return matches[0].path
    raise FileNotFoundError(
        f"{kind.upper()} file not found: {filename}. Supply its actual path (long names and compressed "
        "files are supported), or download it explicitly with NavigationDownloader. No file was renamed.")


def long_product_filename(epoch, kind="sp3", center="IGS", project=None, solution="FIN",
                          duration=None, sampling=None, hour=0, minute=0, version="0") -> str:
    day = as_date(epoch)
    center = normalise_center(center)
    project = (project or ("MGX" if center in MGEX_CENTRES else "OPS")).upper()
    solution = SOLUTION_CODES.get(str(solution).lower(), str(solution).upper())
    if solution not in SOLUTION_RANK:
        raise ValueError("solution must be FIN, RAP or ULT")
    if kind not in {"sp3","clk"}:
        raise ValueError("kind must be sp3 or clk")
    if not re.fullmatch(r"[A-Z0-9]{3}",project) or not re.fullmatch(r"\d",str(version)):
        raise ValueError("Invalid product project/version")
    stamp = datetime(day.year,day.month,day.day,hour,minute).strftime("%Y%j%H%M")
    duration = duration or ("02D" if solution == "ULT" else "01D")
    sampling = sampling or ("30S" if kind == "clk" else "05M" if project == "MGX" else "15M")
    token_seconds(duration); token_seconds(sampling)
    return (f"{center}{version}{project}{solution}_{stamp}_{duration.upper()}_{sampling.upper()}_"
            f"{'ORB.SP3' if kind == 'sp3' else 'CLK.CLK'}")
