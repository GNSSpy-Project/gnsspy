

import os
import http.client


from gnsspy.data_access.observation import ObservationDownloader
from gnsspy.data_access.products import NavigationDownloader
from gnsspy.data_access.utils import load_credentials


from gnsspy.utils.date import doy2date, gpswdtodate
from gnsspy.io.manipulate import crx2rnx
from gnsspy.data.IGS import is_IGS



global _CWD
_CWD = os.getcwd() 

def isfloat(value):
    """ Check if variable is float """
    try:
        float(value)
        return True
    except ValueError:
        return False

def isint(value):
    """ Check if variable is integer """
    try:
        int(value)
        return True
    except ValueError:
        return False

def check_internet():
    """ Check internet connectivity """
    connection = http.client.HTTPConnection("www.google.com", timeout=5)
    try:
        connection.request("HEAD", "/")
        connection.close()
        return True
    except:
        connection.close()
        return False

def _get_credentials():
    """ Load credentials """
    username, password = load_credentials()
    if not username or not password:
        print("\n[WARNING] NASA Earthdata credentials not found!")
        print("Please run 'gnsspy.login(user, pass)' first or check your .netrc file.")
        return None, None
    return username, password

def isexist(fileName):
    """
    Checks if file exists, otherwise attempts to download
    using the new backend system.
    
    Search order:
    1. Verilen tam yol
    2. backend/data/ directory structure (sp3/, clk/, observation/, etc.)
    3. Working directory
    4. Download (if not found)
    """

    if os.path.exists(fileName):
        return True
    


    basename = os.path.basename(fileName)
    ext = basename.split('.')[-1].lower()
    

    possible_data_dirs = [
        os.path.join(_CWD, "gnsspy", "backend", "data"),
        os.path.join(_CWD, "backend", "data"),
        os.path.join(_CWD, "data"),
    ]
    
    for data_dir in possible_data_dirs:
        if not os.path.exists(data_dir):
            continue
            

        if ext == 'sp3':
            subdir = "sp3"
        elif 'clk' in ext:
            subdir = "clk"
        elif ext in ['rnx', 'crx', 'o', 'd']:
            subdir = "observation"
        elif ext in ['n', 'p', 'g']:
            subdir = "navigation"
        elif ext == 'i':
            subdir = "ionosphere"
        else:
            subdir = None
        
        if subdir:
            full_path = os.path.join(data_dir, subdir, basename)
            if os.path.exists(full_path):
                print(f"   Found: {full_path}")


                return True
    

    if os.path.exists(fileName + ".Z"):

        print(f"{fileName}.Z exists. (Use download module for auto-extraction)")
        return True


    print(f"{fileName} not found in working directory. Attempting download...")
    
    if not check_internet():
        raise ConnectionError("No internet connection! Cannot download.")


    username, password = _get_credentials()
    if not username:
        return False


    obs_dl = ObservationDownloader(username, password, _CWD)
    nav_dl = NavigationDownloader(username, password, _CWD)


    try:


        
        parts = fileName.split('.')
        ext = parts[-1].lower()
        
        if ext == 'sp3':



            basename = parts[0]
            

            try:
                gpsweekday_str = basename[-5:]

                fileEpoch = gpswdtodate(gpsweekday_str)
                print(f"   SP3 date: {fileEpoch} (GPS Week/Day: {gpsweekday_str})")
            except Exception as e:
                print(f"GPS week/day parse error: {e}")
                return False
        else:

            fileEpoch = doy2date(fileName)
            
    except Exception as e:
        print(f"Date format could not be parsed: {fileName} | Error: {e}")
        return False




    
    parts = fileName.split('.')
    ext = parts[-1].lower()
    
    success = False
    msg = ""


    if ext[-1] == 'o' and len(ext) == 3:
        station = fileName[:4]
        if is_IGS(station):

            success, msg = obs_dl.download_single(station, fileEpoch, rinex_version=2)
        else:
            print(f"{station} not found in IGS station list.")


    elif ext in ['rnx', 'crx']:
        station = fileName[:4]

        success, msg = obs_dl.download_single(station, fileEpoch, rinex_version=3)
        

        if success:


            potential_crx = fileName.replace('.rnx', '.crx')
            if os.path.exists(potential_crx):
                print(f"Decompressing Hatanaka: {potential_crx}")
                crx2rnx(potential_crx)


    elif ext[-1] in ['n', 'p', 'g'] and len(ext) == 3:
        station = fileName[:4]


        success, msg = nav_dl.download_broadcast(station, fileEpoch, rinex_version=2)


    elif ext == 'sp3':



        center_prefix = fileName[:3].upper()
        
        success, msg, mode = nav_dl.download_sp3_with_fallback(
            center=center_prefix, 
            date=fileEpoch,
            orbit_type='final'
        )


    elif 'clk' in ext:

        center_prefix = fileName[:3].upper()
        success, msg, mode = nav_dl.download_sp3_with_fallback(
            center=center_prefix, 
            date=fileEpoch
        )


    elif ext[-1] == 'i' and len(ext) == 3:
        success, msg = nav_dl.download_ionosphere(fileEpoch, ion_type='auto')

    else:
        print(f"Unknown file extension: {ext}")
        return False


    if success:
        print(f" [SUCCESS] {msg}")
        return True
    else:
        print(f" [ERROR] Download failed: {msg}")

        return False