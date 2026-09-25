"""Deterministic plotting fixtures, not measured GNSS data or validation orbits."""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from gnsspy.geodesy.coordinate import ell2cart
from gnsspy.io.products.ionex import IonexDataset


def make_demo_data():
    """Return (ECEF metre DataFrame, TECU IonexDataset, synthetic station)."""
    start = pd.Timestamp("2024-01-14")
    seconds = np.arange(0, 86400, 300.0)
    epochs = start + pd.to_timedelta(seconds, unit="s")
    rows = []
    system_names = {"G": "GPS", "E": "GALILEO", "C": "COMPASS"}
    for k, sv in enumerate(["G01", "G03", "G12", "E11", "E24", "C19", "C21"]):
        radius = 26_560_000.0 if sv[0] == "G" else 29_600_000.0
        period = 43_200.0 if sv[0] == "G" else 50_400.0
        angle = 2*np.pi*seconds/period + k*0.73
        node = k*0.91 - 2*np.pi*seconds/86164.0
        inclination = np.deg2rad(55 if sv[0] == "G" else 56)
        x = radius*(np.cos(node)*np.cos(angle)-np.sin(node)*np.sin(angle)*np.cos(inclination))
        y = radius*(np.sin(node)*np.cos(angle)+np.cos(node)*np.sin(angle)*np.cos(inclination))
        z = radius*np.sin(angle)*np.sin(inclination)
        vx, vy, vz = [np.gradient(c, seconds) for c in (x, y, z)]
        for i, epoch in enumerate(epochs):
            if sv == "G03" and 80 <= i < 100:
                continue
            xyz = (np.nan, np.nan, np.nan) if sv == "E11" and i == 140 else (x[i], y[i], z[i])
            rows.append((epoch, sv, *xyz, vx[i], vy[i], vz[i]))
    orbit = pd.DataFrame(rows, columns=["Epoch", "SV", "X", "Y", "Z", "Vx", "Vy", "Vz"])
    orbit = orbit.set_index(["Epoch", "SV"]).sort_index()
    orbit.attrs.update(position_unit="m", time_system="GPS", synthetic=True)

    site = np.asarray(ell2cart(40.0, 30.0, 100.0, ellipsoid="WGS84"))
    up = site / np.linalg.norm(site)
    obs_rows = []
    for (epoch, sv), row in orbit.iterrows():
        d = row[["X", "Y", "Z"]].to_numpy()-site
        if not np.isfinite(d).all():
            continue
        el = np.degrees(np.arcsin(np.dot(d, up)/np.linalg.norm(d)))
        if el <= 0:
            continue
        t = (epoch-start).total_seconds()/3600.0
        snr = 27+20*np.sin(np.deg2rad(el))+1.2*np.sin(3*t+int(sv[1:]))
        obs_rows.append((epoch, sv, system_names[sv[0]], snr))
    obs = pd.DataFrame(obs_rows, columns=["Epoch", "SV", "SYSTEM", "S1C"])
    obs = obs.set_index(["Epoch", "SV"]).sort_index()
    obs.attrs.update(time_system="GPS", synthetic=True)
    station = SimpleNamespace(observation=obs, approx_position=site,
                              filename="SYNTHETIC_DEMO", epoch=start.to_pydatetime(),
                              interval=300.0, version="3.04")

    latitudes = np.arange(87.5, -90.0, -2.5)
    longitudes = np.arange(-180.0, 181.0, 5.0)
    xx, yy = np.meshgrid(longitudes, latitudes)
    map_epochs = pd.date_range(start, periods=13, freq="2h")
    maps = []
    for epoch in map_epochs:
        h = (epoch-start).total_seconds()/3600
        daylight = np.clip(np.cos(np.deg2rad(xx+15*h-180)), 0, None)
        belts = (np.exp(-((yy-15)/18)**2)+np.exp(-((yy+15)/18)**2))/1.25
        tec = 3 + 40*belts*(0.2+0.8*daylight) + 3*np.cos(np.deg2rad(yy))**2
        tec[(xx > 55) & (xx < 85) & (yy > 45) & (yy < 65)] = np.nan
        maps.append(np.round(tec, 1))
    tec = np.asarray(maps)
    rms = np.round(0.4+0.02*tec, 1)
    gim = IonexDataset(epochs=map_epochs, latitudes=latitudes,
                       longitudes=longitudes, tec=tec, raw_tec=tec*10,
                       source=Path("SYNTHETIC_GIM.INX"), height_km=450.0, rms=rms,
                       metadata={"synthetic": True, "exponent": -1})
    return orbit, gim, station


def write_sample_files(directory, orbit, gim):
    """Write native SP3/IONEX files for exercising the actual package readers."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    sp3 = directory / "SYNTHETIC_ORBIT.SP3"
    ionex = directory / "SYNTHETIC_GIM.INX"
    first_epoch = orbit.index.get_level_values("Epoch").min()
    nepoch = orbit.index.get_level_values("Epoch").nunique()
    first = (f'#dP{first_epoch.year:4d} {first_epoch.month:2d} {first_epoch.day:2d} '
             f'{first_epoch.hour:2d} {first_epoch.minute:2d} {first_epoch.second:11.8f} ')
    first = first[:32].ljust(32)+f'{nepoch:7d} SYNTH IGS20 FIT TEST\n'
    text = first+'## 2297 0.00000000   300.00000000 60323 0.0000000000000\n'
    text += '%c M  cc GPS ccc cccc cccc cccc cccc ccccc ccccc ccccc ccccc\n'
    text += '/* SYNTHETIC plotting example. Not measured or predicted GNSS ephemerides.\n'
    for epoch, group in orbit.groupby(level="Epoch", sort=True):
        text += f'*  {epoch:%Y %m %d %H %M} {epoch.second:11.8f}\n'
        for (_, sv), row in group.iterrows():
            xyz = row[["X", "Y", "Z"]].to_numpy(dtype=float)/1000
            if not np.isfinite(xyz).all():
                xyz[:] = 0.0
            text += 'P'+sv+''.join(f'{v:14.6f}' for v in [*xyz, 0.0])+'\n'
    sp3.write_text(text+'EOF\n', encoding="ascii")

    def rec(body, label):
        return str(body).ljust(60)+label+'\n'
    def stamp(epoch):
        return ''.join(f'{v:6d}' for v in (epoch.year, epoch.month, epoch.day,
                                          epoch.hour, epoch.minute, epoch.second))
    def axis(coord):
        return '  '+''.join(f'{v:6.1f}' for v in [coord[0], coord[-1], coord[1]-coord[0]])
    text = rec('     1.0            IONOSPHERE MAPS     GNSS', 'IONEX VERSION / TYPE')
    text += rec('SYNTHETIC plotting example, not measured TEC.', 'COMMENT')
    text += rec(stamp(gim.epochs[0]), 'EPOCH OF FIRST MAP')
    text += rec(stamp(gim.epochs[-1]), 'EPOCH OF LAST MAP')
    text += rec('  7200', 'INTERVAL')+rec(f'{len(gim.epochs):6d}', '# OF MAPS IN FILE')
    text += rec('     2', 'MAP DIMENSION')+rec('  6371.0', 'BASE RADIUS')
    text += rec('   450.0 450.0   0.0', 'HGT1 / HGT2 / DHGT')
    text += rec(axis(gim.latitudes), 'LAT1 / LAT2 / DLAT')
    text += rec(axis(gim.longitudes), 'LON1 / LON2 / DLON')
    text += rec('    -1', 'EXPONENT')+rec('', 'END OF HEADER')
    for kind, values in [('TEC', gim.tec), ('RMS', gim.rms)]:
        raw = np.where(np.isfinite(values), np.rint(values*10), 9999).astype(int)
        for k, epoch in enumerate(gim.epochs):
            text += rec(f'{k+1:6d}', f'START OF {kind} MAP')
            text += rec(stamp(epoch), 'EPOCH OF CURRENT MAP')
            for a, latitude in enumerate(gim.latitudes):
                row = '  '+''.join(f'{v:6.1f}' for v in [latitude, gim.longitudes[0],
                                  gim.longitudes[-1], gim.longitudes[1]-gim.longitudes[0], 450.0])
                text += rec(row, 'LAT/LON1/LON2/DLON/H')
                for b in range(0, len(gim.longitudes), 16):
                    text += ''.join(f'{v:5d}' for v in raw[k, a, b:b+16])+'\n'
            text += rec(f'{k+1:6d}', f'END OF {kind} MAP')
    ionex.write_text(text+rec('', 'END OF FILE'), encoding="ascii")
    return sp3, ionex
