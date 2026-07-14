"""Command-line interface for the RINEX 2 <-> 3 converter.

Usage:
    python -m rinex_converter <input> <output> [--target 2|3] [--keep GRECJIS]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .convert import convert_file


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="rinex_converter",
        description="Convert between RINEX 2 and RINEX 3 observation files.",
    )
    p.add_argument("input", type=Path, help="Source observation file (.o / .rnx)")
    p.add_argument("output", type=Path, help="Destination file path")
    p.add_argument(
        "--target",
        type=float,
        default=None,
        help="Target RINEX version (e.g. 2.11 or 3.04). "
             "If omitted, the opposite version of the source is used.",
    )
    p.add_argument(
        "--keep",
        type=str,
        default="GR",
        help="Systems to keep when writing RINEX 2 (default: GR). "
             "Use e.g. GRECJIS to keep all.",
    )
    args = p.parse_args(argv)

    if not args.input.exists():
        print(f"error: input file not found: {args.input}", file=sys.stderr)
        return 2

    convert_file(args.input, args.output,
                 target_version=args.target,
                 keep_systems=args.keep)
    print(f"OK: {args.input} -> {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
