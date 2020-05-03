# ===========================================================
# ========================= imports =========================
import os
from  patoolib import extract_archive
import http.client
from gnsspy import download
from gnsspy.doc.IGS import IGS, is_IGS
from gnsspy.funcs.date import doy2date
from gnsspy.io.manipulate import crx2rnx
# ===========================================================

global _CWD
_CWD = os.getcwd() 

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
            extension = fileName.split(".")[1]
            if extension[-1].lower() == "o":
                if is_IGS(fileName[:4]) == True:
                    print(fileName + ".Z does not exist in working directory | Downloading...")
                    fileEpoch = doy2date(fileName)
                    download.get_rinex([fileName[:4]], fileEpoch, Datetime = True)
                    print(" | Download completed for", fileName + ".Z", " | Extracting...")
                    extract_archive(fileName + ".Z", outdir=_CWD)
                else:
                    raise Warning(fileName,"does not exist in directory and cannot be found in IGS Station list!")
            elif extension.lower() == "rnx":
                if is_IGS(fileName[:4]) == True:
                    print(fileName + " does not exist in working directory | Downloading...")
                    fileName = fileName.split(".")[0] + ".crx"
                    fileEpoch = doy2date(fileName)
                    download.get_rinex3([fileName[:4]], fileEpoch, Datetime = True)
                    print(" | Download completed for", fileName + ".gz", " | Extracting...")
                    extract_archive(fileName + ".gz", outdir=_CWD)
                    crx2rnx(fileName)
                else:
                    raise Warning(fileName,"does not exist in directory and cannot be found in IGS Station list!")
            elif extension.lower() == "crx":
                if is_IGS(fileName[:4]) == True:
                    print(fileName + ".gz does not exist in working directory | Downloading...")
                    fileEpoch = doy2date(fileName)
                    download.get_rinex3([fileName[:4]], fileEpoch, Datetime = True)
                    extract_archive(fileName + ".gz", outdir=_CWD)
                    crx2rnx(fileName)
                else:
                    raise Warning(fileName,"does not exist in directory and cannot be found in IGS Station list!")
            elif extension[-1].lower() in {"n","p","g"}:
                if is_IGS(fileName[:4]) == True:
                    print(fileName + ".Z does not exist in working directory | Downloading...")
                    fileEpoch = doy2date(fileName)
                    download.get_navigation([fileName[:4]], fileEpoch, Datetime = True)
                    extract_archive(fileName + ".Z", outdir=_CWD)
            elif extension.lower() in {"clk","clk_05s"}:
                download.get_clock(fileName)
                extract_archive(fileName + ".Z", outdir=_CWD)
            elif extension.lower() == "sp3":
                download.get_sp3(fileName)
                extract_archive(fileName + ".Z", outdir=_CWD)
            elif extension[-1].lower() == "i":
                download.get_ionosphere(fileName)
                extract_archive(fileName + ".Z", outdir=_CWD)
            else:
                raise Warning("Unknown file extension:",extension.lower())
        elif (os.path.exists(fileName + ".Z") == True) and (fileName.endswith(".Z")==True):
            print(fileName + " exists in working directory | Extracting...")
            extract_archive(fileName, outdir=_CWD)
        else:
            print(fileName + ".Z exists in working directory | Extracting...")
            extract_archive(fileName + ".Z", outdir=_CWD)
    elif (os.path.exists(fileName) == True) and (fileName.endswith(".Z")==True):
        print(fileName + " exists in working directory | Extracting...")
        extract_archive(fileName, outdir=_CWD)
    else:
        print(fileName + " exist in working directory | Reading...")
