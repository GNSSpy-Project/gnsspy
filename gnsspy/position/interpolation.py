# ===========================================================
# ========================= imports =========================
import time
import pandas as _pd
import numpy as _np
from datetime import datetime, timedelta
from gnsspy.io import readFile
from gnsspy.geodesy.coordinate import cart2ell, geocentric_latitude
from gnsspy.funcs.funcs import (sp3FileName, clockFileName, ionFileName, coord_interp)
from gnsspy.position.position import _observation_picker_by_band
# ===========================================================

__all__ = ["sp3_interp", "ionosphere_interp"]

def sp3_interp(epoch, interval=30, poly_degree=16, sp3_product="gfz", clock_product="gfz"):
    epoch_yesterday = epoch - timedelta(days=1)
    epoch_tomorrow =  epoch + timedelta(days=1)
    yesterday = sp3FileName(epoch_yesterday, sp3_product)
    today = sp3FileName(epoch, sp3_product)
    tomorrow = sp3FileName(epoch_tomorrow, sp3_product)
    clockFile = clockFileName(epoch, interval, clock_product)
    #--------------------------------------------------------------------------
    yes   = readFile.read_sp3File(yesterday) 
    tod = readFile.read_sp3File(today) 
    tom   = readFile.read_sp3File(tomorrow) 
    clock = readFile.read_clockFile(clockFile) 
    #--------------------------------------------------------------------------
    if poly_degree > 16:
        raise Warning("Polynomial degree above 16 is not applicable!")
    elif poly_degree < 11:
        print("Warning: Polynomial degree below 11 is not recommended!")
    #--------------------------------------------------------------------------
    start = time.time()
    yes = yes.dropna(subset=["deltaT"])
    tod = tod.dropna(subset=["deltaT"])
    tom = tom.dropna(subset=["deltaT"])
    yes = yes.reorder_levels(["Epoch","SV"])
    tod = tod.reorder_levels(["Epoch","SV"])
    tom = tom.reorder_levels(["Epoch","SV"])
    yes = yes.loc[(slice(_pd.Timestamp(datetime(epoch_yesterday.year, epoch_yesterday.month, epoch_yesterday.day,23,0,0)),_pd.Timestamp(datetime(epoch_yesterday.year, epoch_yesterday.month, epoch_yesterday.day,23,59,59))))]
    tom = tom.loc[(slice(_pd.Timestamp(datetime(epoch_tomorrow.year, epoch_tomorrow.month, epoch_tomorrow.day,0,0,0)),_pd.Timestamp(datetime(epoch_tomorrow.year, epoch_tomorrow.month, epoch_tomorrow.day,3,0,0))))]
    sp3 = _pd.concat([yes,tod,tom], axis=0)
    svList = sp3.index.get_level_values("SV").unique()
    svList = svList.sort_values()
    #--------------------------------------------------------------------------
    epoch_values = sp3.index.get_level_values("Epoch").unique()
    deltaT = epoch_values[1]-epoch_values[0]
    fitTime = _np.linspace(0, deltaT.seconds*16 , 17)
    header = ['X', 'Y', 'Z', 'Vx','Vy','Vz']
    # --------------------------------------------------------------
    epoch_start = _pd.Timestamp(datetime(epoch_yesterday.year, epoch_yesterday.month, epoch_yesterday.day,23,0,0))
    epoch_step = timedelta(hours=3)
    epoch_stop = epoch_start + timedelta(hours=4)
    dti = _pd.date_range(start = _pd.Timestamp(datetime(epoch_yesterday.year, epoch_yesterday.month, epoch_yesterday.day,23,30,0)),
                        end   = _pd.Timestamp(datetime( epoch_tomorrow.year,  epoch_tomorrow.month,  epoch_tomorrow.day,2,29,59)),
                        freq = str(interval) + 'S') 
    index = _pd.MultiIndex.from_product([svList, dti.tolist()], names=['SV', 'Epoch'])
    interp_coord = _pd.DataFrame(index= index, columns = header)
    interp_coord = interp_coord.reorder_levels(['Epoch', 'SV'])
    interp_coord = interp_coord.sort_index()
    while True:
        sp3_temp = sp3.loc[(slice(epoch_start,epoch_stop))].copy()
        sp3_temp = sp3_temp.reorder_levels(["SV","Epoch"])
        epoch_interp_List = _np.zeros(shape=(360,6,len(svList)))
        for svIndex,sv in enumerate(svList):
            epoch_number = len(sp3_temp.loc[sv])
            if epoch_number <= poly_degree:
                print("Warning: Not enough epochs to predict for satellite",sv,"| Epoch No:",epoch_number, " - Polynomial Degree:",poly_degree)
                epoch_interp_List[:,:,svIndex] = _np.full(shape=(int(10800/interval),6),fill_value=None)
                continue
            if epoch_number != 17:
                fitTime = [(sp3_temp.loc[sv].index[t]-sp3_temp.loc[sv].index[0]).seconds for t in range(epoch_number)]
            # Fit sp3 coordinates to 16 deg polynomial
            fitX = _np.polyfit(fitTime, sp3_temp.loc[sv].X.copy(), deg=poly_degree)
            fitY = _np.polyfit(fitTime, sp3_temp.loc[sv].Y.copy(), deg=poly_degree)
            fitZ = _np.polyfit(fitTime, sp3_temp.loc[sv].Z.copy(), deg=poly_degree)
            # Interpolate coordinates
            x_interp = coord_interp(fitX, interval) * 1000 # km to m
            x_velocity = _np.array([(x_interp[i+1]-x_interp[i])/interval if (i+1)<len(x_interp) else 0 for i in range(len(x_interp))])
            y_interp = coord_interp(fitY, interval) * 1000 # km to m
            y_velocity = _np.array([(y_interp[i+1]-y_interp[i])/interval if (i+1)<len(y_interp) else 0 for i in range(len(y_interp))])
            z_interp = coord_interp(fitZ, interval) * 1000 # km to m
            z_velocity = _np.array([(z_interp[i+1]-z_interp[i])/interval if (i+1)<len(z_interp) else 0 for i in range(len(z_interp))])
            sv_interp = _np.vstack((x_interp[:-1], y_interp[:-1], z_interp[:-1], x_velocity[:-1], y_velocity[:-1], z_velocity[:-1])).transpose()
            epoch_interp_List[:,:,svIndex] = sv_interp     
            fitTime = _np.linspace(0, deltaT.seconds*16 , 17) # restore original fitTime in case it has changed!
        interp_coord.loc[(slice(epoch_start+timedelta(minutes=30),epoch_stop-timedelta(minutes=30,seconds=1))), ('X', 'Y', 'Z', 'Vx', 'Vy', 'Vz')] = epoch_interp_List.transpose(1,0,2).reshape(6,-1).transpose()
        epoch_start += epoch_step
        epoch_stop += epoch_step
        if epoch_start == _pd.Timestamp(datetime(epoch_tomorrow.year, epoch_tomorrow.month, epoch_tomorrow.day,2,0,0)):
            break
    # -------------------------------------------------------------------------
    interp_coord = interp_coord.reorder_levels(['Epoch', 'SV']).astype(float)
    clock.index.name = 'SV'
    clock.set_index('Epoch', append=True, inplace=True)
    clock = clock.reorder_levels(['Epoch', 'SV'])
    epochMatch = interp_coord.index.intersection(clock.index) 
    ephemerisMatched = interp_coord.loc[epochMatch] 
    clockMatched   = clock.loc[epochMatch]
    sp3matched = _pd.concat([ephemerisMatched, clockMatched], axis=1)
    # -------------------------------------------------------------------------
    finish = time.time()
    print("SP3 interpolation is done in", '{0:.2f}'.format(finish-start), 'seconds')
    return sp3matched

# IONOSPHERE MODEL INTERPOLATION
def ionosphere_interp(station, unit="meter", system="G", band="L1", epoch_list=None):
    """
    This function interpolates the TEC value from NASA Global Ionosphere
    Model at station location. The unit of the output can be tecu or meters.
    If function externally used, satellite system (G/R/E/C/J/I/S) and 
    frequency band must be specified manually.
    """
    ionosphereFile = ionFileName(station.epoch)
    tec = readFile.read_ionFile(ionosphereFile)

    obsList = _observation_picker_by_band(station, system, band) # observables

    lat, lon, ellHeight = cart2ell(station.approx_position[0], station.approx_position[1], station.approx_position[2])

    geocentric_lat = geocentric_latitude(lat)
    geocentric_lon = lon

    if type(epoch_list)==type(None):
        observationEpochList = station.observation.epoch
    else:
        observationEpochList = epoch_list

    Latitude  = _np.linspace(87.5,-87.5,71)
    Longitude = _np.linspace(-180,180,72)

    for i in range(len(Latitude)):
        if Latitude[i] > geocentric_lat > Latitude[i+1]:
            IndexLat = i
            break

    for i in range(len(Longitude)):
        if Longitude[i] < geocentric_lon < Longitude[i+1]:
            IndexLon = i
            break

    dlat = 2.5
    dlon = 5.0
    p = (geocentric_lon-Longitude[IndexLon])/dlon
    q = (geocentric_lat-Latitude[IndexLat+1])/dlat
    E = (1-p)*(1-q)*tec[:,IndexLat+1,IndexLon]+p*(1-q)*tec[:,IndexLat+1,IndexLon+1]+q*(1-p)*tec[:,IndexLat,IndexLon]+p*q*tec[:,IndexLat,IndexLon+1]
    tecFinal = _np.zeros(len(observationEpochList))
    
    epochStart = _pd.Timestamp(station.epoch)
    j = 0
    for i in range(12):
        epochEnd = epochStart + _pd.Timedelta(hours=2)
        while observationEpochList[j] < epochEnd:
            tecFinal[j] = ((epochEnd-observationEpochList[j])/(epochEnd-epochStart))*E[i]+((observationEpochList[j]-epochStart)/(epochEnd-epochStart))*E[i+1]
            j +=1
            if j == len(observationEpochList):
                break
        epochStart += _pd.Timedelta(hours=2)

    if unit.lower()=="tecu":
        ionDelay = 0.1*tecFinal # unit 0.1 TECU to 1 TECU
    elif unit.lower() in {"meter", "meters", "m"}:
        ionDelay = (0.1*tecFinal*40.3*1e16)/obsList[4]**2
    return ionDelay
