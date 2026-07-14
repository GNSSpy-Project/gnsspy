#!/usr/bin/env python3
"""
gnss_downloader.py

GNSS Data Downloader - Interactive CLI
User-friendly terminal interface tool for downloading GNSS data.
Connects to the backend modules to perform robust downloads.

CRITICAL FIX: SP3 downloads now use ONLY the selected center for ALL dates
(main date + previous day + next day buffer).
"""

import sys
import getpass
import os
import datetime
from pathlib import Path


_PROJECT_ROOT = str(Path.cwd())


try:
    from gnsspy.data_access.observation import ObservationDownloader
    from gnsspy.data_access.products import NavigationDownloader
    from gnsspy.data_access.utils import test_credentials
    from gnsspy.data_access.config import SP3_CENTERS, DEFAULT_OUTPUT_DIR
except ImportError:
    print("Backend modules not found!")
    print("Please install GNSSpy or run this command from a valid GNSSpy environment.")
    sys.exit(1)


class Colors:
    """Terminal color codes for better UI"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(70)}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.ENDC}\n")

def print_success(text):
    print(f"{Colors.GREEN}  {text}{Colors.ENDC}")

def print_error(text):
    print(f"{Colors.RED}  {text}{Colors.ENDC}")

def print_info(text):
    print(f"{Colors.BLUE}  {text}{Colors.ENDC}")

def print_warning(text):
    print(f"{Colors.YELLOW}  {text}{Colors.ENDC}")

def get_input(prompt, default=None):
    if default:
        prompt = f"{prompt} [{default}]: "
    else:
        prompt = f"{prompt}: "
    value = input(f"{Colors.BOLD}{prompt}{Colors.ENDC}").strip()
    return value if value else default

def get_yes_no(prompt, default=True):
    default_text = "Y/n" if default else "y/N"
    response = get_input(f"{prompt} ({default_text})", "y" if default else "n").lower()
    if response in ['e', 'evet', 'y', 'yes']: return True
    elif response in ['h', 'hayir', 'n', 'no']: return False
    else: return default


CREDENTIALS_FILENAME = "credentials.txt"


def _load_credentials_file():
    """Try to read NASA Earthdata credentials from credentials.txt in the
    current working directory. Returns (username, password) or (None, None) if missing /
    unreadable / empty.

    Accepted formats:
        1) Two non-comment lines: first = username, second = password.
        2) Key=value pairs: 'username = foo' / 'password = bar' (any order).
    """
    path = os.path.join(_PROJECT_ROOT, CREDENTIALS_FILENAME)
    if not os.path.isfile(path):
        return None, None
    try:
        with open(path, 'r', encoding='utf-8') as fh:
            raw_lines = fh.readlines()
    except OSError:
        return None, None

    lines = []
    for ln in raw_lines:
        s = ln.strip()
        if not s or s.startswith('#'):
            continue
        lines.append(s)

    username = password = None


    for ln in lines:
        if '=' in ln:
            k, v = ln.split('=', 1)
            k = k.strip().lower()
            v = v.strip().strip('"').strip("'")
            if k == 'username' and v:
                username = v
            elif k == 'password' and v:
                password = v


    if not username or not password:
        plain = [ln for ln in lines if '=' not in ln]
        if len(plain) >= 2:
            username = username or plain[0]
            password = password or plain[1]

    if username and password:
        return username, password
    return None, None


def login_flow():
    """Authenticates with NASA Earthdata.

    First tries to load credentials from credentials.txt in the current working directory.
    If that file is present and the credentials are accepted by Earthdata,
    returns them silently. Otherwise falls back to interactive prompts.
    """
    print_header("NASA EARTHDATA LOGIN")


    file_user, file_pass = _load_credentials_file()
    if file_user and file_pass:
        print_info(f"Found credentials file: {CREDENTIALS_FILENAME}")
        print_info(f"Using username: {file_user}")
        print_info("Testing credentials...")
        success, msg = test_credentials(file_user, file_pass)
        if success:
            print_success(msg)
            return file_user, file_pass
        else:
            print_error(f"Credentials file rejected: {msg}")
            print_warning("Falling back to interactive login.")
    else:

        cred_path = os.path.join(_PROJECT_ROOT, CREDENTIALS_FILENAME)
        if not os.path.isfile(cred_path):
            print_info(f"Tip: create {CREDENTIALS_FILENAME} in the current working directory "
                       "to skip this prompt next time.")


    print_info("Please enter your NASA Earthdata credentials.")
    max_attempts = 3
    for attempt in range(max_attempts):
        username = get_input("NASA Earthdata username")
        password = getpass.getpass(f"{Colors.BOLD}NASA Earthdata password: {Colors.ENDC}")

        if not username or not password:
            print_error("Username and password are required!")
            continue

        print_info("Testing credentials...")
        success, msg = test_credentials(username, password)

        if success:
            print_success(msg)
            return username, password
        else:
            print_error(msg)
            if attempt < max_attempts - 1:
                print_warning(f"Remaining attempts: {max_attempts - attempt - 1}")

    print_error("Login failed. Terminating program.")
    return None, None


def parse_date(date_str):
    """Parse common GNSSpy date inputs."""
    from gnsspy.utils.date import parse_date as _parse_date
    return _parse_date(date_str)


def get_date_range():
    """Gets start and end date from user."""
    print_header("DATE RANGE")
    print_info("Formats: DD-MM-YYYY, YYYY-MM-DD")
    
    while True:
        try:
            start_str = get_input("Start date")
            date_start = parse_date(start_str)
            break
        except ValueError as e:
            print_error(str(e))
    
    date_end = None
    if get_yes_no("Do you want to use a date range?", False):
        while True:
            try:
                end_str = get_input("End date")
                date_end = parse_date(end_str)
                if date_end < date_start:
                    print_error("End date cannot be before start date!")
                    continue
                break
            except ValueError as e:
                print_error(str(e))
        
        days = (date_end - date_start).days + 1
        print_info(f"Total {days} days selected.")
    
    return date_start, date_end


def get_stations():
    """Gets list of station codes."""
    print_header("STATION SELECTION")
    print_info("Enter codes separated by commas (e.g., MATE,ANKR). Use BRDC for global.")
    
    while True:
        station_input = get_input("Station codes")
        if not station_input:
            print_error("Enter at least one station!")
            continue
        
        stations = [s.strip().upper() for s in station_input.split(',') if s.strip()]
        if not stations:
            print_error("No valid code found!")
            continue
        
        print_success(f"Selected: {', '.join(stations)}")
        return stations


def get_rinex_version():
    """Gets RINEX version preference."""
    print_header("RINEX VERSION")
    while True:
        version = get_input("RINEX version (2 or 3)", "3")
        if version in ['2', '3']: return int(version)
        print_error("Enter 2 or 3.")


def get_file_types():
    """Gets user selection for file types."""
    print_header("FILE TYPES SELECTION")
    types = {}
    types['observation'] = get_yes_no("1. Observation", True)
    types['navigation'] = get_yes_no("2. Navigation (Broadcast)", True)
    types['brdc'] = get_yes_no("3. BRDC (Merged)", True)
    types['sp3_clk'] = get_yes_no("4. SP3 + CLK (Precise Orbit/Clock)", True)
    types['ionosphere'] = get_yes_no("5. Ionosphere", False)
    
    if types['sp3_clk']:
        print()
        print_info("SP3 Analysis Center selection:")
        for i, (key, info) in enumerate(SP3_CENTERS.items(), 1):
            print(f"  {i}. {key}: {info['description']}")
        
        while True:
            center = get_input("Analysis Center", "CODE").upper()
            if center in SP3_CENTERS or center in ['COD', 'CODE']:
                types['sp3_center'] = 'CODE' if center == 'COD' else center
                break
            else:
                print_error(f"Invalid! Options: {', '.join(SP3_CENTERS.keys())}")
    
    return types


def get_output_directory():
    """Gets output directory path."""
    print_header("OUTPUT DIRECTORY")
    default_dir = DEFAULT_OUTPUT_DIR
    print_info(f"Default: {default_dir}")
    
    if get_yes_no("Use default directory?", True):
        return default_dir
    
    while True:
        custom_dir = get_input("Output directory")
        if not custom_dir: continue
        try:
            Path(custom_dir).mkdir(parents=True, exist_ok=True)
            return custom_dir
        except Exception as e:
            print_error(f"Error creating directory: {e}")


def show_summary(date_start, date_end, stations, rinex_version, file_types, output_dir):
    """Displays a summary before downloading."""
    print_header("DOWNLOAD SUMMARY")
    print(f"{Colors.BOLD}Date:{Colors.ENDC} {date_start}", end="")
    if date_end: print(f" -> {date_end}")
    else: print(" (Single day)")
    
    print(f"{Colors.BOLD}Stations:{Colors.ENDC} {', '.join(stations)}")
    print(f"{Colors.BOLD}RINEX:{Colors.ENDC} {rinex_version}")
    print(f"{Colors.BOLD}Output:{Colors.ENDC} {output_dir}")
    
    print(f"\n{Colors.BOLD}Selected Files:{Colors.ENDC}")
    if file_types['observation']: print(f"  {Colors.GREEN}+{Colors.ENDC} Observation")
    if file_types['navigation']: print(f"  {Colors.GREEN}+{Colors.ENDC} Navigation")
    if file_types['brdc']: print(f"  {Colors.GREEN}+{Colors.ENDC} BRDC")
    if file_types['sp3_clk']: 
        print(f"  {Colors.GREEN}+{Colors.ENDC} SP3+CLK ({file_types.get('sp3_center')})")
        print(f"    {Colors.YELLOW}Note: Will download for selected center ONLY (main + buffer days){Colors.ENDC}")
    if file_types['ionosphere']: print(f"  {Colors.GREEN}+{Colors.ENDC} Ionosphere")
    print()


def download_data(date_start, date_end, stations, rinex_version, file_types, output_dir, username, password):
    """Orchestrates the download process."""
    print_header("DOWNLOAD STARTING")
    

    date_list = []
    current = date_start
    limit = date_end if date_end else date_start
    while current <= limit:
        date_list.append(current)
        current += datetime.timedelta(days=1)
    

    sp3_date_list = []
    if file_types.get('sp3_clk', False):
        sp3_date_list.append(date_start - datetime.timedelta(days=1))
        sp3_date_list.extend(date_list)
        sp3_date_list.append(limit + datetime.timedelta(days=1))
        
        center_name = file_types.get('sp3_center', 'CODE')
        print_info(f"SP3: Downloading {len(sp3_date_list)} days from '{center_name}' ONLY")
        print_info(f"     Range: {sp3_date_list[0]} to {sp3_date_list[-1]}")
    

    obs_dl = ObservationDownloader(username, password, output_dir)
    nav_dl = NavigationDownloader(username, password, output_dir)
    

    stats = {k: {'success': 0, 'fail': 0} for k in ['observation', 'navigation', 'brdc', 'sp3_clk', 'ionosphere']}
    total_ops = 0
    

    if file_types['observation']: total_ops += len(stations) * len(date_list)
    if file_types['navigation']: total_ops += len(stations) * len(date_list)
    if file_types['brdc']: total_ops += len(date_list)
    if file_types['sp3_clk']: total_ops += len(sp3_date_list)
    if file_types['ionosphere']: total_ops += len(date_list)
    
    current_op = 0
    

    

    if file_types['observation']:
        print(f"\n{Colors.BOLD}OBSERVATION{Colors.ENDC}")
        for station in stations:
            for date in date_list:
                current_op += 1
                print(f"[{current_op}/{total_ops}] {station} {date}... ", end="", flush=True)
                success, msg = obs_dl.download_single(station, date, rinex_version)
                if success:
                    print_success(msg)
                    stats['observation']['success'] += 1
                else:
                    print_error(msg)
                    stats['observation']['fail'] += 1


    if file_types['navigation']:
        print(f"\n{Colors.BOLD}NAVIGATION{Colors.ENDC}")
        for station in stations:
            for date in date_list:
                current_op += 1
                print(f"[{current_op}/{total_ops}] {station} (Nav) {date}... ", end="", flush=True)
                success, msg = nav_dl.download_broadcast(station, date, rinex_version)
                if success:
                    print_success(msg)
                    stats['navigation']['success'] += 1
                else:
                    print_error(msg)
                    stats['navigation']['fail'] += 1


    if file_types['brdc']:
        print(f"\n{Colors.BOLD}BRDC{Colors.ENDC}")
        for date in date_list:
            current_op += 1
            print(f"[{current_op}/{total_ops}] BRDC {date}... ", end="", flush=True)
            success, msg = nav_dl.download_brdc_only(date, rinex_version)
            if success:
                print_success(msg)
                stats['brdc']['success'] += 1
            else:
                print_error(msg)
                stats['brdc']['fail'] += 1


    if file_types['sp3_clk']:
        center = file_types.get('sp3_center', 'CODE')
        print(f"\n{Colors.BOLD}SP3 + CLK (CENTER: {center} STRICT MODE){Colors.ENDC}")
        print_warning(f"Only '{center}' will be used for ALL {len(sp3_date_list)} days (no fallback)")
        
        for date in sp3_date_list:
            current_op += 1
            print(f"[{current_op}/{total_ops}] {center} @ {date}... ", end="", flush=True)
            
            success, msg, mode = nav_dl.download_sp3_with_fallback(
                center=center,
                date=date,
                orbit_type='auto',
                fallback_to_broadcast=False,
                rinex_version=rinex_version,
                strict_center=True
            )
            
            if success:
                print_success(f"{msg} [{mode}]")
                stats['sp3_clk']['success'] += 1
            else:
                print_error(msg)
                stats['sp3_clk']['fail'] += 1


    if file_types['ionosphere']:
        print(f"\n{Colors.BOLD}IONOSPHERE{Colors.ENDC}")
        for date in date_list:
            current_op += 1
            print(f"[{current_op}/{total_ops}] Ionosphere {date}... ", end="", flush=True)
            success, msg = nav_dl.download_ionosphere(date, ion_type='auto')
            if success:
                print_success(msg)
                stats['ionosphere']['success'] += 1
            else:
                print_error(msg)
                stats['ionosphere']['fail'] += 1


    print_header("DOWNLOAD REPORT")
    total_success = sum(s['success'] for s in stats.values())
    total_fail = sum(s['fail'] for s in stats.values())
    
    for k, v in stats.items():
        if v['success'] + v['fail'] > 0:
            print(f"{k.upper()}: {Colors.GREEN}{v['success']} OK{Colors.ENDC}, {Colors.RED}{v['fail']} Fail{Colors.ENDC}")
    
    print(f"\n{Colors.BOLD}Total:{Colors.ENDC} {Colors.GREEN}{total_success} Success{Colors.ENDC}, {Colors.RED}{total_fail} Failed{Colors.ENDC}")
    print(f"{Colors.BOLD}Output Directory:{Colors.ENDC} {output_dir}")

def main():
    try:
        print_header("GNSS DATA DOWNLOADER")
        username, password = login_flow()
        if not username: return
        
        date_start, date_end = get_date_range()
        stations = get_stations()
        rinex = get_rinex_version()
        ftypes = get_file_types()
        out_dir = get_output_directory()
        
        show_summary(date_start, date_end, stations, rinex, ftypes, out_dir)
        
        if get_yes_no("\nStart download?", True):
            download_data(date_start, date_end, stations, rinex, ftypes, out_dir, username, password)
            print_success("Download process completed!")
        else:
            print_warning("Download cancelled.")
            
    except KeyboardInterrupt:
        print_warning("\nProcess aborted by user.")
        sys.exit(0)
    except Exception as e:
        print_error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()