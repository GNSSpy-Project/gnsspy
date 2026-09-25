"""IONEX integration tests using files in GNSSPY_TEST_IONEX_DIR."""
from pathlib import Path
import os
import hashlib
from datetime import datetime, timedelta
from types import SimpleNamespace
import numpy as np
import pytest

from gnsspy import read_ionex, read_ionFile, ionosphere_interp
from gnsspy.io.products.ionex import IonexProductError
from gnsspy.data_access import NavigationDownloader

SAMPLES=[
    ('JPLQ0140.24I',13,7200,'2024-01-14',11.3,'JPLQ',.5,120.8),
    ('igsg0090.07i.Z',13,7200,'2007-01-09',3.5,'IGS',.8,47.9),
    ('COD0OPSFIN_20240140000_01D_01H_GIM.INX',25,3600,'2024-01-14',13.9,'CODE',0.,115.4),
]


@pytest.fixture
def sample_dir(monkeypatch):
    directory=os.environ.get('GNSSPY_TEST_IONEX_DIR')
    if directory is None:
        pytest.skip('Set GNSSPY_TEST_IONEX_DIR to run the four user-supplied ionosphere files')
    def blocked(*a,**kw):
        raise AssertionError('No product request is permitted in real local-file tests')
    monkeypatch.setattr('requests.Session.request',blocked)
    return Path(directory)


@pytest.mark.parametrize('name,count,step,day,first,product,minimum,maximum',SAMPLES)
def test_actual_reader_and_cache(sample_dir,tmp_path,name,count,step,day,first,product,minimum,maximum):
    path=sample_dir/name
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    d=read_ionex(path)
    assert d.shape==(count,71,73)
    assert d.rms.shape==d.shape
    assert d.metadata['interval_seconds']==step
    assert d.epochs[0]==datetime.fromisoformat(day)
    assert d.epochs[-1]==datetime.fromisoformat(day)+timedelta(days=1)
    assert d.tec[0,0,0]==pytest.approx(first)
    assert np.nanmin(d.tec)==pytest.approx(minimum)
    assert np.nanmax(d.tec)==pytest.approx(maximum)
    assert np.isnan(d.tec).sum()==0
    assert np.isnan(d.rms).sum()==0
    np.testing.assert_allclose(d.tec,d.raw_tec*.1)
    np.testing.assert_array_equal(d.tec[:,:,0],d.tec[:,:,-1])
    for a,b in [(0,0),(70,0),(20,35),(40,60)]:
        np.testing.assert_allclose(d.interpolate(d.latitudes[a],d.longitudes[b],d.epochs),d.tec[:,a,b],atol=1e-12)

    a,b,t=25,45,5
    expected=d.tec[t:t+2,a:a+2,b:b+2].mean()
    obtained=d.interpolate(np.mean(d.latitudes[a:a+2]),np.mean(d.longitudes[b:b+2]),
                           [d.epochs[t]+(d.epochs[t+1]-d.epochs[t])/2])[0]
    assert obtained==pytest.approx(expected,abs=1e-12)
    with pytest.warns(FutureWarning):
        raw=read_ionFile(path)
    assert raw.shape==(count,71,72)
    dl=NavigationDownloader(None,None,sample_dir)
    result=dl.acquire_ionosphere(day,product=product,allow_download=False)
    assert result.path==path and result.action=='reused' and result.attempted_urls==()
    assert result.url is None
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest


def test_actual_rot_is_not_gim(sample_dir):
    p=sample_dir/'IGS0OPSFIN_20240140000_01D_01D_ROT.INX'
    before=hashlib.sha256(p.read_bytes()).hexdigest()
    with pytest.raises(IonexProductError,match='ROT/ROTI'):
        read_ionex(p)
    assert hashlib.sha256(p.read_bytes()).hexdigest()==before
    dl=NavigationDownloader(None,None,sample_dir)
    r=dl.acquire_ionosphere('2024-01-14',product='IGS',allow_download=False)
    assert not r.success


def test_actual_station_4h_interpolation(sample_dir):
    phi,lam=np.deg2rad([40,30]);radius=6371000.
    xyz=[radius*np.cos(phi)*np.cos(lam),radius*np.cos(phi)*np.sin(lam),radius*np.sin(phi)]
    station=SimpleNamespace(approx_position=xyz,epoch=datetime(2024,1,14))
    epochs=[station.epoch+timedelta(hours=h) for h in range(0,25,4)]
    out,meta=ionosphere_interp(station,unit='tecu',epoch_list=epochs,data_dir=sample_dir,
                              product='CODE',epoch_time_system='UTC',return_metadata=True)
    np.testing.assert_allclose(out,[16.6,12.8,37.7,41.9,18.5,14.2,15.4],atol=1e-10)
    assert meta['acquisition'].action=='reused'
    assert meta['quantity']=='VTEC' and meta['missing_values']==0
