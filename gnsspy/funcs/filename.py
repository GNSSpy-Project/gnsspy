# ===========================================================
# ========================= imports =========================
import sys
import datetime
from gnsspy.funcs.funcs import (gpsweekday, datetime2doy)
from gnsspy.doc.IGS import IGS, is_IGS
# ===========================================================

def obsFileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True)
    if len(doy) == 1:
        rinexFile = stationName + doy + "0." + str(date.year)[-2:] + "o"
    elif len(doy) == 2:
        rinexFile = stationName + doy + "0." + str(date.year)[-2:] + "o"
    else:
        rinexFile = stationName + doy + "0." + str(date.year)[-2:] + "o"
    
    if zipped == True:
        rinexFile = rinexFile + ".Z"
    
    return rinexFile

def sp3FileName(epoch, product="igs"):
    now = datetime.date.today() # today's date
    timeDif = now - epoch # time difference between rinex epoch and today

    if timeDif.days == 0:
        raise Warning("IGS orbit files are not released for", epoch.ctime())
        sys.exit("Exiting...")
    elif 0 < timeDif.days < 13:
        print("IGS final orbit file is not released for", epoch.ctime(), "\nDownloading IGS Rapid orbit file...")
        product = 'igr' # sp3 file name
    gpsWeek, gpsWeekday = gpsweekday(epoch, Datetime = True)
    if len(str(gpsWeek)) == 3:
        sp3File = product.lower() + "0" + str(gpsWeekday) + ".sp3"
    else:
        sp3File = product.lower() + str(gpsWeekday) + ".sp3" 
    return sp3File

def clockFileName(epoch, interval=30, product="cod"):
    now = datetime.date.today()
    timeDif = now - epoch

    if timeDif.days == 0:
        raise Warning("IGS clock files are not released for", epoch.ctime())
        sys.exit("Exiting...")
    elif 0 < timeDif.days < 13:
        product = 'igr'
    
    if interval < 30:
        product = 'cod'
        extension = '.clk_05s'
    else:
        extension = '.clk'

    gpsWeek, gpsWeekday = gpsweekday(epoch, Datetime = True) 
    if len(str(gpsWeek)) == 3:
        clockFile = product.lower() + "0" + str(gpsWeekday) + extension
    else:
        clockFile = product.lower() + str(gpsWeekday) + extension
    return clockFile

def ionFileName(date, product = "igs", zipped = False):
    doy = datetime2doy(date, string = True)
    if len(doy) == 1:
        ionFile = product + "g" + doy + "0." + str(date.year)[-2:] + "i"
    elif len(doy) == 2:
        ionFile = product + "g" + doy + "0." + str(date.year)[-2:] + "i"
    else:
        ionFile = product + "g" + doy + "0." + str(date.year)[-2:] + "i"

    if zipped == True:
        ionFile = ionFile + ".Z"
    
    return ionFile

def navFileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True)
    if len(doy) == 1:
        rinexFile = stationName + doy + "0." + str(date.year)[-2:] + "n"
    elif len(doy) == 2:
        rinexFile = stationName + doy + "0." + str(date.year)[-2:] + "n"
    else:
        rinexFile = stationName + doy + "0." + str(date.year)[-2:] + "n"
    
    if zipped == True:
        rinexFile = rinexFile + ".Z"
    
    return rinexFile

def nav3FileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True) # for RINEX data names
    siteInfo = IGS(stationName)
    if stationName.upper() == "BRDC":
        rinexFile = "BRDC00IGS_R_" + str(date.year) + str(doy) + "0000_01D_MN.rnx"
    else:
        rinexFile = siteInfo.SITE[0] + "_R_" + str(date.year) + str(doy) + "0000_01D_MN.rnx"
    """
    if len(doy) == 1:
        rinexFile = stationName + doy + "0." + str(date.year)[-2:] + "p"
    elif len(doy) == 2:
        rinexFile = stationName + doy + "0." + str(date.year)[-2:] + "p"
    else:
        rinexFile = stationName + doy + "0." + str(date.year)[-2:] + "p"
    """
    if zipped == True:
        rinexFile = rinexFile + ".gz"
    
    return rinexFile

def obs3FileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True) # for RINEX data names
    siteInfo = IGS(stationName)
    rinexFile = siteInfo.SITE[0] + "_R_" + str(date.year) + str(doy) + "0000_01D_30S_MO.crx"
    if zipped == True:
        rinexFile = rinexFile + ".gz"
    
    return rinexFile
