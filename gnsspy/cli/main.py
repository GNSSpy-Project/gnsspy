#!/usr/bin/env python3
"""Central command-line interface for GNSSpy v3."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from gnsspy.cli import download as downloader


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def show_menu():
    downloader.print_header("GNSSPY - CENTRAL MANAGEMENT INTERFACE")
    print("  1. Download GNSS Data")
    print("  2. Visualize GNSS Data (Skyplots, SNR, Groundtrack)")
    print("  3. Orbit Comparison (Single Epoch)")
    print("  4. Orbit Comparison (Full Day Time Series)")
    print("  5. RINEX Converter (2 <-> 3)")
    print("  6. Exit")
    print("-" * 50)


def handle_data_selection():
    """Ask whether data are already available or should be downloaded."""
    print("\n" + "-" * 40)
    print(" DATA SOURCE SELECTION ".center(40, "-"))

    has_data = downloader.get_yes_no("Do you have pre-downloaded GNSS data?", True)

    if has_data:
        default_dir = str(PROJECT_ROOT / "output")
        out_dir = downloader.get_input("Directory containing your data files", default_dir)
        return out_dir, True, None

    print("\n[LOGIN] NASA Earthdata credentials required for download...")
    username, password = downloader.login_flow()
    if not username:
        return None, None, None
    return None, False, (username, password)


def run_tool(choice):
    try:
        if choice == "1":
            print("\n[LAUNCH] Starting Downloader Tool...")
            importlib.reload(downloader)
            downloader.main()
            return True

        if choice == "5":
            print("")
            print("[LAUNCH] Starting RINEX Converter...")
            from gnsspy.cli import convert_rinex
            importlib.reload(convert_rinex)
            convert_rinex.main()
            return True

        out_dir, skip_download, auth = handle_data_selection()
        if skip_download is None and auth is None:
            return True

        if choice == "2":
            print("\n[LAUNCH] Starting Visualization Tool...")
            from gnsspy.cli import visualize
            importlib.reload(visualize)
            visualize.main(output_dir=out_dir, skip_download=skip_download, auth=auth)

        elif choice == "3":
            print("\n[LAUNCH] Starting Single Epoch Orbit Comparison...")
            orbit_utils = importlib.import_module("gnsspy.orbit.comparison")
            orbit_compare_single = importlib.import_module("gnsspy.workflows.orbit_compare_single")
            importlib.reload(orbit_utils)
            importlib.reload(orbit_compare_single)
            orbit_compare_single.integrated_main(
                out_dir=out_dir,
                skip_download=skip_download,
                auth=auth,
            )

        elif choice == "4":
            print("\n[LAUNCH] Starting Full Day Time Series Orbit Comparison...")
            orbit_utils = importlib.import_module("gnsspy.orbit.comparison")
            brdc_sp3_timeseries = importlib.import_module("gnsspy.workflows.brdc_sp3_timeseries")
            importlib.reload(orbit_utils)
            importlib.reload(brdc_sp3_timeseries)
            brdc_sp3_timeseries.main(
                out_dir=out_dir,
                skip_download=skip_download,
                auth=auth,
            )

        elif choice == "6":
            downloader.print_success("Exiting GNSSPY CLI. Goodbye!")
            return False

        else:
            downloader.print_error("Invalid selection!")

    except Exception as exc:
        downloader.print_error(f"Fatal error while running tool: {exc}")
        import traceback
        traceback.print_exc()

    return True


def main():
    try:
        running = True
        while running:
            show_menu()
            choice = input(
                f"{downloader.Colors.BOLD}Select an option (1-6): {downloader.Colors.ENDC}"
            ).strip()

            if not choice:
                continue

            if choice == "6":
                running = False
                downloader.print_success("Exiting GNSSPY CLI. Goodbye!")
                break

            running = run_tool(choice)

            if running:
                input(f"\n{downloader.Colors.CYAN}Press Enter to return to main menu...{downloader.Colors.ENDC}")
                os.system("cls" if os.name == "nt" else "clear")

    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)


if __name__ == "__main__":
    main()
