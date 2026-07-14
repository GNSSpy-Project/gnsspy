"""
Common functions for all downloaders
"""

import datetime
import requests
from gnsspy.utils.date import parse_date as _parse_date
from requests.auth import _basic_auth_str
from urllib.parse import urlparse
from pathlib import Path


class EarthdataSession(requests.Session):
    """Requests session for NASA Earthdata/CDDIS redirects.

    The initial request is sent to cddis.nasa.gov without a Basic-Auth header.
    When CDDIS redirects to urs.earthdata.nasa.gov, the Basic-Auth header is
    added. When URS redirects back to CDDIS, the Authorization header is removed
    again. This follows the Earthdata redirect model more safely than preserving
    the same Authorization header for every host.
    """

    AUTH_HOST = "urs.earthdata.nasa.gov"

    def __init__(self, username=None, password=None):
        super().__init__()
        self.username = username
        self.password = password

    def rebuild_auth(self, prepared_request, response):
        """Control where the Earthdata username/password are sent."""
        try:
            redirect_hostname = urlparse(prepared_request.url).hostname
        except Exception:
            redirect_hostname = None


        prepared_request.headers.pop("Authorization", None)
        if redirect_hostname == self.AUTH_HOST and self.username and self.password:
            prepared_request.headers["Authorization"] = _basic_auth_str(
                self.username,
                self.password,
            )

class BaseDownloader:
    """Base class for all downloaders to inherit from"""
    
    def __init__(self, username, password, output_dir):
        self.username = username
        self.password = password
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)


        self.session = EarthdataSession(username, password)
        self.session.max_redirects = 10
        

        self.timeout = 120
        

        self.debug = False
    
    def day_of_year(self, date):
        """Day of year (001-366)"""
        return date.timetuple().tm_yday
    
    def parse_date(self, date_str):
        """Convert common GNSSpy date inputs to ``datetime.date``."""
        return _parse_date(date_str)
    
    def download_file(self, url, filepath):
        """
        Download file (using session)
        
        Returns:
            tuple: (success, message)
        """
        try:
            if self.debug:
                print(f"  [DEBUG] URL: {url}")
            

            response = self.session.get(
                url, 
                timeout=self.timeout,
                allow_redirects=True
            )
            
            if self.debug:
                print(f"  [DEBUG] Status: {response.status_code}")
                print(f"  [DEBUG] Content-Type: {response.headers.get('content-type', 'N/A')}")
                print(f"  [DEBUG] Content-Length: {len(response.content)} bytes")
            
            if response.status_code == 404:
                return False, "File not found (404)"
            
            if response.status_code == 401:
                return False, "Authorization error (401)"
            
            if response.status_code == 403:
                return False, "Access denied (403 - CDDIS authorization required)"
            
            if response.status_code != 200:
                return False, f"HTTP {response.status_code}"
            

            content_type = response.headers.get('content-type', '').lower()
            if 'html' in content_type or 'text/html' in content_type:
                if self.debug:
                    print(f"  [DEBUG] HTML Response (first 300 characters):")
                    print(f"  {response.text[:300]}")
                return False, "File not found (HTML page returned)"
            

            with open(filepath, 'wb') as f:
                f.write(response.content)
            

            size = filepath.stat().st_size
            
            if size < 1000:
                return False, f"File too small ({size} bytes)"
            
            size_mb = size / (1024 * 1024)
            return True, f"{size_mb:.2f} MB"
        
        except requests.exceptions.ConnectionError:
            return False, "Connection error: Check your internet connection"
        
        except requests.exceptions.Timeout:
            return False, "Timeout"
        
        except Exception as e:
            return False, f"Unknown error: {str(e)}"
