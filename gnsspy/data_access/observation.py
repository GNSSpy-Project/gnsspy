"""
RINEX observation file downloader
FINAL FIX: 
- RINEX 2 uses .Z extension (not .gz)
- Respects user's version choice
- Multi-folder support (d and o)
- ADDS DOWNLOAD LINKS TO OUTPUT
"""

import gzip

from .earthdata import BaseDownloader
from .utils import get_full_code
from .config import BASE_URL


class ObservationDownloader(BaseDownloader):
    """Downloader for observation files"""
    
    def __init__(self, username, password, output_dir):
        super().__init__(username, password, output_dir)
    
    def make_rinex3_filename(self, station, date, data_source='R'):
        """RINEX 3 observation file name"""
        station_full = get_full_code(station)
        year = date.year
        doy = str(self.day_of_year(date)).zfill(3)
        return f"{station_full}_{data_source}_{year}{doy}0000_01D_30S_MO.crx.gz"
    
    def make_rinex2_filename(self, station, date, file_ext='d'):
        """
        RINEX 2 observation file name
        CRITICAL FIX: Returns .Z extension (not .gz)
        """
        station_lower = station.lower()[:4]
        doy = str(self.day_of_year(date)).zfill(3)
        year_short = str(date.year)[-2:]
        return f"{station_lower}{doy}0.{year_short}{file_ext}.Z"
    
    def build_url(self, date, filename, folder_suffix='d'):
        """Build download URL"""
        year = date.year
        doy = str(self.day_of_year(date)).zfill(3)
        year_short = str(year)[-2:]
        folder = f"{year_short}{folder_suffix}"
        return f"{BASE_URL}/{year}/{doy}/{folder}/{filename}"
    
    def extract_gz(self, filepath):
        """Extract .gz file"""
        try:
            output = filepath.with_suffix('')
            if output.exists():
                return True, f"Already extracted: {output.name}"
            
            with gzip.open(filepath, 'rb') as f_in:
                with open(output, 'wb') as f_out:
                    f_out.write(f_in.read())
            return True, f"Extracted: {output.name}"
        except Exception as e:
            return False, f"gz error: {str(e)}"
    
    def extract_z(self, filepath):
        """
        Extracts .Z files (Windows/Linux compatible - uses unlzw3)
        """
        try:

            output = filepath.with_suffix('')
            if output.exists():
                return True, "Already extracted"
            

            try:
                import unlzw3
                with open(filepath, 'rb') as f_in:
                    compressed_data = f_in.read()
                    uncompressed_data = unlzw3.unlzw(compressed_data)
                
                with open(output, 'wb') as f_out:
                    f_out.write(uncompressed_data)
                    


                return True, "Extracted (unlzw3)"
            
            except ImportError:

                return False, "ERROR: Please install 'pip install unlzw3'!"
                
        except Exception as e:

            output = filepath.with_suffix('')
            if output.exists() and output.stat().st_size == 0:
                output.unlink()
            return False, f".Z Error: {str(e)}"
    
    def download_single(self, station, date, rinex_version=3):
        """
        Download observation file
        """
        date = self.parse_date(date)
        
        base_dir = self.output_dir / 'observation'
        base_dir.mkdir(parents=True, exist_ok=True)
        
        attempted_urls = []
        

        if rinex_version == 3:
            formats_to_try = [3]
            if date.year < 2022:
                formats_to_try.append(2)
        elif rinex_version == 2:
            formats_to_try = [2]
            if date.year >= 2022:
                formats_to_try.append(3)
        else:
            formats_to_try = [3, 2]
        
        if self.debug:
            print(f"  [OBS] User choice: RINEX {rinex_version}")
            print(f"  [OBS] Try order: RINEX {formats_to_try}")
        

        for fmt in formats_to_try:
            if fmt == 3:

                for data_source in ['R', 'S']:
                    filename = self.make_rinex3_filename(station, date, data_source)
                    filepath = base_dir / filename
                    
                    if filepath.exists():
                        if self.debug:
                            print(f"  [OBS] Found existing RINEX 3: {filename}")
                        return True, f"Already exists (RINEX 3, {data_source})"
                    
                    url = self.build_url(date, filename, 'd')
                    attempted_urls.append(url)
                    
                    if self.debug:
                        print(f"  [OBS] Trying (RINEX 3, {data_source}): {filename}")
                        print(f"  [OBS] URL: {url}")
                    
                    success, message = self.download_file(url, filepath)
                    
                    if success:
                        if filename.endswith('.gz'):
                            self.extract_gz(filepath)

                        return True, f"{message} (RINEX 3, {data_source}) -> LINK: {url}"
            
            elif fmt == 2:

                for folder_type in ['d', 'o']:
                    filename = self.make_rinex2_filename(station, date, folder_type)
                    filepath = base_dir / filename
                    
                    if filepath.exists():
                        if self.debug:
                            print(f"  [OBS] Found existing RINEX 2: {filename}")
                        return True, f"Already exists (RINEX 2, .{folder_type})"
                    
                    url = self.build_url(date, filename, folder_type)
                    attempted_urls.append(url)
                    
                    if self.debug:
                        print(f"  [OBS] Trying (RINEX 2, .{folder_type}): {filename}")
                        print(f"  [OBS] URL: {url}")
                    
                    success, message = self.download_file(url, filepath)
                    
                    if success:
                        if filename.endswith('.Z'):
                            self.extract_z(filepath)
                        elif filename.endswith('.gz'):
                            self.extract_gz(filepath)

                        return True, f"{message} (RINEX 2, .{folder_type}) -> LINK: {url}"
        

        error_msg = f"File not found (RINEX {rinex_version} requested)\nAttempted URLs:"
        for url in attempted_urls[:3]:
            error_msg += f"\n  - {url}"
        
        if len(attempted_urls) > 3:
            error_msg += f"\n  ... and {len(attempted_urls)-3} more URLs"
        
        return False, error_msg