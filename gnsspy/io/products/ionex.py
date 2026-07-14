"""IONEX ionosphere-map reader for GNSSpy v3."""

import time
import datetime

import numpy as np

from gnsspy.utils.checkif import isexist


def read_ionFile(IonFile):
    """ Function that reads Ionosphere file """

    isexist(IonFile)

    start = time.time()  
    f = open(IonFile, errors = 'ignore')
    obsLines = f.readlines() 

    line = 0
    while True:
        if 'END OF HEADER' in obsLines[line]:
            line +=1
            break
        else:
            line +=1
    
    del obsLines[0:line]

    tecuList = np.zeros([13, 71,72])
    for etime in range(13):
        line = 0
        del obsLines[0]
        epochLine = obsLines[0].split()
        _epoch = datetime.datetime(year = int(epochLine[0]), month = int(epochLine[1]), day = int(epochLine[2]), 
                                            hour = int(epochLine[3]), minute = int(epochLine[4]), second = int(epochLine[5]))
        del obsLines[0]
        for phi in range(71):
            temp = obsLines[0].split()
            _LAT, _LON1, _LON2, _DLON, _H = temp[0], temp[1], temp[2], temp[3], temp[4]
            tecu = obsLines[1] + obsLines[2] + obsLines[3] + obsLines[4] + obsLines[5]
            tecu = tecu.split()
            tecu = [int(tec) for tec in tecu]
            for lamda in range(len(tecu)-1):
                tecuList[etime,phi,lamda] = tecu[lamda]
            del obsLines[0:6]
        del obsLines[0]

    f.close()
    finish = time.time()
    print("Ionosphere file ", IonFile," is read in", "{0:.2f}".format(finish-start), "seconds.")
    return tecuList

read_ionex_file = read_ionFile

__all__ = ['read_ionFile', 'read_ionex_file']
