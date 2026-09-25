"""Backend-independent map validation, coordinates and segmentation."""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from collections.abc import Mapping
import warnings

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class MapStyle:
    """Map appearance. Colours follow the supplied Robinson-map example."""

    ocean_colour: str = "lightgray"
    land_colour: str = "white"
    coastline_colour: str = "black"
    border_colour: str = "0.35"
    missing_colour: str = "white"
    grid_colour: str = "0.65"
    coastline_width: float = 0.65
    border_width: float = 0.5
    grid_width: float = 0.4
    track_width: float = 1.4
    title_size: float = 12.0


def map_style(value=None):
    if value is None:
        return MapStyle()
    if isinstance(value, MapStyle):
        return value
    if isinstance(value, Mapping):
        return replace(MapStyle(), **value)
    raise TypeError("style must be a MapStyle or a mapping of MapStyle fields")


def backend_name(value):
    name = str(value).lower().strip()
    if name not in {"cartopy", "plotly"}:
        raise ValueError("backend must be 'cartopy' or 'plotly'")
    return name


def output_path(value, backend):
    if value is None:
        return None
    path = Path(value).expanduser()
    if not path.suffix:
        path = path.with_suffix(".png" if backend == "cartopy" else ".html")
    allowed = {".png", ".pdf", ".svg", ".jpg", ".jpeg", ".tif", ".tiff", ".eps", ".ps"}
    if backend == "plotly":
        allowed = {".html", ".htm"}
    if path.suffix.lower() not in allowed:
        raise ValueError(
            f"{backend} output must use one of {', '.join(sorted(allowed))}; "
            "choose backend='plotly' for HTML, or backend='cartopy' for static maps"
        )
    return path


def validate_extent(extent):
    if extent is None:
        return None
    box = np.asarray(extent, dtype=float)
    if box.shape != (4,) or not np.isfinite(box).all():
        raise ValueError("extent must be (west, east, south, north) in degrees")
    west, east, south, north = box
    if not (0 < east-west <= 360 and -90 <= south < north <= 90):
        raise ValueError("extent requires west < east (span <= 360), -90 <= south < north <= 90")
    return tuple(float(x) for x in box)


def coordinate_labels(value, extent):
    """Resolve coordinate-label behaviour for a geographic map.

    ``None`` and ``"auto"`` label regional maps (those with an explicit
    extent) while leaving global maps unchanged.
    """
    if value is None or (isinstance(value, str) and value.strip().lower() == "auto"):
        return extent is not None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    raise TypeError("coordinate_labels must be True, False, None or 'auto'")


def positive(value, name):
    value = float(value)
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return value


def _systems(system):
    if system is None or str(system).strip().upper() in {"", "AUTO", "ALL", "M"}:
        return None
    if isinstance(system, str):
        letters = list(system.upper().replace("+", "").replace(",", "").replace(" ", ""))
    else:
        letters = [str(x).upper() for x in system]
    if not letters or any(x not in {"G", "R", "E", "C", "J", "I", "S"} for x in letters):
        raise ValueError("system must contain G, R, E, C, J, I or S; use None for all")
    return tuple(dict.fromkeys(letters))


def _lonlat(xyz, latitude_type):
    """ECEF metres to longitude/latitude; bounded iteration avoids NaN loops."""
    x, y, z = xyz.T
    p = np.hypot(x, y)
    lon = np.degrees(np.arctan2(y, x))
    if latitude_type == "geocentric":
        lat = np.arctan2(z, p)
    else:
        a, b = 6378137.0, 6356752.314245
        e2 = 1.0 - (b/a)**2
        lat = np.arctan2(z, p*(1.0-e2))
        for _ in range(20):
            n = a / np.sqrt(1.0-e2*np.sin(lat)**2)
            new = np.arctan2(z+e2*n*np.sin(lat), p)
            if np.all(np.abs(new-lat) < 1e-13):
                lat = new
                break
            lat = new
        else:
            raise ValueError("ECEF to WGS84 latitude conversion did not converge")
    return lon, np.degrees(lat)


def prepare_tracks(orbit, system="G", sv_list=None, *, position_unit="auto",
                   latitude_type="geodetic", max_gap=None, central_longitude=0.0):
    """Return a dict of native-sampling lon/lat tracks split at seams and gaps.

    Units use DataFrame.attrs['position_unit'] when position_unit='auto', and
    otherwise default to metres for compatibility with sp3_interp output.
    Invalid rows create breaks rather than connecting neighbouring valid rows.
    """
    if not isinstance(orbit, pd.DataFrame):
        raise TypeError("orbit must be a pandas DataFrame")
    if latitude_type not in {"geodetic", "geocentric"}:
        raise ValueError("latitude_type must be 'geodetic' or 'geocentric'")
    centre = float(central_longitude)
    if not np.isfinite(centre):
        raise ValueError("central_longitude must be finite")
    if max_gap is not None:
        max_gap = positive(max_gap, "max_gap")
    units = orbit.attrs.get("position_unit", "m") if position_unit == "auto" else position_unit
    units = str(units).lower()
    if units not in {"m", "km"}:
        raise ValueError("position_unit must be 'auto', 'm' or 'km'")
    if {"SV", "Epoch"}.issubset(orbit.index.names):
        frame = orbit.reset_index()
    elif {"SV", "Epoch"}.issubset(orbit.columns):
        frame = orbit.copy()
    else:
        raise ValueError("orbit needs Epoch and SV index levels or columns")
    frame["SV"] = frame["SV"].astype(str).str.upper()
    frame["Epoch"] = pd.to_datetime(frame["Epoch"], errors="raise")
    if frame["Epoch"].isna().any():
        raise ValueError("orbit contains missing epochs")
    systems = _systems(system)
    if systems is not None:
        frame = frame[frame["SV"].str.startswith(systems)]
    if isinstance(sv_list, str) and sv_list.strip().upper() in {"AUTO", "ALL", ""}:
        sv_list = None
    if sv_list is not None:
        selected = [sv_list] if isinstance(sv_list, str) else list(sv_list)
        selected = [str(s).upper() for s in selected]
        frame = frame[frame["SV"].isin(selected)]
    if frame.empty:
        raise ValueError("No orbit data match the requested system/sv_list")
    columns = {str(c).upper(): c for c in frame.columns}
    if not {"X", "Y", "Z"}.issubset(columns):
        raise ValueError("orbit requires X, Y and Z ECEF coordinate columns")
    frame = frame.sort_values(["SV", "Epoch"])
    if frame.duplicated(["SV", "Epoch"]).any():
        raise ValueError("orbit contains duplicate (SV, Epoch) records")
    result = {}
    for sv, data in frame.groupby("SV", sort=True):
        xyz = data[[columns[c] for c in "XYZ"]].to_numpy(dtype=float)
        xyz = xyz * (1000.0 if units == "km" else 1.0)
        valid = np.isfinite(xyz).all(axis=1) & (np.linalg.norm(xyz, axis=1) > 0)
        if not valid.all():
            warnings.warn(f"{sv}: {int((~valid).sum())} invalid ECEF rows omitted; tracks are broken there",
                          RuntimeWarning, stacklevel=2)
        if not valid.any():
            continue
        if (np.linalg.norm(xyz[valid], axis=1) < 1e6).any():
            raise ValueError("ECEF magnitudes are too small for GNSS orbits; check position_unit='km' for raw SP3 data")
        lon = np.full(len(data), np.nan)
        lat = np.full(len(data), np.nan)
        lon[valid], lat[valid] = _lonlat(xyz[valid], latitude_type)
        times = pd.DatetimeIndex(data["Epoch"])
        dt = np.asarray((times[1:] - times[:-1]).total_seconds())
        cadence = float(np.median(dt[dt > 0])) if np.any(dt > 0) else 0.0
        gap = max_gap if max_gap is not None else max(600.0, 1.5*cadence)
        relative_lon = (lon-centre+180.0) % 360.0 - 180.0
        breaks = (~valid[1:] | ~valid[:-1] | (dt > gap)
                  | (np.abs(np.diff(lon)) > 180.0)
                  | (np.abs(np.diff(relative_lon)) > 180.0))
        bounds = np.r_[0, np.flatnonzero(breaks)+1, len(data)]
        segments = []
        for a, b in zip(bounds[:-1], bounds[1:]):
            if valid[a:b].all():
                segments.append((lon[a:b].copy(), lat[a:b].copy(), times[a:b]))
        first = np.flatnonzero(valid)[0]
        result[sv] = {"segments": segments, "start": (lon[first], lat[first]),
                      "count": int(valid.sum()), "max_gap_seconds": gap}
    if not result:
        raise ValueError("No finite non-zero ECEF positions are available to plot")
    return result


def read_gim(value):
    from gnsspy.io.products.ionex import IonexDataset, read_ionex
    dataset = read_ionex(value) if isinstance(value, (str, Path)) else value
    if not isinstance(dataset, IonexDataset):
        raise TypeError("gim must be an IonexDataset or an IONEX file path, not a raw unscaled array")
    if (np.shape(dataset.tec) != (len(dataset.epochs), len(dataset.latitudes), len(dataset.longitudes))
            or not len(dataset.epochs)):
        raise ValueError("IONEX TEC shape must match (epoch, latitude, longitude)")
    if dataset.epochs.has_duplicates or dataset.epochs.hasnans:
        raise ValueError("IONEX epochs must be unique and non-missing")
    return dataset


def select_epochs(dataset, epochs=None, *, panels=False):
    available = pd.DatetimeIndex(dataset.epochs)
    if epochs is None:
        if panels:
            day = available.min().normalize()
            requested = pd.DatetimeIndex([day+pd.Timedelta(hours=h) for h in range(0, 24, 4)])
        else:
            requested = available[:1]
    else:
        if isinstance(epochs, (str, pd.Timestamp)) or not hasattr(epochs, "__iter__"):
            epochs = [epochs]
        requested = pd.DatetimeIndex(pd.to_datetime(epochs))
    if len(requested) == 0 or requested.hasnans or requested.has_duplicates:
        raise ValueError("Select one or more unique, non-missing epochs")
    if requested.tz is not None:
        requested = requested.tz_convert("UTC").tz_localize(None)
    if available.tz is not None:
        available = available.tz_convert("UTC").tz_localize(None)
    indices = available.get_indexer(requested)
    if (indices < 0).any():
        missing = ", ".join(str(x) for x in requested[indices < 0])
        raise ValueError(f"IONEX epochs not present: {missing}. Select from gim.epochs; plotting does not interpolate in time.")
    return requested, indices


def _edges(centres, *, latitude=False):
    middle = (centres[:-1]+centres[1:])/2.0
    edges = np.r_[centres[0]-(centres[1]-centres[0])/2.0,
                  middle, centres[-1]+(centres[-1]-centres[-2])/2.0]
    return np.clip(edges, -90.0, 90.0) if latitude else edges


def prepare_grid(dataset, indices, field="tec"):
    """Return centres, cell edges and masked TECU maps without interpolation.

    A duplicated global endpoint is removed once. Complete cyclic grids cover
    exactly 360 degrees via their cell edges. Regional grids are never closed.
    """
    if field not in {"tec", "rms"}:
        raise ValueError("field must be 'tec' or 'rms'")
    values = getattr(dataset, field)
    if values is None:
        raise ValueError("This IONEX dataset does not contain RMS maps")
    if np.shape(values) != np.shape(dataset.tec):
        raise ValueError("RMS and TEC shapes must match")
    lat = np.array(dataset.latitudes, dtype=float, copy=True)
    lon = np.array(dataset.longitudes, dtype=float, copy=True)
    if (lat.ndim != 1 or lon.ndim != 1 or min(len(lat), len(lon)) < 2
            or not np.isfinite(lat).all() or not np.isfinite(lon).all()):
        raise ValueError("Map coordinates need at least two finite latitudes and longitudes")
    if (np.abs(lat) > 90).any():
        raise ValueError("Latitudes must be within [-90, 90] degrees")
    maps = np.asarray(np.ma.filled(np.ma.asarray(values, dtype=float), np.nan))[indices].copy()
    for axis, coord in [(1, lat), (2, lon)]:
        diff = np.diff(coord)
        if not (np.all(diff > 0) or np.all(diff < 0)):
            raise ValueError("Map coordinates must be strictly monotonic")
        if not np.allclose(diff, diff[0], atol=1e-7, rtol=1e-7):
            raise ValueError("IONEX plotting requires regularly spaced coordinate axes")
        if diff[0] < 0:
            coord[:] = coord[::-1]
            maps = np.flip(maps, axis=axis)
    span, step = lon[-1]-lon[0], lon[1]-lon[0]
    if span > 360.0+1e-7:
        raise ValueError("Longitude coverage cannot exceed 360 degrees")
    duplicate = np.isclose(span, 360.0, atol=1e-7, rtol=0)
    if duplicate:
        if not np.allclose(maps[..., 0], maps[..., -1], equal_nan=True, atol=1e-6):
            warnings.warn("Duplicate longitude seam differs; keeping the western endpoint without averaging",
                          RuntimeWarning, stacklevel=2)
        lon, maps = lon[:-1], maps[..., :-1]
    global_grid = np.isclose(len(lon)*step, 360.0, atol=1e-6, rtol=0)
    if global_grid:
        normalised = (lon+180.0) % 360.0-180.0
        order = np.argsort(normalised)
        lon, maps = normalised[order], maps[..., order]
    if len(lon) < 2:
        raise ValueError("At least two distinct longitude columns are required")
    return lon, lat, _edges(lon), _edges(lat, latitude=True), np.ma.masked_invalid(maps)


def colour_limits(maps, vmin=None, vmax=None):
    values = np.ma.masked_invalid(maps).compressed()
    if len(values) == 0:
        raise ValueError("The selected maps contain no finite values")
    lo = float(values.min()) if vmin is None else float(vmin)
    hi = float(values.max()) if vmax is None else float(vmax)
    if not np.isfinite([lo, hi]).all():
        raise ValueError("vmin and vmax must be finite")
    if lo == hi and vmin is None and vmax is None:
        pad = max(1.0, abs(lo)*0.01)
        lo, hi = lo-pad, hi+pad
    if lo >= hi:
        raise ValueError("vmin must be less than vmax")
    return lo, hi
