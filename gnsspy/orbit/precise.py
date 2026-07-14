"""Precise-orbit interpolation for GNSSpy v3.

This module contains the SP3 interpolation routine used to match precise
orbit products to observation epochs.
"""

import time
import os
from datetime import datetime, timedelta

import pandas as _pd
import numpy as _np

from gnsspy.io.products.sp3 import read_sp3File
from gnsspy.io.products.clk import read_clockFile
from gnsspy.utils.filename import sp3FileName, clockFileName
from gnsspy.utils.interpolation import coord_interp

__all__ = [
    "sp3_interp",
    "interpolate_sp3",
    "sp3_interpolation",
]

def sp3_interp(epoch, interval=30 , poly_degree=16, sp3_product="gfz", clock_product="gfz", data_dir=None):
    """
    SP3 Interpolation Function 
    FIXED: Uses Left Join to keep Orbit data even if Clock data is missing.
    """
    import os

    epoch_yesterday = epoch - timedelta(days=1)
    epoch_tomorrow =  epoch + timedelta(days=1)
    

    yesterday = sp3FileName(epoch_yesterday, sp3_product)
    today = sp3FileName(epoch, sp3_product)
    tomorrow = sp3FileName(epoch_tomorrow, sp3_product)
    clockFile = clockFileName(epoch, interval, clock_product)
    
    if data_dir:
        sp3_dir = os.path.join(data_dir, "sp3")
        clk_dir = os.path.join(data_dir, "clk")
        yesterday_path = os.path.join(sp3_dir, yesterday)
        today_path = os.path.join(sp3_dir, today)
        tomorrow_path = os.path.join(sp3_dir, tomorrow)
        clock_path = os.path.join(clk_dir, clockFile)
        yesterday = yesterday_path if os.path.exists(yesterday_path) else yesterday
        today = today_path if os.path.exists(today_path) else today
        tomorrow = tomorrow_path if os.path.exists(tomorrow_path) else tomorrow
        clockFile = clock_path if os.path.exists(clock_path) else clockFile
        

    yes   = read_sp3File(yesterday) 
    tod = read_sp3File(today) 
    tom   = read_sp3File(tomorrow) 
    clock = read_clockFile(clockFile) 

    if poly_degree > 16:
        raise Warning("Polynomial degree above 16 is not applicable!")
    elif poly_degree < 11:
        print("Warning: Polynomial degree below 11 is not recommended!")

    start = time.time()
    

    yes = yes.dropna(subset=["X", "Y", "Z"])
    tod = tod.dropna(subset=["X", "Y", "Z"])
    tom = tom.dropna(subset=["X", "Y", "Z"])
    
    yes_start = _pd.Timestamp(datetime(epoch_yesterday.year, epoch_yesterday.month, epoch_yesterday.day, 23, 0, 0))
    yes_end = _pd.Timestamp(datetime(epoch_yesterday.year, epoch_yesterday.month, epoch_yesterday.day, 23, 59, 59))
    tom_start = _pd.Timestamp(datetime(epoch_tomorrow.year, epoch_tomorrow.month, epoch_tomorrow.day, 0, 0, 0))
    tom_end = _pd.Timestamp(datetime(epoch_tomorrow.year, epoch_tomorrow.month, epoch_tomorrow.day, 3, 0, 0))
    

    yes_filtered = yes[(yes.index.get_level_values(0) >= yes_start) & (yes.index.get_level_values(0) <= yes_end)]
    yes_filtered = yes_filtered.reorder_levels(["Epoch", "SV"]).sort_index()
    
    tom_filtered = tom[(tom.index.get_level_values(0) >= tom_start) & (tom.index.get_level_values(0) <= tom_end)]
    tom_filtered = tom_filtered.reorder_levels(["Epoch", "SV"]).sort_index()
    
    tod_reordered = tod.reorder_levels(["Epoch", "SV"]).sort_index()
    
    sp3 = _pd.concat([yes_filtered, tod_reordered, tom_filtered], axis=0)
    sp3 = sp3.sort_index()
    sp3 = sp3.reset_index().set_index(['Epoch', 'SV']).sort_index()
    
    svList = sp3.index.get_level_values("SV").unique().sort_values()
    epoch_values = sp3.index.get_level_values("Epoch").unique()
    
    if len(epoch_values) < 2:
        print("[!] Error: Insufficient or empty SP3 data.")
        return _pd.DataFrame()

    deltaT = epoch_values[1]-epoch_values[0]
    header = ['X', 'Y', 'Z', 'Vx','Vy','Vz']
    
    epoch_start = _pd.Timestamp(datetime(epoch_yesterday.year, epoch_yesterday.month, epoch_yesterday.day,23,0,0))
    epoch_step = timedelta(hours=3)
    epoch_stop = epoch_start + timedelta(hours=4)
    
    dti = _pd.date_range(start = _pd.Timestamp(datetime(epoch_yesterday.year, epoch_yesterday.month, epoch_yesterday.day,23,30,0)),
                        end   = _pd.Timestamp(datetime( epoch_tomorrow.year,  epoch_tomorrow.month,  epoch_tomorrow.day,2,29,59)),
                        freq = str(interval) + 's')
    
    index = _pd.MultiIndex.from_product([svList, dti.tolist()], names=['SV', 'Epoch'])
    interp_coord = _pd.DataFrame(index= index, columns = header)
    interp_coord = interp_coord.reorder_levels(['Epoch', 'SV']).sort_index()
    
    while True:
        mask_sp3 = (sp3.index.get_level_values('Epoch') >= epoch_start) & (sp3.index.get_level_values('Epoch') <= epoch_stop)
        sp3_temp = sp3.loc[mask_sp3].copy().sort_index().reorder_levels(["SV","Epoch"]).sort_index()
        
        epoch_interp_List = _np.zeros(shape=(10800//interval,6,len(svList)))
        
        for svIndex, sv in enumerate(svList):
            try:
                if sv not in sp3_temp.index.get_level_values('SV'):
                    epoch_interp_List[:,:,svIndex] = _np.full(shape=(int(10800/interval),6),fill_value=None); continue
                
                sv_data = sp3_temp.loc[sv]
                epoch_number = len(sv_data)
                
                if epoch_number <= poly_degree:
                    epoch_interp_List[:,:,svIndex] = _np.full(shape=(int(10800/interval),6),fill_value=None); continue
            except KeyError: continue
            
            fitTime = [(sv_data.index[t] - sv_data.index[0]).seconds for t in range(epoch_number)]
            fitX = _np.polyfit(fitTime, sv_data.X.copy(), deg=poly_degree)
            fitY = _np.polyfit(fitTime, sv_data.Y.copy(), deg=poly_degree)
            fitZ = _np.polyfit(fitTime, sv_data.Z.copy(), deg=poly_degree)
            
            x_interp = coord_interp(fitX, interval) * 1000 
            y_interp = coord_interp(fitY, interval) * 1000 
            z_interp = coord_interp(fitZ, interval) * 1000 
            

            x_v = _np.diff(x_interp, append=x_interp[-1]) / interval
            y_v = _np.diff(y_interp, append=y_interp[-1]) / interval
            z_v = _np.diff(z_interp, append=z_interp[-1]) / interval

            sv_interp = _np.vstack((x_interp, y_interp, z_interp, x_v, y_v, z_v)).transpose()

            target_len = epoch_interp_List.shape[0]
            if len(sv_interp) > target_len: sv_interp = sv_interp[:target_len]
            elif len(sv_interp) < target_len:
                 padding = _np.full((target_len - len(sv_interp), 6), _np.nan)
                 sv_interp = _np.vstack((sv_interp, padding))
                 
            epoch_interp_List[:,:,svIndex] = sv_interp     
            
        epoch_slice_start = epoch_start + timedelta(minutes=30)
        epoch_slice_end = epoch_stop - timedelta(minutes=30, seconds=1)
        
        mask_interp = (interp_coord.index.get_level_values('Epoch') >= epoch_slice_start) & \
                      (interp_coord.index.get_level_values('Epoch') <= epoch_slice_end)
                      
        interp_coord.loc[mask_interp, ['X', 'Y', 'Z', 'Vx', 'Vy', 'Vz']] = epoch_interp_List.transpose(1,0,2).reshape(6,-1).transpose()
        
        epoch_start += epoch_step
        epoch_stop += epoch_step
        if epoch_start == _pd.Timestamp(datetime(epoch_tomorrow.year, epoch_tomorrow.month, epoch_tomorrow.day,2,0,0)):
            break
            
    interp_coord = interp_coord.reorder_levels(['Epoch', 'SV']).astype(float).sort_index()
    

    clock.index.name = 'SV'
    clock.set_index('Epoch', append=True, inplace=True)
    clock = clock.reorder_levels(['Epoch', 'SV']).sort_index()
    


    sp3matched = interp_coord.join(clock, how='left')
    
    finish = time.time()
    print("   [OK] SP3 interpolation is done in", '{0:.2f}'.format(finish-start), 'seconds')
    return sp3matched



interpolate_sp3 = sp3_interp
sp3_interpolation = sp3_interp
