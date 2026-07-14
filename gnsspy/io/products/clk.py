"""CLK clock-product reader for GNSSpy v3."""

import os
import time
import datetime

import pandas as pd


def read_clockFile(clkFile):
    """ Read Clock file """

    if not os.path.exists(clkFile):
        basename = os.path.basename(clkFile)
        possible_paths = [
            os.path.join(os.getcwd(), "data", "clk", basename),
            os.path.join(os.getcwd(), "output", "data", "clk", basename),
            os.path.join(os.getcwd(), "output", "clk", basename),
            clkFile
        ]
        found = False
        for path in possible_paths:
            if os.path.exists(path): clkFile = path; found = True; break
        if not found:
            print(f"   [INFO] CLK file not found ({basename}), proceeding without clock correction.")
            import pandas as _pd_clk
            return _pd_clk.DataFrame(columns=['Epoch', 'DeltaTSV'])
    
    start = time.time()
    f = open(clkFile)
    clk = f.readlines()
    

    Sat = []
    Epochlist = []
    SVtime = []
    
    for line in clk:
        if line.startswith('AS '):
            parts = line.split()

            try:
                Sat.append(parts[1])
                _epoch = datetime.datetime(year = int(parts[2]), month = int(parts[3]),
                                        day = int(parts[4]), hour = int(parts[5]), 
                                        minute = int(parts[6]), second =int(float(parts[7])))
                Epochlist.append(_epoch)
                SVtime.append(float(parts[9]))
            except:
                continue

    SVTimelist = pd.DataFrame(list(zip(Epochlist, SVtime)), index = Sat, columns=['Epoch','DeltaTSV'])
    f.close()
    print('{}'.format(clkFile), 'file is read in', '{0:.2f}'.format(time.time()-start), 'seconds')
    return SVTimelist

read_clock_file = read_clockFile

__all__ = ['read_clockFile', 'read_clock_file']
