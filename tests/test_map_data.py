"""Numerical/map preparation tests: no rendering libraries or network needed."""
from dataclasses import replace
from pathlib import Path
import importlib
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from gnsspy.io.products.ionex import IonexDataset
from gnsspy.visualization._maps import (
    MapStyle, map_style, backend_name, output_path, validate_extent, positive,
    prepare_tracks, read_gim, select_epochs, prepare_grid, colour_limits,
    coordinate_labels, _lonlat,
)
from gnsspy.visualization import groundtrack, ionosphere_map, ionosphere_maps


def orbit_at(longitudes, latitudes=None, seconds=None):
    lon=np.radians(longitudes)
    lat=np.radians(np.zeros(len(lon)) if latitudes is None else latitudes)
    times=pd.Timestamp('2024-01-14')+pd.to_timedelta(
        np.arange(len(lon))*300 if seconds is None else seconds, unit='s')
    radius=26_560_000.
    frame=pd.DataFrame(dict(Epoch=times, SV='G01',
        X=radius*np.cos(lat)*np.cos(lon), Y=radius*np.cos(lat)*np.sin(lon),
        Z=radius*np.sin(lat))).set_index(['Epoch','SV'])
    frame.attrs['position_unit']='m'
    return frame


def tiny_gim(lon=None, lat=None):
    lon=np.asarray([-180,-90,0,90,180] if lon is None else lon, dtype=float)
    lat=np.asarray([60,0,-60] if lat is None else lat, dtype=float)
    epochs=pd.date_range('2024-01-14', periods=13, freq='2h')
    values=15+np.cos(np.radians(lon))[None,None,:]+np.sin(np.radians(lat))[None,:,None]
    values=values+np.arange(13)[:,None,None]
    return IonexDataset(epochs,lat,lon,values,values*10,Path('SYNTHETIC'),450.,rms=values/10)


@pytest.mark.parametrize('input,expected',[('cartopy','cartopy'),(' PLOTLY ','plotly')])
def test_backend_names(input,expected):
    assert backend_name(input)==expected


@pytest.mark.parametrize('input',['matplotlib','auto','',None])
def test_invalid_backend(input):
    with pytest.raises(ValueError): backend_name(input)


@pytest.mark.parametrize('backend,suffix',[('cartopy','.png'),('plotly','.html')])
def test_default_extension(backend,suffix):
    assert output_path('x',backend)==Path('x'+suffix)
    assert output_path(None,backend) is None


@pytest.mark.parametrize('backend,path',[('cartopy','x.html'),('plotly','x.png'),('plotly','x.pdf')])
def test_output_extension_errors(backend,path):
    with pytest.raises(ValueError): output_path(path,backend)


def test_style_defaults_and_override():
    assert map_style()==MapStyle()
    assert map_style({'ocean_colour':'lightblue'}).ocean_colour=='lightblue'
    assert map_style().ocean_colour=='lightgray'
    with pytest.raises(TypeError): map_style({'misspelled':True})


@pytest.mark.parametrize('box',[(1,0,-10,10),(0,361,-10,10),(0,20,-100,10),(0,20,0,0),(0,20,np.nan,20),(1,2,3)])
def test_invalid_extent(box):
    with pytest.raises(ValueError): validate_extent(box)


def test_regional_coordinate_label_policy():
    assert coordinate_labels(None, (20, 45, 30, 50)) is True
    assert coordinate_labels('auto', None) is False
    assert coordinate_labels(True, None) is True
    assert coordinate_labels(False, (20, 45, 30, 50)) is False
    with pytest.raises(TypeError, match='coordinate_labels'):
        coordinate_labels('sometimes', (20, 45, 30, 50))


@pytest.mark.parametrize('value',[0,-1,np.nan,np.inf])
def test_invalid_positive(value):
    with pytest.raises(ValueError): positive(value,'dpi')


def test_tracks_units_geodetic_and_immutable():
    metres=orbit_at([10,11,12],[30,31,32]); before=metres.copy(deep=True)
    km=metres/1000; km.attrs['position_unit']='km'
    a,b=prepare_tracks(metres)['G01'],prepare_tracks(km)['G01']
    np.testing.assert_allclose(a['segments'][0][0],b['segments'][0][0])
    np.testing.assert_allclose(a['segments'][0][1],b['segments'][0][1])
    pd.testing.assert_frame_equal(metres,before)
    km.attrs.clear()
    with pytest.raises(ValueError,match='position_unit'): prepare_tracks(km)
    c=prepare_tracks(km,position_unit='km')['G01']
    np.testing.assert_allclose(c['segments'][0][1],a['segments'][0][1])


def test_geodetic_latitude_against_ellipsoid_forward():
    from gnsspy.geodesy.coordinate import ell2cart
    xyz=np.array([ell2cart(lat,lon,20_200_000.) for lat,lon in [(0,0),(45,30),(-65,-170),(90,15)]])
    lon,lat=_lonlat(xyz,'geodetic')
    np.testing.assert_allclose(lat,[0,45,-65,90],atol=1e-10)
    np.testing.assert_allclose(lon[:3],[0,30,-170],atol=1e-10)
    geocentric=_lonlat(xyz,'geocentric')[1]
    assert not np.isclose(lat[1],geocentric[1],atol=1e-3)


@pytest.mark.parametrize('centre,lons,expected',[(0,[178,179,-179,-178],2),(180,[-2,-1,1,2],2),(0,[10,11,12],1)])
def test_seams(centre,lons,expected):
    track=prepare_tracks(orbit_at(lons),central_longitude=centre)['G01']
    assert len(track['segments'])==expected
    assert sum(len(s[0]) for s in track['segments'])==len(lons)
    for segment in track['segments']: assert np.all(np.abs(np.diff(segment[0]))<=180)


def test_time_gap_and_invalid_rows_break_not_bridge():
    frame=orbit_at([0,1,2,3,4,5],seconds=[0,300,600,900,3000,3300])
    frame.iloc[2,:]=np.nan
    with pytest.warns(RuntimeWarning,match='invalid ECEF'):
        result=prepare_tracks(frame)['G01']
    assert [len(s[0]) for s in result['segments']]==[2,1,2]
    assert result['count']==5
    assert result['start']==(0,0)


def test_all_invalid():
    frame=orbit_at([0,1]);frame.iloc[:,:]=0
    with pytest.warns(RuntimeWarning),pytest.raises(ValueError,match='No finite'):
        prepare_tracks(frame)


@pytest.mark.parametrize('options',[{'system':'GPS'},{'system':'E'},{'sv_list':[]},{'latitude_type':'wrong'},
                                   {'position_unit':'feet'},{'max_gap':0},{'central_longitude':np.nan}])
def test_invalid_tracks(options):
    with pytest.raises(ValueError): prepare_tracks(orbit_at([0,1]),**options)


def test_track_index_order_columns_and_constellations():
    g=orbit_at([0,1]);e=g.reset_index();e['SV']='E11'
    frame=pd.concat([g.reset_index(),e],ignore_index=True)
    assert list(prepare_tracks(frame,'G+E'))==['E11','G01']
    frame=frame.set_index(['SV','Epoch'])
    assert list(prepare_tracks(frame,None,sv_list='e11'))==['E11']
    with pytest.raises(ValueError,match='duplicate'):
        prepare_tracks(pd.concat([g,g]))


def test_default_dispatch_does_not_silently_select_plotly(monkeypatch):
    module=importlib.import_module('gnsspy.visualization.cartopy_backend')
    captured={}
    def collect(data,**kwargs):
        captured.update(kwargs);return 'DISPATCH_ONLY'
    monkeypatch.setattr(module,'groundtrack',collect)
    assert groundtrack(orbit_at([0,1]),save_path='a')=='DISPATCH_ONLY'
    assert captured['save_path']==Path('a.png')
    assert captured['projection']=='robinson'
    monkeypatch.setattr(module,'ionosphere_maps',lambda *a,**kw:'DISPATCH_ONLY')
    assert ionosphere_map(tiny_gim())=='DISPATCH_ONLY'
    assert ionosphere_maps(tiny_gim())=='DISPATCH_ONLY'


def test_lazy_import_without_cartopy_or_plotly():
    code='''
import builtins, sys
original=builtins.__import__
def blocked(name,*a,**kw):
    if name.split('.')[0] in {'cartopy','plotly'}: raise ImportError('deliberately unavailable')
    return original(name,*a,**kw)
builtins.__import__=blocked
import gnsspy
import gnsspy.visualization
assert gnsspy.__version__ == '3.0.2'
assert 'plotly' not in sys.modules and 'cartopy' not in sys.modules
'''
    subprocess.run([sys.executable,'-c',code],check=True,capture_output=True,text=True)


def test_grid_scaled_tec_latitude_order_seam_and_immutability():
    data=tiny_gim();before=data.tec.copy()
    lon,lat,xe,ye,maps=prepare_grid(read_gim(data),[0,6])
    np.testing.assert_array_equal(lon,[-180,-90,0,90])
    np.testing.assert_array_equal(lat,[-60,0,60])
    np.testing.assert_allclose(maps,data.tec[[0,6],::-1,:-1])
    assert xe[-1]-xe[0]==360
    assert ye[0]==-90 and ye[-1]==90
    np.testing.assert_array_equal(data.tec,before)
    assert maps.max()<30


def test_0_to_360_grid_rotation():
    data=tiny_gim(lon=[0,90,180,270,360])
    lon,_,edges,_,maps=prepare_grid(data,[0])
    np.testing.assert_array_equal(lon,[-180,-90,0,90])
    np.testing.assert_allclose(maps[0],data.tec[0,::-1][:,[2,3,0,1]])
    assert edges[-1]-edges[0]==360


def test_descending_longitude():
    data=tiny_gim(lon=[180,90,0,-90,-180])
    lon,lat,_,_,maps=prepare_grid(data,[0])
    np.testing.assert_array_equal(lon,[-180,-90,0,90])
    np.testing.assert_allclose(maps[0],data.tec[0,::-1,::-1][:,:-1])


def test_regional_grid_not_closed():
    data=tiny_gim(lon=[20,25,30,35])
    lon,lat,edges,_,maps=prepare_grid(data,[0])
    assert len(lon)==4 and maps.shape[-1]==4
    assert edges[-1]-edges[0]==20


def test_seam_disagreement_reported_not_averaged():
    data=tiny_gim();data.tec[0,0,-1]=999
    with pytest.warns(RuntimeWarning,match='seam differs'):
        grid=prepare_grid(data,[0])
    assert grid[-1][0,-1,0]==data.tec[0,0,0]


def test_nan_rms_and_colour_limits():
    data=tiny_gim();data.tec[0,1,2]=np.nan
    maps=prepare_grid(data,[0])[-1]
    assert maps.mask[0,1,2]
    assert colour_limits(maps)[0]<colour_limits(maps)[1]
    assert colour_limits(maps,0,50)==(0,50)
    assert colour_limits(np.array([5,5]))==(4,6)
    np.testing.assert_allclose(prepare_grid(data,[0],field='rms')[-1],data.rms[[0],::-1,:-1])
    with pytest.raises(ValueError,match='RMS'): prepare_grid(replace(data,rms=None),[0],field='rms')
    with pytest.raises(ValueError): colour_limits(np.array([np.nan]))
    with pytest.raises(ValueError): colour_limits(maps,10,5)


def test_epoch_selection_exact_shared_panels():
    data=tiny_gim()
    epochs,indices=select_epochs(data,panels=True)
    assert list(epochs.hour)==[0,4,8,12,16,20]
    np.testing.assert_array_equal(indices,[0,2,4,6,8,10])
    assert select_epochs(data,'2024-01-14T15:00:00+03:00')[1][0]==6
    with pytest.raises(ValueError,match='does not interpolate'): select_epochs(data,'2024-01-14T13:00')
    with pytest.raises(ValueError): select_epochs(data,[])
    with pytest.raises(ValueError): ionosphere_map(data,epoch=list(data.epochs[:2]))


@pytest.mark.parametrize('lon,lat',[([0,3,7],[30,0,-30]),([0,3,3],[30,0,-30]),
                                  ([0,3,6],[91,0,-30]),([0,3,6],[30,np.nan,-30])])
def test_grid_invalid_axes(lon,lat):
    with pytest.raises(ValueError): prepare_grid(tiny_gim(lon,lat),[0])


def test_grid_invalid_object_and_shapes():
    with pytest.raises(TypeError): read_gim(np.zeros((3,3)))
    data=tiny_gim()
    with pytest.raises(ValueError): read_gim(replace(data,tec=data.tec[0]))
    with pytest.raises(ValueError): prepare_grid(data,[0],field='height')


def test_missing_cartopy_is_explicit_no_fallback(monkeypatch,tmp_path):
    import builtins
    original=builtins.__import__
    def blocked(name,*args,**kwargs):
        if name.split('.')[0]=='cartopy':
            raise ImportError('deliberately unavailable')
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',blocked)
    with pytest.raises(ImportError,match='Cartopy maps require'):
        groundtrack(orbit_at([0,1]),save_path=tmp_path/'missing.png')
    assert not (tmp_path/'missing.png').exists()
    assert not (tmp_path/'missing.html').exists()
