# ===========================================================
# ========================= imports =========================
import os
import http.client
from gnsspy import download
from gnsspy.doc.IGS import is_IGS
from gnsspy.funcs.date import doy2date
from hatanaka import decompress_on_disk
# ===========================================================


def isfloat(value):
    """ To check if any variable can be converted to float or not """
    try:
        float(value)
        return True
    except ValueError:
        return False

def isint(value):
    """ To check if any variable can be converted to integer """
    try:
        int(value)
        return True
    except ValueError:
        return False

def check_internet():
    """ To check if there is an internet connection for FTP downloads """
    connection = http.client.HTTPConnection("www.google.com", timeout=5)
    try:
        connection.request("HEAD", "/")
        connection.close()
        return True
    except:
        connection.close()
        return False

def isexist(fileName):
    if os.path.exists(fileName) == False:
        if (os.path.exists(fileName + ".Z") == False) and (fileName.endswith(".Z")==False):
            extension = fileName.split(".")[1].lower()
            if extension[-1] == "o":
                if is_IGS(fileName[:4]):
                    print(fileName + ".Z does not exist in working directory | Downloading...")
                    fileEpoch = doy2date(fileName)
                    download.get_rinex([fileName[:4]], fileEpoch, Datetime = True)
                    print(" | Download completed for", fileName + ".Z", " | Extracting...")
                    decompress_on_disk(fileName + ".Z", delete=True)
                else:
                    raise Warning(fileName,"does not exist in directory and cannot be found in IGS Station list!")
            elif extension == "rnx":
                if is_IGS(fileName[:4]):
                    print(fileName + " does not exist in working directory | Downloading...")
                    fileName = fileName.split(".")[0] + ".crx"
                    fileEpoch = doy2date(fileName)
                    download.get_rinex3([fileName[:4]], fileEpoch, Datetime = True)
                    print(" | Download completed for", fileName + ".gz", " | Extracting...")
                    decompress_on_disk(fileName + ".gz", delete=True)
                else:
                    raise Warning(fileName,"does not exist in directory and cannot be found in IGS Station list!")
            elif extension == "crx":
                if is_IGS(fileName[:4]):
                    print(fileName + ".gz does not exist in working directory | Downloading...")
                    fileEpoch = doy2date(fileName)
                    download.get_rinex3([fileName[:4]], fileEpoch, Datetime = True)
                    decompress_on_disk(fileName + ".gz", delete=True)
                else:
                    raise Warning(fileName,"does not exist in directory and cannot be found in IGS Station list!")
            elif extension[-1] in {"n","p","g"}:
                if is_IGS(fileName[:4]):
                    print(fileName + ".Z does not exist in working directory | Downloading...")
                    fileEpoch = doy2date(fileName)
                    download.get_navigation([fileName[:4]], fileEpoch, Datetime = True)
                    decompress_on_disk(fileName + ".Z", delete=True)
            elif extension in {"clk","clk_05s"}:
                download.get_clock(fileName)
                decompress_on_disk(fileName + ".Z", delete=True)
            elif extension == "sp3":
                download.get_sp3(fileName)
                decompress_on_disk(fileName + ".Z", delete=True)
            elif extension[-1].lower() == "i":
                download.get_ionosphere(fileName)
                decompress_on_disk(fileName + ".Z", delete=True)
            else:
                raise Warning("Unknown file extension:", extension)
        elif os.path.exists(fileName + ".Z"):
            print(fileName + " exists in working directory | Extracting...")
            decompress_on_disk(fileName, delete=True)
        else:
            print(fileName + ".Z exists in working directory | Extracting...")
            decompress_on_disk(fileName + ".Z", delete=True)
    elif os.path.exists(fileName) and fileName.endswith(".Z"):
        print(fileName + " exists in working directory | Extracting...")
        decompress_on_disk(fileName, delete=True)
    else:
        print(fileName + " exist in working directory | Reading...")
