"""RINEX CLK satellite-clock reader, with local-only path resolution."""
from datetime import datetime, timedelta
import time
import warnings

import pandas as pd

from gnsspy.utils.product_files import open_product_text, resolve_product_path


def read_clockFile(clkFile, *, data_dir=None, verbose=True, missing='empty'):
    """Read satellite AS records from a RINEX clock file.

    Return an SV-indexed DataFrame with Epoch and DeltaTSV columns. Clock biases
    are in seconds. missing='empty' returns an empty frame for an absent file;
    missing='raise' requires the file. Malformed files raise an error.
    """
    if missing not in {'empty','raise'}:
        raise ValueError("missing must be 'empty' or 'raise'")
    try:
        path = resolve_product_path(clkFile,'clk',data_dir)
    except FileNotFoundError:
        if missing == 'raise':
            raise
        warnings.warn(f"CLK file not found ({clkFile}); clock corrections are unavailable.",
                      RuntimeWarning,stacklevel=2)
        empty = pd.DataFrame({'Epoch':pd.Series(dtype='datetime64[ns]'),
                              'DeltaTSV':pd.Series(dtype=float)})
        empty.index.name = 'SV'
        return empty
    started = time.monotonic()
    rows = []
    time_system = None
    with open_product_text(path) as stream:
        first = stream.readline()
        if 'RINEX VERSION / TYPE' not in first or 'C' not in first[:40]:
            raise ValueError(f"{path}:1: not a RINEX CLK file")
        for line_number,line in enumerate(stream,2):
            if 'TIME SYSTEM ID' in line:
                time_system = line.split()[0].upper()
            if not line.startswith('AS '):
                continue
            try:
                parts = line.split()
                count = int(parts[8])
                if count < 1:
                    raise ValueError('AS record has no clock bias')
                epoch = datetime(*map(int,parts[2:7])) + timedelta(seconds=float(parts[7]))
                bias = float(parts[9].replace('D','E').replace('d','e'))
                rows.append((parts[1],epoch,bias))
            except (ValueError,IndexError,OverflowError) as exc:
                raise ValueError(f"{path}:{line_number}: invalid CLK AS record: {exc}") from exc
    if not rows:
        raise ValueError(f"{path}: no satellite clock (AS) records found")
    frame = pd.DataFrame(rows,columns=['SV','Epoch','DeltaTSV'])
    duplicates = frame[frame.duplicated(['SV','Epoch'],keep=False)]
    if not duplicates.empty and (duplicates.groupby(['SV','Epoch']).DeltaTSV.nunique(dropna=False) > 1).any():
        raise ValueError(f"{path}: conflicting duplicate satellite clock records")
    frame = frame.drop_duplicates(['SV','Epoch']).set_index('SV')
    frame.attrs.update(source_path=str(path),clock_unit='seconds',time_system=time_system)
    if verbose:
        print(f"{path} file is read in {time.monotonic()-started:.2f} seconds")
    return frame


read_clock_file = read_clockFile
__all__ = ['read_clockFile','read_clock_file']
