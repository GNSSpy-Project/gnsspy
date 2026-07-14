import os
import datetime
import glob
import re
import warnings
from pathlib import Path

try:
    import georinex as gr
    import pandas as pd
    import openpyxl
except ImportError as exc:
    raise ImportError(
        "This workflow requires optional dependencies. "
        "Install them with: pip install 'gnsspy[workflows]'"
    ) from exc

import numpy as np


from gnsspy.orbit import comparison as orbit_utils




_MAX_DIFF_M = 100.0


from gnsspy.cli import download as dn





def compare_orbits(nav_file_paths, sp3_file_paths, clk_file_paths, target_dt,
                   save_dir=None, sv_filter=None):
    target_gpst_tow = orbit_utils.datetime_to_gps_tow(target_dt)
    target_dt64 = np.datetime64(target_dt)


    print(f"\n[SP3] Processing with gnsspy.orbit.precise (this may take 1-2 minutes)...")
    base_dir = os.path.dirname(nav_file_paths[0])

    try:
        sp3matched = orbit_utils.run_sp3_interp(target_dt.date(), sp3_file_paths, clk_file_paths, base_dir)
    except Exception as e:
        print(f"SP3 Interpolation Error: {e}")
        import traceback; traceback.print_exc()
        return

    if sp3matched.empty:
        print("-> SP3 data could not be produced.")
        return
        
    tgt_ts = pd.Timestamp(target_dt)
    avail_epochs = sp3matched.index.get_level_values('Epoch').unique()
    nearest_epoch = avail_epochs[np.argmin(np.abs(avail_epochs - tgt_ts))]
    dt_sec = (tgt_ts - nearest_epoch).total_seconds()


    print(f"\n[BRDC] Processing navigation files with GeoRINEX ({len(nav_file_paths)} files)...")
    brdc_positions = {}
    
    for f in nav_file_paths:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                nav_data = gr.load(f, use=['G', 'E', 'C'])

            if 'sv' not in nav_data.coords: continue

            for sv in nav_data.sv.values:
                if not isinstance(sv, str) or len(sv) < 3: continue
                sys_type = sv[0]
                if not orbit_utils.sv_matches_filter(sv, sv_filter):
                    continue
                
                sv_data = nav_data.sel(sv=sv)
                if 'Toe' not in sv_data.data_vars: continue
                sv_data = sv_data.dropna(dim='time', subset=['Toe'])
                
                if sv_data.time.size == 0: continue
                
                times = sv_data.time.values
                valid_times = times[times <= target_dt64]
                
                if len(valid_times) == 0:
                    best_time = times[0]
                    if (times[0] - target_dt64).astype('timedelta64[h]').astype(int) > 4: continue
                else:
                    best_time = valid_times[-1]
                    if (target_dt64 - best_time).astype('timedelta64[h]').astype(int) > 4: continue

                eph_record = sv_data.sel(time=best_time)
                try:
                    pos = orbit_utils.compute_keplerian_xyz(eph_record, target_gpst_tow, sys_type)
                    if pos is not None:
                        brdc_positions[sv] = pos
                except Exception:
                    pass
        except Exception as e:
            print(f"  -> Skipped loading error in {os.path.basename(f)}: {e}")

    
    results = []
    print(f"\n  Comparison for epoch {target_dt} (ECEF):")
    print("  (SP3 nearest epoch: {} used with dV={}s extrapolation)".format(nearest_epoch, dt_sec))
    print("  " + "-" * 105)
    print(f"  {'PRN':<4} | {'GeoRINEX BRDC X,Y,Z (km)':<28} | {'SP3 Interp X,Y,Z (km)':<28} | {'Diff dX,dY,dZ (m)':<25} | {'3D Error':<8}")
    print("  " + "-" * 105)

    sp3_satellites = sp3matched.index.get_level_values('SV').unique()
    all_prns = sorted(set(brdc_positions.keys()) | set(sp3_satellites))
    if sv_filter is not None:
        before = len(all_prns)
        all_prns = [p for p in all_prns if orbit_utils.sv_matches_filter(p, sv_filter)]
        print(f"  [SV FILTER] {before} -> {len(all_prns)} satellites after filter.")
    
    for prn in all_prns:
        brdc_pos = brdc_positions.get(prn)
        try:
            row = sp3matched.loc[(nearest_epoch, prn)]
            sp3_pos = [row['X'] + row['Vx']*dt_sec, 
                       row['Y'] + row['Vy']*dt_sec, 
                       row['Z'] + row['Vz']*dt_sec]
        except KeyError:
            sp3_pos = None

        if brdc_pos is not None and sp3_pos is not None and not np.isnan(sp3_pos[0]):
            dx = brdc_pos[0] - sp3_pos[0]
            dy = brdc_pos[1] - sp3_pos[1]
            dz = brdc_pos[2] - sp3_pos[2]
            dist = (dx**2 + dy**2 + dz**2)**0.5


            if (not np.isfinite(dist) or dist > _MAX_DIFF_M
                    or abs(dx) > _MAX_DIFF_M or abs(dy) > _MAX_DIFF_M
                    or abs(dz) > _MAX_DIFF_M):
                print(f"  {prn:<4} | [SKIPPED outlier: 3D={dist:.1f} m > {_MAX_DIFF_M:.0f} m]")
                continue

            print(f"  {prn:<4} | {brdc_pos[0]/1000:8.1f} {brdc_pos[1]/1000:8.1f} {brdc_pos[2]/1000:8.1f} | {sp3_pos[0]/1000:8.1f} {sp3_pos[1]/1000:8.1f} {sp3_pos[2]/1000:8.1f} | {dx:7.2f} {dy:7.2f} {dz:7.2f} | {dist:7.2f} m")
            
            results.append({
                'PRN': prn,
                'BRDC_X (m)': brdc_pos[0],
                'BRDC_Y (m)': brdc_pos[1],
                'BRDC_Z (m)': brdc_pos[2],
                'SP3_X (m)': sp3_pos[0],
                'SP3_Y (m)': sp3_pos[1],
                'SP3_Z (m)': sp3_pos[2],
                'Diff_X (m)': dx,
                'Diff_Y (m)': dy,
                'Diff_Z (m)': dz,
                '3D_Error (m)': dist
            })

    if results:
        df = pd.DataFrame(results)

        base_output = save_dir if save_dir else os.path.dirname(nav_file_paths[0])
        excel_name = os.path.join(base_output, f"georinex_portable_{target_dt.strftime('%Y%m%d_%H%M%S')}.xlsx")
        
        df.to_excel(excel_name, index=False)
        print("  " + "-" * 105)
        print(f"  [SUCCESS] Results saved to Excel!\n  File: {excel_name}")
    else:
        print("  " + "-" * 105)
        print("  -> No common satellites found (active in both SP3 and BRDC simultaneously).")


def integrated_main(out_dir=None, skip_download=None, auth=None):
    dn.print_header("GNSS DOWNLOADER & ORBIT CALCULATOR")
    

    gnsspy.workflows_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(gnsspy.workflows_dir, "output")
    

    if skip_download is None:
        skip_download = dn.get_yes_no("Do you have pre-downloaded GNSS (Nav + SP3) files? (Yes to SKIP download)", False)
    
    if skip_download:
        if out_dir is None:
            out_dir = dn.get_input("Directory containing data files", output_dir)
    else:

        if auth is None:
            username, password = dn.login_flow()
        else:
            username, password = auth
            
        if not username: return
        date_start, date_end = dn.get_date_range()
        stations = dn.get_stations()
        rinex = dn.get_rinex_version()
        

        print("\n" + "-"*40)
        print(" ANALYSIS CENTER SELECTION ".center(40, '-'))
        print(" Recommended: CODE (GPS/GLO/GAL), WUM (Multi/BDS), GFZ")
        sp3_center = dn.get_input("Select Center", "CODE").upper()
        if sp3_center == 'COD': sp3_center = 'CODE'
        print(f"   [i] Selected Center: {sp3_center}")

        ftypes = {
            'observation': False,
            'navigation': True,
            'brdc': True,
            'sp3_clk': True,
            'ionosphere': False,
            'sp3_center': sp3_center
        }
            

        out_dir = output_dir
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        dn.show_summary(date_start, date_end, stations, rinex, ftypes, out_dir)
        if dn.get_yes_no("\nStart download?", True):
            dn.download_data(date_start, date_end, stations, rinex, ftypes, out_dir, username, password)
            dn.print_success("Download complete!")
        else: return

    dn.print_header("ORBIT COMPARISON ")
    if not os.path.exists(out_dir): return

    valid_nav_files, valid_sp3_files, valid_clk_files = orbit_utils.discover_files(out_dir)

    if not valid_nav_files: dn.print_error("BRDC/Navigation file not found."); return
    if not valid_sp3_files: dn.print_error("SP3 file not found."); return
    
    available_dates = orbit_utils.get_dates_from_nav_files(valid_nav_files)
    if not available_dates:
        target_time_str = dn.get_input("Time (UTC) (YYYY-MM-DD HH:MM:SS)")
        target_dt = datetime.datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
    else:
        print("\nBroadcast data found for these dates:")
        for idx, d in enumerate(available_dates, 1): print(f"  {idx}. {d.strftime('%Y-%m-%d')}")
            
        while True:
            sel_str = dn.get_input("Select DATE (index or date string)", "1")
            if sel_str.isdigit() and 1 <= int(sel_str) <= len(available_dates):
                selected_date = available_dates[int(sel_str)-1]; break
            else:
                try:
                    parsed_date = datetime.datetime.strptime(sel_str, "%Y-%m-%d").date()
                    if parsed_date in available_dates: selected_date = parsed_date; break
                except ValueError: pass
        
        while True:
            time_str = dn.get_input(f"Select TIME for {selected_date.strftime('%Y-%m-%d')} (HH:MM:SS)", "12:00:00")
            try:
                target_dt = datetime.datetime.strptime(f"{selected_date.strftime('%Y-%m-%d')} {time_str}", "%Y-%m-%d %H:%M:%S"); break
            except ValueError: pass

    filtered_sp3_files = orbit_utils.filter_sp3_by_date(valid_sp3_files, target_dt.date())


    print("\n" + "-"*40)
    print(" SATELLITE SELECTION ".center(40, '-'))
    print(" Examples: all | gps | gps2-23-24 | galileo01:10 | beidou12-15")
    sv_expr = dn.get_input("SV filter", "all")
    sv_filter = orbit_utils.parse_sv_filter(sv_expr)


    results_dir = os.path.join(out_dir, "data")
    os.makedirs(results_dir, exist_ok=True)

    print(f"\n[INFO] Starting Portable Orbit Calculation (Results: {results_dir})...")
    compare_orbits(valid_nav_files, filtered_sp3_files, valid_clk_files, target_dt,
                   save_dir=results_dir, sv_filter=sv_filter)

if __name__ == "__main__":
    integrated_main()
