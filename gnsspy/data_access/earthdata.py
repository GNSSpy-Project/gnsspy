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
        """Atomic download; never label cache reuse as a network transfer.

        A failed HTTP/HTML/short/invalid response does not create or overwrite
        the destination. Precise products receive a lightweight header/data check.
        """
        import os
        import tempfile
        from gnsspy.utils.product_files import product_kind, validate_product_file
        filepath = Path(filepath)
        kind = product_kind(filepath)
        from gnsspy.utils.ionex_files import is_ionex_path
        ionex = is_ionex_path(filepath)

        def valid_ionex(candidate):
            from gnsspy.data_access.ionosphere import validate_ionex_payload
            try:
                validate_ionex_payload(candidate, expected_name=filepath)
                return True
            except (OSError, ValueError, ImportError, EOFError):
                return False
        temporary = None
        try:
            if filepath.is_file() and filepath.stat().st_size:
                usable = (validate_product_file(filepath,kind) if kind else
                          valid_ionex(filepath) if ionex else filepath.stat().st_size >= 1000)
                if usable:
                    return True,f"Reused locally (no download): {filepath}"
            if self.debug:
                print(f"  [DEBUG] URL: {url}")
            with self.session.get(url,timeout=self.timeout,allow_redirects=True) as response:
                status = response.status_code
                if status != 200:
                    messages = {404:'File not found (404)',401:'Authorization error (401)',
                                403:'Access denied (403 - CDDIS authorization required)'}
                    return False,messages.get(status,f'HTTP {status}')
                content = response.content
                content_type = response.headers.get('content-type','').lower()
                lead = content.lstrip()[:256].lower()
                if 'html' in content_type or lead.startswith((b'<!doctype html',b'<html')):
                    return False,'HTML login/error page returned, not product data'
                if not content or (not kind and not ionex and len(content) < 1000):
                    return False,f'File too small ({len(content)} bytes)'
                filepath.parent.mkdir(parents=True,exist_ok=True)


                fd,name = tempfile.mkstemp(prefix='.'+filepath.name+'.',suffix='.part'+filepath.suffix,
                                           dir=filepath.parent)
                temporary = Path(name)
                with os.fdopen(fd,'wb') as stream:
                    stream.write(content)
                if kind and not validate_product_file(temporary,kind):
                    return False,f'Invalid {kind.upper()} response (header/data check failed)'
                if ionex and not valid_ionex(temporary):
                    return False, 'Invalid IONEX response (complete GIM parsing/content-date check failed)'
                os.replace(temporary,filepath)
                temporary = None
                return True,f'Downloaded {len(content)/(1024*1024):.2f} MB: {filepath}'
        except requests.exceptions.ConnectionError:
            return False,'Connection error: check the network'
        except requests.exceptions.Timeout:
            return False,'Timeout'
        except requests.exceptions.TooManyRedirects:
            return False,'Too many redirects (check Earthdata authentication)'
        except (OSError,ValueError) as exc:
            return False,f'Download error: {exc}'
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
