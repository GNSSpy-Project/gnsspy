"""
GPS

"""
# ===========================================================
# ========================= imports =========================
import os
import urllib.request as url
from pyunpack import Archive
import datetime
from dateutil.relativedelta import relativedelta
from gnsspy.funcs.funcs import (check_internet, obsFileName,
                                navFileName, nav3FileName, 
                                obs3FileName, datetime2doy)
# ===========================================================

__all__ = ["get_rinex", "get_rinex3", "get_navigation", "get_clock", "get_sp3", "get_ionosphere"]

def get_rinex(stationList, date_start, date_finish=None, period='day', Datetime=False, directory=os.getcwd()):
    """
    This function downloads IGS rinex observation file from NASA CDDIS ftp server.
    
    Usage: 
        get_rinex(['mate'],'02-01-2017')
        get_rinex(['mate', 'onsa'],'01-01-2017')
        get_rinex(['mate'], date_start = '01-01-2017', date_finish = '05-01-2017', period = 'day')
        get_rinex(['mate'], date_start = '01-01-2017', date_finish = '01-06-2017', period = 'month')
        get_rinex(['mate', 'onsa'], date_start = '01-01-2017', date_finish = '03-01-2017', period = 'month')
        get_rinex(['mate'], date_start = '01-01-2017', date_finish = '01-01-2018', period = 'year')
    """
    internet = check_internet()
    if internet == False:
        raise Warning('No internet connection! | Cannot download RINEX file...')
    
    if Datetime == False:
        date_start = datetime.date(year = int(date_start[-4:]), month = int(date_start[-7:-5]), day = int(date_start[-10:-8]))
        if date_finish != None:
            date_finish = datetime.date(year = int(date_finish[-4:]), month = int(date_finish[-7:-5]), day = int(date_finish[-10:-8]))
    
    timedelta = {'day'   : relativedelta(days   = 1),
                 'month' : relativedelta(months = 1),
                 'year'  : relativedelta(years  = 1)}[period]
    dateList = [date_start] # dates of observation files
    if date_finish != None:
        while dateList[-1] != date_finish:
            date = dateList[-1] + timedelta
            dateList.append(date)

    ftpserver  = 'ftp://cddis.gsfc.nasa.gov'
    obsFileDir = 'gnss/data/daily' # observation file directory in ftp server
    
    for stationName in stationList:
        for date in dateList:
            doy = datetime2doy(date, string = True)
            fileName = obsFileName(stationName, date, zipped = True)
            # check if the file already exist in the directory
            if os.path.exists(fileName)  == True:
                if os.path.exists(fileName[:-2])  == True:
                    print(fileName[:-2] + " exists in working directory")
                    continue
                else:
                    print(fileName + " exists in working directory | Extracting...")
                    Archive(fileName).extractall(os.getcwd())
                    continue
            file_topath = os.path.join(directory, fileName)
            fileDir = [ftpserver, obsFileDir, str(date.year), doy, str(date.year)[-2:] + 'o', fileName] # file directory
            ftp = '/'.join(fileDir)
            # Download the file
            try:
                print('Downloading:', fileName, end= '')
                url.urlretrieve(ftp, file_topath)
                print(" | Download completed for", fileName, " | Extracting...")
                Archive(fileName).extractall(os.getcwd())
            except:
                raise Warning("Requested file", fileName, "cannot be not found!")

def get_navigation(stationList, date_start, date_finish=None, period='day', Datetime=False, directory=os.getcwd()):
    """
    This function downloads mutli-gnss navigation file (.p) from NASA CDDIS ftp server.
    
    Usage: 
        get_navigation(['mate'],'02-01-2017')
        get_navigation(['mate', 'onsa'],'01-01-2017')
        get_navigation(['mate'], date_start = '01-01-2017', date_finish = '05-01-2017', period = 'day')
        get_navigation(['mate'], date_start = '01-01-2017', date_finish = '01-06-2017', period = 'month')
        get_navigation(['mate', 'onsa'], date_start = '01-01-2017', date_finish = '03-01-2017', period = 'month')
        get_navigation(['mate'], date_start = '01-01-2017', date_finish = '01-01-2018', period = 'year')
    """

    internet = check_internet()
    if internet == False:
        raise Warning('No internet connection! | Cannot download rinex file')
    
    if Datetime == False:
        date_start = datetime.date(year = int(date_start[-4:]), month = int(date_start[-7:-5]), day = int(date_start[-10:-8]))
        if date_finish != None:
            date_finish = datetime.date(year = int(date_finish[-4:]), month = int(date_finish[-7:-5]), day = int(date_finish[-10:-8]))
    
    timedelta = {'day'   : relativedelta(days   = 1),
                 'month' : relativedelta(months = 1),
                 'year'  : relativedelta(years  = 1)}[period]
    dateList = [date_start]
    if date_finish != None:
        while dateList[-1] != date_finish:
            date = dateList[-1] + timedelta
            dateList.append(date)

    ftpserver  = 'ftp://cddis.gsfc.nasa.gov'
    obsFileDir = 'gnss/data/daily'
    
    for stationName in stationList:
        for date in dateList:
            if date >= datetime.date(year=2016,month=1,day=1):
                print("Downloading RINEX3 navigation file...")
                doy = datetime2doy(date, string = True)
                fileName = nav3FileName(stationName, date, zipped = True)
                if os.path.exists(fileName)  == True:
                    if os.path.exists(fileName[:-2])  == True:
                        print(fileName[:-2] + " exists in working directory")
                        continue
                    else:
                        print(fileName + " exists in working directory | Extracting...")
                        Archive(fileName).extractall(os.getcwd())
                        continue
                file_topath = os.path.join(directory, fileName)
                fileDir = [ftpserver, obsFileDir, str(date.year), doy, str(date.year)[-2:] + 'p', fileName]
                ftp = '/'.join(fileDir)
                try:
                    print('Downloading:', fileName, end= '')
                    url.urlretrieve(ftp, file_topath)
                    print(" | Download completed for", fileName, " | Extracting...")
                    Archive(fileName).extractall(os.getcwd())
                except:
                    print("| Requested navigation file", fileName, "cannot be not found! | Checking for IGS Navigation File..." )
                    try:
                        igsFileName = nav3FileName("BRDC", date, zipped = True)
                        
                        if os.path.exists(igsFileName)  == True:
                            if os.path.exists(igsFileName[:-3])  == True:
                                print(igsFileName[:-3] + " exists in working directory")
                                continue
                            else:
                                print(igsFileName + " exists in working directory | Extracting...")
                                Archive(igsFileName).extractall(os.getcwd())
                                continue
                        file_topath = os.path.join(directory, igsFileName)
                        fileDir = [ftpserver, obsFileDir, str(date.year), doy, str(date.year)[-2:] + 'p', igsFileName]
                        ftp = '/'.join(fileDir) 
                        print('Downloading:', igsFileName, end= '')
                        url.urlretrieve(ftp, file_topath)
                        print(" | Download completed for", igsFileName, " | Extracting...")
                        Archive(igsFileName).extractall(os.getcwd())
                    except:
                        raise Warning("IGS Navigation File", igsFileName, "cannot be not found!")
            else:
                print("Downloading RINEX2 navigation file...")
                doy = datetime2doy(date, string = True)
                fileName = navFileName(stationName, date, zipped = True)
                if os.path.exists(fileName)  == True:
                    if os.path.exists(fileName[:-2])  == True:
                        print(fileName[:-2] + " exists in working directory")
                        continue
                    else:
                        print(fileName + " exists in working directory | Extracting...")
                        Archive(fileName).extractall(os.getcwd())
                        continue
                file_topath = os.path.join(directory, fileName)
                fileDir = [ftpserver, obsFileDir, str(date.year), doy, str(date.year)[-2:] + 'n', fileName]
                ftp = '/'.join(fileDir) # FTP link of file
                try:
                    print('Downloading:', fileName, end= '')
                    url.urlretrieve(ftp, file_topath)
                    print(" | Download completed for", fileName, " | Extracting...")
                    Archive(fileName).extractall(os.getcwd())
                except:
                    print("| Requested navigation file", fileName, "cannot be not found! | Checking for IGS Navigation File..." )
                    try:
                        igsFileName = navFileName("brdc", date, zipped = True)
                        if os.path.exists(igsFileName)  == True:
                            if os.path.exists(igsFileName[:-2])  == True:
                                print(fileName[:-2] + " exists in working directory")
                                continue
                            else:
                                print(igsFileName + " exists in working directory | Extracting...")
                                Archive(igsFileName).extractall(os.getcwd())
                                continue
                        file_topath = os.path.join(directory, igsFileName)
                        fileDir = [ftpserver, obsFileDir, str(date.year), doy, str(date.year)[-2:] + 'n', igsFileName]
                        ftp = '/'.join(fileDir)
                        print('Downloading:', igsFileName, end= '')
                        url.urlretrieve(ftp, file_topath)
                        print(" | Download completed for", igsFileName, " | Extracting...")
                        Archive(igsFileName).extractall(os.getcwd())
                    except:
                        raise Warning("IGS Navigation File", igsFileName, "cannot be not found!")


def get_rinex3(stationList, date_start, date_finish=None, period='day', Datetime=False, directory=os.getcwd()):
    """
    This function downloads IGS rinex observation file from NASA CDDIS ftp server.
    
    Usage: 
        get_rinex(['mate'],'02-01-2017')
        get_rinex(['mate', 'onsa'],'01-01-2017')
        get_rinex(['mate'], date_start = '01-01-2017', date_finish = '05-01-2017', period = 'day')
        get_rinex(['mate'], date_start = '01-01-2017', date_finish = '01-06-2017', period = 'month')
        get_rinex(['mate', 'onsa'], date_start = '01-01-2017', date_finish = '03-01-2017', period = 'month')
        get_rinex(['mate'], date_start = '01-01-2017', date_finish = '01-01-2018', period = 'year')
    """
    internet = check_internet()
    if internet == False:
        raise Warning('No internet connection! | Cannot download RINEX file...')
    
    if Datetime == False:
        date_start = datetime.date(year = int(date_start[-4:]), month = int(date_start[-7:-5]), day = int(date_start[-10:-8]))
        if date_finish != None:
            date_finish = datetime.date(year = int(date_finish[-4:]), month = int(date_finish[-7:-5]), day = int(date_finish[-10:-8]))
    
    timedelta = {'day'   : relativedelta(days   = 1),
                 'month' : relativedelta(months = 1),
                 'year'  : relativedelta(years  = 1)}[period]
    dateList = [date_start]
    if date_finish != None:
        while dateList[-1] != date_finish:
            date = dateList[-1] + timedelta
            dateList.append(date)

    ftpserver  = 'ftp://cddis.gsfc.nasa.gov'
    obsFileDir = 'gnss/data/daily' # observation file directory in ftp server
    
    for stationName in stationList:
        for date in dateList:
            doy = datetime2doy(date, string = True)
            fileName = obs3FileName(stationName, date, zipped = True)
            # check if the file already exist in the directory
            if os.path.exists(fileName)  == True:
                if os.path.exists(fileName[:-2])  == True:
                    print(fileName[:-2] + " exists in working directory")
                    continue
                else:
                    print(fileName + " exists in working directory | Extracting...")
                    Archive(fileName).extractall(os.getcwd())
                    continue
            file_topath = os.path.join(directory, fileName)
            fileDir = [ftpserver, obsFileDir, str(date.year), doy, str(date.year)[-2:] + 'd', fileName] 
            ftp = '/'.join(fileDir) 
            try:
                print('Downloading:', fileName, end= '')
                url.urlretrieve(ftp, file_topath)
                print(" | Download completed for", fileName, " | Extracting...")
                Archive(fileName).extractall(os.getcwd())
            except:
                raise Warning("Requested file", fileName, "cannot be not found!")


def get_sp3(sp3file, directory=os.getcwd()):
    """
    This function downloads IGS orbit file from NASA CDDIS ftp server.
    """
    fileName = sp3file + ".Z"
    if os.path.exists(fileName) == True:
        if os.path.exists(fileName[:-2]) == True:
            print(fileName[-2] + " exists in working directory")
            return
        else:
            print(fileName + " exists in working directory | Extracting...")
            Archive(fileName + ".Z").extractall(os.getcwd())
            return
    internet = check_internet()
    if internet == False:
        raise Warning('No internet connection! | Cannot download orbit file')
    
    ftpserver  = 'ftp://cddis.gsfc.nasa.gov'
    sp3FileDir = 'gnss/products'
    if sp3file.startswith("wum"): 
        sp3FileDir += '/mgex'
    file_topath = os.path.join(directory, fileName)
    fileDir = [ftpserver, sp3FileDir, fileName[3:-7], fileName]
    ftp = '/'.join(fileDir) # FTP link of file

    try:
        print('Downloading:', fileName, end = '')
        url.urlretrieve(ftp, file_topath)
        print(' | Download completed for', fileName)
        Archive(fileName).extractall(os.getcwd())
    except:
        print(" | Requested file", fileName, "cannot be not found!")

def get_clock(clockFile, directory=os.getcwd()):
    """
    This function downloads IGS clock file from NASA CDDIS ftp server.
    """    
    fileName = clockFile + ".Z"
    if os.path.exists(fileName) == True:
        if os.path.exists(fileName[:-2]) == True:
            print(fileName[:-2] + " exists in working directory")
            return
        else:
            print(fileName + " exists in working directory | Extracting...")
            Archive(fileName + ".Z").extractall(os.getcwd())
            return
    internet = check_internet()
    if internet == False:
        raise Warning('No internet connection! | Cannot download clock file')
    
    ftpserver  = 'ftp://cddis.gsfc.nasa.gov'
    clockFileDir = 'gnss/products' 
    if clockFile.startswith("wum"): 
        clockFileDir += '/mgex'
    file_topath = os.path.join(directory, fileName)
    fileDir = [ftpserver, clockFileDir, fileName[3:7], fileName] 
    ftp = '/'.join(fileDir) 

    try:
        print('Downloading:', fileName, end = '')
        url.urlretrieve(ftp, file_topath)
        print(' | Download completed for', fileName)
        return fileName[:-2]
    except:
        print("Requested file", fileName, "cannot be not found in ftp server")
        fileName = "gfz" + clockFile[3:] + ".Z"
        file_topath = os.path.join(directory, fileName)
        fileDir = [ftpserver, clockFileDir, fileName[3:7], fileName] 
        ftp = '/'.join(fileDir)
        try:
            print("Looking for GFZ clock file in ftp server...")
            print('Downloading:', fileName, end = '')
            url.urlretrieve(ftp, file_topath)
            print(' | Download completed for', fileName)
            return fileName[:-2]
        except:
            raise Warning("Requested file", fileName, "cannot be not found in FTP server | Exiting")

def get_ionosphere(ionFile, directory=os.getcwd()):
    """
    This function downloads Ionosphere file from NASA CDDIS ftp server.
    
    Usage: 
    
    """
    internet = check_internet()
    if internet == False:
        raise Warning('No internet connection! | Cannot download ionosphere file')
    
    fileName = ionFile + ".Z"
    year = int(ionFile[-3:-1])
    if 79 < year < 100:
        year += 1900
    elif year <= 79:
        year += 2000
    # FTP download
    ftpserver  = 'ftp://cddis.gsfc.nasa.gov'
    ionFileDir = 'gnss/products/ionex'
    file_topath = os.path.join(directory, fileName)
    fileDir = [ftpserver, ionFileDir, str(year), fileName[4:7], fileName] 
    ftp = '/'.join(fileDir)

    try:
        print('Downloading:', fileName, end = '')
        url.urlretrieve(ftp, file_topath)
        print(' | Download completed for', fileName)
        return fileName[:-2]
    except:
        print("Requested file", fileName, "cannot be not found in FTP server")
        fileName = "igs" + ionFile[3:] + ".Z"
        file_topath = os.path.join(directory, fileName)
        fileDir = [ftpserver, ionFileDir, fileName[3:7], fileName]
        ftp = '/'.join(fileDir)
        try:
            print("Looking for ionosphere file in FTP server...")
            print('Downloading:', fileName, end = '')
            url.urlretrieve(ftp, file_topath)
            print(' | Download completed for', fileName)
            return fileName[:-2]
        except:
            raise Warning("Requested file", fileName, "cannot be not found in FTP server | Exiting")
