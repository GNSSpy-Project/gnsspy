"""Non-interactive maps from local SP3 and IONEX products."""
from __future__ import annotations
import argparse
from pathlib import Path
import sys


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="kind", required=True)
    for name, help_text in [("groundtrack", "Satellite ground tracks from SP3"),
                            ("ionosphere", "Vertical TEC/RMS maps from IONEX")]:
        s = sub.add_parser(name, help=help_text)
        s.add_argument("input", type=Path, help="Local SP3 or IONEX file (compressed input accepted)")
        s.add_argument("--backend", choices=("cartopy", "plotly"), default="cartopy")
        s.add_argument("--output", type=Path, help="PNG/PDF/SVG for Cartopy; HTML for Plotly")
        s.add_argument("--projection", default="robinson",
                       choices=("robinson", "platecarree", "mollweide", "naturalearth",
                                "equalearth", "mercator"))
        s.add_argument("--central-longitude", type=float, default=0)
        s.add_argument("--extent", nargs=4, type=float, metavar=("WEST", "EAST", "SOUTH", "NORTH"))
        s.add_argument("--no-features", action="store_true", help="No Natural Earth features/downloads")
        s.add_argument("--resolution", choices=("110m", "50m", "10m"), default="110m",
                       help="Cartopy Natural Earth resolution")
        s.add_argument("--dpi", type=float, default=200, help="Cartopy static output resolution")
        s.add_argument("--title")
        if name == "groundtrack":
            s.add_argument("--system", default="ALL", help="ALL, G, E, G+E+C, etc.")
            s.add_argument("--sv", nargs="+", help="Satellite identifiers, e.g. G01 G03 E11")
            s.add_argument("--latitude-type", choices=("geodetic", "geocentric"), default="geodetic")
            s.add_argument("--max-gap", type=float, help="Maximum connected time gap in seconds")
        else:
            group = s.add_mutually_exclusive_group()
            group.add_argument("--epochs", nargs="+", help="Exact UTC timestamps from the file")
            group.add_argument("--hours", nargs="+", type=int, help="Exact UTC hours on --date/first source date")
            s.add_argument("--date", help="Date for --hours (YYYY-MM-DD)")
            s.add_argument("--field", choices=("tec", "rms"), default="tec")
            s.add_argument("--vmin", type=float)
            s.add_argument("--vmax", type=float)
            s.add_argument("--cmap", help="Cartopy default batlow_r; Plotly default Viridis")
            s.add_argument("--ncols", type=int, default=2)
            s.add_argument(
                "--coordinate-labels", action=argparse.BooleanOptionalAction,
                default=None,
                help="label longitude/latitude axes (default: on for --extent, off globally)",
            )
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    from gnsspy.visualization import groundtrack, ionosphere_maps
    output = args.output or Path(f"{args.kind}.{'png' if args.backend == 'cartopy' else 'html'}")
    options = dict(backend=args.backend, projection=args.projection,
                   central_longitude=args.central_longitude, extent=args.extent,
                   features=not args.no_features, save_path=output)
    if args.title is not None:
        options["title"] = args.title
    if args.backend == "cartopy":
        options.update(resolution=args.resolution, dpi=args.dpi)
    try:
        if args.backend == "cartopy":
            import matplotlib
            matplotlib.use("Agg")
        if args.kind == "groundtrack":
            from gnsspy import read_sp3File
            fig = groundtrack(read_sp3File(args.input, verbose=False), system=args.system,
                              sv_list=args.sv, latitude_type=args.latitude_type,
                              max_gap=args.max_gap, **options)
        else:
            import pandas as pd
            from gnsspy import read_ionex
            gim = read_ionex(args.input)
            epochs = args.epochs
            if args.date is not None and args.hours is None:
                raise ValueError("--date must be used with --hours")
            if args.hours is not None:
                if any(h < 0 or h > 23 for h in args.hours):
                    raise ValueError("--hours must be between 0 and 23")
                day = pd.Timestamp(args.date).normalize() if args.date else gim.epochs.min().normalize()
                epochs = [day + pd.Timedelta(hours=h) for h in args.hours]
            fig = ionosphere_maps(gim, epochs=epochs, field=args.field,
                                  vmin=args.vmin, vmax=args.vmax, cmap=args.cmap,
                                  ncols=args.ncols,
                                  coordinate_labels=args.coordinate_labels,
                                  **options)
        if args.backend == "cartopy":
            import matplotlib.pyplot as plt
            plt.close(fig)
        from gnsspy.visualization._maps import output_path
        print(f"Saved: {output_path(output, args.backend).resolve()}")
    except Exception as exc:
        print(f"Map failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
