#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
brdc_timeseries.py
==================
Day-long time series analysis of BRDC vs SP3 orbit differences.
For each epoch, the ephemeris with the nearest Toe is selected (midpoint rule).
Generates interactive Plotly HTML charts (compatible with gnsspy plot.py style).
"""
import os, datetime, webbrowser
import numpy as np
import pandas as pd

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from pathlib import Path


from gnsspy.orbit import comparison as orbit_utils







_MAX_DIFF_M = 100.0



_MAX_TK_SEC = 7200








_MAD_K = 6.0
_MAD_FLOOR_M = 5.0


from gnsspy.cli import download as dn





def compute_day_timeseries(nav_files, sp3_files, clk_files, target_date,
                           interval=30, sv_filter=None):
    """Day-long BRDC vs SP3 comparison. Returns: {sv: DataFrame}.

    sv_filter: result of orbit_utils.parse_sv_filter() — None means all SVs.
    """

    print(f"\n[1/3] SP3 interpolasyonu (interval={interval}s, poly=16)...")
    base_dir = os.path.dirname(nav_files[0])

    sp3data = orbit_utils.run_sp3_interp(target_date, sp3_files, clk_files, base_dir, interval=interval, poly_degree=16)

    if sp3data.empty:
        print("SP3 data could not be produced!"); return {}

    print(f"[2/3] Reading navigation files ({len(nav_files)} files)...")
    eph_table = orbit_utils.build_ephemeris_table(nav_files)
    print(f"       Ephemeris found for {len(eph_table)} satellites.")

    print(f"[3/3] Computing time series...")
    day_start = pd.Timestamp(datetime.datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0))
    day_end = pd.Timestamp(datetime.datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59))
    all_epochs = sp3data.index.get_level_values('Epoch').unique().sort_values()
    day_epochs = all_epochs[(all_epochs >= day_start) & (all_epochs <= day_end)]
    common_svs = sorted(set(sp3data.index.get_level_values('SV').unique()) & set(eph_table.keys()))


    if sv_filter is not None:
        before = len(common_svs)
        common_svs = [sv for sv in common_svs if orbit_utils.sv_matches_filter(sv, sv_filter)]
        print(f"       [SV FILTER] {before} -> {len(common_svs)} satellites after filter.")
        if not common_svs:
            print("       No satellites match the filter; aborting."); return {}

    results = {}
    skipped_hard = 0
    skipped_tk = 0
    skipped_mad = 0
    for sv in common_svs:
        sys_type = sv[0]
        sv_ephs = eph_table[sv]
        rows = []
        for epoch in day_epochs:
            epoch_dt = epoch.to_pydatetime()
            tow = orbit_utils.datetime_to_gps_tow(epoch_dt)
            nearest = orbit_utils.find_nearest_eph(sv_ephs, tow)
            if nearest is None: continue
            toe_used, eph = nearest
            tk = abs(tow - toe_used)
            if tk > 302400: tk = 604800 - tk

            if tk > _MAX_TK_SEC:
                skipped_tk += 1
                continue
            try:
                brdc = orbit_utils.compute_keplerian_xyz(eph, tow, sys_type)
            except Exception: continue
            if brdc is None: continue
            try:
                sp3r = sp3data.loc[(epoch, sv)]
                sx, sy, sz = sp3r['X'], sp3r['Y'], sp3r['Z']
            except KeyError: continue
            if np.isnan(sx): continue
            dx, dy, dz = brdc[0]-sx, brdc[1]-sy, brdc[2]-sz
            d3d = np.sqrt(dx**2 + dy**2 + dz**2)

            if (not np.isfinite(d3d) or d3d > _MAX_DIFF_M
                    or abs(dx) > _MAX_DIFF_M or abs(dy) > _MAX_DIFF_M
                    or abs(dz) > _MAX_DIFF_M):
                skipped_hard += 1
                continue
            rows.append({'epoch': epoch_dt,
                         'brdc_x': brdc[0], 'brdc_y': brdc[1], 'brdc_z': brdc[2],
                         'sp3_x': sx, 'sp3_y': sy, 'sp3_z': sz,
                         'dx': dx, 'dy': dy, 'dz': dz,
                         'd3d': d3d, 'toe_used': toe_used})

        if not rows:
            continue

        df_sv = pd.DataFrame(rows)


        d3d_arr = df_sv['d3d'].values
        if len(d3d_arr) >= 5:
            med = float(np.median(d3d_arr))
            mad = float(np.median(np.abs(d3d_arr - med)))
            sigma_est = 1.4826 * mad
            threshold = med + max(_MAD_K * sigma_est, _MAD_FLOOR_M)
            mask = d3d_arr <= threshold
            dropped = int((~mask).sum())
            if dropped > 0:
                skipped_mad += dropped
                df_sv = df_sv[mask].reset_index(drop=True)

        if len(df_sv) > 0:
            results[sv] = df_sv

    if skipped_tk > 0:
        print(f"       [FILTER-1] Dropped {skipped_tk} epochs outside "
              f"|tk| <= {_MAX_TK_SEC}s ephemeris validity window.")
    if skipped_hard > 0:
        print(f"       [FILTER-2] Dropped {skipped_hard} epochs with "
              f"|diff| > {_MAX_DIFF_M:.0f} m (hard ceiling).")
    if skipped_mad > 0:
        print(f"       [FILTER-3] Dropped {skipped_mad} per-satellite MAD "
              f"outliers (K={_MAD_K}, floor={_MAD_FLOOR_M:.0f} m).")
    print(f"       Time series created for {len(results)} satellites.")
    return results





def plot_satellite(df, sv, target_date, save_dir=None):
    """Single satellite dX, dY, dZ, 3D time series (Matplotlib PNG)."""
    fig, axes = plt.subplots(4, 1, figsize=(10, 12), sharex=True, constrained_layout=True)
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
    labels = ['dX (m)', 'dY (m)', 'dZ (m)', '3D Error (m)']
    keys = ['dx', 'dy', 'dz', 'd3d']

    for i, (ax, key, color, label) in enumerate(zip(axes, keys, colors, labels)):
        data = df[key]
        rms = np.sqrt(np.mean(data**2))
        
        ax.plot(df['epoch'], data, color=color, linewidth=1.2, label=label)
        
        if key != 'd3d':
            stat_txt = f'Mean: {np.mean(data):.2f} | Std: {np.std(data):.2f} | RMS: {rms:.2f}'
        else:
            stat_txt = f'Mean: {np.mean(data):.2f} | Max: {np.max(data):.2f} | RMS: {rms:.2f}'
        
        ax.text(0.01, 0.92, stat_txt, transform=ax.transAxes, fontsize=10,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))
        

        changes = df['toe_used'].diff().fillna(0) != 0
        for idx in df[changes].index:
            ax.axvline(x=df.loc[idx, 'epoch'], color='red', linestyle='--', linewidth=0.8, alpha=0.4)
            
        ax.set_ylabel(label, fontsize=11)
        ax.grid(True, linestyle=':', alpha=0.6)
        
    axes[-1].set_xlabel("UTC Time", fontsize=11)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.suptitle(f'{sv} -- BRDC vs SP3 Orbit Differences ({target_date})', fontsize=14, fontweight='bold')

    if save_dir:
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        fname = os.path.join(save_dir, f"ts_{sv}_{target_date}.png")
        plt.savefig(fname, dpi=300)
        plt.close(fig)
        return fname
    return fig


def plot_system_rms(results, target_date, system='G', save_dir=None):
    """Per-satellite 3D RMS bar chart (Matplotlib PNG)."""
    svs = sorted([sv for sv in results if sv.startswith(system)])
    if not svs: return None
    
    rms_vals = [np.sqrt(np.mean(results[sv]['d3d']**2)) for sv in svs]
    sys_name = orbit_utils.SYSTEM_NAMES.get(system, system)
    median_val = np.median(rms_vals)
    
    plt.figure(figsize=(10, 6))
    colors = ['firebrick' if v > 5 else 'seagreen' if v < 2 else 'goldenrod' for v in rms_vals]
    bars = plt.bar(svs, rms_vals, color=colors, edgecolor='black', alpha=0.8)
    plt.axhline(y=median_val, color='royalblue', linestyle='--', linewidth=1.5, label=f'Median: {median_val:.2f} m')
    
    plt.title(f'{sys_name} -- Per-Satellite 3D RMS ({target_date})', fontsize=14)
    plt.xlabel("Satellite PRN", fontsize=12)
    plt.ylabel("3D RMS Error (m)", fontsize=12)
    plt.xticks(rotation=45)
    plt.grid(axis='y', linestyle='--', alpha=0.7)
    plt.legend()
    plt.tight_layout()

    if save_dir:
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        fname = os.path.join(save_dir, f"rms_{system}_{target_date}.png")
        plt.savefig(fname, dpi=300)
        plt.close()
        return fname
    return plt.gcf()


def plot_all_satellites_overlay(results, target_date, system='G', save_dir=None):
    """Time evolution overlay for all satellites (Matplotlib PNG)."""
    svs = sorted([sv for sv in results if sv.startswith(system)])
    if not svs: return None
    
    sys_name = orbit_utils.SYSTEM_NAMES.get(system, system)
    axes_labels = ['dX (m)', 'dY (m)', 'dZ (m)']
    keys = ['dx', 'dy', 'dz']

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True, constrained_layout=True)
    
    colors = plt.get_cmap('tab20').colors
    
    for i, (ax, key, label) in enumerate(zip(axes, keys, axes_labels)):
        for j, sv in enumerate(svs):
            df = results[sv]
            ax.plot(df['epoch'], df[key], linewidth=0.8, color=colors[j % len(colors)], label=sv if i == 0 else "")
            
        ax.set_ylabel(label, fontsize=11)
        ax.grid(True, linestyle=':', alpha=0.6)
        if i == 0:
            ax.legend(loc='upper right', fontsize=8, ncol=6, frameon=True, framealpha=0.8)
            
    axes[-1].set_xlabel("UTC Time", fontsize=11)
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    fig.suptitle(f'{sys_name} -- All Satellites Orbit Comparison ({target_date})', fontsize=14, fontweight='bold')

    if save_dir:
        Path(save_dir).mkdir(parents=True, exist_ok=True)
        fname = os.path.join(save_dir, f"overlay_{system}_{target_date}.png")
        plt.savefig(fname, dpi=300)
        plt.close()
        return fname
    return fig


def plot_all_coords_compare(results, target_date, system='G', save_dir=None):
    """BRDC vs SP3 coordinate comparison (Matplotlib PNG per satellite)."""
    svs = sorted([sv for sv in results if sv.startswith(system)])
    if not svs: return
    
    fig_dir = os.path.join(save_dir, f"coords_{system}") if save_dir else None
    if fig_dir: Path(fig_dir).mkdir(parents=True, exist_ok=True)

    for sv in svs:
        df = results[sv]
        fig, axes = plt.subplots(3, 1, figsize=(10, 10), sharex=True, constrained_layout=True)
        axes_names = ['x', 'y', 'z']
        labels = ['X (km)', 'Y (km)', 'Z (km)']
        
        for i, (ax, name, label) in enumerate(zip(axes, axes_names, labels)):
            brdc_km = df[f'brdc_{name}'] / 1000.0
            sp3_km = df[f'sp3_{name}'] / 1000.0
            ax.plot(df['epoch'], brdc_km, color='#d62728', linewidth=1.5, label='BRDC')
            ax.plot(df['epoch'], sp3_km, color='#1f77b4', linewidth=1.2, linestyle='--', label='SP3')
            ax.set_ylabel(label, fontsize=11)
            ax.grid(True, linestyle=':', alpha=0.6)
            if i == 0: ax.legend()
            
        axes[-1].set_xlabel("UTC Time", fontsize=11)
        axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        fig.suptitle(f'{sv} -- BRDC vs SP3 Coordinate Comparison ({target_date})', fontsize=13)
        
        if fig_dir:
            plt.savefig(os.path.join(fig_dir, f"coords_{sv}.png"), dpi=300)
        plt.close()


def plot_all_diffs(results, target_date, system='G', save_dir=None):
    """Per-satellite dX, dY, dZ, 3D differences (Matplotlib PNG per satellite)."""
    svs = sorted([sv for sv in results if sv.startswith(system)])
    if not svs: return

    fig_dir = os.path.join(save_dir, f"diffs_{system}") if save_dir else None
    if fig_dir: Path(fig_dir).mkdir(parents=True, exist_ok=True)

    for sv in svs:

        plot_satellite(results[sv], sv, target_date, fig_dir)





def main(out_dir=None, skip_download=None, auth=None):
    dn.print_header("BRDC vs SP3 TIME SERIES ANALYSIS")
    

    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    
    if skip_download is None:
        skip_download = dn.get_yes_no("Do you have pre-downloaded GNSS (Nav + SP3) files? (Yes to SKIP download)", False)
    
    if skip_download:
        if out_dir is None:
            out_dir = dn.get_input("Data directory", data_dir)
    else:

        if auth is None:
            username, password = dn.login_flow()
        else:
            username, password = auth
        if not username: return
        
        date_start, date_end = dn.get_date_range()
        stations = dn.get_stations()
        rinex = dn.get_rinex_version()
        
        dn.print_info("REQUIRED FOR ANALYSIS: Navigation/BRDC and SP3+CLK")
        ftypes = {
            'observation': False,
            'navigation': True,
            'brdc': True,
            'sp3_clk': True,
            'ionosphere': False,
            'sp3_center': 'CODE'
        }
        
        if out_dir is None:
            out_dir = data_dir
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        dn.show_summary(date_start, date_end, stations, rinex, ftypes, out_dir)
        if dn.get_yes_no("\nStart download?", True):
            dn.download_data(date_start, date_end, stations, rinex, ftypes, out_dir, username, password)
            dn.print_success("Download complete!")
        else: return

    if not os.path.exists(out_dir):
        print(f"Directory not found: {out_dir}"); return

    nav_files, sp3_files, clk_files = orbit_utils.discover_files(out_dir)
    if not nav_files: print("Nav file not found!"); return
    if not sp3_files: print("SP3 file not found!"); return

    dates = orbit_utils.get_dates_from_nav_files(nav_files)
    if dates:
        print("\nAvailable dates:")
        for i, d in enumerate(dates, 1): print(f"  {i}. {d}")
        sel = dn.get_input("Select date (index)", "1")
        target_date = dates[int(sel)-1] if sel.isdigit() and 1 <= int(sel) <= len(dates) else dates[0]
    else:
        ds = dn.get_input("Date (YYYY-MM-DD)")
        target_date = datetime.datetime.strptime(ds, "%Y-%m-%d").date()

    filt_sp3 = orbit_utils.filter_sp3_by_date(sp3_files, target_date)
    interval = 30


    print("\n" + "-"*40)
    print(" SATELLITE SELECTION ".center(40, '-'))
    print(" Examples: all | gps | gps2-23-24 | galileo01:10")
    print("           gps,galileo | beidou12-15 | g05,e12,c07")
    sv_expr = dn.get_input("SV filter", "all")
    sv_filter = orbit_utils.parse_sv_filter(sv_expr)
    if sv_filter is None:
        print("       [SV FILTER] No filter applied (all satellites)")
    else:
        systems, svs = sv_filter
        bits = []
        if systems:
            bits.append("systems=" + "+".join(sorted(orbit_utils.SYSTEM_NAMES[s] for s in systems)))
        if svs:
            bits.append(f"explicit={sorted(svs)}")
        print(f"       [SV FILTER] {' | '.join(bits)}")

    results = compute_day_timeseries(nav_files, filt_sp3, clk_files, target_date,
                                     interval, sv_filter=sv_filter)
    if not results: print("No results produced!"); return


    save_dir = os.path.join(out_dir, "data", "figures")
    os.makedirs(save_dir, exist_ok=True)
    

    all_rows = []
    for sv, df in results.items():

        records = df.to_dict('records')
        for rec in records:
            rec['PRN'] = sv

            rec['Epoch'] = rec.pop('epoch').strftime('%Y-%m-%d %H:%M:%S')
            all_rows.append(rec)
    

    df_export = pd.DataFrame(all_rows)
    cols = ['PRN', 'Epoch'] + [c for c in df_export.columns if c not in ['PRN', 'Epoch']]
    df_export = df_export[cols]
    
    excel_name = os.path.join(out_dir, "data", f"timeseries_{target_date}.xlsx")
    df_export.to_excel(excel_name, index=False)
    print(f"\n[SAVE] Excel: {excel_name}")


    print("\n[CHART] Generating publication-quality charts (300 DPI PNG)...")
    for sys_letter in orbit_utils.SYSTEMS:
        sys_name = orbit_utils.SYSTEM_NAMES.get(sys_letter, sys_letter)
        sys_count = len([s for s in results if s.startswith(sys_letter)])
        if sys_count == 0: continue
        print(f"\n  --- {sys_name} ({sys_count} satellites) ---")
        plot_system_rms(results, target_date, sys_letter, save_dir)
        plot_all_satellites_overlay(results, target_date, sys_letter, save_dir)
        plot_all_coords_compare(results, target_date, sys_letter, save_dir)
        plot_all_diffs(results, target_date, sys_letter, save_dir)

    print("\n[DONE] All charts generated.")


if __name__ == "__main__":
    main()
