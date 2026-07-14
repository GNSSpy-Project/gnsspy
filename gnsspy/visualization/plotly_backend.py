"""
Plotting module - Plotly Implementation with EXACT Matplotlib Logic
Features:
- Preserves exact data processing logic (gap handling, jumps, smoothing).
- Generates interactive HTML plots.
- Fixed: Date attribute error in Skyplot.
"""
import os
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.io as pio





__all__ = ["skyplot", "azelplot", "bandplot", "timelplot", "groundtrack"]

def _prepare_save_path(path):
    """Converts PNG path to HTML-ready path and creates output directory"""
    if not path: return None
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    root, _ = os.path.splitext(path)
    return root + ".html"

def _process_segments_for_plotly(x_data, y_data, break_indices, color_data=None):
    if len(x_data) == 0: return [], [], []
    x_list, y_list, c_list = [], [], []
    start_idx = 0
    boundaries = list(break_indices) + [len(x_data)]
    
    for end_idx in boundaries:
        if end_idx > start_idx:
            slc = slice(start_idx, end_idx)
            x_seg = x_data.iloc[slc] if hasattr(x_data, 'iloc') else x_data[slc]
            y_seg = y_data.iloc[slc] if hasattr(y_data, 'iloc') else y_data[slc]
            x_list.extend(x_seg)
            y_list.extend(y_seg)
            if color_data is not None:
                c_seg = color_data.iloc[slc] if hasattr(color_data, 'iloc') else color_data[slc]
                c_list.extend(c_seg)
            x_list.append(None)
            y_list.append(None)
            if color_data is not None: c_list.append(None)
        start_idx = end_idx 
    return x_list, y_list, c_list

def _get_date_str(epoch_obj):
    """Safely converts a date object to string format"""
    try:

        return str(epoch_obj.date())
    except AttributeError:

        return str(epoch_obj).split()[0]




def skyplot(station, orbit, system='G', sv_list=None, color_mode='snr', save_path=None):
    from gnsspy.positioning.observations import gnssDataframe
    try:
        gnss = gnssDataframe(station, orbit, system, cut_off=0.0)
        if 'SV' in gnss.index.names and 'Epoch' in gnss.index.names:
             gnss = gnss.reorder_levels(["SV", "Epoch"]).sort_index()
        else:
             gnss = gnss.reset_index().set_index(['SV', 'Epoch']).sort_index()

        if sv_list:
            gnss = gnss.loc[gnss.index.get_level_values('SV').intersection(sv_list)]
            if gnss.empty: return

        SVList = gnss.index.get_level_values('SV').unique()
        save_path = _prepare_save_path(save_path)
        
        fig = go.Figure()

        cmin, cmax = (15, 50) if color_mode == 'snr' else (0, 90)
        c_label = "SNR (dB-Hz)" if color_mode == 'snr' else "Elevation (°)"

        for sv in sorted(SVList):
            try:
                sv_data = gnss.loc[sv]
                times = sv_data.index.get_level_values('Epoch')
                az = np.radians(sv_data['Azimuth'].values)
                el = sv_data['Elevation'].values
                r = 90 - el 
                
                if color_mode == 'snr':
                    cols = [c for c in sv_data.columns if c.startswith('S')]
                    c_vals = sv_data[cols[0]] if cols else sv_data['Elevation']
                else:
                    c_vals = sv_data['Elevation']

                elevation_mask = el > 0
                if elevation_mask.sum() < 2: continue
                
                az = az[elevation_mask]
                el = el[elevation_mask]
                r = r[elevation_mask]
                times = times[elevation_mask]
                c_vals = c_vals[elevation_mask]

                dt = pd.Series(times).diff().dt.total_seconds().abs()
                x = r * np.cos(az)
                y = r * np.sin(az)
                dist = np.sqrt(np.diff(x)**2 + np.diff(y)**2)
                
                breaks = np.where((dt[1:].values > 600) | (dist > 15))[0]
                split_points = breaks + 1
                az_deg = np.degrees(az)
                theta_list, r_list, _ = _process_segments_for_plotly(az_deg, el, split_points)
                
                fig.add_trace(go.Scatterpolar(
                    r=r_list, theta=theta_list, mode='lines',
                    line=dict(color='gray', width=1), showlegend=False, hoverinfo='skip'
                ))
                
                fig.add_trace(go.Scatterpolar(
                    r=el, theta=az_deg, mode='markers', name=sv,
                    marker=dict(
                        color=c_vals, colorscale='Jet', cmin=cmin, cmax=cmax,
                        size=6, showscale=True if sv == SVList[0] else False,
                        colorbar=dict(title=c_label)
                    ),
                    hovertemplate="<b>" + sv + "</b><br>Az: %{theta:.1f}°<br>El: %{r:.1f}°<br>Val: %{marker.color:.1f}<extra></extra>"
                ))
            except Exception as e: continue


        date_str = _get_date_str(station.epoch)
        
        fig.update_layout(
            title=f"Skyplot ({station.filename}) - {date_str}",
            template="plotly_white",
            polar=dict(
                radialaxis=dict(range=[90, 0], angle=45, showline=False),
                angularaxis=dict(direction="clockwise", rotation=90)
            ),
            legend=dict(x=1.1, y=1)
        )
        if save_path: fig.write_html(save_path)
    except Exception as e: print(f"Skyplot Error: {e}")




def azelplot(station, orbit, system='G', sv_list=None, color_mode='snr', save_path=None):
    from gnsspy.positioning.observations import gnssDataframe
    try:
        gnss = gnssDataframe(station, orbit, system)
        if 'SV' in gnss.index.names: gnss = gnss.reorder_levels(["SV", "Epoch"]).sort_index()
        else: gnss = gnss.reset_index().set_index(['SV', 'Epoch']).sort_index()
        
        if sv_list: gnss = gnss.loc[gnss.index.get_level_values('SV').intersection(sv_list)]
        
        SVList = gnss.index.get_level_values('SV').unique()
        save_path = _prepare_save_path(save_path)
        fig = go.Figure()

        for sv in sorted(SVList):
            try:
                sv_data = gnss.loc[sv]
                az = (sv_data['Azimuth'] + 360) % 360
                el = sv_data['Elevation']
                mask = el > 0
                if not mask.any(): continue
                
                az = az[mask]
                el = el[mask]
                times = sv_data.index.get_level_values('Epoch')[mask]
                dt = pd.Series(times).diff().dt.total_seconds().abs()
                az_diff = np.abs(np.diff(az.values))
                
                breaks = np.where((dt[1:].values > 600) | (az_diff > 300))[0]
                split_points = breaks + 1
                x_plot, y_plot, _ = _process_segments_for_plotly(az, el, split_points)
                
                fig.add_trace(go.Scatter(
                    x=x_plot, y=y_plot, mode='markers+lines', name=sv,
                    line=dict(color='gray', width=1),
                    marker=dict(
                        color=el if color_mode != 'snr' else sv_data.loc[mask, [c for c in sv_data.columns if c.startswith('S')][0]],
                        colorscale='Jet', size=6
                    ),
                    hovertemplate="<b>" + sv + "</b><br>Az: %{x:.1f}<br>El: %{y:.1f}<extra></extra>"
                ))
            except Exception: continue

        fig.update_layout(
            title=f"Azimuth vs Elevation - {station.filename}",
            xaxis_title="Azimuth (°)", yaxis_title="Elevation (°)",
            xaxis=dict(range=[0, 360], tickmode='linear', dtick=45),
            yaxis=dict(range=[0, 90]), template="plotly_white"
        )
        if save_path: fig.write_html(save_path)
    except Exception as e: print(f"AzEl Error: {e}")




def timelplot(station, orbit=None, system='G', sv_list=None, mode='snr', save_path=None):
    from gnsspy.positioning.observations import gnssDataframe
    try:
        if mode == 'elevation':
            gnss = gnssDataframe(station, orbit, system)
            if 'SV' in gnss.index.names: gnss = gnss.reorder_levels(["SV", "Epoch"]).sort_index()
            else: gnss = gnss.reset_index().set_index(['SV', 'Epoch']).sort_index()
            y_label = "Elevation (°)"
        else:
            gnss = station.observation.copy()
            gnss = gnss.reset_index().set_index(['SV', 'Epoch']).sort_index()
            if 'SYSTEM' in gnss.columns:
                sys_map = {'G':'GPS', 'R':'GLONASS', 'E':'GALILEO', 'C':'COMPASS', 'J':'QZSS', 'I':'IRNSS', 'S':'SBAS'}
                gnss = gnss[gnss['SYSTEM'] == sys_map.get(system, 'GPS')]
            else: 
                gnss = gnss[gnss.index.get_level_values('SV').str.startswith(system)]
            y_label = "SNR (dB-Hz)"

        if sv_list: gnss = gnss.loc[gnss.index.get_level_values('SV').intersection(sv_list)]
        
        SVList = gnss.index.get_level_values('SV').unique()
        save_path = _prepare_save_path(save_path)
        fig = go.Figure()

        try:
            from scipy.ndimage import uniform_filter1d
            has_scipy = True
        except: has_scipy = False

        for sv in sorted(SVList):
            try:
                sv_data = gnss.loc[sv]
                times = sv_data.index.get_level_values('Epoch')
                
                vals = None
                if mode == 'elevation': vals = sv_data['Elevation']
                elif mode == 'snr':
                    cols = [c for c in sv_data.columns if c.startswith('S') and c!='SYSTEM']
                    if cols: vals = sv_data[cols[0]]
                
                if vals is not None:
                    mask = vals.notna()
                    if mask.any():
                        times = times[mask]
                        vals = vals[mask]
                        dt = pd.Series(times).diff().dt.total_seconds().abs()
                        threshold_val = 30 if mode == 'elevation' else 15
                        val_diff = np.abs(np.diff(vals.values))
                        breaks = np.where((dt[1:].values > 600) | (val_diff > threshold_val))[0]
                        split_points = breaks + 1
                        
                        if mode == 'snr' and has_scipy and len(vals) > 3:
                            smoothed_vals = uniform_filter1d(vals.values, size=3, mode='nearest')
                            vals = pd.Series(smoothed_vals, index=vals.index)
                        
                        t_plot, v_plot, _ = _process_segments_for_plotly(times, vals, split_points)
                        fig.add_trace(go.Scatter(
                            x=t_plot, y=v_plot, mode='lines+markers', name=sv,
                            marker=dict(size=3), line=dict(width=1.5),
                            hovertemplate="<b>" + sv + "</b><br>Time: %{x}<br>Val: %{y:.1f}<extra></extra>"
                        ))
            except Exception: continue

        fig.update_layout(
            title=f"Time Series ({mode.upper()}) - {station.filename}",
            xaxis_title="Time (UTC)", yaxis_title=y_label,
            template="plotly_white", hovermode="x unified"
        )
        if save_path: fig.write_html(save_path)
    except Exception as e: print(f"TimePlot Error: {e}")




def bandplot(station, system='G', sv_list=None, save_path=None):
    try:
        gnss = station.observation.copy()
        if 'SV' in gnss.index.names: gnss = gnss.reset_index()
        gnss = gnss[gnss['SV'].str.startswith(system)]
        if sv_list: gnss = gnss[gnss['SV'].isin(sv_list)]
        
        SVList = sorted(gnss['SV'].unique())
        save_path = _prepare_save_path(save_path)
        fig = go.Figure()

        for sv in SVList:
            sv_data = gnss[gnss['SV'] == sv]
            fig.add_trace(go.Scatter(
                x=sv_data['Epoch'], y=[sv] * len(sv_data),
                mode='markers', name=sv,
                marker=dict(symbol='line-ns-open', size=10, line=dict(width=2)),
                hovertemplate="<b>%{y}</b><br>%{x}<extra></extra>"
            ))

        fig.update_layout(
            title=f"Visibility (BandPlot) - {station.filename}",
            xaxis_title="Time", yaxis_title="Satellite",
            yaxis=dict(categoryorder='category descending'), template="plotly_white"
        )
        if save_path: fig.write_html(save_path)
    except Exception as e: print(f"BandPlot Error: {e}")




def groundtrack(orbit, system='G', sv_list=None, save_path=None):
    """
    Plots satellite ground tracks on a world map using Plotly.
    'orbit' is a MultiIndex DataFrame with [Epoch, SV] or [SV, Epoch] and columns X, Y, Z.
    """
    from gnsspy.geodesy.coordinate import cart2ell
    try:

        if 'SV' in orbit.index.names and 'Epoch' in orbit.index.names:
            orbit = orbit.reorder_levels(["SV", "Epoch"]).sort_index()
        else:
            orbit = orbit.reset_index().set_index(['SV', 'Epoch']).sort_index()


        if system:
             mask = [sv.startswith(system) for sv in orbit.index.get_level_values('SV')]
             orbit = orbit[mask]
             
        if sv_list:
            orbit = orbit.loc[orbit.index.get_level_values('SV').intersection(sv_list)]
            
        if orbit.empty:
            print("   [!] No orbit data for groundtrack.")
            return

        SVList = sorted(orbit.index.get_level_values('SV').unique())
        save_path = _prepare_save_path(save_path)
        
        fig = go.Figure()
        

        colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8',
                  '#F7DC6F', '#BB8FCE', '#85C1E9', '#F0B27A', '#AED6F1']

        for idx, sv in enumerate(SVList):
            try:
                sv_data = orbit.loc[sv]
                

                cols = {c.upper(): c for c in sv_data.columns}
                x_col = cols.get('X')
                y_col = cols.get('Y')
                z_col = cols.get('Z')
                
                if not (x_col and y_col and z_col):
                    continue


                lats, lons = [], []
                times = sv_data.index.get_level_values('Epoch')
                


                if len(sv_data) > 300:
                   step = len(sv_data) // 288
                   sv_subset = sv_data.iloc[::step]
                else:
                   sv_subset = sv_data

                for i in range(len(sv_subset)):
                    row = sv_subset.iloc[i]

                    lat, lon, h = cart2ell(row[x_col], row[y_col], row[z_col], ellipsoid='WGS84')
                    lats.append(lat)
                    lons.append(lon)
                

                seg_lats, seg_lons = [[]], [[]]
                for i in range(len(lats)):
                    if i > 0 and abs(lons[i] - lons[i-1]) > 180:
                        seg_lats.append([])
                        seg_lons.append([])
                    seg_lats[-1].append(lats[i])
                    seg_lons[-1].append(lons[i])
                
                color = colors[idx % len(colors)]
                for si, (slat, slon) in enumerate(zip(seg_lats, seg_lons)):
                    fig.add_trace(go.Scattergeo(
                        lat=slat, lon=slon,
                        mode='lines',
                        name=sv if si == 0 else None,
                        showlegend=(si == 0),
                        line=dict(width=2, color=color),
                        hovertext=f"{sv} Ground Track",
                        hovertemplate="<b>" + sv + "</b><br>Lat: %{lat:.2f}<br>Lon: %{lon:.2f}<extra></extra>"
                    ))
                

                if lats:
                    fig.add_trace(go.Scattergeo(
                        lat=[lats[0]], lon=[lons[0]],
                        mode='markers', showlegend=False,
                        marker=dict(size=6, color=color, symbol='diamond'),
                        hoverinfo='skip'
                    ))

            except Exception as e: continue

        fig.update_geos(
            showcountries=True, countrycolor='rgb(220, 220, 220)',
            showcoastlines=True, coastlinecolor='rgb(180, 180, 180)',
            showland=True, landcolor='rgb(245, 245, 245)',
            showocean=True, oceancolor='rgb(230, 240, 250)',
            projection_type='natural earth',
        )
        
        fig.update_layout(
            title=dict(
                text='Satellite Ground Tracks',
                x=0.5, font=dict(size=20)
            ),
            template="plotly_white",
            height=600,
            margin=dict(l=20, r=20, t=60, b=20),
            legend=dict(x=1.02, y=1)
        )
        
        if save_path: fig.write_html(save_path)
    except Exception as e: print(f"GroundTrack Error: {e}")





azimuth_elevation_plot = azelplot
time_elevation_plot = timelplot
visibility_plot = bandplot
ground_track = groundtrack

__all__ = [
    "skyplot",
    "azelplot",
    "azimuth_elevation_plot",
    "bandplot",
    "visibility_plot",
    "timelplot",
    "time_elevation_plot",
    "groundtrack",
    "ground_track",
]

