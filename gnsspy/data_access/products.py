"""
navigation.py

Handles downloading of GNSS Navigation (Broadcast), SP3 (Precise Orbit), 
CLK (Clock), and Ionosphere (IONEX) products.

CRITICAL FIXES IN THIS VERSION:
1. Added Weekly (07D) fallback: If daily SP3 is missing, tries downloading the weekly file (starts on Sunday).
2. Expanded fallback logic: Checks Rapid/Ultra-Rapid even for older dates if Final is missing.
3. MGEX Naming: Corrected 'OPSRAP' to 'MGXRAP' for MGEX centers.
"""

import gzip
import datetime
from pathlib import Path
from typing import Tuple, Optional, Union, List


try:
    from .earthdata import BaseDownloader
    from .utils import get_full_code
    from .config import BASE_URL, PRODUCTS_URL, IONOSPHERE_URL, ORBIT_TYPES, IONOSPHERE_TYPES
except ImportError:
    from gnsspy.data_access.earthdata import BaseDownloader
    from gnsspy.data_access.utils import get_full_code
    from gnsspy.data_access.config import BASE_URL, PRODUCTS_URL, IONOSPHERE_URL, ORBIT_TYPES, IONOSPHERE_TYPES

class NavigationDownloader(BaseDownloader):
    """
    Downloader class for GNSS Navigation, Orbit (SP3), Clock (CLK), and Ionosphere data.
    """
    
    def __init__(self, username, password, output_dir):
        super().__init__(username, password, output_dir)




    
    def get_gps_week_day(self, date: Union[datetime.date, datetime.datetime]) -> Tuple[int, int]:
        """Calculates GPS Week and Day of Week."""
        gps_epoch = datetime.date(1980, 1, 6)
        if isinstance(date, datetime.datetime):
            date = date.date()
            
        delta = (date - gps_epoch).days
        gps_week = delta // 7
        day_of_week = delta % 7
        
        return gps_week, day_of_week

    def determine_orbit_type(self, date: Union[datetime.date, datetime.datetime]) -> str:
        """Determines if we should look for 'final', 'rapid', or 'ultra-rapid' products."""
        if isinstance(date, datetime.datetime):
            target_date = date.date()
        else:
            target_date = date
            
        today = datetime.date.today()
        days_ago = (today - target_date).days
        
        if days_ago >= ORBIT_TYPES['final']['delay_days']:
            return 'final'
        elif days_ago >= ORBIT_TYPES['rapid']['delay_days']:
            return 'rapid'
        else:
            return 'ultra-rapid'





    def make_rinex3_nav_filename(self, station: str, date: datetime.date) -> str:
        year = date.year
        doy = str(self.day_of_year(date)).zfill(3)
        if station.upper() == "BRDC":
            return f"BRDC00IGS_R_{year}{doy}0000_01D_MN.rnx.gz"
        else:
            station_full = get_full_code(station)
            return f"{station_full}_R_{year}{doy}0000_01D_MN.rnx.gz"
    
    def make_rinex2_nav_filename(self, station: str, date: datetime.date) -> str:
        doy = str(self.day_of_year(date)).zfill(3)
        year_short = str(date.year)[-2:]
        if station.lower() == "brdc":
            return f"brdc{doy}0.{year_short}n.Z"
        else:
            station_lower = station.lower()[:4]
            return f"{station_lower}{doy}0.{year_short}n.Z"
    
    def build_nav_url(self, date: datetime.date, filename: str) -> str:
        year = date.year
        doy = str(self.day_of_year(date)).zfill(3)
        year_short = str(year)[-2:]
        folder = f"{year_short}p" if '.rnx' in filename else f"{year_short}n"
        return f"{BASE_URL}/{year}/{doy}/{folder}/{filename}"

    def download_brdc_only(self, date, rinex_version=3) -> Tuple[bool, str]:
        date = self.parse_date(date)
        if date.year < 2020: rinex_version = 2
        
        output_path = self.output_dir / 'brdc'
        output_path.mkdir(parents=True, exist_ok=True)
        
        filename = (self.make_rinex3_nav_filename("BRDC", date) if rinex_version == 3 
                    else self.make_rinex2_nav_filename("brdc", date))
        
        filepath = output_path / filename
        if filepath.exists(): return True, "File already exists"
        
        url = self.build_nav_url(date, filename)
        success, msg = self.download_file(url, filepath)
        
        if success:
            self._extract_file(filepath)
            return True, f"{msg} -> LINK: {url}"
        return False, f"BRDC failed. URL: {url}"

    def download_broadcast(self, station, date, rinex_version=3) -> Tuple[bool, str]:
        date = self.parse_date(date)
        if date.year < 2020: rinex_version = 2
        
        base_dir = self.output_dir / 'navigation'
        base_dir.mkdir(parents=True, exist_ok=True)
        
        filename = (self.make_rinex3_nav_filename(station, date) if rinex_version == 3 
                    else self.make_rinex2_nav_filename(station, date))
        
        filepath = base_dir / filename
        if filepath.exists(): return True, "Station file already exists"
        
        url = self.build_nav_url(date, filename)
        success, msg = self.download_file(url, filepath)
        
        if success:
            self._extract_file(filepath)
            return True, f"{msg} -> LINK: {url}"
            
        brdc_filename = (self.make_rinex3_nav_filename("BRDC", date) if rinex_version == 3 
                         else self.make_rinex2_nav_filename("brdc", date))
        brdc_filepath = base_dir / brdc_filename
        if brdc_filepath.exists(): return True, "BRDC already exists (Fallback)"
        
        brdc_url = self.build_nav_url(date, brdc_filename)
        brdc_success, brdc_msg = self.download_file(brdc_url, brdc_filepath)
        
        if brdc_success:
            self._extract_file(brdc_filepath)
            return True, f"Used BRDC fallback: {brdc_msg}"
            
        return False, f"Both Station and BRDC failed."





    def make_sp3_filename(self, center: str, date: datetime.date, orbit_type='final', duration='01D') -> Optional[str]:
        """
        Generates modern SP3 filename.
        Added 'duration' parameter to support 07D (Weekly) files.
        """
        year = date.year
        doy = str(self.day_of_year(date)).zfill(3)
        
        center_map = { 
            "CODE": "COD0", "COD": "COD0", "GFZ": "GFZ0", "IGS": "IGS0", 
            "WUM": "WUM0", "MIT": "MIT0", "GBM": "GBM0", "COM": "COM0",
            "JAX": "JAX0", "GRG": "GRG0"
        }
        prefix = center_map.get(center.upper(), "IGS0")
        
        mgex_centers = ["COD", "WUM", "GBM", "GFZ", "GRG", "JAX"]
        is_mgex = any(c in prefix for c in mgex_centers)
        

        rate = "05M" if is_mgex else "15M"
        
        if is_mgex:
            if orbit_type == 'final': 
                return f"{prefix}MGXFIN_{year}{doy}0000_{duration}_{rate}_ORB.SP3.gz"
            elif orbit_type == 'rapid':

                return f"{prefix}MGXRAP_{year}{doy}0000_{duration}_{rate}_ORB.SP3.gz"
            elif orbit_type == 'ultra-rapid':
                return f"{prefix}MGXULR_{year}{doy}0000_{duration}_{rate}_ORB.SP3.gz"
        else:
            if orbit_type == 'final': 
                return f"{prefix}OPSFIN_{year}{doy}0000_{duration}_{rate}_ORB.SP3.gz"
            elif orbit_type == 'rapid': 
                return f"{prefix}OPSRAP_{year}{doy}0000_{duration}_{rate}_ORB.SP3.gz"
            elif orbit_type == 'ultra-rapid':
                return f"{prefix}OPSULR_{year}{doy}0000_{duration}_{rate}_ORB.SP3.gz"
                
        return None

    def make_sp3_filename_legacy(self, center: str, date: datetime.date, orbit_type='final') -> Optional[str]:
        gps_week, day_of_week = self.get_gps_week_day(date)
        center_lower = center.lower()[:3]
        if orbit_type == 'final': return f"{center_lower}{gps_week}{day_of_week}.sp3.Z"
        elif orbit_type == 'rapid': return f"igr{gps_week}{day_of_week}.sp3.Z"
        elif orbit_type == 'ultra-rapid': return f"igu{gps_week}{day_of_week}.sp3.Z"
        return None

    def build_sp3_url(self, filename: str, date: datetime.date) -> str:
        gps_week, _ = self.get_gps_week_day(date)
        
        mgex_folder_prefixes = ['GBM', 'COM', 'JAX', 'GRG', 'GFZ0MGX']
        is_mgex_folder = any(filename.startswith(p) for p in mgex_folder_prefixes)
        

        if 'MGX' in filename:
            if filename.startswith('WUM') or filename.startswith('COD'):
                is_mgex_folder = False
            else:
                is_mgex_folder = True

        if is_mgex_folder:
            url = f"{PRODUCTS_URL}/mgex/{gps_week}/{filename}"
        else:
            url = f"{PRODUCTS_URL}/{gps_week}/{filename}"
            
        return url





    def make_clk_filename(self, center: str, date: datetime.date, orbit_type='final', duration='01D') -> Optional[str]:
        year = date.year
        doy = str(self.day_of_year(date)).zfill(3)
        
        center_map = { "CODE": "COD0", "WUM": "WUM0", "GBM": "GBM0", "GFZ": "GFZ0", "IGS": "IGS0" }
        prefix = center_map.get(center.upper(), "IGS0")
        
        mgex_centers = ["COD", "WUM", "GBM", "GFZ", "GRG"]
        is_mgex = any(c in prefix for c in mgex_centers)
        
        if is_mgex:
            if orbit_type == 'final':
                return f"{prefix}MGXFIN_{year}{doy}0000_{duration}_30S_CLK.CLK.gz"
            elif orbit_type == 'rapid':
                return f"{prefix}MGXRAP_{year}{doy}0000_{duration}_30S_CLK.CLK.gz"
        else:
            if orbit_type == 'final': 
                return f"{prefix}OPSFIN_{year}{doy}0000_{duration}_30S_CLK.CLK.gz"
            elif orbit_type == 'rapid': 
                return f"{prefix}OPSRAP_{year}{doy}0000_{duration}_30S_CLK.CLK.gz"
        return None

    def make_clk_filename_legacy(self, center: str, date: datetime.date, orbit_type='final') -> Optional[str]:
        gps_week, day_of_week = self.get_gps_week_day(date)
        center_lower = center.lower()[:3]
        if orbit_type == 'final': return f"{center_lower}{gps_week}{day_of_week}.clk.Z"
        elif orbit_type == 'rapid': return f"igr{gps_week}{day_of_week}.clk.Z"
        return None





    def download_sp3_with_fallback(self, center='CODE', date=None, orbit_type='auto', 
                                   fallback_to_broadcast=True, rinex_version=3,
                                   strict_center=True) -> Tuple[bool, str, str]:
        date = self.parse_date(date)
        if orbit_type == 'auto': orbit_type = self.determine_orbit_type(date)
        
        sp3_dir = self.output_dir / 'sp3'
        clk_dir = self.output_dir / 'clk'
        sp3_dir.mkdir(parents=True, exist_ok=True)
        clk_dir.mkdir(parents=True, exist_ok=True)
        
        if strict_center:
            centers_to_try = [center]
        else:
            centers_to_try = [center, 'CODE', 'GFZ', 'IGS', 'WUM', 'GBM']
            centers_to_try = list(dict.fromkeys([c.upper() for c in centers_to_try]))
        

        if strict_center or orbit_type == 'final':
            orbit_types = ['final', 'rapid', 'ultra-rapid']
        else:
            orbit_priority = {'final': ['final'], 'rapid': ['rapid', 'final'], 'ultra-rapid': ['ultra-rapid']}
            orbit_types = orbit_priority.get(orbit_type, ['final'])
        
        attempted_urls = []

        for current_center in centers_to_try:
            for current_orbit in orbit_types:
                

                sp3_success, sp3_file, sp3_url = self._try_download_sp3(
                    current_center, current_orbit, date, sp3_dir, attempted_urls, duration='01D'
                )
                


                if not sp3_success and current_orbit == 'final':
                    gps_week, _ = self.get_gps_week_day(date)



                    gps_epoch = datetime.date(1980, 1, 6)
                    sunday_date = gps_epoch + datetime.timedelta(days=gps_week * 7)
                    
                    if sunday_date != date:
                        if self.debug: print(f"  [SP3] Daily missing. Trying Weekly (07D) starting {sunday_date}...")
                        sp3_success, sp3_file, sp3_url = self._try_download_sp3(
                            current_center, current_orbit, sunday_date, sp3_dir, attempted_urls, duration='07D'
                        )

                clk_success, clk_file, clk_url = False, None, None
                if sp3_success:

                    is_weekly = '07D' in str(sp3_file)
                    clk_date = sunday_date if is_weekly else date
                    clk_dur = '07D' if is_weekly else '01D'
                    
                    clk_success, clk_file, clk_url = self._try_download_clk(
                        current_center, current_orbit, clk_date, clk_dir, attempted_urls, duration=clk_dur
                    )
                    
                    self._extract_file(sp3_file)
                    if clk_success: self._extract_file(clk_file)
                    
                    msg = f"SP3+CLK downloaded [{current_center}/{current_orbit}]"
                    if is_weekly: msg += " [WEEKLY FILE]"
                    if sp3_url: msg += f"\n   SP3 LINK: {sp3_url}"
                    if clk_url: msg += f"\n   CLK LINK: {clk_url}"
                    
                    status_type = "precise" if clk_success else "precise_partial"
                    return True, msg, status_type
            
            if strict_center: break

        error_msg = f"SP3 failed for center '{center}'"
        if attempted_urls: error_msg += f"\nLast checked: {attempted_urls[-1]}"
        
        if fallback_to_broadcast:
            brdc_success, brdc_msg = self.download_broadcast("BRDC", date, rinex_version)
            if brdc_success: return True, f"SP3 failed, used Broadcast.\n{brdc_msg}", "broadcast"
        
        return False, error_msg, "none"

    def _try_download_sp3(self, center, orbit, date, out_dir, log_list, duration='01D'):
        """Tries Legacy, Modern (05M), and Modern (15M) formats."""
        

        if duration == '01D':
            fname = self.make_sp3_filename_legacy(center, date, orbit)
            if fname:
                fpath = out_dir / fname
                if fpath.exists(): return True, fpath, None
                url = self.build_sp3_url(fname, date)
                success, _ = self.download_file(url, fpath)
                if success: return True, fpath, url
                log_list.append(url)


        fname = self.make_sp3_filename(center, date, orbit, duration)
        if fname:
            fpath = out_dir / fname
            if fpath.exists(): return True, fpath, None
            
            url = self.build_sp3_url(fname, date)
            success, _ = self.download_file(url, fpath)
            if success: return True, fpath, url
            log_list.append(url)


            if "05M" in fname:
                fname_15m = fname.replace("05M", "15M")
                fpath_15m = out_dir / fname_15m
                url_15m = self.build_sp3_url(fname_15m, date)
                success_15m, _ = self.download_file(url_15m, fpath_15m)
                if success_15m: return True, fpath_15m, url_15m
                log_list.append(url_15m)

        return False, None, None

    def _try_download_clk(self, center, orbit, date, out_dir, log_list, duration='01D'):

        if duration == '01D':
            fname = self.make_clk_filename_legacy(center, date, orbit)
            if fname:
                fpath = out_dir / fname
                if fpath.exists(): return True, fpath, None
                url = self.build_sp3_url(fname, date)
                success, _ = self.download_file(url, fpath)
                if success: return True, fpath, url


        fname = self.make_clk_filename(center, date, orbit, duration)
        if fname:
            fpath = out_dir / fname
            if fpath.exists(): return True, fpath, None
            url = self.build_sp3_url(fname, date)
            success, _ = self.download_file(url, fpath)
            if success: return True, fpath, url
            
        return False, None, None




    def determine_ionosphere_type(self, date):
        if isinstance(date, datetime.datetime): date = date.date()
        today = datetime.date.today()
        days_ago = (today - date).days
        if days_ago >= IONOSPHERE_TYPES['final']['delay_days']: return 'final'
        elif days_ago >= IONOSPHERE_TYPES['rapid']['delay_days']: return 'rapid'
        return 'predicted'

    def download_ionosphere(self, date, ion_type='auto') -> Tuple[bool, str]:
        """Download IGS IONEX products.

        Supports both the current long filename convention used since GPS week
        2238 and the older legacy IONEX filenames.  The current route is tried
        first for final/rapid products; the legacy route is retained for older
        archives and predicted products.
        """
        try:
            date = self.parse_date(date)
            if ion_type == 'auto': ion_type = self.determine_ionosphere_type(date)
            ion_dir = self.output_dir / 'ionosphere'
            ion_dir.mkdir(parents=True, exist_ok=True)



            gps_week, _ = self.get_gps_week_day(date)
            long_type_map = {'final': 'FIN', 'rapid': 'RAP'}
            current_types = [ion_type] + [t for t in ['final', 'rapid'] if t != ion_type]
            attempted = []
            for current_type in current_types:
                if current_type not in long_type_map:
                    continue
                typ = long_type_map[current_type]
                doy = str(self.day_of_year(date)).zfill(3)
                filename = f"IGS0OPS{typ}_{date.year}{doy}0000_01D_02H_GIM.INX.gz"
                filepath = ion_dir / filename
                extracted = filepath.with_suffix('')
                if extracted.exists(): return True, f"Exists [{current_type}]"
                if filepath.exists():
                    self._extract_file(filepath)
                    return True, f"Exists [{current_type}]"
                url = f"{IONOSPHERE_URL}/{gps_week}/{filename}"
                attempted.append(url)
                success, msg = self.download_file(url, filepath)
                if success:
                    self._extract_file(filepath)
                    return True, f"{msg} [{current_type}] -> LINK: {url}"


            types_to_try = [ion_type] + [t for t in ['final', 'rapid', 'predicted'] if t != ion_type]
            for current_type in types_to_try:
                prefix = IONOSPHERE_TYPES.get(current_type, {}).get('prefix', 'igsg')
                doy = str(self.day_of_year(date)).zfill(3)
                year_short = str(date.year)[-2:]
                filename = f"{prefix}{doy}0.{year_short}i.Z"
                filepath = ion_dir / filename
                if filepath.exists(): return True, f"Exists [{current_type}]"
                url = f"{IONOSPHERE_URL}/{date.year}/{doy}/{filename}"
                attempted.append(url)
                success, msg = self.download_file(url, filepath)
                if success:
                    self._extract_file(filepath)
                    return True, f"{msg} [{current_type}] -> LINK: {url}"

            if attempted:
                return False, "Ionosphere not found. Last checked: " + attempted[-1]
            return False, "Ionosphere not found."
        except Exception as e: return False, f"Ionosphere error: {e}"

    def _extract_file(self, filepath: Path):
        s_path = str(filepath)
        if s_path.endswith('.gz'): self.extract_gz(filepath)
        elif s_path.endswith('.Z'): self.extract_z(filepath)

    def extract_gz(self, filepath):
        try:
            output = filepath.with_suffix('')
            if output.exists(): return
            with gzip.open(filepath, 'rb') as f_in, open(output, 'wb') as f_out:
                f_out.write(f_in.read())
        except Exception as e: print(f"GZ Error: {e}")

    def extract_z(self, filepath):
        try:
            output = filepath.with_suffix('')
            if output.exists(): return
            try:
                import unlzw3
                with open(filepath, 'rb') as f_in: data = unlzw3.unlzw(f_in.read())
                with open(output, 'wb') as f_out: f_out.write(data)
            except ImportError: print("Warning: 'unlzw3' not installed.")
        except Exception as e: print(f"Z Error: {e}")