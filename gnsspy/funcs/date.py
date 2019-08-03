# ===========================================================
# ========================= imports =========================
import datetime
# ===========================================================
def gpsweekday(date, Datetime = False):
    start = datetime.date(year= 1980, month= 1, day =6)
    if Datetime == True:
        date = date
    else:
        date = datetime.date(year= int(date[-4:]), month= int(date[-7:-5]), day = int(date[:2]))
    diff = date-start
    diff = diff.days
    week = int(diff/7)
    day = diff%7
    gpswday = int(str(week)+str(day))
    return week, gpswday

def gpswdtodate(gpsweekday):
    week = int(gpsweekday[:4])
    totalday = week*7 + int(gpsweekday[4])
    start = datetime.datetime(year= 1980, month= 1, day =6)
    day = start + datetime.timedelta(days=totalday)
    day = day.date()
    return day

def jday(date):
    """ This function calculates the Julian day of a given date as DD MM YYYY"""
    # year and month
    year = int(date[-4:])
    month = int(date[3:5])
    if month == 1 or month == 2:
        month += 12
        year += -1
    # calculate JD of input time
    A = int(year/100)
    B = int(A/4)
    C = 2-A+B
    D = int(date[:2])
    E = int(365.25*(year+4716))
    F = int(30.6001*(month+1))
    Jd = C+D+E+F-1524.5
    return Jd

def julianday2date(JDay):
    MJd = JDay - 2400000.5 #calculate modified Julian date
    start = datetime.datetime(year= 1858, month = 11, day = 17, hour=0, minute=0, second=0)
    date = start + datetime.timedelta(days=MJd)
    return date

def doy(date: str) -> str:
    """ This function calculates the GPS day of year for the date given """
    year=int(date[-4:])
    month=int(date[-7:-5])
    day=int(date[-10:-8])
    doy=((month-1)*(30))+day
    if year%4!=0:
        if month == 1 or month == 4 or month == 5:
            doy=doy
        elif month == 2 or month == 6 or month == 7:
            doy=doy+1
        elif month == 3:
            doy=doy-1
        elif month == 8:
            doy=doy+2
        elif month == 9 or month == 10:
            doy=doy+3
        elif month ==11 or month == 12:
            doy=doy+4
    #for leap year
    else:
        if month ==1 or month ==3:
            doy=doy
        elif month ==2 or month == 4 or month == 5:
            doy=doy+1
        elif month ==6 or month == 7:
            doy=doy+2
        elif month ==8:
            doy=doy+3
        elif month ==9 or month == 10:
            doy=doy+4
        elif month ==11 or month == 12:
            doy=doy+5
    return doy

def doy2date(rinexFile):
    if len(rinexFile) == 12: # RINEX 2.x naming
        if int(rinexFile[-3:-1]) < 80:
            year = int('20'+rinexFile[-3:-1])
        else:
            year = int('19'+rinexFile[-3:-1])
        doy = int(rinexFile[4:7])
    elif len(rinexFile) == 38: # RINEX 3.x naming
        year = int(rinexFile.split("_")[2][0:4])
        doy  = int(rinexFile.split("_")[2][4:7])
    # Datetime
    start = datetime.date(year = year, month = 1,  day =1)
    date = start + datetime.timedelta(days=doy)-datetime.timedelta(days=1)
    return date

def datetime2doy(date, string = False):
    start = datetime.date(year= date.year, month = 1,  day =1)
    doy = date - start + datetime.timedelta(days = 1)
    doy = doy.days
    if string == True:
        doy = str(doy)
        if len(doy) == 1:
            doy = "00" + doy 
        elif len(doy) == 2:
            doy = "0" + doy
        else:
            doy = doy 
    return doy
