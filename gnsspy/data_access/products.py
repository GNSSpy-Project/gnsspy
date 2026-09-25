"""GNSS navigation, orbit, clock and ionosphere product acquisition."""

import gzip
from dataclasses import dataclass, field
import warnings
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

from gnsspy.utils.product_files import (
    SOLUTION_CODES, SOLUTION_NAMES, MGEX_CENTRES, ProductName,
    normalise_center, normalise_orbit_type, product_spec, product_sort_key,
    parse_product_name, long_product_filename, find_product_files,
    local_product_paths, validate_product_file,
)


@dataclass(frozen=True)
class ProductAcquisition:
    path: Optional[Path] = None
    action: str = "missing"
    url: Optional[str] = None
    detail: str = ""


@dataclass(frozen=True)
class PreciseProductResult:
    sp3: ProductAcquisition = field(default_factory=ProductAcquisition)
    clk: ProductAcquisition = field(default_factory=ProductAcquisition)
    attempted_urls: tuple = ()
    errors: tuple = ()
    broadcast_used: bool = False

    @property
    def success(self):
        return self.sp3.path is not None or self.broadcast_used

    @property
    def mode(self):
        if self.broadcast_used:
            return "broadcast"
        return "precise" if self.sp3.path and self.clk.path else "precise_partial" if self.sp3.path else "none"

    @property
    def message(self):
        lines = []
        for label,item in (("SP3",self.sp3),("CLK",self.clk)):
            if item.path:
                verb = "reused locally (no download)" if item.action == "reused" else "downloaded"
                lines.append(f"{label} {verb}: {item.path}")
                if item.url:
                    lines.append(f"  {label} LINK: {item.url}")
            else:
                lines.append(f"{label} {item.action}" + (f": {item.detail}" if item.detail else ""))
        if self.errors:
            lines.append("Last acquisition error: " + self.errors[-1])
        return "\n".join(lines)


class NavigationDownloader(BaseDownloader):
    """
    Downloader class for GNSS Navigation, Orbit (SP3), Clock (CLK), and Ionosphere data.
    """

    def __init__(self, username, password, output_dir):
        super().__init__(username, password, output_dir)
        self.timeout = (10, 30)
        self.last_precise_result = None
        self.last_ionosphere_result = None
        self.ionosphere_max_attempts = 32
        self.precise_max_attempts = 64
        self._precise_abort = False
        self._precise_errors = []


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


    def make_sp3_filename(self, center, date, orbit_type='final', duration=None,
                          sampling=None, project=None, hour=0):
        """Generate a modern candidate; 05M/15M availability is resolved separately."""
        center, selected_project, selected_solution, version = product_spec(center)
        orbit_type = normalise_orbit_type(orbit_type)
        if center is None or orbit_type == 'auto':
            raise ValueError('A specific centre and orbit type are needed to generate one filename')
        solution = SOLUTION_CODES[orbit_type]
        if selected_solution and selected_solution != solution:
            raise ValueError('Requested series conflicts with orbit_type')
        return long_product_filename(self.parse_date(date),'sp3',center,project or selected_project,
                                     solution,duration,sampling,hour,version=version or '0') + '.gz'

    def make_sp3_filename_legacy(self, center, date, orbit_type='final', hour=0):
        gps_week,dow = self.get_gps_week_day(date)
        center = normalise_center(center)
        orbit_type = normalise_orbit_type(orbit_type)
        if orbit_type == 'final':
            return f'{center.lower()}{gps_week:04d}{dow}.sp3.Z'
        if center != 'IGS':
            return None
        if orbit_type == 'rapid':
            return f'igr{gps_week:04d}{dow}.sp3.Z'
        if orbit_type == 'ultra-rapid':
            return f'igu{gps_week:04d}{dow}_{hour:02d}.sp3.Z'
        return None

    def build_sp3_urls(self, filename, date):
        """Use the content start week, including ultra-rapid year/week boundaries."""
        info = parse_product_name(filename)
        archive_date = info.start.date() if info and not info.legacy else self.parse_date(date)
        week,_ = self.get_gps_week_day(archive_date)
        standard = f'{PRODUCTS_URL}/{week}/{filename}'
        mgex = f'{PRODUCTS_URL}/mgex/{week}/{filename}'


        return [mgex,standard] if info and info.project == 'MGX' else [standard,mgex]

    def build_sp3_url(self, filename, date):
        return self.build_sp3_urls(filename,date)[0]

    def make_clk_filename(self, center, date, orbit_type='final', duration='01D',
                          sampling='30S', project=None, hour=0):
        center, selected_project, selected_solution, version = product_spec(center)
        orbit_type = normalise_orbit_type(orbit_type)
        if center is None or orbit_type == 'auto':
            raise ValueError('A specific centre and orbit type are needed to generate one filename')
        if center == 'IGS' and orbit_type == 'ultra-rapid':
            return None
        solution = SOLUTION_CODES[orbit_type]
        if selected_solution and selected_solution != solution:
            raise ValueError('Requested series conflicts with orbit_type')
        return long_product_filename(self.parse_date(date),'clk',center,project or selected_project,
                                     solution,duration,sampling,hour,version=version or '0') + '.gz'

    def make_clk_filename_legacy(self, center, date, orbit_type='final'):
        gps_week,dow = self.get_gps_week_day(date)
        center = normalise_center(center)
        if orbit_type == 'final':
            return f'{center.lower()}{gps_week:04d}{dow}.clk.Z'
        if center == 'IGS' and orbit_type == 'rapid':
            return f'igr{gps_week:04d}{dow}.clk.Z'
        return None

    def _product_candidates(self, center, orbit, date, kind, duration='01D', project=None):
        """Finite candidates, with symmetric 05M/15M and OPS/MGX support."""
        center = normalise_center(center)
        preferred = 'MGX' if center in MGEX_CENTRES else 'OPS'
        projects = [project] if project else [preferred, 'OPS' if preferred == 'MGX' else 'MGX']

        if not project and center not in MGEX_CENTRES:
            projects = ['OPS']
        modern = []
        for campaign in projects:
            rates = (['05M','15M'] if campaign == 'MGX' else ['15M','05M']) if kind == 'sp3' else ['30S','05M','15M','05S']
            if orbit == 'ultra-rapid':
                starts = [(date,0)] + [(date-datetime.timedelta(days=1),h) for h in (18,12,6,0)] + [(date,h) for h in (6,12,18)]
            else:
                starts = [(date,0)]
            for start,hour in starts:
                for rate in rates:
                    maker = self.make_sp3_filename if kind == 'sp3' else self.make_clk_filename
                    name = maker(center,start,orbit,'02D' if orbit == 'ultra-rapid' else duration,
                                 rate,campaign,hour)
                    if name:
                        modern.append((name,start))
        legacy = []
        if duration == '01D' and (project is None or project == 'OPS'):
            maker = self.make_sp3_filename_legacy if kind == 'sp3' else self.make_clk_filename_legacy
            if orbit == 'ultra-rapid' and kind == 'sp3':
                legacy = [(maker(center,date,orbit,h),date) for h in (0,6,12,18)]
            else:
                legacy = [(maker(center,date,orbit),date)]
            legacy = [(name,stamp) for name,stamp in legacy if name]
        return legacy+modern if date < datetime.date(2022,11,27) else modern+legacy

    def _local_product(self, kind, date, centers, orbit_types, project=None, version=None):
        paths = local_product_paths(self.output_dir,kind) + local_product_paths(None,kind)
        infos = find_product_files(date,kind,files=paths)
        infos = [info for info in infos if info.center in centers
                 and info.solution in {SOLUTION_CODES[value] for value in orbit_types}
                 and (project is None or info.project == project)
                 and (version is None or info.version == version)]
        infos.sort(key=lambda info: product_sort_key(info,centers[0]))
        for info in infos:
            if validate_product_file(info.path,kind):
                return info
            warnings.warn(f'Ignoring invalid {kind.upper()} cache entry: {info.path}',RuntimeWarning,stacklevel=3)
        return None

    def _try_download_product(self, center, orbit, date, out_dir, log_list,
                              kind, duration='01D', project=None):
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True,exist_ok=True)
        for name,stamp in self._product_candidates(center,orbit,date,kind,duration,project):
            if self._precise_abort:
                break
            path = out_dir/name
            for local in (path.with_suffix(''),path):
                if local.is_file() and validate_product_file(local,kind):
                    return True,local,None
            for url in self.build_sp3_urls(name,stamp):
                if url in log_list:
                    continue
                if len(log_list) >= self.precise_max_attempts:
                    self._precise_abort = True
                    self._precise_errors.append(f'Precise-product request limit ({self.precise_max_attempts}) reached')
                    break
                log_list.append(url)
                success,message = self.download_file(url,path)
                if success and validate_product_file(path,kind):
                    reused = str(message).lower().startswith('reused locally')
                    return True,path,None if reused else url
                if success:
                    message = 'Downloaded response is not a readable ' + kind.upper() + ' product'
                self._precise_errors.append(f'{message} | {url}')
                lowered = str(message).lower()
                if any(term in lowered for term in ('401','403','authorization','authentication',
                                                    'connection error','timeout','html','redirect')):


                    self._precise_abort = True
                    break
        return False,None,None

    def _try_download_sp3(self, center, orbit, date, out_dir, log_list, duration='01D', project=None):
        return self._try_download_product(center,orbit,date,out_dir,log_list,'sp3',duration,project)

    def _try_download_clk(self, center, orbit, date, out_dir, log_list, duration='01D', project=None):
        return self._try_download_product(center,orbit,date,out_dir,log_list,'clk',duration,project)

    def acquire_precise_products(self, center='CODE', date=None, orbit_type='auto',
                                 strict_center=True, *, allow_download=True, download_clk=True):
        """Acquire precise products, checking local files before downloading.

        Auto selection prioritises FIN, RAP, then ULT. Explicit solution requests
        are strict. strict_center controls centre selection, not solution quality.
        CLK selection matches the SP3 centre, project, solution and version.
        The result includes paths and per-file acquisition actions.
        """
        date = self.parse_date(date)
        requested,project,series_solution,version = product_spec(center)
        if requested is None:
            requested = 'COD'
            strict_center = False
        orbit_type = normalise_orbit_type(orbit_type)
        if series_solution:
            if series_solution not in SOLUTION_NAMES:
                raise ValueError('Only FIN, RAP and ULT acquisition is supported')
            if orbit_type != 'auto' and SOLUTION_CODES[orbit_type] != series_solution:
                raise ValueError('Requested series conflicts with orbit_type')
            orbit_type = SOLUTION_NAMES[series_solution]
        centers = [requested] if strict_center else list(dict.fromkeys([requested,'COD','GFZ','IGS','WUM','EMR']))
        orbits = ['final','rapid','ultra-rapid'] if orbit_type == 'auto' else [orbit_type]
        self._precise_abort = False
        self._precise_errors = []
        attempted = []
        sp3 = ProductAcquisition(detail=f'No matching {center}/{orbit_type} product for {date}')
        clk = ProductAcquisition(action='missing' if download_clk else 'disabled')
        info = self._local_product('sp3',date,centers,orbits,project,version)
        if info:
            sp3 = ProductAcquisition(info.path,'reused')
        elif allow_download:
            if version not in {None,'0'}:
                self._precise_errors.append('Automatic remote candidates use version 0; supply this version locally')
            else:
                for orbit in orbits:
                    for current_center in centers:
                        ok,path,url = self._try_download_sp3(current_center,orbit,date,
                            self.output_dir/'sp3',attempted,project=project)
                        if not ok and orbit == 'final' and not self._precise_abort:
                            _,dow = self.get_gps_week_day(date)
                            sunday = date-datetime.timedelta(days=dow)

                            ok,path,url = self._try_download_sp3(current_center,orbit,sunday,
                                self.output_dir/'sp3',attempted,'07D',project)
                        if ok:
                            sp3 = ProductAcquisition(path,'downloaded' if url else 'reused',url)
                            info = parse_product_name(path)
                            break
                        if self._precise_abort:
                            break
                    if info or self._precise_abort:
                        break
        if info and download_clk:
            orbit = SOLUTION_NAMES.get(info.solution)
            local_clock = self._local_product('clk',date,[info.center],[orbit],info.project,info.version) if orbit else None
            if local_clock:
                clk = ProductAcquisition(local_clock.path,'reused')
            elif allow_download and not self._precise_abort and orbit and info.version == '0':
                ok,path,url = self._try_download_clk(info.center,orbit,date,self.output_dir/'clk',
                                                     attempted,project=info.project)
                if not ok and info.duration == '07D' and not self._precise_abort:
                    ok,path,url = self._try_download_clk(info.center,orbit,info.start.date(),
                                self.output_dir/'clk',attempted,'07D',info.project)
                if ok:
                    clk = ProductAcquisition(path,'downloaded' if url else 'reused',url)
            if clk.path is None:
                clk = ProductAcquisition(detail=f'No matching {info.center}/{info.project}/{info.solution} clock; SP3 remains available')
        result = PreciseProductResult(sp3,clk,tuple(attempted),tuple(self._precise_errors))
        self.last_precise_result = result
        return result

    def download_sp3_with_fallback(self, center='CODE', date=None, orbit_type='auto',
                                   fallback_to_broadcast=True, rinex_version=3,
                                   strict_center=True, *, allow_download=True, download_clk=True):
        """Return availability, message and product mode as a tuple.

        Inspect last_precise_result for per-file paths and actions. Explicit quality
        requests remain strict regardless of strict_center.
        """
        result = self.acquire_precise_products(center,date,orbit_type,strict_center,
                                               allow_download=allow_download,download_clk=download_clk)
        if not result.success and fallback_to_broadcast and allow_download and not self._precise_abort:
            ok,msg = self.download_broadcast('BRDC',date,rinex_version)
            if ok:
                self.last_precise_result = PreciseProductResult(result.sp3,result.clk,
                                                result.attempted_urls,result.errors,True)
                return True,'SP3 unavailable; used broadcast.\n'+msg,'broadcast'
        return result.success,result.message,result.mode


    def determine_ionosphere_type(self, date):
        """Estimate final or rapid product latency without checking availability."""
        date = self.parse_date(date)
        days_ago = (datetime.date.today() - date).days
        return 'final' if days_ago >= IONOSPHERE_TYPES['final']['delay_days'] else 'rapid'

    def acquire_ionosphere(self, date, ion_type='auto', *, product='IGS',
                           allow_download=True, sampling=None, max_attempts=None):
        from .ionosphere import acquire_ionosphere
        return acquire_ionosphere(self, date, ion_type, product=product,
                                  allow_download=allow_download, sampling=sampling,
                                  max_attempts=max_attempts)

    def download_ionosphere(self, date, ion_type='auto', **kwargs) -> Tuple[bool, str]:
        """Return product availability and a status message.

        Inspect last_ionosphere_result for the path and acquisition action.
        The returned path can be passed directly to the IONEX reader.
        """
        result = self.acquire_ionosphere(date, ion_type, **kwargs)
        return result.success, result.message

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
