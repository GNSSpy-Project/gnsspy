"""No live archive requests: controlled transport, candidate and cache tests."""
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse
import gzip

import pytest
import requests

from conftest import PRECISE_DAY, sp3_text, clk_text
from gnsspy.data_access.products import NavigationDownloader
from gnsspy.data_access.earthdata import BaseDownloader
from gnsspy.utils.product_files import parse_product_name


@pytest.fixture
def downloader(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path)
    return NavigationDownloader(None,None,tmp_path)


def forbid_network(*args,**kwargs):
    pytest.fail('Local product availability must be checked before the network')


@pytest.mark.parametrize('strict',[True,False])
@pytest.mark.parametrize('suffix',['','.gz'])
def test_auto_uses_local_final_not_age_inferred_ultra(downloader,write_product,strict,suffix):
    sp3 = write_product('COD0MGXFIN_20242210000_01D_15M_ORB.SP3'+suffix)
    clk = write_product('COD0MGXFIN_20242210000_01D_30S_CLK.CLK'+suffix,length=60)
    downloader.determine_orbit_type = lambda epoch: 'ultra-rapid'
    downloader.download_file = forbid_network
    ok,message,mode = downloader.download_sp3_with_fallback('CODE',PRECISE_DAY,
                               strict_center=strict,fallback_to_broadcast=False)
    assert ok and mode == 'precise'
    assert message.count('reused locally (no download)') == 2 and 'downloaded' not in message
    result = downloader.last_precise_result
    assert result.sp3.path == sp3 and result.clk.path == clk
    assert not result.attempted_urls and result.sp3.url is None and result.clk.url is None


def test_auto_final_then_rapid_then_ult(downloader,write_product):
    paths = [write_product(f'COD0MGX{solution}_20242210000_01D_05M_ORB.SP3') for solution in ['ULT','RAP','FIN']]
    downloader.download_file = forbid_network
    for solution in ['FIN','RAP','ULT']:
        result = downloader.acquire_precise_products('CODE',PRECISE_DAY,allow_download=False,download_clk=False)
        assert parse_product_name(result.sp3.path).solution == solution
        result.sp3.path.unlink()


@pytest.mark.parametrize('strict',[True,False])
def test_explicit_quality_is_not_relaxed(downloader,write_product,strict):
    write_product('COD0MGXRAP_20242210000_01D_05M_ORB.SP3')
    write_product('COD0MGXULT_20242210000_02D_05M_ORB.SP3')
    result = downloader.acquire_precise_products('CODE',PRECISE_DAY,'final',strict,
                                                 allow_download=False,download_clk=False)
    assert not result.success and result.mode == 'none'


def test_strict_center_does_not_use_other_center(downloader,write_product):
    write_product('EMR0OPSFIN_20242210000_01D_15M_ORB.SP3')
    result = downloader.acquire_precise_products('CODE',PRECISE_DAY,allow_download=False,download_clk=False)
    assert not result.success
    result = downloader.acquire_precise_products('CODE',PRECISE_DAY,strict_center=False,
                                                  allow_download=False,download_clk=False)
    assert result.success and result.sp3.path.name.startswith('EMR')


def test_dont_mix_ops_clock_with_mgx_orbit(downloader,write_product):
    write_product()
    write_product('COD0OPSFIN_20242210000_01D_30S_CLK.CLK',length=60)
    result = downloader.acquire_precise_products('CODE',PRECISE_DAY,allow_download=False)
    assert result.mode == 'precise_partial'
    assert result.clk.path is None and 'CLK missing' in result.message
    assert 'SP3+CLK downloaded' not in result.message


def test_weekly_cache_covers_target_even_on_sunday(downloader,write_product):
    weekly = write_product('EMR0OPSFIN_20242170000_07D_15M_ORB.SP3')
    downloader.download_file = forbid_network
    for day in [date(2024,8,4),date(2024,8,8),date(2024,8,10)]:
        result = downloader.acquire_precise_products('EMR',day,download_clk=False)
        assert result.sp3.path == weekly and not result.attempted_urls


@pytest.mark.parametrize('center,project,rate',[('CODE','MGX','15M'),('EMR','OPS','05M'),('COD','OPS','05M'),('GFZ','OPS','15M')])
def test_remote_sampling_and_project_fallback(downloader,center,project,rate):
    from gnsspy.utils.product_files import normalise_center
    agency = normalise_center(center)
    expected = f'{agency}0{project}FIN_20242210000_01D_{rate}_ORB.SP3.gz'
    calls=[]
    def fetch(url,path):
        calls.append(url)
        if Path(path).name == expected:
            Path(path).write_bytes(gzip.compress(sp3_text().encode('ascii')))
            return True,'Downloaded 1 MB'
        return False,'File not found (404)'
    downloader.download_file = fetch
    result = downloader.acquire_precise_products(center,PRECISE_DAY,'final',download_clk=False)
    assert result.success and result.sp3.action == 'downloaded'
    assert result.sp3.path.name == expected and result.sp3.url in calls
    assert not result.sp3.path.with_suffix('').exists()
    assert 'SP3 downloaded' in result.message


def test_mixed_reused_sp3_downloaded_clk(downloader,write_product):
    sp3 = write_product()
    def fetch(url,path):
        assert '.CLK' in path.name
        path.write_bytes(gzip.compress(clk_text(length=60).encode('ascii')))
        return True,'Downloaded 1 MB'
    downloader.download_file = fetch
    result = downloader.acquire_precise_products('CODE',PRECISE_DAY)
    assert result.mode == 'precise'
    assert result.sp3.action == 'reused' and result.sp3.path == sp3 and result.sp3.url is None
    assert result.clk.action == 'downloaded' and result.clk.url
    assert 'SP3 reused locally' in result.message and 'CLK downloaded' in result.message


def test_orbit_only_remote_success_not_reported_as_clock_download(downloader):
    def fetch(url,path):
        if '_ORB.SP3' in path.name:
            path.write_bytes(gzip.compress(sp3_text().encode('ascii')))
            return True,'Downloaded 1 MB'
        return False,'File not found (404)'
    downloader.download_file = fetch
    result = downloader.acquire_precise_products('CODE',PRECISE_DAY,'final')
    assert result.mode == 'precise_partial'
    assert result.sp3.action == 'downloaded' and result.clk.action == 'missing'
    assert 'CLK downloaded' not in result.message


@pytest.mark.parametrize('day',[date(2024,8,4),date(2024,8,8)])
def test_weekly_remote_fallback_includes_sunday(downloader,day):
    expected = 'EMR0OPSFIN_20242170000_07D_15M_ORB.SP3.gz'
    def fetch(url,path):
        if path.name == expected:
            path.write_bytes(gzip.compress(sp3_text().encode('ascii')))
            return True,'Downloaded'
        return False,'File not found (404)'
    downloader.download_file = fetch
    result = downloader.acquire_precise_products('EMR',day,'final',download_clk=False)
    assert result.success and result.sp3.path.name == expected


@pytest.mark.parametrize('error',['Authorization error (401)','Access denied (403)','Timeout',
                                 'Connection error','HTML login/error page returned'])
def test_transport_auth_failures_stop_after_one_request(downloader,error):
    calls=[]
    def fetch(url,path):
        calls.append(url)
        return False,error
    downloader.download_file=fetch
    downloader.download_broadcast=forbid_network
    ok,msg,mode = downloader.download_sp3_with_fallback('CODE',PRECISE_DAY,strict_center=False)
    assert not ok and mode == 'none' and len(calls) == 1
    assert error in msg


def test_request_budget_bounds_not_found_search(downloader):
    downloader.precise_max_attempts=3
    downloader.download_file=lambda *args: (False,'File not found (404)')
    result = downloader.acquire_precise_products('CODE',PRECISE_DAY,strict_center=False)
    assert not result.success and len(result.attempted_urls) == 3
    assert 'request limit' in result.message


def test_invalid_cache_not_reported_as_reused(downloader,write_product):
    path = write_product(text='<html>bad cache</html>')
    with pytest.warns(RuntimeWarning,match='invalid SP3 cache'):
        result = downloader.acquire_precise_products('CODE',PRECISE_DAY,allow_download=False)
    assert not result.success and result.sp3.path is None
    assert path.read_text() == '<html>bad cache</html>'


def test_ultra_names_and_archive_week_use_content_start(downloader):
    name = downloader.make_sp3_filename('IGS',date(2024,8,3),'ultra-rapid',hour=18)
    assert name == 'IGS0OPSULT_20242161800_02D_15M_ORB.SP3.gz'
    assert '/2325/' in downloader.build_sp3_url(name,date(2024,8,4))
    candidates = downloader._product_candidates('IGS','ultra-rapid',date(2024,8,4),'sp3')
    assert any('_20242161800_02D_15M_' in n for n,_ in candidates)
    assert not any('ULR' in n for n,_ in candidates)
    assert downloader.make_sp3_filename_legacy('CODE',PRECISE_DAY,'rapid') is None
    assert downloader.make_clk_filename('COD',PRECISE_DAY).startswith('COD0MGX')


class Response:
    def __init__(self,status=200,content=b'',content_type='application/octet-stream'):
        self.status_code=status; self.content=content
        self.headers={'content-type':content_type}
    def __enter__(self): return self
    def __exit__(self,*args): return False


@pytest.mark.parametrize('response',[
    Response(404,b'not found'), Response(401,b'login'),Response(403,b'blocked'),
    Response(200,b'<html>login</html>'),Response(200,b'garbage'),Response(200,b''),
    Response(200,b'#dP truncated file'),
])
def test_base_download_failure_never_leaves_success_cache(downloader,tmp_path,response):
    downloader.session.get=lambda *a,**k: response
    target=tmp_path/'new'/'EMR0OPSFIN_20242210000_01D_15M_ORB.SP3'
    ok,message=downloader.download_file('https://example.test/file',target)
    assert not ok and not target.exists()
    assert not list(tmp_path.rglob('*.part*'))


def test_atomic_download_repeat_reuses_and_preserves_original(downloader,tmp_path):
    data=gzip.compress(sp3_text().encode('ascii'))
    calls=[]
    downloader.session.get=lambda *a,**k:(calls.append(a[0]) or Response(content=data))
    target=tmp_path/'COD0MGXFIN_20242210000_01D_05M_ORB.SP3.gz'
    ok,msg=downloader.download_file('https://example.test/file',target)
    assert ok and msg.startswith('Downloaded') and target.read_bytes() == data
    ok,msg=downloader.download_file('https://example.test/file',target)
    assert ok and msg.startswith('Reused locally') and len(calls) == 1
    assert not list(tmp_path.glob('.*.part*'))


def test_failed_replacement_does_not_destroy_user_file(downloader,tmp_path):
    target=tmp_path/'COD0MGXFIN_20242210000_01D_05M_ORB.SP3'
    target.write_bytes(b'user incomplete copy')
    downloader.session.get=lambda *a,**k: Response(404)
    assert not downloader.download_file('https://example.test/file',target)[0]
    assert target.read_bytes() == b'user incomplete copy'


def test_base_transport_exceptions_are_reported(downloader,tmp_path):
    def get(*a,**k): raise requests.exceptions.Timeout('timeout')
    downloader.session.get=get
    assert downloader.download_file('https://example.test/file',tmp_path/'x.sp3') == (False,'Timeout')


def test_nonzero_local_version_does_not_fetch_zero_version_clock(downloader,write_product):
    orbit=write_product('COD1MGXFIN_20242210000_01D_05M_ORB.SP3')
    downloader.download_file=forbid_network
    result=downloader.acquire_precise_products('COD1MGXFIN',PRECISE_DAY)
    assert result.sp3.path==orbit and result.clk.path is None
    assert result.mode=='precise_partial' and not result.attempted_urls
