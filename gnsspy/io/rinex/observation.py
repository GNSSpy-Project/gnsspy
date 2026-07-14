"""RINEX observation-file readers for GNSSpy v3."""

import time
import datetime

import numpy as np
import pandas as pd

from gnsspy.io.io import Observation, _ObservationTypes
from gnsspy.utils.checkif import isfloat, isint, isexist
from gnsspy.utils.constants import _system_name


def read_obsFile(observationFile):
    if observationFile.endswith(".Z")==True:
        raise ValueError("All I/O functions take uncompressed files as an input (remove .Z/.gz from filename) | Next release will include this feature...")

    isexist(observationFile)

    f = open(observationFile, errors = 'ignore')
    obsLines = f.readlines()
    line = 0
    while True:
        if 'RINEX VERSION / TYPE' in obsLines[line]:
            version = obsLines[line][0:-20].split()[0]
            break
        else:
            line += 1
    if version.startswith("2"):
        return read_obsFile_v2(observationFile)
    elif version.startswith("3"):
        return read_obsFile_v3(observationFile)

def read_obsFile_v2(observationFile):
    """ Function that reads RINEX observation file """
    start = time.time()
    f = open(observationFile, errors = 'ignore')
    obsLines = f.readlines()

    line = 0
    ToB=[]
    while True:
        if 'RINEX VERSION / TYPE' in obsLines[line]:
            version = obsLines[line][0:-21].split()[0]
            line += 1
        elif 'REC # / TYPE / VERS' in obsLines[line]:
            receiver_type = obsLines[line][0:-20].split()
            line += 1
        elif 'ANT # / TYPE' in obsLines[line]:
            antenna_type = obsLines[line][0:-20].split()
            line += 1
        elif 'APPROX POSITION XYZ' in obsLines[line]:
            approx_position = obsLines[line][0:obsLines[line].index('A')].split()
            approx_position = [float(i) for i in approx_position]
            line += 1
        elif 'TYPES OF OBSERV' in obsLines[line]:
            ToB.extend(obsLines[line][0:obsLines[line].index('#')].split())
            obsNumber = int(ToB[0])
            line +=1
        elif 'END OF HEADER' in obsLines[line]:
            line += 1
            break
        else:
            line += 1
    
    del obsLines[0:line]

    obsLines = [lines.rstrip() for lines in obsLines] 
    obsList = []
    SVList= []
    epochList = []
    while True:

        while True:
            if 'COMMENT' in obsLines[0]:
                del obsLines[0]
                line += 1
            elif 'APPROX POSITION XYZ' in obsLines[0]:
                del obsLines[0]
                line += 1
            elif 'REC # / TYPE / VERS' in obsLines[0]:
                raise ValueError("Receiver type is changed! | Exiting...")
            elif isint(obsLines[0][1:3])==False:

                del obsLines[0]
                line += 1

            else:
                break

        year = int(obsLines[0][1:3])
        if 79 < year < 100:
            year += 1900
        elif year <= 79:
            year += 2000
        else:
            raise ValueError('Observation year is not recognized! | Program stopped!')
        epoch = datetime.datetime(year = year, 
                                month =int(obsLines[0][4:6]),
                                day =int(obsLines[0][7:9]),
                                hour = int(obsLines[0][10:12]),
                                minute = int(obsLines[0][13:15]),
                                second  = int(obsLines[0][16:18])  if isint(obsLines[0][16:18])==True else 0)

        epochList.append(epoch)
        eflag = int(obsLines[0][28:30])
        if eflag == 4:
            del obsLines[0]
            while True:
                if 'COMMENT' in obsLines[0]:
                    print(obsLines[0])
                    del obsLines[0]
                    line += 1
                else: 
                    break

        if len(obsLines[0]) == 80:
            receiver_clock = float(obsLines[0][-12:])
            obsLines[0] = obsLines[0][:-12]
        else:
            receiver_clock = 0

        NoSV  = int(obsLines[0][30:32])

        if len(obsLines[0][32:]) != 3*NoSV:
            noLine = [int(NoSV/12) if NoSV % 12 != 0 else int(NoSV/12)-1]
            for i in range(noLine[0]):
                obsLines[0] = obsLines[0] + obsLines[1][32:]
                del obsLines[1]
            if len(obsLines[0][32:]) != 3*NoSV:
                obsLines[0] = " " + obsLines[0].strip()

        SV=[obsLines[0][32:][i:i+3] for i in range(0, len(obsLines[0][32:]), 3)]
        SV = [i.replace('  ', 'G0') for i in SV]
        SV = [i.replace(' ', 'G') if i[0]==' ' else i.replace(' ', '0') for i in SV]
        SVList.extend(SV)

        obsEpoch = []
        del obsLines[0]
        rowNumber = np.ceil(obsNumber/5).astype('int')
        for i in range(0, rowNumber*NoSV, rowNumber): 
            for j in range(0, rowNumber):
                lineLenght = len(obsLines[i+j])
                if lineLenght != 80:
                    obsLines[i+j] += ' '*(80-lineLenght)
                if j!=0:
                    obsLines[i] += obsLines[i+j]
            obsLines[i] = [float(obsLines[i][j:j+14]) if isfloat(obsLines[i][j:j+14])==True else None for j in range(0, 80*rowNumber, 16)]
            if len(obsLines[i]) != obsNumber:
                del obsLines[i][-(len(obsLines[i])-obsNumber):]
            obsLines[i].append(epoch)
            obsEpoch.append(obsLines[i])
        obsList.extend(obsEpoch)
        del obsLines[0:rowNumber*NoSV]
        if len(obsLines) == 0:
            break
    columnNames = ToB[1:]
    columnNames.append('Epoch')
    observation = pd.DataFrame(obsList, index=SVList, columns=columnNames)
    observation.index.name = 'SV'
    observation['epoch'] = observation.Epoch
    observation['Epoch'] = observation.Epoch
    observation.set_index('Epoch', append=True, inplace=True)
    observation = observation.reorder_levels(['Epoch', 'SV'])

    observation["SYSTEM"] = _system_name(observation.index.get_level_values("SV"))

    fileEpoch = datetime.date(year = epoch.year,
                                month = epoch.month,
                                day  = epoch.day)
    if len(epochList) == 1:
        interval = 30
    else:
        interval = epochList[1] - epochList[0]
        interval = interval.seconds
    f.close()

    finish = time.time()
    print("Observation file ", observationFile," is read in", "{0:.2f}".format(finish-start), "seconds.")
    return Observation(f.name, fileEpoch, observation, approx_position, receiver_type, antenna_type, interval, receiver_clock, version, ToB)

def read_obsFile_v3(obsFileName):
    start = time.time()

    if obsFileName.endswith("crx"): obsFileName = obsFileName.split(".")[0] + ".rnx"
    f = open(obsFileName, errors = 'ignore')
    obsLines = f.readlines()


    line = 0
    ToB_GPS,ToB_GLONASS,ToB_GALILEO,ToB_COMPASS,ToB_QZSS,ToB_IRSS,ToB_SBAS = [], [], [], [], [], [], []
    while True:
        if 'RINEX VERSION / TYPE' in obsLines[line]:
            version = obsLines[line][0:-21].split()[0]
            line += 1
        elif 'REC # / TYPE / VERS' in obsLines[line]:
            receiver_type = obsLines[line][0:-20].split()
            line += 1
        elif 'ANT # / TYPE' in obsLines[line]:
            antenna_type = obsLines[line][0:-20].split()
            line += 1
        elif 'APPROX POSITION XYZ' in obsLines[line]:
            approx_position = obsLines[line][0:obsLines[line].index('A')].split()
            approx_position = [float(i) for i in approx_position]
            line += 1
        elif 'SYS / # / OBS TYPES' in obsLines[line]:
            if obsLines[line][0] == "G":
                obsTypes = obsLines[line][0:obsLines[line].index('SYS')].split()
                obsNumber_GPS = int(obsTypes[1])
                ToB_GPS = obsTypes[2:]
                line += 1
                if obsNumber_GPS > 13:
                    for _ in range(int(np.ceil(obsNumber_GPS/13))-1):
                        ToB_GPS.extend(obsLines[line][0:obsLines[line].index('SYS')].split())
                        line += 1
            elif obsLines[line][0] == "R":
                obsTypes = obsLines[line][0:obsLines[line].index('SYS')].split()
                obsNumber_GLONASS = int(obsTypes[1])
                ToB_GLONASS = obsTypes[2:]
                line += 1
                if obsNumber_GLONASS > 13:
                    for _ in range(int(np.ceil(obsNumber_GLONASS/13))-1):
                        ToB_GLONASS.extend(obsLines[line][0:obsLines[line].index('SYS')].split())
                        line += 1
            elif obsLines[line][0] == "E":
                obsTypes = obsLines[line][0:obsLines[line].index('SYS')].split()
                obsNumber_GALILEO = int(obsTypes[1])
                ToB_GALILEO = obsTypes[2:]
                line += 1
                if obsNumber_GALILEO > 13:
                    for _ in range(int(np.ceil(obsNumber_GALILEO/13))-1):
                        ToB_GALILEO.extend(obsLines[line][0:obsLines[line].index('SYS')].split())
                        line += 1
            elif obsLines[line][0] == "C":
                obsTypes = obsLines[line][0:obsLines[line].index('SYS')].split()
                obsNumber_COMPASS = int(obsTypes[1])
                ToB_COMPASS = obsTypes[2:]
                line += 1
                if obsNumber_COMPASS > 13:
                    for _ in range(int(np.ceil(obsNumber_COMPASS/13))-1):
                        ToB_COMPASS.extend(obsLines[line][0:obsLines[line].index('SYS')].split())
                        line += 1
            elif obsLines[line][0] == "J":
                obsTypes = obsLines[line][0:obsLines[line].index('SYS')].split()
                obsNumber_QZSS = int(obsTypes[1])
                ToB_QZSS = obsTypes[2:]
                line += 1
                if obsNumber_QZSS > 13:
                    for _ in range(int(np.ceil(obsNumber_QZSS/13))-1):
                        ToB_QZSS.extend(obsLines[line][0:obsLines[line].index('SYS')].split())
                        line += 1
            elif obsLines[line][0] == "I":
                obsTypes = obsLines[line][0:obsLines[line].index('SYS')].split()
                obsNumber_IRSS = int(obsTypes[1])
                ToB_IRSS = obsTypes[2:]
                line += 1
                if obsNumber_IRSS > 13:
                    for _ in range(int(np.ceil(obsNumber_IRSS/13))-1):
                        ToB_IRSS.extend(obsLines[line][0:obsLines[line].index('SYS')].split())
                        line += 1
            elif obsLines[line][0] == "S":
                obsTypes = obsLines[line][0:obsLines[line].index('SYS')].split()
                obsNumber_SBAS = int(obsTypes[1])
                ToB_SBAS = obsTypes[2:]
                line += 1
                if obsNumber_SBAS > 13:
                    for _ in range(int(np.ceil(obsNumber_SBAS/13))-1):
                        ToB_SBAS.extend(obsLines[line][0:obsLines[line].index('SYS')].split())
                        line += 1
        elif 'END OF HEADER' in obsLines[line]:
            line +=1
            break
        else:
            line +=1
    del obsLines[0:line]


    ToB = np.unique(np.concatenate((ToB_GPS,ToB_GLONASS,ToB_GALILEO,ToB_COMPASS,ToB_QZSS,ToB_IRSS,ToB_SBAS)))

    index_GPS = np.searchsorted(ToB,ToB_GPS)
    index_GLONASS = np.searchsorted(ToB,ToB_GLONASS)
    index_GALILEO = np.searchsorted(ToB,ToB_GALILEO)
    index_COMPASS = np.searchsorted(ToB,ToB_COMPASS)
    index_QZSS = np.searchsorted(ToB,ToB_QZSS)
    index_IRSS = np.searchsorted(ToB,ToB_IRSS)
    index_SBAS = np.searchsorted(ToB,ToB_SBAS)
    observation_types = _ObservationTypes(ToB_GPS,ToB_GLONASS,ToB_GALILEO,ToB_COMPASS,ToB_QZSS,ToB_IRSS,ToB_SBAS)

    obsLines = [lines.rstrip() for lines in obsLines]
    obsList = []
    svList= []
    epochList = []
    while True:

        while True:
            if 'COMMENT' in obsLines[0]:
                del obsLines[0]
                line += 1
            elif 'APPROX POSITION XYZ' in obsLines[0]:
                del obsLines[0]
                line += 1
            elif 'REC # / TYPE / VERS' in obsLines[0]:
                raise ValueError("Receiver type is changed! | Exiting...")
            else:
                break

        if obsLines[0][0] == ">":
            epochLine = obsLines[0][1:].split()
            if len(epochLine) == 8:
                epoch_year, epoch_month, epoch_day, epoch_hour, epoch_minute, epoch_second, epoch_flag, epoch_SVNumber = obsLines[0][1:].split()
                receiver_clock = 0 
            elif len(epochLine) == 9:
                epoch_year, epoch_month, epoch_day, epoch_hour, epoch_minute, epoch_second, epoch_flag, epoch_SVNumber, receiver_clock = obsLines[0][1:].split()
            else: raise ValueError("Unexpected epoch line format detected! | Program stopped!")
        else: raise ValueError("Unexpected format detected! | Program stopped!")

        if epoch_flag in {"1","3","5","6"}:
            raise ValueError("Deal with this later!")
        elif epoch_flag == "4":
            del obsLines[0]
            while True:
                if 'COMMENT' in obsLines[0]:
                    print(obsLines[0])
                    del obsLines[0]
                    line += 1
                elif 'SYS / PHASE SHIFT' in obsLines[0]:
                    del obsLines[0]

                else: 
                    break
        else:

            epoch = datetime.datetime(year = int(epoch_year), 
                                    month = int(epoch_month),
                                    day = int(epoch_day),
                                    hour = int(epoch_hour),
                                    minute = int(epoch_minute),
                                    second = int(float(epoch_second)))
            epochList.append(epoch)
            del obsLines[0]

            epoch_SVNumber = int(epoch_SVNumber)
            for svLine in range(epoch_SVNumber):
                obsEpoch = np.full((1,len(ToB)), None)
                svList.append(obsLines[svLine][:3])
                if obsLines[svLine].startswith("G"):
                    obsEpoch[0,index_GPS] = np.array([[float(obsLines[svLine][3:][i:i+14]) if isfloat(obsLines[svLine][3:][i:i+14])==True else None for i in range(0,len(ToB_GPS)*16,16)]])
                elif obsLines[svLine].startswith("R"):
                    obsEpoch[0,index_GLONASS] = np.array([[float(obsLines[svLine][3:][i:i+14]) if isfloat(obsLines[svLine][3:][i:i+14])==True else None for i in range(0,len(ToB_GLONASS)*16,16)]])

                elif obsLines[svLine].startswith("E"):
                    obsEpoch[0,index_GALILEO] = np.array([[float(obsLines[svLine][3:][i:i+14]) if isfloat(obsLines[svLine][3:][i:i+14])==True else None for i in range(0,len(ToB_GALILEO)*16,16)]])
                elif obsLines[svLine].startswith("C"):
                    obsEpoch[0,index_COMPASS] = np.array([[float(obsLines[svLine][3:][i:i+14]) if isfloat(obsLines[svLine][3:][i:i+14])==True else None for i in range(0,len(ToB_COMPASS)*16,16)]])
                elif obsLines[svLine].startswith("J"):
                    obsEpoch[0,index_QZSS] = np.array([[float(obsLines[svLine][3:][i:i+14]) if isfloat(obsLines[svLine][3:][i:i+14])==True else None for i in range(0,len(ToB_QZSS)*16,16)]])
                elif obsLines[svLine].startswith("I"):
                    obsEpoch[0,index_IRSS] = np.array([[float(obsLines[svLine][3:][i:i+14]) if isfloat(obsLines[svLine][3:][i:i+14])==True else None for i in range(0,len(ToB_IRSS)*16,16)]])
                elif obsLines[svLine].startswith("S"):
                    obsEpoch[0,index_SBAS] = np.array([[float(obsLines[svLine][3:][i:i+14]) if isfloat(obsLines[svLine][3:][i:i+14])==True else None for i in range(0,len(ToB_SBAS)*16,16)]])
                obsEpoch = np.append(obsEpoch,epoch)
                obsList.append(obsEpoch)

            del obsLines[0:epoch_SVNumber]
        if len(obsLines) == 0:
            break

    columnNames = ToB
    columnNames = np.append(ToB,'Epoch')
    obs = pd.DataFrame(obsList, index=svList, columns=columnNames)
    obs.index.name = 'SV'
    obs['epoch'] = obs.Epoch 
    obs['Epoch'] = obs.Epoch
    obs.set_index('Epoch', append=True, inplace=True)
    obs = obs.reorder_levels(['Epoch', 'SV'])
    obs["SYSTEM"] = _system_name(obs.index.get_level_values("SV"))

    fileEpoch = datetime.date(year = epoch.year,
                                month = epoch.month,
                                day  = epoch.day)
    if len(epochList) == 1:
        interval = 30
    else:
        interval = epochList[1] - epochList[0]
        interval = interval.seconds
    f.close()

    finish = time.time()
    print("Observation file ", obsFileName," is read in", "{0:.2f}".format(finish-start), "seconds.")
    return Observation(f.name, fileEpoch, obs, approx_position, receiver_type, antenna_type, interval, receiver_clock, version, observation_types)

read_observation_file = read_obsFile
read_observation_file_v2 = read_obsFile_v2
read_observation_file_v3 = read_obsFile_v3

__all__ = [
    'read_obsFile', 'read_obsFile_v2', 'read_obsFile_v3',
    'read_observation_file', 'read_observation_file_v2', 'read_observation_file_v3',
]
