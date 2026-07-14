


"""RINEX file manipulation utilities."""


import os
import sys
import shutil
import subprocess
from pathlib import Path

try:
    from importlib import resources as _resources
except Exception:
    _resources = None


__all__ = ["rinex_merge", "crx2rnx", "standardize_snr"]


def rinex_merge(station, doy, year, directory=os.getcwd()):
    """
    Merge split RINEX observation files into one daily RINEX 2 observation file.

    Parameters
    ----------
    station : str
        Four-character station identifier.
    doy : int or str
        Day of year.
    year : int
        Four-digit year.
    directory : str, default current working directory
        Directory containing the split RINEX files.
    """
    rinexObsFiles = []
    file_start = station + str(doy)
    file_end = "." + str(year)[2:] + "o"
    file_fullName = file_start + "0" + file_end
    for file in os.listdir(directory):
        if file.startswith(file_start) and file.endswith(file_end):
            rinexObsFiles.append(os.path.join(directory, file))

    if not rinexObsFiles:
        raise FileNotFoundError(f"No RINEX files matching {file_start}*{file_end} in {directory}")

    if os.path.join(directory, file_fullName) in rinexObsFiles:
        print("The file", file_fullName, "exists in the working directory!")
        while True:
            choice = input("Would you like to overwrite the file [Y/N]? | ")
            if choice.upper() in ("Y", "YES"):
                rinexObsFiles.remove(os.path.join(directory, file_fullName))
                break
            if choice.upper() in ("N", "NO"):
                sys.exit("Exiting...")
            print("Invalid choice | [Y/N]")

    with open(os.path.join(directory, file_fullName), 'w') as rinexMerged:
        with open(rinexObsFiles[0]) as rinexTemp:
            for line in rinexTemp:
                if "TIME OF LAST OBS" not in line:
                    rinexMerged.write(line)

    with open(os.path.join(directory, file_fullName), 'a') as rinexMerged:
        for rinex in range(1, len(rinexObsFiles)):
            with open(rinexObsFiles[rinex]) as rinexTemp:
                header = True
                for line in rinexTemp:
                    if header:
                        if "END OF HEADER" not in line:
                            continue
                        header = False
                    else:
                        rinexMerged.write(line)


def _candidate_crx2rnx_names():
    if sys.platform == "win32":
        return ("crx2rnx.exe", "CRX2RNX.exe")
    return ("CRX2RNX", "crx2rnx")


def _find_crx2rnx_executable():
    """Find CRX2RNX from PATH, package data or source-tree fallback."""

    for name in _candidate_crx2rnx_names():
        found = shutil.which(name)
        if found:
            return found




    if sys.platform == "darwin":
        return None

    if _resources is not None:
        for name in _candidate_crx2rnx_names():
            try:
                res = _resources.files("gnsspy").joinpath("bin", name)
                if res.is_file():
                    with _resources.as_file(res) as path:
                        return str(path)
            except Exception:
                pass


    here = Path(__file__).resolve()
    candidates = []
    for parent in here.parents:
        for name in _candidate_crx2rnx_names():
            candidates.append(parent / "bin" / name)
            candidates.append(parent / "gnsspy" / "bin" / name)
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return str(candidate)
    return None


def crx2rnx(rinexFile, output_dir=None, check=True):
    """Convert a Hatanaka-compressed observation file to RINEX.

    GNSSpy first searches for ``CRX2RNX`` on the system ``PATH``. If it is not
    available, it tries the optional bundled executable under ``gnsspy/bin`` and
    then the source-tree ``bin`` directory.

    Parameters
    ----------
    rinexFile : str or path-like
        Input ``.crx``/``.d`` Hatanaka file.
    output_dir : str or path-like, optional
        Directory in which the converter should be executed. If omitted, the
        input file directory is used.
    check : bool, default True
        If True, raise an exception when the converter returns a non-zero exit
        status.

    Returns
    -------
    subprocess.CompletedProcess
        Result of the CRX2RNX command.
    """
    rinex_path = Path(rinexFile).expanduser().resolve()
    if not rinex_path.exists():
        raise FileNotFoundError(f"Hatanaka file not found: {rinex_path}")

    exe_path = _find_crx2rnx_executable()
    if exe_path is None:
        raise FileNotFoundError(
            "CRX2RNX executable was not found. Install it and make sure it is "
            "available on PATH, or place CRX2RNX/crx2rnx.exe under gnsspy/bin."
        )

    exe = Path(exe_path)
    if sys.platform != "win32":
        try:
            exe.chmod(exe.stat().st_mode | 0o111)
        except OSError:
            pass

    cwd = Path(output_dir).expanduser().resolve() if output_dir else rinex_path.parent
    result = subprocess.run([str(exe), str(rinex_path)], cwd=str(cwd), check=check)
    return result





def standardize_snr(station_data, system='G'):
    """
    Map available system-specific SNR columns to GNSSpy's standard SNR aliases.

    Different satellite systems can store signal strength with different RINEX
    observation codes (for example ``S2I`` for some BeiDou observations). This
    function creates the aliases ``S1C`` and ``S1`` where possible so older
    GNSSpy functions can operate on multi-GNSS datasets.
    """
    if station_data is None or not hasattr(station_data, 'observation'):
        return station_data

    obs_df = station_data.observation
    if obs_df.empty:
        return station_data

    existing_cols = list(obs_df.columns)
    snr_cols = [c for c in existing_cols if c.startswith('S')]
    if not snr_cols:
        return station_data

    target_snr = None
    if system == 'C':
        priority_list = ['S2I', 'S1I', 'S2X', 'S7I', 'S6I', 'S1C']
    elif system == 'E':
        priority_list = ['S1C', 'S1X', 'S5Q', 'S7Q', 'S8Q']
    elif system == 'R':
        priority_list = ['S1C', 'S1P', 'S2C', 'S2P']
    else:
        priority_list = ['S1C', 'S1', *snr_cols]

    for p in priority_list:
        if p in snr_cols:
            target_snr = p
            break

    if not target_snr and snr_cols:
        target_snr = snr_cols[0]

    if target_snr:
        if 'S1C' not in existing_cols:
            station_data.observation['S1C'] = station_data.observation[target_snr]
        if 'S1' not in existing_cols:
            station_data.observation['S1'] = station_data.observation[target_snr]

    return station_data
