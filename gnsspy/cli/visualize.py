import os
import sys
import getpass
import datetime
import shutil
import gzip
import warnings
import glob
from pathlib import Path




PROJECT_ROOT = str(Path(__file__).resolve().parents[2])

from gnsspy.io.manipulate import crx2rnx
from gnsspy.utils.product_files import find_product_files, parse_product_name

try:
    from gnsspy.cli import download as downloader
    from gnsspy.data_access.products import NavigationDownloader

    from gnsspy.io.rinex.observation import read_obsFile
    from gnsspy.io.rinex.navigation import read_navFile
    from gnsspy.io.products.sp3 import read_sp3File
    from gnsspy.io.manipulate import crx2rnx
    from gnsspy.visualization import skyplot, azelplot, bandplot, timelplot, groundtrack
    from gnsspy.orbit.precise import sp3_interp
    from gnsspy.orbit.broadcast import calculate_orbit_from_nav

except ImportError as e:
    print(f"[CRITICAL ERROR] Modules could not be loaded: {e}")
    sys.exit(1)


def get_gps_week_day(date_obj):
    if isinstance(date_obj, datetime.datetime): date_obj = date_obj.date()
    delta = date_obj - datetime.date(1980, 1, 6)
    return delta.days // 7, delta.days % 7

def extract_compressed_file(filepath):
    """Automatically extracts .gz or .Z compressed files."""
    file_lower = filepath.lower()
    output_path = os.path.splitext(filepath)[0]

    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
        return output_path, True

    try:
        if file_lower.endswith('.gz'):
            with gzip.open(filepath, 'rb') as f_in:
                with open(output_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return output_path, True
        elif file_lower.endswith('.z'):
            try:
                import unlzw3
                with open(filepath, 'rb') as f_in:
                    f_out_content = unlzw3.unlzw(f_in.read())
                with open(output_path, 'wb') as f_out:
                    f_out.write(f_out_content)
                return output_path, True
            except:
                return filepath, False
    except Exception as e:
        return filepath, False
    return filepath, False

def detect_agency_from_filename(filename):
    info = parse_product_name(filename)
    return info.center.lower() if info else 'auto'


def create_legacy_bridge(sp3_dir, target_date, center):
    """Deprecated no-op; supply product paths directly to the reader."""
    warnings.warn('create_legacy_bridge is deprecated; pass product paths directly to the reader.',
                  DeprecationWarning,stacklevel=2)


def find_files_for_date(output_dir, target_date, station, needs_sp3=True, priority_agency=None):
    doy = target_date.timetuple().tm_yday
    str_doy = f"{doy:03d}"
    year_long = str(target_date.year)

    obs_path = None
    sp3_path = None


    obs_dir = os.path.join(output_dir, "observation")
    if os.path.exists(obs_dir):
        for root, _, files in os.walk(obs_dir):
            for f in files:
                f_low = f.lower()
                if station.lower() not in f_low: continue
                if (str_doy in f):
                    if f_low.endswith(('.rnx', '.crx', '.crx.gz', 'o', 'd', 'd.z')):
                         obs_path = os.path.join(root, f); break
            if obs_path: break


    if needs_sp3:
        matches = find_product_files(target_date,'sp3',product=priority_agency or 'auto',
                                     data_dir=output_dir)
        if matches:
            sp3_path = str(matches[0].path)

    return obs_path, sp3_path

def manage_login():
    """Return Earthdata credentials for visualization workflows.

    Credentials are read through GNSSpy's shared downloader login flow. If the
    user chooses to save them, they are written to the standard `.netrc` file
    with restricted permissions instead of a plain `user_config.txt` file.
    """
    print("\n[Login] CDDIS / NASA Earthdata Login")
    username, password = downloader.login_flow()

    if username and password:
        save = input("   Save credentials to .netrc? (y/N) [n]: ").strip().lower()
        if save in ['y', 'yes']:
            try:
                from gnsspy.data_access.utils import save_credentials
                ok, msg = save_credentials(username, password)
                if ok:
                    print(f"   {msg}")
                else:
                    print(f"   Credentials were not saved: {msg}")
            except Exception as exc:
                print(f"   Credentials were not saved: {exc}")
    return username, password

def select_plots_interactive():
    print("\n" + "="*40)
    print(" SELECT PLOTS TO GENERATE ".center(40, '='))
    print("="*40)
    print("1. Skyplot (Requires Orbit)")
    print("2. Azimuth-Elevation (Requires Orbit)")
    print("3. Elevation Time Series (Requires Orbit)")
    print("4. SNR Time Series (Observation Only)")
    print("5. Bandplot/Visibility (Observation Only)")
    print("6. Groundtrack (Requires Orbit)")
    print("7. ALL PLOTS")

    selection = input("\nSelect plots (e.g., 1,4 or 7): ").strip()
    selected_plots = []
    needs_sp3 = False

    if selection == '7' or selection == '':
        selected_plots = ['skyplot', 'azel', 'elevation', 'snr', 'bandplot', 'groundtrack']
        needs_sp3 = True
    else:
        parts = selection.split(',')
        if '1' in parts: selected_plots.append('skyplot'); needs_sp3 = True
        if '2' in parts: selected_plots.append('azel'); needs_sp3 = True
        if '3' in parts: selected_plots.append('elevation'); needs_sp3 = True
        if '4' in parts: selected_plots.append('snr')
        if '5' in parts: selected_plots.append('bandplot')
        if '6' in parts: selected_plots.append('groundtrack'); needs_sp3 = True

    print(f"   [+] Selected: {', '.join(selected_plots).upper()}")
    return selected_plots, needs_sp3

def render_plots(station, orbit, analyses_dir, base_name, config, selected_plots):
    """Render selected plots; return paths only after confirming saved output."""
    from gnsspy.visualization._maps import backend_name
    backend = backend_name(config.get('map_backend', 'cartopy'))
    fmt = 'html' if backend == 'plotly' else config.get('map_format', 'png').lower()
    if backend == 'cartopy' and fmt not in {'png', 'pdf', 'svg'}:
        raise ValueError('map_format must be png, pdf or svg for Cartopy')
    directory = Path(analyses_dir)
    directory.mkdir(parents=True, exist_ok=True)
    names = {'skyplot': 'Skyplot', 'azel': 'AzEl', 'elevation': 'Elevation',
             'snr': 'SNR', 'bandplot': 'BandPlot', 'groundtrack': 'Groundtrack'}
    common = dict(system=config.get('system', 'G'), sv_list=config.get('sv_list'))
    colour = config.get('color_mode', 'snr')
    outputs = []
    for kind in selected_plots:
        if kind not in names:
            raise ValueError(f'Unknown plot: {kind}')
        if kind != 'groundtrack' and station is None:
            raise ValueError(f'{kind} requires observations')
        if kind in {'skyplot', 'azel', 'elevation', 'groundtrack'} and orbit is None:
            raise ValueError(f'{kind} requires orbit data')
        ext = fmt if kind == 'groundtrack' else 'html'
        path = directory / f'{base_name}_{names[kind]}.{ext}'
        png_path = (path.with_suffix('.png')
                    if kind != 'groundtrack' and config.get('plotly_png', False)
                    else None)
        png_options = dict(png_path=png_path,
                           png_scale=config.get('plotly_png_scale', 2.0))
        if kind == 'groundtrack':
            options = dict(backend=backend, projection=config.get('map_projection', 'robinson'),
                           features=config.get('map_features', True))
            if backend == 'cartopy':
                options.update(dpi=config.get('map_dpi', 200),
                               resolution=config.get('map_resolution', '110m'))
            fig = groundtrack(orbit, **common, save_path=path, **options)
            if backend == 'cartopy':
                import matplotlib.pyplot as plt
                plt.close(fig)
        elif kind == 'skyplot':
            fig = skyplot(station, orbit, **common, color_mode=colour,
                          save_path=str(path), snr_code=config.get('snr_code', 'auto'),
                          **png_options)
        elif kind == 'azel':
            fig = azelplot(station, orbit, **common, color_mode=colour,
                           save_path=str(path), snr_code=config.get('snr_code', 'auto'),
                           **png_options)
        elif kind in {'elevation', 'snr'}:
            fig = timelplot(station, orbit, **common, mode=kind,
                            save_path=str(path), snr_code=config.get('snr_code', 'auto'),
                            **png_options)
        else:
            fig = bandplot(station, **common, save_path=str(path), **png_options)
        expected = [path] + ([png_path] if png_path is not None else [])
        for result in expected:
            if fig is None or not result.is_file() or result.stat().st_size == 0:
                raise RuntimeError(f'{kind} did not produce the expected output: {result}')
            outputs.append(result)
            config.setdefault('_generated_files', []).append(str(result.resolve()))
            print(f'   [+] Saved: {result}')
    return outputs


def process_single_day(date, station, output_dir, analyses_dir, config, selected_plots, needs_sp3):
    print(f"\n>>> PROCESSING: {date} ({station})")

    sys_code = config.get('system', 'G')
    needs_brdc = sys_code in ['I', 'J']
    preferred_agency = config.get('sp3_product', 'auto')


    obs_path, sp3_path = find_files_for_date(output_dir, date, station, needs_sp3, priority_agency=preferred_agency)

    if selected_plots == ['groundtrack'] and sp3_path:
        try:
            orbit = read_sp3File(sp3_path)
            render_plots(None, orbit, analyses_dir, f"{station}_{date}", config, selected_plots)
            return True
        except Exception as exc:
            print(f"   [!] Ground-track plotting failed: {exc}")
            return False

    if not obs_path:
        print(f"   [!] Observation file missing for {date}"); return False


    if needs_brdc:
        needs_sp3 = False

    if needs_sp3 and not needs_brdc:
        if not sp3_path:
            print(f"   [!] SP3 file missing for {date} (Expected: {preferred_agency})"); return False

        print(f"   [Process] Found SP3: {os.path.basename(sp3_path)}")


    lower_path = obs_path.lower()
    if lower_path.endswith(('.gz', '.z')):
        obs_path, _ = extract_compressed_file(obs_path)
        lower_path = obs_path.lower()

    if lower_path.endswith('.crx'):
        rnx_path = obs_path[:-4] + '.rnx'
        if not os.path.exists(rnx_path):
            print("   [Process] Unpacking .crx..."); crx2rnx(obs_path)
        obs_path = rnx_path
    elif lower_path.endswith('d'):
        rnx_path = obs_path[:-1] + 'o'
        if not os.path.exists(rnx_path):
            print("   [Process] Unpacking .d..."); crx2rnx(obs_path)
        obs_path = rnx_path

    try:


        sys_code = config.get('system', 'G')

        print(f"   [Process] Reading OBS...")
        st_data = read_obsFile(obs_path)
        or_data = None





        if needs_brdc:

            print(f"   [Process] Calculating orbit from BRDC for system {sys_code}...")
            try:

                brdc_path = None
                brdc_dirs = [
                    os.path.join(output_dir, "brdc"),
                    os.path.join(output_dir, "navigation"),
                    os.path.join(os.getcwd(), "gnsspy", "backend", "data", "brdc"),
                    os.path.join(output_dir)
                ]

                doy = date.timetuple().tm_yday
                year = date.year

                for brdc_dir in brdc_dirs:
                    if not os.path.exists(brdc_dir):
                        continue
                    for f in os.listdir(brdc_dir):
                        f_upper = f.upper()

                        if ('BRDC' in f_upper or 'MN' in f_upper or f_upper.endswith('N') or f_upper.endswith('.RNX')):
                            if f"{doy:03d}" in f or f"{year}" in f:
                                brdc_path = os.path.join(brdc_dir, f)
                                break
                    if brdc_path:
                        break

                if not brdc_path:
                    print(f"   [!] BRDC/Navigation file not found for {date}")
                    print("   [!] Cannot calculate orbits for IRNSS/QZSS without BRDC.")
                    or_data = None
                else:

                    if brdc_path.lower().endswith(('.gz', '.z')):
                        brdc_path, _ = extract_compressed_file(brdc_path)

                    print(f"   [Process] Found BRDC: {os.path.basename(brdc_path)}")
                    nav_data = read_navFile(brdc_path)


                    t_start = datetime.datetime(date.year, date.month, date.day, 0, 0, 0)
                    t_end = datetime.datetime(date.year, date.month, date.day, 23, 59, 59)

                    or_data = calculate_orbit_from_nav(
                        navigation=nav_data,
                        t_start=t_start,
                        t_end=t_end,
                        interval=st_data.interval,
                        system_filter=sys_code
                    )

                    if or_data is not None and not or_data.empty:
                        print(f"   [+] BRDC orbit calculation done.")
                    else:
                        print(f"   [!] BRDC orbit calculation returned empty data.")
                        or_data = None

            except Exception as e:
                print(f"   [!] BRDC orbit calculation failed: {e}")
                import traceback
                traceback.print_exc()
                or_data = None

        elif needs_sp3:

            print(f"   [Process] Interpolating Orbit (Product: {config.get('sp3_product', 'auto').upper()})...")
            try:
                data_dir = output_dir

                or_data = sp3_interp(
                    epoch=st_data.epoch,
                    interval=st_data.interval,
                    poly_degree=16,
                    sp3_product=config.get('sp3_product', 'auto'),
                    clock_product=config.get('clock_product', 'auto'),
                    data_dir=data_dir
                )
                print("   [+] Interpolation done.")
            except Exception as e:
                print(f"   [!] Interpolation via gnsspy failed: {e}")


                return False

        render_plots(st_data, or_data, analyses_dir, f"{station}_{date}", config, selected_plots)
        return True
    except Exception as e:
        import traceback
        print(f"   [!] Error during processing: {e}")
        traceback.print_exc()
        return False


def main(output_dir=None, skip_download=None, auth=None):
    downloader.print_header("GNSSpy - GNSS VISUALIZER")


    username,password = auth if auth else (None,None)


    if output_dir is None:
        output_dir = downloader.get_output_directory()

    analyses_dir = os.path.join(output_dir, "analyses")

    selected_plots, needs_sp3 = select_plots_interactive()
    plotly_png = False
    if any(kind != 'groundtrack' for kind in selected_plots):
        response = input(
            "Also export PNG copies of Plotly observation plots "
            "(requires Kaleido + Chrome)? (y/N) [n]: "
        ).strip().lower()
        if response not in {'', 'n', 'no', 'y', 'yes'}:
            raise ValueError("PNG export response must be yes or no")
        plotly_png = response in {'y', 'yes'}
    map_backend, map_format = 'cartopy', 'png'
    if 'groundtrack' in selected_plots:
        response = input("Map backend (cartopy/plotly) [cartopy]: ").strip().lower()
        if response and response not in {'cartopy', 'plotly'}:
            raise ValueError("Map backend must be cartopy or plotly")
        map_backend = response or 'cartopy'
        if map_backend == 'cartopy':
            response = input("Static map format (png/pdf/svg) [png]: ").strip().lower()
            if response and response not in {'png', 'pdf', 'svg'}:
                raise ValueError("Static map format must be png, pdf or svg")
            map_format = response or 'png'
        else:
            map_format = 'html'

    print("\n" + "-"*40)
    print(" SETTINGS ".center(40, '-'))

    sys_input = input("GNSS System (G=GPS, R=GLO, E=GAL, C=BDS, I=IRNSS, J=QZSS) [G]: ").strip().upper()
    sys_code = sys_input if sys_input in ['G','R','E','C','I','J','S','AUTO','ALL'] else 'G'


    needs_brdc = sys_code in ['I', 'J']

    sp3_center = 'AUTO'
    if needs_sp3:
        print("\n" + "-"*40)
        print(" ANALYSIS CENTER SELECTION ".center(40, '-'))
        print("AUTO discovers local products; enter a centre (CODE/GFZ/EMR/IGS/...) to restrict it.")
        user_center = input(f"Select Center (Default: {sp3_center}): ").strip().upper()
        if user_center: sp3_center = user_center
        print(f"   [i] Selected Center: {sp3_center}")

    print("\n" + "-"*40)
    print(" DATA ACQUISITION ".center(40, '-'))


    do_download = False
    if skip_download is True:
        do_download = False
    elif skip_download is False:
        do_download = True
    else:
        do_download = downloader.get_yes_no("Download new data?", True)

    if do_download:
        if not username:
            username,password = manage_login()
        if not username:
            return
        date_start, date_end = downloader.get_date_range()
        if date_end is None: date_end = date_start
        stations = downloader.get_stations()
        rinex_ver = downloader.get_rinex_version()

        file_types = {
            'observation': True,
            'navigation': needs_brdc,
            'brdc': needs_brdc,
            'sp3_clk': needs_sp3 and not needs_brdc,
            'ionosphere': False,
            'sp3_center': sp3_center
        }

        downloader.download_data(date_start, date_end, stations, rinex_ver, file_types, output_dir, username, password)
        if str(rinex_ver) == '2':
            print("\n[Download] Checking fallback for RINEX 3 if needed...")
            downloader.download_data(date_start, date_end, stations, 3, file_types, output_dir, username, password)
    else:

        try:
            s = input("Start (YYYY-MM-DD): ")
            date_start = datetime.datetime.strptime(s, "%Y-%m-%d").date()
            e = input("End (YYYY-MM-DD) [Enter for same]: ")
            date_end = datetime.datetime.strptime(e, "%Y-%m-%d").date() if e.strip() else date_start
            st = input("Station Code (e.g. MATE): ").strip().upper()
            stations = [st]
        except: print("Invalid inputs!"); return

    snr_code = input('SNR observation code [auto]: ').strip().upper() or 'auto'

    config = {
        'system': sys_code,
        'sv_list': None,
        'color_mode': 'snr',
        'snr_code': snr_code,
        'sp3_product': sp3_center.lower(),
        'clock_product': 'auto',
        'map_backend': map_backend,
        'map_format': map_format,
        'plotly_png': plotly_png,
        'plotly_png_scale': 2.0
    }

    print("\n" + "="*40)
    print(" STARTING VISUALIZATION ".center(40, '='))
    delta = date_end - date_start
    date_list = [date_start + datetime.timedelta(days=i) for i in range(delta.days + 1)]

    for st in stations:
        for d in date_list:
            if process_single_day(d, st, output_dir, analyses_dir, config, selected_plots, needs_sp3):
                print(f"[+] {d} Processed successfully.")
            else:
                print(f"[!] {d} Skipped or Failed.")

    print(f"\nDone! Charts saved in: {analyses_dir}")


    import webbrowser
    html_files = [f for f in config.get('_generated_files', []) if f.endswith('.html')]
    if html_files:
        print(f"   [i] Opening {len(html_files)} plots in browser...")
        for f in html_files:
            webbrowser.open('file://' + os.path.abspath(f).replace('\\', '/'))

if __name__ == "__main__":
    main()
