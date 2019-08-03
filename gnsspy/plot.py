"""
Plotting module
"""
# ===========================================================
# ========================= imports =========================
import pandas as _pd
import numpy as _np
try:
    from mpl_toolkits.basemap import Basemap
    _BasemapStatus = True
except Exception as e:
    print("Warning: Basemap package cannot be imported |",e," error detected - Groundtrack plot disabled!")
    _BasemapStatus = False
import matplotlib.patches as _mpatches
from gnsspy.geodesy.coordinate import cart2ell_direct
from gnsspy.position.position import gnssDataframe, multipath, _observation_picker_by_band
from gnsspy.position.interpolation import ionosphere_interp
import matplotlib.pyplot as _plt
import matplotlib as _mptl
# ===========================================================

__all__ = ["skyplot","azelplot","bandplot","timelplot","groundtrack"]

# SKYPLOT
def skyplot(station, orbit, system = 'G', SVlist=None, color=None):
    # ----------------------------------------------------------------------
    if color != None:
        color = color.lower()
        if color not in {'ionosphere','snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9','multipath1', 'multipath2'}:
            raise Warning(color,"option for color mapping is not available for skyplot!")
    # ----------------------------------------------------------------------
    gnss = gnssDataframe(station, orbit, system)
    gnss = gnss.reorder_levels(["SV", "Epoch"])

    if color == 'multipath1' or color == 'multipath2':
        multipath_temp = multipath(station, system)
        epochMatch = gnss.index.intersection(multipath_temp.index)
        gnss = _pd.concat([gnss.loc[epochMatch].copy(), multipath_temp.loc[epochMatch].copy()], axis=1)
    
    # ----------------------------------------------------------------------
    SVList = gnss.index.get_level_values('SV').unique()
    gnss['svx'] = _np.radians(gnss.Azimuth.values)
    if SVlist == None:
        SVlist = SVList
    else:
        for sv in SVlist:
            if sv[0] not in {'G','R','C','E'} or sv[1:].isdigit() == False or len(sv)!=3:
                raise Warning("Invalid format: Please enter satellite(s) that you want to plot proper format. Exp. SVlist= ['G01', 'G02', 'G11',....] Program Stopped")
            elif sv not in SVList:
                SVlist.remove(sv)
                print('{} satellite not in SP3 file'.format(sv))
    if len(SVlist) == 0:
        raise Warning("Satellite(s) that you have entered not in SP3 file Program Stopped")
    fig = _plt.figure('Skyplot')
    figName = 'Skyplot'
    ax = fig.add_axes([0.1,0.1,0.8,0.8], polar=True)
    # -------------------------------------------------------------------------
    if color!=None:
        minValue, maxValue = 1e9, -1e9
        if color=="ionosphere":
            gnss['Ion_Delay'] = ionosphere_interp(station, unit  = 'meter', system= system, band = 'L1', epoch_list = gnss.epoch)
        for sv in SVlist:
            if color == 'ionosphere':
                if minValue > gnss.loc[sv].Ion_Delay.min():
                    minValue = gnss.loc[sv].Ion_Delay.min()
                if maxValue < gnss.loc[sv].Ion_Delay.max():
                    maxValue = gnss.loc[sv].Ion_Delay.max()
            elif color in {'snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9'}:
                obslist = _observation_picker_by_band(station, system, band = 'L'+color[-1])
                snr = getattr(gnss.loc[sv], obslist[6])
                if minValue > snr.min():
                    minValue = snr.min()
                if maxValue < snr.max():
                    maxValue = snr.max()
            elif color == 'multipath1':
                if minValue > gnss.loc[sv].Multipath1.min():
                    minValue = gnss.loc[sv].Multipath1.min()
                if maxValue < gnss.loc[sv].Multipath1.max():
                    maxValue = gnss.loc[sv].Multipath1.max()
            elif color == 'multipath2':
                if minValue > gnss.loc[sv].Multipath2.min():
                    minValue = gnss.loc[sv].Multipath2.min()
                if maxValue < gnss.loc[sv].Multipath2.max():
                    maxValue = gnss.loc[sv].Multipath2.max()
    # -------------------------------------------------------------------------
    for sv in SVlist:
        if color==None:
            skyplot=ax.scatter(gnss.loc[sv].svx, gnss.loc[sv].Zenith, s=3, cmap = _mptl.cm.jet)
            ax.text(gnss.loc[sv].svx[int(len(gnss.loc[sv].svx)/4)], gnss.loc[sv].Zenith[int(len(gnss.loc[sv].Zenith)/4)], sv, fontsize=9)
        elif color == 'ionosphere':
            skyplot=ax.scatter(gnss.loc[sv].svx, gnss.loc[sv].Zenith, s=3, c = gnss.loc[sv].Ion_Delay, cmap = _mptl.cm.jet, vmin=minValue, vmax=maxValue)
            ax.text(gnss.loc[sv].svx[int(len(gnss.loc[sv].svx)/4)], gnss.loc[sv].Zenith[int(len(gnss.loc[sv].Zenith)/4)], sv, fontsize=9)
        elif color in {'snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9'}:
            obslist = _observation_picker_by_band(station, system, band = 'L'+color[-1])
            snr = getattr(gnss.loc[sv], obslist[6])
            skyplot=ax.scatter(gnss.loc[sv].svx, gnss.loc[sv].Zenith, s=3, c = snr, cmap = _mptl.cm.jet, vmin=minValue, vmax=maxValue)
            ax.text(gnss.loc[sv].svx[int(len(gnss.loc[sv].svx)/4)], gnss.loc[sv].Zenith[int(len(gnss.loc[sv].Zenith)/4)], sv, fontsize=9)
        elif color == 'multipath1':
            skyplot=ax.scatter(gnss.loc[sv].svx, gnss.loc[sv].Zenith, s=3, c = gnss.loc[sv].Multipath1, cmap = _mptl.cm.jet, vmin=minValue, vmax=maxValue)
            ax.text(gnss.loc[sv].svx[int(len(gnss.loc[sv].svx)/4)], gnss.loc[sv].Zenith[int(len(gnss.loc[sv].Zenith)/4)], sv, fontsize=9)
        elif color == 'multipath2':
            skyplot=ax.scatter(gnss.loc[sv].svx, gnss.loc[sv].Zenith, s=3, c = gnss.loc[sv].Multipath2, cmap = _mptl.cm.jet, vmin=minValue, vmax=maxValue)
            ax.text(gnss.loc[sv].svx[int(len(gnss.loc[sv].svx)/4)], gnss.loc[sv].Zenith[int(len(gnss.loc[sv].Zenith)/4)], sv, fontsize=9)
    # Axes properties
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    ax.set_rmax(90.0)
    ax.set_yticks(range(0, 90, 10))
    ax.set_yticklabels(map(str, range(90, 0, -10)))
    if color in {'ionosphere','snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9','multipath1', 'multipath2'}:
        figName = figName + " ("+ color + ") for " + station.filename
        fig.colorbar(skyplot,extend="both")
    else:
        figName = figName + " for " + station.filename
    _plt.title(figName)
    fig.savefig(station.filename+"_Skyplot.png",transparent=True)

# AZEL PLOT
def azelplot(station, orbit, system = 'G', SVlist = None, color = None):
    if color != None:
        color = color.lower()
        if color not in {'ionosphere','snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9','troposphere'}:
            raise Warning(color,"option for color mapping is not available for azelplot!")
    # ----------------------------------------------------------------------
    gnss = gnssDataframe(station, orbit, system)
    gnss = gnss.reorder_levels(["SV", "Epoch"])

    if color == 'multipath1' or color == 'multipath2':
        multipath_temp = multipath(station, system)
        epochMatch = gnss.index.intersection(multipath_temp.index)
        gnss = _pd.concat([gnss.loc[epochMatch].copy(), multipath_temp.loc[epochMatch].copy()], axis=1)
    
    # ----------------------------------------------------------------------
    
    SVList = gnss.index.get_level_values('SV').unique()
    if SVlist == None:
        SVlist = SVList
    else:
        for sv in SVlist:
            if sv[0] not in {'G','R','C','E'} or sv[1:].isdigit() == False or len(sv)!=3:
                raise Warning('''Invalid format: Please enter satellite(s) that you want to plot proper format.
                Exp. SVlist= ['G01', 'G02', 'G11',....] 
                Program Stopped''')
            elif sv not in SVList:
                SVlist.remove(sv)
                print('{} satellite not in SP3 file'.format(sv))
    
    if len(SVlist) == 0:
        raise Warning("Satellite(s) not found in SP3 file | Program Stopped!")
    
    _plt.figure("Azimuth-Elevation Plot")
    figName = "Azimuth-Elevation Plot"
    _plt.xlabel('Azimuth', fontsize=12)
    _plt.ylabel('Elevation', fontsize=12)
    _plt.xlim(-180.0, 180.0)
    _plt.ylim(-1.0, 91.0)
    # -------------------------------------------------------------------------
    if color!=None:
        minValue, maxValue = 1e9, -1e9
        if color=="ionosphere":
            gnss['Ion_Delay'] = ionosphere_interp(station, unit  = 'meter', system= system, band = 'L1', epoch_list = gnss.epoch)
        for sv in SVlist:
            if color == 'ionosphere':
                if minValue > gnss.loc[sv].Ion_Delay.min():
                    minValue = gnss.loc[sv].Ion_Delay.min()
                if maxValue < gnss.loc[sv].Ion_Delay.max():
                    maxValue = gnss.loc[sv].Ion_Delay.max()
            elif color == 'troposphere':
                if minValue > gnss.loc[sv].Tropo.min():
                    minValue = gnss.loc[sv].Tropo.min()
                if maxValue < gnss.loc[sv].Tropo.max():
                    maxValue = gnss.loc[sv].Tropo.max()
            elif color in {'snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9'}:
                obslist = _observation_picker_by_band(station, system, band = 'L'+color[-1])
                snr = getattr(gnss.loc[sv], obslist[6])
                if minValue > snr.min():
                    minValue = snr.min()
                if maxValue < snr.max():
                    maxValue = snr.max()
            elif color == 'multipath1':
                if minValue > gnss.loc[sv].Multipath1.min():
                    minValue = gnss.loc[sv].Multipath1.min()
                if maxValue < gnss.loc[sv].Multipath1.max():
                    maxValue = gnss.loc[sv].Multipath1.max()
            elif color == 'multipath2':
                if minValue > gnss.loc[sv].Multipath2.min():
                    minValue = gnss.loc[sv].Multipath2.min()
                if maxValue < gnss.loc[sv].Multipath2.max():
                    maxValue = gnss.loc[sv].Multipath2.max()
    # -------------------------------------------------------------------------
    for sv in SVlist:
        if color == None:
            _plt.scatter(gnss.loc[sv].Azimuth, gnss.loc[sv].Elevation, s=3, cmap = _mptl.cm.jet, lw=0, vmin=minValue, vmax=maxValue)
            _plt.text(gnss.loc[sv].Azimuth[int(len(gnss.loc[sv].Azimuth)/3)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Azimuth)/3)], sv, fontsize=9)
            _plt.text(gnss.loc[sv].Azimuth[int(len(gnss.loc[sv].Azimuth)/3*2)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Azimuth)/3*2)], sv, fontsize=9)
        elif color == 'ionosphere':
            _plt.scatter(gnss.loc[sv].Azimuth, gnss.loc[sv].Elevation, s=3, c = gnss.loc[sv].Ion_Delay, cmap = _mptl.cm.jet, lw=0)
            _plt.text(gnss.loc[sv].Azimuth[int(len(gnss.loc[sv].Azimuth)/3)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Azimuth)/3)], sv, fontsize=9)
            _plt.text(gnss.loc[sv].Azimuth[int(len(gnss.loc[sv].Azimuth)/3*2)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Azimuth)/3*2)], sv, fontsize=9)
        elif color in {'snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9'}:
            obslist = _observation_picker_by_band(station, system, band = 'L'+color[-1])
            snr = getattr(gnss.loc[sv], obslist[6])
            _plt.scatter(gnss.loc[sv].Azimuth, gnss.loc[sv].Elevation, s=3, c = snr, cmap = _mptl.cm.jet, lw=0, vmin=minValue, vmax=maxValue)
            _plt.text(gnss.loc[sv].Azimuth[int(len(gnss.loc[sv].Azimuth)/3)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Azimuth)/3)], sv, fontsize=9)
            _plt.text(gnss.loc[sv].Azimuth[int(len(gnss.loc[sv].Azimuth)/3*2)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Azimuth)/3*2)], sv, fontsize=9)
        elif color == 'troposphere':
            _plt.scatter(gnss.loc[sv].Azimuth, gnss.loc[sv].Elevation, s=3, c = gnss.loc[sv].Tropo, cmap = _mptl.cm.jet, lw=0, vmin=minValue, vmax=maxValue)
            _plt.text(gnss.loc[sv].Azimuth[int(len(gnss.loc[sv].Azimuth)/3)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Elevation)/3)], sv, fontsize=9)
            _plt.text(gnss.loc[sv].Azimuth[int(len(gnss.loc[sv].Azimuth)/3*2)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Elevation)/3*2)], sv, fontsize=9)
    
    if color in {'ionosphere','snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9','troposphere'}: 
        _plt.colorbar(extend="both")
        figName = figName + " ("+ color + ") for " + station.filename
    else:
        figName = figName + " for " + station.filename
    _plt.title(figName)
    _plt.savefig(station.filename+"_AzelPlot.png",transparent=True)

# BANDPLOT
def bandplot(station, system = 'G', SVlist=None):
    gnss = station.observation
    # ----------------------------------------------------------------------
    SVList = gnss.index.get_level_values('SV').unique()

    if SVlist == None:
        SVlist = SVList
    else:
        for sv in SVlist:
            if sv[0] not in {'G','R','C','E'} or sv[1:].isdigit() == False or len(sv)!=3:
                raise Warning('''Invalid format: Please enter satellite(s) that you want to plot proper format.
                Exp. SVlist= ['G01', 'G02', 'G11',....] 
                Program Stopped''')
            elif sv not in SVList:
                SVlist.remove(sv)
                print('{} satellite not in SP3 file'.format(sv))
    
    if len(SVlist) == 0:
        raise Warning('''Satellite(s) that you have entered not in SP3 file
            Program Stopped''')
    RefPos = []
    line= 500
    for i in range(len(SVList)):
        RefPos.append(line+(i*500))
    
    RefPos = _pd.DataFrame(data = RefPos, index = SVList, columns = ['Visibility'])
    gnss = gnss.join(RefPos, how='inner')
    gnss = gnss.reorder_levels(['SV','Epoch'])
    gnss = gnss.sort_index()
    
    gnss['Time'] = gnss.epoch.dt.time
    _plt.figure("Band Plot")
    _plt.title("Band Plot", fontsize=12)
    _plt.xlabel('Time', fontsize=12)
    _plt.axes().get_yaxis().set_visible(False)
    
    for sv in SVlist:
        _plt.plot(gnss.loc[sv].Time, gnss.loc[sv].Visibility, linestyle='', marker='.',linewidth=1)
            #ax.xaxis.set_major_locator(mdates.HourLocator(byhour=range(24), interval=4))
        _plt.annotate(sv, xy=(gnss.loc[sv].Time[0], gnss.loc[sv].Visibility[0]+20), 
               size='medium', color='black')
    _plt.savefig(station.filename+"_BandPlot.png",transparent=True)

# TIME_ELEVATION PLOT
def timelplot(station, orbit, system = 'G', SVlist=None, color=None):
    if color != None:
        color = color.lower()
        if color not in {'ionosphere','troposphere','snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9','multipath1', 'multipath2'}:
            raise Warning(color,"option for color mapping is not available for timelplot!")
    # ----------------------------------------------------------------------
    gnss = gnssDataframe(station, orbit, system)
    gnss = gnss.reorder_levels(["SV", "Epoch"])

    if color == 'multipath1' or color == 'multipath2':
        multipath_temp = multipath(station, system)
        epochMatch = gnss.index.intersection(multipath_temp.index) # list of matched epochs and SVs
        gnss = _pd.concat([gnss.loc[epochMatch].copy(), multipath_temp.loc[epochMatch].copy()], axis=1)
    
    # ----------------------------------------------------------------------
    SVList = gnss.index.get_level_values('SV').unique()

    if SVlist == None:
        SVlist = SVList
    else:
        for sv in SVlist:
            if sv[0] not in {'G','R','C','E'} or sv[1:].isdigit() == False or len(sv)!=3:
                raise Warning('''Invalid format: Please enter satellite(s) that you want to plot proper format.
                Exp. SVlist= ['G01', 'G02', 'G11',....] 
                Program Stopped''')
            elif sv not in SVList:
                SVlist.remove(sv)
                print('{} satellite not in SP3 file'.format(sv))
    
    if len(SVlist) == 0:
        raise Warning('''Satellite(s) that you have entered not in SP3 file
            Program Stopped''')
    
    gnss['Time'] = gnss['epoch'].dt.time
    gnss['Seconds']= _pd.to_timedelta(gnss['epoch']).apply(lambda x: x.total_seconds())
    _plt.figure("Time-Elevation Plot")
    figName = "Time-Elevation Plot"
    _plt.xlabel('Time', fontsize=12)
    _plt.ylabel('Elevation', fontsize=12)
    _plt.ylim(-1.0, 91.0)
    _plt.grid()
    # -------------------------------------------------------------------------
    if color!=None:
        minValue, maxValue = 1e9, -1e9
        if color=="ionosphere":
            gnss['Ion_Delay'] = ionosphere_interp(station, unit  = 'meter', system= system, band = 'L1', epoch_list = gnss.epoch)
        for sv in SVlist:
            if color == 'ionosphere':
                if minValue > gnss.loc[sv].Ion_Delay.min():
                    minValue = gnss.loc[sv].Ion_Delay.min()
                if maxValue < gnss.loc[sv].Ion_Delay.max():
                    maxValue = gnss.loc[sv].Ion_Delay.max()
            elif color == 'troposphere':
                if minValue > gnss.loc[sv].Tropo.min():
                    minValue = gnss.loc[sv].Tropo.min()
                if maxValue < gnss.loc[sv].Tropo.max():
                    maxValue = gnss.loc[sv].Tropo.max()
            elif color in {'snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9'}:
                obslist = _observation_picker_by_band(station, system, band = 'L'+color[-1])
                snr = getattr(gnss.loc[sv], obslist[6])
                if minValue > snr.min():
                    minValue = snr.min()
                if maxValue < snr.max():
                    maxValue = snr.max()
            elif color == 'multipath1':
                if minValue > gnss.loc[sv].Multipath1.min():
                    minValue = gnss.loc[sv].Multipath1.min()
                if maxValue < gnss.loc[sv].Multipath1.max():
                    maxValue = gnss.loc[sv].Multipath1.max()
            elif color == 'multipath2':
                if minValue > gnss.loc[sv].Multipath2.min():
                    minValue = gnss.loc[sv].Multipath2.min()
                if maxValue < gnss.loc[sv].Multipath2.max():
                    maxValue = gnss.loc[sv].Multipath2.max()
    # -------------------------------------------------------------------------
    for sv in SVlist:
        if color == None:
            _plt.scatter(gnss.loc[sv].Seconds, gnss.loc[sv].Elevation, s=3, cmap = _mptl.cm.jet, lw=0, vmin=minValue, vmax=maxValue)
            _plt.text(gnss.loc[sv].Seconds[int(len(gnss.loc[sv].Seconds)/2)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Elevation)/2)], sv, fontsize=9)
        elif color == 'troposphere':
            _plt.scatter(gnss.loc[sv].Seconds, gnss.loc[sv].Elevation, s=3, c = gnss.loc[sv].Tropo, cmap = _mptl.cm.jet, lw=0, vmin=minValue, vmax=maxValue)
            _plt.text(gnss.loc[sv].Seconds[int(len(gnss.loc[sv].Seconds)/2)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Elevation)/2)], sv, fontsize=9)
        elif color in {'snr1', 'snr2','snr3','snr4','snr5','snr6','snr7','snr8','snr9'}:
            obslist = _observation_picker_by_band(station, system, band = 'L'+color[-1])
            snr = getattr(gnss.loc[sv], obslist[6])
            _plt.scatter(gnss.loc[sv].Seconds, gnss.loc[sv].Elevation, s=3, c = snr, cmap = _mptl.cm.jet, lw=0, vmin=minValue, vmax=maxValue)
            _plt.text(gnss.loc[sv].Seconds[int(len(gnss.loc[sv].Seconds)/2)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Elevation)/2)], sv, fontsize=9)
        elif color == 'multipath1':
            _plt.scatter(gnss.loc[sv].Seconds, gnss.loc[sv].Elevation, s=3, c = gnss.loc[sv].Multipath1, cmap = _mptl.cm.jet, lw=0, vmin=minValue, vmax=maxValue)
            _plt.text(gnss.loc[sv].Seconds[int(len(gnss.loc[sv].Seconds)/2)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Elevation)/2)], sv, fontsize=9)
        elif color == 'multipath2':
            _plt.scatter(gnss.loc[sv].Seconds, gnss.loc[sv].Elevation, s=3, c = gnss.loc[sv].Multipath2, cmap = _mptl.cm.jet, lw=0, vmin=minValue, vmax=maxValue)
            _plt.text(gnss.loc[sv].Seconds[int(len(gnss.loc[sv].Seconds)/2)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Elevation)/2)], sv, fontsize=9)
        elif color == 'ionosphere':
            _plt.scatter(gnss.loc[sv].Seconds, gnss.loc[sv].Elevation, s=3, c = gnss.loc[sv].Ion_Delay, cmap = _mptl.cm.jet, lw=0, vmin=minValue, vmax=maxValue)
            _plt.text(gnss.loc[sv].Seconds[int(len(gnss.loc[sv].Seconds)/2)], gnss.loc[sv].Elevation[int(len(gnss.loc[sv].Elevation)/2)], sv, fontsize=9)
            
    if color in {"ionosphere","snr1","snr2","multipath1","multipath2","troposphere"}: 
        _plt.colorbar(extend="both")
        figName = figName + " ("+ color + ") for " + station.filename
    else:
        figName = figName + " for " + station.filename
    _plt.title(figName)
    _plt.savefig(station.filename+"_TimelPlot.png",transparent=True)

# GROUNDTRACK
if _BasemapStatus:
    def groundtrack(station, system = 'G', SVlist=None):
        gnss = station.observation
        SatEllCoor = cart2ell_direct(gnss.X.values, gnss.Y.values, gnss.Z.values)
        SVList = gnss.index.get_level_values('SVs').unique()
        gnss['Latitude'] = SatEllCoor[0]
        gnss['Longitude'] = SatEllCoor[1]
        gnss['EllHeight'] = SatEllCoor[2]
        gnss = gnss.reorder_levels(['SV','Epoch'])
    
        for sv in SVlist:
            if sv[0] not in {'G','R','C','E'} or sv[1:].isdigit() == False or len(sv)!=3:
                raise Warning('''Invalid format: Please enter satellite(s) that you want to plot proper format.
                Exp. SVlist= ['G01', 'G02', 'G11',....] 
                Program Stopped''')
            elif sv not in SVList:
                SVlist.remove(sv)
                print('{} satellite not in SP3 file'.format(sv))
        
        if len(SVlist) == 0:
            raise Warning('''Satellite(s) that you have entered not in SP3 file
                Program Stopped''')
        
        #------------------------start figure plot-------------------------------------#
        '''create map using BASEMAP
        llcrnrlat,llcrnrlon,urcrnrlat,urcrnrlon
        are the lat/lon values of the lower left and upper right corners
        of the map.
        lat_ts is the latitude of true scale.
        resolution = 'c' means use crude resolution coastlines'''
        
        m = Basemap(projection='merc',llcrnrlat=-80,urcrnrlat=80,\
                llcrnrlon=-180,urcrnrlon=180,lat_ts=20,resolution='c')
        m.drawcoastlines()
        m.fillcontinents(color='coral',lake_color='aqua')
        # draw parallels and meridians.
        m.drawparallels(_np.arange(-90.,91.,30.))
        m.drawmeridians(_np.arange(-180.,181.,60.))
        m.drawmapboundary(fill_color='aqua')
        
        coloropt = ['violet', 'red', 'wheat', 'yellow', 'orange', 'magenta', 'lime', 'ivory', 
                'gold', 'cyan', 'coral']
        
        for sv, i in zip(SVlist, range(len(SVlist))):
            lat = _pd.DataFrame()
            lon = _pd.DataFrame()
            lat[sv] = gnss.loc[sv].Latitude.values
            lon[sv] = gnss.loc[sv].Longitude.values
            lons, lats = m(lon[sv].values, lat[sv].values)
            m.scatter(lons, lats, color = coloropt[i], zorder=4, marker='.',s=3)
        recs = []
        for i in range(0,len(coloropt)):
            recs.append(_mpatches.Rectangle((0,0),1,1,fc=coloropt[i]))
        _plt.legend(recs, SVlist)
        _plt.title("Ground Track of GPS Satellites for {}".format(station.filename), fontweight='bold')
        _plt.savefig(station.filename+"_Groundtrack.png",transparent=True)
