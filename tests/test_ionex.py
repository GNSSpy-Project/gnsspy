"""Native IONEX reader, naming, interpolation and bounded acquisition tests."""
from datetime import datetime, timedelta
import bz2
import gzip
import lzma
from pathlib import Path
from types import SimpleNamespace
import shutil
import numpy as np
import pandas as pd
import pytest

from gnsspy import read_ionex, read_ionFile, ionosphere_interp, interpolate_vtec
from gnsspy.io.products.ionex import IonexFormatError, IonexProductError
from gnsspy.utils.ionex_files import (
    parse_ionex_name, ionex_filename, ionex_request, find_ionex_files,
    resolve_ionex_path, open_ionex_text, TRANSITION_DATE,
)
from gnsspy.utils.filename import ionFileName
from gnsspy.data_access import NavigationDownloader
from gnsspy.data_access.ionosphere import ionex_candidates

DAY = datetime(2024, 1, 14)
NAME = 'IGS0OPSFIN_20240140000_01D_02H_GIM.INX'


def rec(text, label, column=60):
    return str(text).ljust(column)+label+'\n'


def stamp(t):
    return ''.join(f'{v:6d}' for v in (t.year, t.month, t.day, t.hour, t.minute, t.second))


def ionex_text(*, epochs=None, interval=3600, latitudes=(10., 0., -10.),
               longitudes=(-180., -90., 0., 90., 180.), exponent=-1,
               per_map_exponents=None, rms=True, values=None, column=60, height_maps=False):
    epochs = [DAY, DAY+timedelta(hours=1), DAY+timedelta(hours=2)] if epochs is None else epochs
    latitudes, longitudes = np.asarray(latitudes), np.asarray(longitudes)
    shape = (len(epochs), len(latitudes), len(longitudes))
    if values is None:
        values = np.zeros(shape, dtype=int)
        for t in range(len(epochs)):
            for a in range(len(latitudes)):
                for b in range(len(longitudes)):
                    values[t, a, b] = 200+100*t+10*a+b
    def r(t, label): return rec(t, label, column)
    def ax(a): return '  '+''.join(f'{v:6.1f}' for v in [a[0], a[-1], a[1]-a[0] if len(a) > 1 else 0])
    text = r('     1.0            IONOSPHERE MAPS     GNSS', 'IONEX VERSION / TYPE')
    text += r(stamp(epochs[0]), 'EPOCH OF FIRST MAP')+r(stamp(epochs[-1]), 'EPOCH OF LAST MAP')
    text += r(f'{interval:6d}', 'INTERVAL')+r(f'{len(epochs):6d}', '# OF MAPS IN FILE')
    text += r('     2', 'MAP DIMENSION')+r('  6371.0', 'BASE RADIUS')
    text += r(ax([450., 450.]), 'HGT1 / HGT2 / DHGT')
    text += r(ax(latitudes), 'LAT1 / LAT2 / DLAT')+r(ax(longitudes), 'LON1 / LON2 / DLON')
    if exponent is not None:
        text += r(f'{exponent:6d}', 'EXPONENT')
    text += r('', 'END OF HEADER')
    for kind in ['TEC']+(['RMS'] if rms else [])+(['HEIGHT'] if height_maps else []):
        for k, epoch in enumerate(epochs):
            text += r(f'{k+1:6d}', f'START OF {kind} MAP')
            if per_map_exponents is not None:
                text += r(f'{per_map_exponents[k]:6d}', 'EXPONENT')
            text += r(stamp(epoch), 'EPOCH OF CURRENT MAP')
            for a, lat in enumerate(latitudes):
                row = '  '+''.join(f'{v:6.1f}' for v in [lat, longitudes[0], longitudes[-1],
                    longitudes[1]-longitudes[0] if len(longitudes)>1 else 0, 450.])
                text += r(row, 'LAT/LON1/LON2/DLON/H')
                val = values[k, a] if kind == 'TEC' else np.full(len(longitudes), 20 if kind == 'RMS' else 50)
                for b in range(0, len(longitudes), 16):
                    text += ''.join(f'{int(v):5d}' for v in val[b:b+16])+'\n'
            text += r(f'{k+1:6d}', f'END OF {kind} MAP')
    return text+r('', 'END OF FILE')


@pytest.fixture(autouse=True)
def no_live_network(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    def blocked(*args, **kwargs):
        raise AssertionError('Test unexpectedly attempted a live network request')
    monkeypatch.setattr('requests.Session.request', blocked)


@pytest.fixture
def write_ion(tmp_path):
    def write(name=NAME, text=None, **kwargs):
        p = tmp_path/name
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = (ionex_text(**kwargs) if text is None else text).encode('latin1')
        suffix = p.suffix.lower()
        encoder = {'.gz': gzip.compress, '.bz2': bz2.compress, '.xz': lzma.compress}.get(suffix, lambda x:x)
        p.write_bytes(encoder(payload))
        return p
    return write


@pytest.mark.parametrize('name,center,sol,naming', [
    ('igsg0090.07i.Z', 'IGS', 'FIN', 'IGSG'),
    ('IGRG0140.24I.GZ', 'IGS', 'RAP', 'IGRG'),
    ('igpg0140.24i', 'IGS', 'PRE', 'IGPG'),
    ('JPLQ0140.24I', 'JPL', 'QCK', 'JPLQ'),
    ('COD0OPSFIN_20240140000_01D_01H_GIM.INX', 'COD', 'FIN', 'COD0OPSFIN'),
    ('igs0opsrap_20240140000_01d_15m_gim.inx.gz', 'IGS', 'RAP', 'IGS0OPSRAP'),
])
def test_parse_names(name, center, sol, naming):
    info = parse_ionex_name(name)
    assert (info.center, info.solution, info.series) == (center, sol, naming)


@pytest.mark.parametrize('name', ['bad.inx', 'igsg0000.07i', 'igsg3660.07i',
    'IGS0OPSFIN_20233660000_01D_02H_GIM.INX', 'IGS0OPSFIN_20240009999_01D_02H_GIM.INX',
    'IGS0OPSFIN_20240140000_00D_02H_GIM.INX'])
def test_invalid_names(name):
    assert parse_ionex_name(name) is None


def test_transition_only_orders_names():
    assert str(TRANSITION_DATE) == '2022-11-27'
    assert ionFileName(datetime(2022, 11, 26)).startswith('igsg')
    assert ionFileName(datetime(2022, 11, 27)).startswith('IGS0OPSFIN_')
    assert ionFileName(DAY, product='CODE', zipped=True).endswith('_01H_GIM.INX.gz')
    assert ionFileName(DAY, product='igpg') == 'igpg0140.24i'
    assert ionFileName(DAY, product='igs').startswith('IGS0OPSFIN')
    assert ionFileName(DAY, product='JPLQ') == 'jplq0140.24i'
    assert ionFileName(DAY, legacy=True) == 'igsg0140.24i'
    assert ionFileName(datetime(2007,1,9), legacy=False).startswith('IGS0OPSFIN')


@pytest.mark.parametrize('product,typ', [('IGS0OPSFIN','rapid'),('igrg','final'),('JPLQ','final'),('igpg','final'),('IGS','typo')])
def test_conflicting_requests(product, typ):
    with pytest.raises(ValueError):
        ionex_request(product,typ)


def test_predictions_never_in_auto():
    assert ionex_request('IGS').solutions == ('FIN', 'RAP')
    for _, url in ionex_candidates(DAY):
        assert 'igpg' not in url.lower() and 'ROT.INX' not in url
    candidates = ionex_candidates(DAY, 'IGS', 'final')
    assert all('RAP' not in u and 'igrg' not in u for _,u in candidates)
    assert any('/2024/014/' in u for _,u in candidates)
    assert any('/2297/' in u for _,u in candidates)
    old = ionex_candidates(datetime(2007,1,9), 'IGS', 'final')
    assert old[0][0] == 'igsg0090.07i.Z'
    assert any('IGS0OPSFIN_' in n for n,_ in old)
    pre = ionex_candidates(DAY, 'IGS', 'predicted')
    assert pre and all(n.startswith('igpg') for n,_ in pre)
    with pytest.raises(ValueError):
        ionex_filename(DAY, 'igpg', solution='auto', legacy=False)


@pytest.mark.parametrize('suffix', ['', '.gz', '.GZ', '.bz2', '.xz'])
def test_compressed_direct_read(write_ion, suffix):
    p = write_ion(NAME+suffix)
    original = p.read_bytes()
    d = read_ionex(p)
    assert d.shape == (3, 3, 5)
    assert d.tec[0,0,0] == 20
    assert d.rms[0,0,0] == 2
    assert d.metadata['time_system'] == 'UTC'
    assert p.read_bytes() == original
    if suffix:
        assert not p.with_suffix('').exists()


@pytest.mark.parametrize('step', [900, 1800, 3600, 7200])
def test_arbitrary_map_cadence_and_count(write_ion, step):
    epochs = [DAY+timedelta(seconds=i) for i in range(0, 86401, step)]
    p = write_ion(epochs=epochs, interval=step)
    d = read_ionex(p)
    assert len(d.epochs) == len(epochs)
    assert d.epochs[-1] == DAY+timedelta(days=1)


@pytest.mark.parametrize('exp,factor', [(-2, .01),(-1,.1),(0,1),(1,10),(None,.1)])
def test_exponent_scaling(write_ion, exp, factor):
    d = read_ionex(write_ion(exponent=exp))
    np.testing.assert_allclose(d.tec, d.raw_tec*factor)


def test_exponent_updates_and_missing(write_ion):
    values = np.full((3,3,5), 123)
    values[0,0,0] = 9999
    d = read_ionex(write_ion(values=values, per_map_exponents=[-1,-2,0]))
    assert np.isnan(d.tec[0,0,0]) and np.isnan(d.raw_tec[0,0,0])
    np.testing.assert_allclose(d.tec[:,1,1], [12.3,1.23,123])
    assert d.metadata['missing_tec_values'] == 1


def test_i5_fields_need_not_have_spaces(write_ion):
    values = np.full((3,3,5), -1234)
    d = read_ionex(write_ion(values=values))
    np.testing.assert_allclose(d.tec, -123.4)


@pytest.mark.parametrize('column',[57,58,60])
def test_real_world_label_alignment(write_ion, column):
    assert read_ionex(write_ion(column=column)).tec[0,0,0] == 20


def test_rms_optional_and_height_maps(write_ion):
    d = read_ionex(write_ion(rms=False, height_maps=True))
    assert d.rms is None
    np.testing.assert_allclose(d.height_maps_km,455)


def test_no_rms_epoch_uses_matching_tec(write_ion):
    text = ionex_text()
    a,b = text.split(rec('     1', 'START OF RMS MAP'),1)
    b = '\n'.join(line for line in b.split('\n') if 'EPOCH OF CURRENT MAP' not in line)
    d=read_ionex(write_ion(text=a+rec('     1','START OF RMS MAP')+b))
    assert d.rms is not None


def test_raw_compatibility_explicit_warning(write_ion):
    p=write_ion()
    with pytest.warns(FutureWarning,match='RAW'):
        raw = read_ionFile(p)
    assert raw.shape == (3,3,4)
    assert raw[0,0,0] == 200
    d = read_ionFile(p, return_dataset=True)
    assert d.shape == (3,3,5) and d.tec[0,0,0] == 20


@pytest.mark.parametrize('transform,match', [
    (lambda t:t.replace('END OF HEADER','BAD HEADER'), 'END OF HEADER'),
    (lambda t:t[:t.index('END OF TEC MAP')], 'expected|truncated'),
    (lambda t:t.replace('END OF FILE',''), 'END OF FILE'),
    (lambda t:t.replace(rec('     3','# OF MAPS IN FILE'),rec('     4','# OF MAPS IN FILE')), 'declares'),
    (lambda t:t.replace('     2'.ljust(60)+'MAP DIMENSION','     3'.ljust(60)+'MAP DIMENSION'), '2-D'),
    (lambda t:t.replace('  200  201  202  203  204','  200oops!  202  203  204'), 'invalid literal'),
    (lambda t:t.replace(rec('     1','END OF TEC MAP'),rec('     2','END OF TEC MAP'),1), 'numbers disagree'),
    (lambda t:t+rec('bad','COMMENT'), 'after END OF FILE'),
    (lambda t:t.replace('   450.0 450.0   0.0','   450.0 550.0 100.0'), '2-D'),
])
def test_malformed_files(write_ion, transform, match):
    with pytest.raises(IonexFormatError, match=match):
        read_ionex(write_ion(text=transform(ionex_text())))


@pytest.mark.parametrize('text', ['', '<html>login</html>', 'SP3 is not IONEX\n'])
def test_wrong_content(write_ion,text):
    with pytest.raises(IonexFormatError):
        read_ionex(write_ion(text=text))


@pytest.mark.parametrize('name,text', [
    ('IGS0OPSFIN_20240140000_01D_01D_ROT.INX', ionex_text()),
    ('renamed.inx', ' 1.0 IGS ROTI maps\nSTART OF ROTIPOLARMAP\n'),
    ('roti0140.24f', 'Not TEC\n')])
def test_rot_never_tec(write_ion,name,text):
    with pytest.raises(IonexProductError, match='ROT'):
        read_ionex(write_ion(name,text=text))


def test_case_compression_and_sampling_resolution(write_ion):
    path=write_ion('igs0opsfin_20240140000_01d_01h_gim.inx.GZ')
    assert resolve_ionex_path('igsg0140.24i') == path
    assert read_ionex(NAME).source == path
    assert read_ionex('IGS0OPSFIN_20240140000_01D_01H_GIM.INX').source == path
    with pytest.raises(FileNotFoundError):
        read_ionex('igrg0140.24i')
    with pytest.raises(FileNotFoundError):
        read_ionex('igpg0140.24i')


def test_sampling_and_center_not_swapped(write_ion):
    cod=write_ion('COD0OPSFIN_20240140000_01D_01H_GIM.INX')
    rot=write_ion('IGS0OPSFIN_20240140000_01D_01D_ROT.INX')
    assert not find_ionex_files(DAY,'IGS')
    assert find_ionex_files(DAY,'CODE')[0].path == cod
    assert not any(i.path==rot for i in find_ionex_files(DAY,'auto'))


def affine_fixture(write_ion, *, ascending=False):
    lats = [-10.,0.,10.] if ascending else [10.,0.,-10.]
    lons = [0.,10.,20.]
    vals=np.array([[[1000 + 10*lat + 20*lon+100*t for lon in lons] for lat in lats] for t in range(3)])
    return read_ionex(write_ion(latitudes=lats,longitudes=lons,values=vals))


@pytest.mark.parametrize('ascending',[False,True])
def test_affine_space_time_exact(write_ion,ascending):
    d = affine_fixture(write_ion,ascending=ascending)
    times = [DAY+timedelta(minutes=90), DAY,DAY+timedelta(hours=2),DAY+timedelta(minutes=90)]
    values=d.interpolate([5,0,-5,5],[5,10,15,5],times)
    np.testing.assert_allclose(values,[130,120,145,130],atol=1e-12)
    np.testing.assert_allclose(d.interpolate(d.latitudes[0],d.longitudes[0],d.epochs),d.tec[:,0,0])


def test_periodic_without_duplicate_seam(write_ion):
    values=np.array([[[100,200,300,200]]]*3)
    d=read_ionex(write_ion(latitudes=[0],longitudes=[0,90,180,270],values=values))
    np.testing.assert_allclose(d.interpolate(0,[-45,315,675],[DAY]*3),[15,15,15])


def test_periodic_with_duplicate_seam(write_ion):
    values=np.array([[[100,200,300,200,100]]]*3)
    d=read_ionex(write_ion(latitudes=[0],longitudes=[-180,-90,0,90,180],values=values))
    np.testing.assert_allclose(d.interpolate(0,[-180,180,540,-540],[DAY]*4),[10]*4)


def test_exact_node_ignores_unused_missing_corner(write_ion):
    d=affine_fixture(write_ion)
    d.tec[0,0,0]=np.nan
    assert np.isfinite(d.interpolate(0,10,[DAY])[0])
    assert np.isnan(d.interpolate(5,5,[DAY])[0])
    assert np.isfinite(d.interpolate(10,0,[DAY+timedelta(hours=1)])[0])


@pytest.mark.parametrize('lat,lon,t', [(80,10,DAY),(0,30,DAY),(0,10,DAY-timedelta(seconds=1)),(0,10,DAY+timedelta(hours=2,seconds=1))])
def test_no_extrapolation(write_ion,lat,lon,t):
    d=affine_fixture(write_ion)
    assert np.isnan(d.interpolate(lat,lon,[t])[0])
    with pytest.raises(ValueError):
        d.interpolate(lat,lon,[t],bounds='raise')


def test_missing_scheduled_map_not_bridged(write_ion):
    with pytest.warns(RuntimeWarning,match='spacing'):
        d=read_ionex(write_ion(epochs=[DAY,DAY+timedelta(hours=1),DAY+timedelta(hours=3)]))
    assert np.isnan(d.interpolate(0,0,[DAY+timedelta(hours=2)])[0])
    assert np.isfinite(d.interpolate(0,0,[DAY+timedelta(hours=3)])[0])
    assert np.isfinite(d.interpolate(0,0,[DAY+timedelta(hours=2)],max_gap=7200)[0])


def test_timezone_conversion(write_ion):
    d=affine_fixture(write_ion)
    a=d.interpolate(0,10,[pd.Timestamp(DAY,tz='UTC')])
    b=d.interpolate(0,10,[pd.Timestamp(DAY,tz='UTC').tz_convert('Europe/Istanbul')])
    np.testing.assert_equal(a,b)


def test_station_tecu_needs_no_observation_band(write_ion):
    d=affine_fixture(write_ion)
    s=SimpleNamespace(approx_position=[6378137.,0,0],epoch=DAY)
    v=ionosphere_interp(s,unit='tecu',epoch_list=d.epochs,ionex_file=d,epoch_time_system='UTC')
    np.testing.assert_allclose(v,[100,110,120])
    m,meta=ionosphere_interp(s,epoch_list=d.epochs,ionex_file=d,frequency_hz=1e9,
                            epoch_time_system='UTC',return_metadata=True)
    np.testing.assert_allclose(m,v*.403)
    assert meta['quantity']=='vertical_group_delay' and meta['units']=='m'


def test_station_clock_convention_must_not_be_guessed(write_ion):
    d=affine_fixture(write_ion)
    s=SimpleNamespace(approx_position=[6378137.,0,0],epoch=DAY)
    with pytest.raises(ValueError,match='gps_utc_offset'):
        ionosphere_interp(s,unit='tecu',epoch_list=d.epochs,ionex_file=d,epoch_time_system='GPS')

    a=ionosphere_interp(s,unit='tecu',epoch_list=d.epochs+pd.Timedelta(seconds=18),ionex_file=d,
                        epoch_time_system='GPS',gps_utc_offset=18)
    b=ionosphere_interp(s,unit='tecu',epoch_list=d.epochs,ionex_file=d,epoch_time_system='UTC')
    np.testing.assert_equal(a,b)
    with pytest.warns(RuntimeWarning,match='assuming UTC'):
        ionosphere_interp(s,unit='tecu',epoch_list=d.epochs,ionex_file=d)


def test_station_dataframe_epochs(write_ion):
    d=affine_fixture(write_ion)
    obs=pd.DataFrame(index=pd.MultiIndex.from_product([d.epochs,['G01','G02']],names=['Epoch','SV']))
    s=SimpleNamespace(approx_position=[6378137.,0,0],epoch=DAY,observation=obs)
    out=ionosphere_interp(s,unit='tecu',ionex_file=d,epoch_time_system='UTC')
    assert len(out)==3


def test_local_final_selected_before_network_and_predictions(write_ion,tmp_path,monkeypatch):
    pre=write_ion('igpg0140.24i')
    rap=write_ion('IGS0OPSRAP_20240140000_01D_01H_GIM.INX')
    final=write_ion('IONOSPHERE/IGS0OPSFIN_20240140000_01D_01H_GIM.INX')

    final2=write_ion('ionosphere/IGS0OPSFIN_20240140000_01D_01H_GIM.INX')
    dl=NavigationDownloader(None,None,tmp_path)
    r=dl.acquire_ionosphere(DAY)
    assert r.action=='reused' and r.path==final2 and r.url is None and not r.attempted_urls
    assert 'no download' in r.message
    assert dl.last_ionosphere_result is r
    assert dl.acquire_ionosphere(DAY,ion_type='rapid',allow_download=False).path==rap
    assert dl.acquire_ionosphere(DAY,ion_type='predicted',allow_download=False).path==pre
    final2.unlink()
    assert dl.acquire_ionosphere(DAY,ion_type='final',allow_download=False).path is None


def test_local_invalid_is_not_success(write_ion,tmp_path):
    write_ion(text='<html>'+('X'*2000)+'</html>')
    dl=NavigationDownloader(None,None,tmp_path)
    with pytest.warns(RuntimeWarning,match='Invalid IONEX'):
        r=dl.acquire_ionosphere(DAY,allow_download=False)
    assert not r.success and r.errors


def test_local_compressed_reused_without_extraction(write_ion,tmp_path):
    p=write_ion(NAME+'.gz')
    dl=NavigationDownloader(None,None,tmp_path)
    success,message=dl.download_ionosphere(DAY,allow_download=False)
    assert success and 'reused locally' in message and dl.last_ionosphere_result.path==p
    assert not p.with_suffix('').exists()


def test_high_level_auto_uses_returned_path(write_ion,tmp_path):
    p=write_ion('COD0OPSFIN_20240140000_01D_01H_GIM.INX')
    s=SimpleNamespace(approx_position=[6378137.,0,0],epoch=DAY)
    out,meta=ionosphere_interp(s,unit='tecu',epoch_list=[DAY],data_dir=tmp_path,product='CODE',
                              epoch_time_system='UTC',return_metadata=True)
    assert np.isfinite(out).all() and meta['ionex_file']==str(p)
    assert meta['acquisition'].action=='reused'


class Response:
    def __init__(self, content=b'', status=200, content_type='application/octet-stream'):
        self.content=content; self.status_code=status; self.headers={'content-type':content_type}
    def __enter__(self): return self
    def __exit__(self,*args): pass


def test_atomic_real_download_function(tmp_path,monkeypatch):
    dl=NavigationDownloader(None,None,tmp_path)
    payload=gzip.compress(ionex_text(interval=7200,epochs=[DAY,DAY+timedelta(hours=2)]).encode())
    calls=[]
    def get(url,**kw):
        calls.append(url)
        assert kw['timeout']==(10,30)
        return Response(payload)
    monkeypatch.setattr(dl.session,'get',get)
    r=dl.acquire_ionosphere(DAY,ion_type='final')
    assert r.action=='downloaded' and r.url==calls[0] and len(calls)==1
    assert r.path.read_bytes()==payload and r.attempted_urls==(calls[0],)
    r2=dl.acquire_ionosphere(DAY)
    assert r2.action=='reused' and r2.url is None and len(calls)==1
    assert not list((tmp_path/'ionosphere').glob('*.part*'))


def test_404_tries_other_directory_then_success(tmp_path,monkeypatch):
    dl=NavigationDownloader(None,None,tmp_path)
    payload=gzip.compress(ionex_text().encode())
    calls=[]
    def get(url,**kw):
        calls.append(url)
        return Response(status=404) if len(calls)==1 else Response(payload)
    monkeypatch.setattr(dl.session,'get',get)
    r=dl.acquire_ionosphere(DAY,'final')
    assert r.success and len(calls)==2 and '/2297/' in r.url


@pytest.mark.parametrize('status', [401,403,429,500])
def test_access_failure_stops_not_prediction_fallback(tmp_path,monkeypatch,status):
    dl=NavigationDownloader(None,None,tmp_path)
    calls=[]
    monkeypatch.setattr(dl.session,'get',lambda url,**kw:(calls.append(url) or Response(status=status)))
    r=dl.acquire_ionosphere(DAY)
    assert not r.success and len(calls)==1 and not any('igpg' in u for u in calls)


def test_missing_candidates_bounded(tmp_path,monkeypatch):
    dl=NavigationDownloader(None,None,tmp_path)
    calls=[]
    monkeypatch.setattr(dl.session,'get',lambda url,**kw:(calls.append(url) or Response(status=404)))
    r=dl.acquire_ionosphere(DAY,max_attempts=3)
    assert not r.success and len(calls)==3 and '3-request limit' in r.detail
    assert not list((tmp_path/'ionosphere').iterdir())


@pytest.mark.parametrize('payload', [b'<html>'+b'X'*5000+b'</html>', b'not gzip', gzip.compress(b'not IONEX'),
    gzip.compress(ionex_text().replace('END OF FILE','').encode()),
    gzip.compress(ionex_text(epochs=[DAY+timedelta(days=1)]).encode()),
    gzip.compress(b'IGS ROTI maps\nSTART OF ROTIPOLARMAP\n')])
def test_invalid_transfer_not_committed(tmp_path,monkeypatch,payload):
    dl=NavigationDownloader(None,None,tmp_path)
    monkeypatch.setattr(dl.session,'get',lambda *a,**kw:Response(payload))
    r=dl.acquire_ionosphere(DAY,'final')
    assert not r.success and r.action=='missing'
    assert not list((tmp_path/'ionosphere').iterdir())


def test_transfer_does_not_replace_bad_cache_with_bad_bytes(write_ion,tmp_path,monkeypatch):
    p=write_ion('ionosphere/'+NAME+'.gz',text='bad cached content')
    old=p.read_bytes()
    dl=NavigationDownloader(None,None,tmp_path)
    monkeypatch.setattr(dl.session,'get',lambda *a,**kw:Response(b'invalid'))
    with pytest.warns(RuntimeWarning):
        r=dl.acquire_ionosphere(DAY,'final')
    assert not r.success and p.read_bytes()==old


def test_compression_corruption_detected(write_ion):
    p=write_ion(NAME+'.gz')
    p.write_bytes(p.read_bytes()[:-4])
    with pytest.raises((EOFError,OSError,ValueError)):
        read_ionex(p)


def test_different_content_day_not_reused(write_ion,tmp_path):
    write_ion(epochs=[DAY+timedelta(days=1)])
    dl=NavigationDownloader(None,None,tmp_path)
    with pytest.warns(RuntimeWarning,match='start epoch'):
        r=dl.acquire_ionosphere(DAY,allow_download=False)
    assert not r.success


def test_empty_requests_and_single_node(write_ion):
    d=read_ionex(write_ion(epochs=[DAY], latitudes=[0], longitudes=[10],values=np.array([[[250]]])))
    assert d.interpolate(0,10,[DAY])[0]==25
    assert d.interpolate(0,10,[]).size==0
    assert np.isnan(d.interpolate(0,10,[DAY+timedelta(seconds=1)])[0])


def test_legacy_request_does_not_change_project_version(write_ion):
    p=write_ion('IGS1R03FIN_20240140000_01D_02H_GIM.INX')
    assert not find_ionex_files(DAY,'IGS')
    assert find_ionex_files(DAY,'IGS1R03FIN')[0].path==p
    with pytest.raises(FileNotFoundError):
        resolve_ionex_path('igsg0140.24i')


def test_latitude_row_mismatch(write_ion):
    text=ionex_text().replace('    10.0-180.0 180.0  90.0 450.0','    11.0-180.0 180.0  90.0 450.0',1)
    with pytest.raises(IonexFormatError,match='header grid'):
        read_ionex(write_ion(text=text))


def test_timeout_stops_request_loop(tmp_path,monkeypatch):
    import requests
    dl=NavigationDownloader(None,None,tmp_path)
    calls=[]
    def get(url,**kwargs):
        calls.append(url)
        raise requests.exceptions.Timeout()
    monkeypatch.setattr(dl.session,'get',get)
    r=dl.acquire_ionosphere(DAY)
    assert len(calls)==1 and not r.success and 'Timeout' in r.errors[0]


def test_cache_race_is_not_reported_as_download(tmp_path,monkeypatch):
    dl=NavigationDownloader(None,None,tmp_path)
    def download(url,path):
        path.write_bytes(gzip.compress(ionex_text().encode()))
        return True,f'Reused locally (no download): {path}'
    monkeypatch.setattr(dl,'download_file',download)
    r=dl.acquire_ionosphere(DAY)
    assert r.success and r.action=='reused' and r.url is None and r.attempted_urls==()


def test_unknown_named_local_file_read_explicitly(write_ion):
    p=write_ion('my_actual_file.txt')
    assert read_ionex(p).shape==(3,3,5)
    assert find_ionex_files(DAY)==[]


def test_periodic_grid_has_same_results_in_both_longitude_orders(write_ion):
    vals=np.array([[[100,200,300,200,100]]]*3)
    p=write_ion(latitudes=[0],longitudes=[180,90,0,-90,-180],values=vals)
    d=read_ionex(p)
    np.testing.assert_allclose(d.interpolate(0,[-180,180,-45,315],[DAY]*4),[10,10,25,25])
