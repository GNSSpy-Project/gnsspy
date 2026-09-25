#!/usr/bin/env python3
"""Exercise maps and optional non-geographic plots with labelled synthetic data.

Run from the installed source tree:
  python examples/plot_demo.py
  python examples/plot_demo.py --backend both --non-geographic
  python examples/plot_demo.py --no-features
"""
from pathlib import Path
import argparse
import json
import sys
import traceback


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from synthetic_data import make_demo_data, write_sample_files


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend', choices=['cartopy', 'plotly', 'both'], default='cartopy')
    parser.add_argument('--output-dir', type=Path, default=Path('plot_demo_output'))
    parser.add_argument('--no-features', action='store_true', help='No Cartopy basemap downloads')
    parser.add_argument('--non-geographic', action='store_true', help='Also exercise the five retained Plotly views')
    parser.add_argument('--generate-only', action='store_true', help='Only write synthetic SP3/IONEX inputs')
    parser.add_argument('--cmap', help='Override map colour palette, e.g. viridis')
    args = parser.parse_args(argv)
    if args.backend in {'cartopy', 'both'} and not args.generate_only:
        import matplotlib
        matplotlib.use('Agg')
    from gnsspy import __version__, read_sp3File, read_ionex
    from gnsspy.visualization import (groundtrack, ionosphere_map, ionosphere_maps,
                                     skyplot, azelplot, timelplot, bandplot)
    orbit, gim, station = make_demo_data()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sp3_path, ionex_path = write_sample_files(output/'data', orbit, gim)
    print(f'GNSSpy {__version__}; all example data are SYNTHETIC.')
    print(f'Inputs: {sp3_path}\n        {ionex_path}')
    if args.generate_only:
        return 0

    raw_orbit = read_sp3File(sp3_path, verbose=False)
    native_gim = read_ionex(ionex_path)
    outcomes = []
    def run(name, function, *positional, **kwargs):
        path = output/name
        try:
            fig = function(*positional, save_path=path, **kwargs)
            if fig is None or not path.exists() or path.stat().st_size == 0:
                raise RuntimeError('The expected plot file was not created')
            if hasattr(fig, 'savefig'):
                import matplotlib.pyplot as plt
                plt.close(fig)
            outcomes.append(dict(name=name, status='passed', bytes=path.stat().st_size))
            print(f'PASS {name}')
        except Exception as exc:
            outcomes.append(dict(name=name, status='failed', error=str(exc)))
            print(f'FAIL {name}: {exc}', file=sys.stderr)
            traceback.print_exc()
    backends = ['cartopy', 'plotly'] if args.backend == 'both' else [args.backend]
    for backend in backends:
        suffix = 'png' if backend == 'cartopy' else 'html'
        common = dict(backend=backend, features=not args.no_features)
        run(f'groundtracks_{backend}.{suffix}', groundtrack, raw_orbit,
            system=None, title='SYNTHETIC — satellite ground tracks', **common)
        run(f'tec_12UTC_{backend}.{suffix}', ionosphere_map, native_gim,
            epoch='2024-01-14T12:00:00', cmap=args.cmap, vmin=0, vmax=60,
            title='SYNTHETIC — vertical TEC', **common)
        run(f'tec_regional_{backend}.{suffix}', ionosphere_map, native_gim,
            epoch='2024-01-14T12:00:00', cmap=args.cmap, vmin=0, vmax=60,
            projection='platecarree', extent=[20, 45, 30, 50],
            title='SYNTHETIC — regional vertical TEC', **common)
        run(f'tec_4hour_panels_{backend}.{suffix}', ionosphere_maps, native_gim,
            cmap=args.cmap, vmin=0, vmax=60, ncols=2,
            title='SYNTHETIC — four-hour TEC maps', **common)
        run(f'rms_12UTC_{backend}.{suffix}', ionosphere_map, native_gim,
            epoch='2024-01-14T12:00:00', field='rms', cmap=args.cmap,
            title='SYNTHETIC — IONEX RMS', **common)
        run(f'groundtracks_regional_{backend}.{suffix}', groundtrack, raw_orbit,
            system=None, projection='platecarree', extent=[-20, 65, 10, 70],
            title='SYNTHETIC — regional satellite ground tracks', **common)
    if args.non_geographic:
        run('skyplot_plotly.html', skyplot, station, orbit, system='G')
        run('azimuth_elevation_plotly.html', azelplot, station, orbit, system='G')
        run('elevation_time_plotly.html', timelplot, station, orbit, system='G', mode='elevation')
        run('snr_time_plotly.html', timelplot, station, system='G', mode='snr')
        run('visibility_plotly.html', bandplot, station, system='G')
    failures = sum(item['status'] != 'passed' for item in outcomes)
    report = dict(gnsspy_version=__version__, synthetic=True,
                  features=not args.no_features, plots=outcomes,
                  passed=len(outcomes)-failures, failed=failures,
                  note='Figure creation/file writing only; inspect maps visually. Not a scientific accuracy validation.')
    (output/'demo_report.json').write_text(json.dumps(report, indent=2)+'\n')
    print(f'Report: {output / "demo_report.json"}')
    return 1 if failures else 0


if __name__ == '__main__':
    raise SystemExit(main())
