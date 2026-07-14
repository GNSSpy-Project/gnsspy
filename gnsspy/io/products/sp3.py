"""SP3 precise-orbit reader for GNSSpy v3."""

import os
import time
import datetime

import pandas as pd

from gnsspy.utils.checkif import isfloat, isexist


def read_sp3File(sp3file):
    """
    Read SP3 precise-orbit file
    UPDATED: Robust line-by-line reading for Galileo support
    """
    start = time.time()
    

    if not os.path.exists(sp3file):
        basename = os.path.basename(sp3file)
        possible_paths = [
            os.path.join(os.getcwd(), "data", "sp3", basename),
            os.path.join(os.getcwd(), "output", "data", "sp3", basename),
            os.path.join(os.getcwd(), "output", "sp3", basename),
            sp3file
        ]
        found = False
        for path in possible_paths:
            if os.path.exists(path):
                sp3file = path; found = True; break
        if not found: isexist(sp3file)
    
    f = open(sp3file)
    sp3 = f.readlines()
    

    line = 0
    while True:
        if '/*' in sp3[line]:
             if '/*' in sp3[line+1]: line +=1
             else: line +=1; break
        else: line +=1
    del sp3[0:line]
    
    header = ['X', 'Y', 'Z', 'deltaT', 'sigmaX', 'sigmaY', 'sigmaZ', 'sigmadeltaT', 'Epoch']
    sat, pos = [], []
    current_epoch = None
    

    for line_content in sp3:
        if line_content.startswith('*'):
            parts = line_content.split()
            current_epoch = datetime.datetime(year=int(parts[1]), month=int(parts[2]), day=int(parts[3]), hour=int(parts[4]), minute=int(parts[5]), second=0)
        elif line_content.startswith('P') and current_epoch is not None:

            line_content = line_content.replace(' 999999.999999', '          None')
            parts = line_content.split()
            if not parts: continue
            

            sat_id = parts[0][1:] 
            
            raw_data = parts[1:]
            

            if len(raw_data) == 4:
                raw_data.extend(['None', 'None', 'None', 'None'])
            elif len(raw_data) > 8:
                raw_data = raw_data[:8]
            
            parsed_data = [float(j) if isfloat(j) else None for j in raw_data]
            parsed_data.append(current_epoch)
            
            pos.append(parsed_data)
            sat.append(sat_id)
            
    position = pd.DataFrame(pos, index = sat, columns = header)
    position.index.name = 'SV'
    position.set_index('Epoch', append=True, inplace=True)
    position = position.reorder_levels(["Epoch","SV"])
    

    position = position[~position.index.duplicated(keep='first')]
    



        

    def calculate_velocity(group):
        group = group.sort_index(level='Epoch')
        epochs = group.index.get_level_values('Epoch')
        dt = pd.Series(epochs).diff().dt.total_seconds().values.copy()
        dt[0] = dt[1] if len(dt) > 1 else 900
        group['Vx'] = group['X'].diff() / dt
        group['Vy'] = group['Y'].diff() / dt
        group['Vz'] = group['Z'].diff() / dt
        group[['Vx', 'Vy', 'Vz']] = group[['Vx', 'Vy', 'Vz']].bfill().fillna(0.0)
        return group

    position = position.groupby(level='SV', group_keys=False).apply(calculate_velocity)
    f.close()
    print('{}'.format(sp3file), 'file is read in', '{0:.2f}'.format(time.time()-start), 'seconds')
    return position

read_sp3_file = read_sp3File

__all__ = ['read_sp3File', 'read_sp3_file']
