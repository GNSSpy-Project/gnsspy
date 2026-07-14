


import sys
import datetime
from gnsspy.utils.date import (gpsweekday, datetime2doy)
from gnsspy.data.IGS import IGS




def get_long_filename(date, product_type="SP3", agency="IGS", project="OPS", solution="FIN"):
    """
    Generates filenames following the IGS Long Product Filename standard.
    Example: IGS0OPSFIN_20251240000_01D_15M_ORB.SP3
    """
    doy = date.timetuple().tm_yday
    year = date.year
    

    sampling = "15M"
    content = "ORB"
    ext = "SP3"
    
    if product_type.upper() == "CLK":
        sampling = "30S"
        content = "CLK"
        ext = "CLK"
    


    filename = f"{agency}0{project}{solution}_{year}{doy:03d}0000_01D_{sampling}_{content}.{ext}"
    return filename




def obsFileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True)
    year_short = str(date.year)[-2:]
    

    rinexFile = stationName + doy + "0." + year_short + "o"
    
    if zipped:
        rinexFile = rinexFile + ".Z"
    
    return rinexFile




def sp3FileName(epoch, product="igs"):
    now = datetime.date.today()
    timeDif = now - epoch

    if timeDif.days == 0:
        raise Warning("IGS orbit files are not released for", epoch.ctime())
        sys.exit("Exiting...")
    elif 0 < timeDif.days < 13:
        print("IGS final orbit file is not released for", epoch.ctime(), "\nDownloading IGS Rapid orbit file...")
        product = 'igr' 
    

    if epoch.year >= 2022 and product.lower() in ['igs', 'igr']:


        return get_long_filename(epoch, product_type="SP3")


    gpsWeek, _ = gpsweekday(epoch, Datetime = True)
    start = datetime.date(year=1980, month=1, day=6)
    diff_days = (epoch - start).days
    day_of_week = diff_days % 7
    
    week_str = str(gpsWeek)
    if len(week_str) == 3: week_str = "0" + week_str

    sp3File = f"{product.lower()}{week_str}{day_of_week}.sp3"
    
    return sp3File




def clockFileName(epoch, interval=30, product="cod"):
    now = datetime.date.today()
    timeDif = now - epoch

    if timeDif.days == 0:
        raise Warning("IGS clock files are not released for", epoch.ctime())
        sys.exit("Exiting...")
    elif 0 < timeDif.days < 13:
        product = 'igr'
    

    if epoch.year >= 2022 and product.lower() in ['igs', 'cod', 'igr']:
         return get_long_filename(epoch, product_type="CLK")


    if interval < 30:
        product = 'cod'
        extension = '.clk_05s'
    else:
        extension = '.clk'

    gpsWeek, _ = gpsweekday(epoch, Datetime = True)
    start = datetime.date(year=1980, month=1, day=6)
    diff_days = (epoch - start).days
    day_of_week = diff_days % 7
    
    week_str = str(gpsWeek)
    if len(week_str) == 3: week_str = "0" + week_str

    clockFile = f"{product.lower()}{week_str}{day_of_week}{extension}"
    
    return clockFile




def ionFileName(date, product = "igs", zipped = False):
    doy = datetime2doy(date, string = True)
    year_short = str(date.year)[-2:]
    ionFile = product + "g" + doy + "0." + year_short + "i"
    if zipped:
        ionFile = ionFile + ".Z"
    return ionFile

def navFileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True)
    year_short = str(date.year)[-2:]
    rinexFile = stationName + doy + "0." + year_short + "n"
    if zipped:
        rinexFile = rinexFile + ".Z"
    return rinexFile

def nav3FileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True) 
    siteInfo = IGS(stationName)
    if stationName.upper() == "BRDC":
        rinexFile = "BRDC00IGS_R_" + str(date.year) + str(doy) + "0000_01D_MN.rnx"
    else:
        rinexFile = siteInfo.SITE[0] + "_R_" + str(date.year) + str(doy) + "0000_01D_MN.rnx"
    if zipped:
        rinexFile = rinexFile + ".gz"
    return rinexFile

def obs3FileName(stationName, date, zipped = False):
    doy = datetime2doy(date, string = True)
    siteInfo = IGS(stationName)
    rinexFile = siteInfo.SITE[0] + "_R_" + str(date.year) + str(doy) + "0000_01D_30S_MO.crx"
    if zipped:
        rinexFile = rinexFile + ".gz"
    return rinexFile