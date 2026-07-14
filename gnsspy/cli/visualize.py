


import os
import sys
import getpass
import datetime
import shutil
import gzip
import warnings
import glob
from pathlib import Path


warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore")


import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt




PROJECT_ROOT = str(Path(__file__).resolve().parents[2])

from gnsspy.io.manipulate import crx2rnx
from gnsspy.quality.snr import standardize_snr

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
    name = filename.upper()
    if 'COD' in name: return 'cod'
    if 'IGS' in name: return 'igs'
    if 'GFZ' in name: return 'gfz'
    if 'WUM' in name: return 'wum'
    if 'ESA' in name: return 'esa'
    if 'GRG' in name: return 'grg'
    if 'JAX' in name: return 'jax'
    if 'GBM' in name: return 'gbm'
    return 'igs'

def create_legacy_bridge(sp3_dir, target_date, center):
    """
    Creates legacy filename copies from modern naming convention (e.g. WUM0MGX... -> wum22995.sp3).
    This allows gnsspy's internal functions to locate the files correctly.
    """

    parent_dir = os.path.dirname(sp3_dir)
    clk_dir = os.path.join(parent_dir, "clk")
    

    if not os.path.exists(clk_dir):
        clk_dir = sp3_dir

    dates_to_check = [
        target_date - datetime.timedelta(days=1),
        target_date,
        target_date + datetime.timedelta(days=1)
    ]
    
    center_short = center.lower()[:3]
    if center_short == 'cod': center_short = 'cod' 
    
    for d in dates_to_check:
        week, day = get_gps_week_day(d)
        doy = d.timetuple().tm_yday
        str_doy = f"{doy:03d}"
        year_long = str(d.year)
        



        legacy_sp3_name = f"{center_short}{week}{day}.sp3"
        legacy_sp3_path = os.path.join(sp3_dir, legacy_sp3_name)
        
        if not os.path.exists(legacy_sp3_path):
            candidates = []
            for f in os.listdir(sp3_dir):
                if f.lower().endswith(('.sp3', '.eph')) and str_doy in f and year_long in f:
                     if center.upper() in f.upper():
                        candidates.append(f)
            
            if candidates:
                src = os.path.join(sp3_dir, candidates[0])
                try: shutil.copy(src, legacy_sp3_path)
                except: pass




        legacy_clk_name = f"{center_short}{week}{day}.clk"
        legacy_clk_path = os.path.join(clk_dir, legacy_clk_name)
        
        if not os.path.exists(legacy_clk_path) and os.path.exists(clk_dir):
            candidates_clk = []
            for f in os.listdir(clk_dir):
                f_upper = f.upper()
                if 'CLK' in f_upper and str_doy in f and year_long in f:
                     if center.upper() in f.upper():
                        candidates_clk.append(f)
            
            if candidates_clk:
                src = os.path.join(clk_dir, candidates_clk[0])
                try: 
                    shutil.copy(src, legacy_clk_path)
                except Exception as e:
                    print(f"   [!] CLK Bridge Error: {e}")


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
        sp3_dir = os.path.join(output_dir, "sp3")
        gps_week, gps_day = get_gps_week_day(target_date)
        found_files = [] 
        
        if os.path.exists(sp3_dir):
            for root, _, files in os.walk(sp3_dir):
                for f in files:
                    f_low = f.lower()
                    if f_low.endswith(('.sp3', '.eph', '.clk', '.sp3.z', '.sp3.gz', '.clk.gz')):
                        if f"{gps_week}{gps_day}" in f or f"{year_long}{str_doy}" in f:
                            found_files.append(os.path.join(root, f))

        if priority_agency:
            for f in found_files:
                if priority_agency.upper() in os.path.basename(f).upper():
                    sp3_path = f; break
        
        if sp3_path is None and found_files:
            sp3_path = found_files[0]
            
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

def process_single_day(date, station, output_dir, analyses_dir, config, selected_plots, needs_sp3):
    print(f"\n>>> PROCESSING: {date} ({station})")
    
    sys_code = config.get('system', 'G')
    needs_brdc = sys_code in ['I', 'J']
    preferred_agency = config.get('sp3_product', 'cod')
    

    obs_path, sp3_path = find_files_for_date(output_dir, date, station, needs_sp3, priority_agency=preferred_agency)
    
    if not obs_path: 
        print(f"   [!] Observation file missing for {date}"); return False
    

    if needs_brdc:
        needs_sp3 = False
    
    if needs_sp3 and not needs_brdc:
        if not sp3_path:
            print(f"   [!] SP3 file missing for {date} (Expected: {preferred_agency})"); return False
        

        sp3_dir = os.path.dirname(sp3_path)
        create_legacy_bridge(sp3_dir, date, preferred_agency)
        
        found_agency = detect_agency_from_filename(os.path.basename(sp3_path))
        print(f"   [Process] Found SP3: {os.path.basename(sp3_path)}")
                

    if sp3_path and sp3_path.lower().endswith(('.z', '.gz')): 
        sp3_path, _ = extract_compressed_file(sp3_path)
        sp3_dir = os.path.dirname(sp3_path)
        create_legacy_bridge(sp3_dir, date, preferred_agency)
    
    if needs_sp3:
        clk_dir = os.path.join(os.path.dirname(os.path.dirname(sp3_path)), "clk")
        if os.path.exists(clk_dir):
            for f in os.listdir(clk_dir):
                if f.endswith('.gz') or f.endswith('.Z'):
                    extract_compressed_file(os.path.join(clk_dir, f))
            create_legacy_bridge(os.path.dirname(sp3_path), date, preferred_agency)

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
        

        st_data = standardize_snr(st_data, system=sys_code)
        

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

            print(f"   [Process] Interpolating Orbit (Product: {config['sp3_product'].upper()})...")
            try:
                data_dir = None
                possible_data_dir = os.path.join(output_dir, "..", "data")
                if not os.path.exists(possible_data_dir):
                    possible_data_dir = os.path.join(os.getcwd(), "gnsspy", "backend", "data")
                
                if os.path.basename(output_dir) == 'data':
                    data_dir = output_dir
                elif os.path.exists(possible_data_dir): 
                    data_dir = possible_data_dir
                
                if not data_dir: data_dir = output_dir

                or_data = sp3_interp(
                    epoch=st_data.epoch, 
                    interval=st_data.interval, 
                    poly_degree=16,
                    sp3_product=config.get('sp3_product', 'cod'),
                    clock_product=config.get('clock_product', 'cod'),
                    data_dir=data_dir 
                )
                print("   [+] Interpolation done.")
            except Exception as e:
                print(f"   [!] Interpolation via gnsspy failed: {e}")
                print("   [!] Trying raw SP3 read (visualization might be less accurate)...")
                or_data = read_sp3File(sp3_path)

        base_name = f"{station}_{date}"
        if not os.path.exists(analyses_dir): os.makedirs(analyses_dir)
        
        svs = config.get('sv_list', None)
        color = config.get('color_mode', 'snr')
        
        print(f"   [Plot] Generating selected charts for System: {sys_code}...")
        
        if 'skyplot' in selected_plots and or_data is not None:
            skyplot(st_data, or_data, system=sys_code, sv_list=svs, color_mode=color, save_path=os.path.join(analyses_dir, f"{base_name}_Skyplot.html"))
        if 'azel' in selected_plots and or_data is not None:
            azelplot(st_data, or_data, system=sys_code, sv_list=svs, color_mode=color, save_path=os.path.join(analyses_dir, f"{base_name}_AzEl.html"))
        if 'elevation' in selected_plots and or_data is not None:
            timelplot(st_data, or_data, system=sys_code, sv_list=svs, mode='elevation', save_path=os.path.join(analyses_dir, f"{base_name}_Elevation.html"))
        if 'snr' in selected_plots:
            timelplot(st_data, or_data, system=sys_code, sv_list=svs, mode='snr', save_path=os.path.join(analyses_dir, f"{base_name}_SNR.html"))
        if 'bandplot' in selected_plots:
            bandplot(st_data, system=sys_code, sv_list=svs, save_path=os.path.join(analyses_dir, f"{base_name}_BandPlot.html"))
        if 'groundtrack' in selected_plots and or_data is not None:
            groundtrack(or_data, system=sys_code, sv_list=svs, save_path=os.path.join(analyses_dir, f"{base_name}_Groundtrack.html"))
            
        return True
    except Exception as e:
        import traceback
        print(f"   [!] Error during processing: {e}")
        traceback.print_exc()
        return False





def main(output_dir=None, skip_download=None, auth=None):
    downloader.print_header("GNSS VISUALIZER (FINAL FIXED v3)")
    

    if auth:
        username, password = auth
    else:
        username, password = manage_login()
        
    if not username: return
    

    if output_dir is None:
        output_dir = downloader.get_output_directory()
    
    analyses_dir = os.path.join(output_dir, "analyses")

    selected_plots, needs_sp3 = select_plots_interactive()

    print("\n" + "-"*40)
    print(" SETTINGS ".center(40, '-'))
    
    sys_input = input("GNSS System (G=GPS, R=GLO, E=GAL, C=BDS, I=IRNSS, J=QZSS) [G]: ").strip().upper()
    sys_code = sys_input if sys_input in ['G','R','E','C','I','J','S'] else 'G'
    

    needs_brdc = sys_code in ['I', 'J']
    
    sp3_center = 'CODE'
    if needs_sp3:
        print("\n" + "-"*40)
        print(" ANALYSIS CENTER SELECTION ".center(40, '-'))
        print(" Recommended: CODE (GPS/GLO/GAL), WUM (Multi/BDS), GFZ")
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

    config = {
        'system': sys_code, 
        'sv_list': None, 
        'color_mode': 'snr', 
        'sp3_product': sp3_center.lower(),
        'clock_product': sp3_center.lower()
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
    html_files = glob.glob(os.path.join(analyses_dir, "*.html"))
    if html_files:
        print(f"   [i] Opening {len(html_files)} plots in browser...")
        for f in html_files:
            webbrowser.open('file://' + os.path.abspath(f).replace('\\', '/'))

if __name__ == "__main__":
    main()
