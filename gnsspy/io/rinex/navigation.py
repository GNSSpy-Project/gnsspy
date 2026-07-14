"""RINEX navigation-file reader for GNSSpy v3."""

import time
import datetime

import numpy as np
import pandas as pd

from gnsspy.io.io import Navigation
from gnsspy.utils.checkif import isfloat, isint


def read_navFile(navigationFile):
    """ Read navigation file """
    start = time.time()
    f = open(navigationFile)
    nav = f.readlines()
    line = 0
    while True:
        if 'RINEX VERSION / TYPE' in nav[line]:
            version = nav[line][0:-21].split()[0]
            line +=1
        elif 'END OF HEADER' in nav[line]:
            line +=1
            break
        else:
            line +=1
    del nav[0:line]
    nav = [lines.replace('E ','E0') for lines in nav]
    nav = [lines.replace('D','E') for lines in nav]
    nav = [lines.replace('0-','0 -') for lines in nav]
    nav = [lines.replace('1-','1 -') for lines in nav]
    nav = [lines.replace('2-','2 -') for lines in nav]
    nav = [lines.replace('3-','3 -') for lines in nav]
    nav = [lines.replace('4-','4 -') for lines in nav]
    nav = [lines.replace('5-','5 -') for lines in nav]
    nav = [lines.replace('6-','6 -') for lines in nav]
    nav = [lines.replace('7-','7 -') for lines in nav]
    nav = [lines.replace('8-','8 -') for lines in nav]
    nav = [lines.replace('9-','9 -') for lines in nav]
    nav = [lines.split() for lines in nav]
    ephemeris_list=[]
    svList = []
    PRN_old = "X00"
    epoch_old = datetime.datetime.now()
    while True:

        _GPS = GLONASS = _GALILEO = _COMPASS = SBAS = False
        PRN = nav[0][0]
        if   "G" in PRN: _GPS = True
        elif "R" in PRN: GLONASS = True
        elif "E" in PRN: _GALILEO = True
        elif "C" in PRN: _COMPASS = True
        elif "J" in PRN: _QZSS = True
        elif "I" in PRN: _IRSS = True
        elif "S" in PRN: SBAS = True
        else:
            if len(PRN)==1:
                PRN = 'G0' + PRN
            elif len(PRN)==2:
                PRN = 'G' + PRN


        if len(nav[0][1]) == 2:
            year = int(nav[0][1])
            if 79 < year < 100:
                year += 1900
            elif year <= 79:
                year += 2000
            else:
                raise ValueError('Navigation year is not recognized! | Program stopped!')
        else:
            year = int(nav[0][1])
        month, day, hour, minute = int(nav[0][2]), int(nav[0][3]), int(nav[0][4]), int(nav[0][5])
        second_float = float(nav[0][6])
        second = int(second_float)
        microsecond = int(round((second_float - second) * 1_000_000))
        if microsecond == 1_000_000:
            second += 1
            microsecond = 0
        epoch = datetime.datetime(year   = year,
                                  month  = month,
                                  day    = day,
                                  hour   = hour,
                                  minute = minute,
                                  second = second,
                                  microsecond = microsecond)

        clockBias = nav[0][7] 
        relFeqBias = nav[0][8]
        transmissionTime = nav[0][9]
        if GLONASS or SBAS:
            x, vx, ax = float(nav[1][0]), float(nav[1][1]), float(nav[1][2])
            y, vy, ay = float(nav[2][0]), float(nav[2][1]), float(nav[2][2])
            z, vz, az = float(nav[3][0]), float(nav[3][1]), float(nav[3][2])
            health = float(nav[1][3])
            freqNumber = float(nav[2][3])
            operationDay = float(nav[3][3])
            roota, toe, m0, e, delta_n, smallomega, cus, cuc, crs, crc, cis, cic, idot, i0, bigomega0, bigomegadot = [np.nan for _ in range(16)]
            if PRN == PRN_old and epoch == epoch_old:
                ephemeris_list[-1] = [PRN, epoch, clockBias, relFeqBias, 
                                transmissionTime, roota, toe, m0, e, delta_n, 
                                smallomega, cus, cuc, crs, crc, cis, cic, 
                                idot, i0, bigomega0, bigomegadot,
                                x, y, z, vx, vy, vz, ax, ay, az,
                                health, freqNumber, operationDay]
            else:
                svList.append(PRN)
                ephemeris_list.append([PRN, epoch, clockBias, relFeqBias, 
                                    transmissionTime, roota, toe, m0, e, delta_n, 
                                    smallomega, cus, cuc, crs, crc, cis, cic, 
                                    idot, i0, bigomega0, bigomegadot,
                                    x, y, z, vx, vy, vz, ax, ay, az,
                                    health, freqNumber, operationDay])
            del nav[0:4]
        else:
            e = float(nav[2][1])
            m0 = float(nav[1][3])
            i0 = float(nav[4][0])
            toe = float(nav[3][0])
            cus = float(nav[2][2])
            cuc = float(nav[2][0])
            crs = float(nav[1][1])
            crc = float(nav[4][1])
            cis = float(nav[3][3])
            cic = float(nav[3][1])
            idot = float(nav[5][0])
            roota = float(nav[2][3])
            delta_n = float(nav[1][2])
            smallomega = float(nav[4][2])
            bigomega0 = float(nav[3][2])
            bigomegadot = float(nav[4][3])
            x, y, z, vx, vy, vz, ax, ay, az, health, freqNumber, operationDay = [np.nan for _ in range(12)]
            if PRN == PRN_old and epoch == epoch_old:
                ephemeris_list[-1] = [PRN, epoch, clockBias, relFeqBias, 
                                transmissionTime, roota, toe, m0, e, delta_n, 
                                smallomega, cus, cuc, crs, crc, cis, cic, 
                                idot, i0, bigomega0, bigomegadot,
                                x, y, z, vx, vy, vz, ax, ay, az,
                                health, freqNumber, operationDay]
            else:
                svList.append(PRN)
                ephemeris_list.append([PRN, epoch, clockBias, relFeqBias, 
                                    transmissionTime, roota, toe, m0, e, delta_n, 
                                    smallomega, cus, cuc, crs, crc, cis, cic, 
                                    idot, i0, bigomega0, bigomegadot,
                                    x, y, z, vx, vy, vz, ax, ay, az,
                                    health, freqNumber, operationDay])
            del nav[0:8]
        PRN_old = PRN
        epoch_old = epoch
        if len(nav) == 0:
            break
    columnNames = ["SV", "Epoch", "clockBias", "relFeqBias", "transmissionTime", "roota", "toe", "m0", "eccentricity", "delta_n", 
                "smallomega", "cus", "cuc", "crs", "crc", "cis", "cic", 
                "idot", "i0", "bigomega0", "bigomegadot",
                "x", "y", "z", "vx", "vy", "vz", "ax", "ay", "az",
                "health", "freqNumber", "operationDay"]
    ephemeris = pd.DataFrame(ephemeris_list, index=svList, columns=columnNames)
    ephemeris.index.name = 'SV'
    ephemeris["epoch"] = ephemeris.Epoch
    ephemeris.set_index('Epoch', append=True, inplace=True)
    ephemeris = ephemeris.reorder_levels(['Epoch', 'SV'])

    fileEpoch = datetime.date(year  = year,
                              month = month,
                              day   = day)
    f.close()
    finish = time.time()
    print("Navigation file ", navigationFile," is read in", "{0:.2f}".format(finish-start), "seconds.")
    return Navigation(fileEpoch, ephemeris, version)

read_navigation_file = read_navFile

__all__ = ['read_navFile', 'read_navigation_file']
