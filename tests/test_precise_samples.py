"""SP3 and CLK integration tests using files in GNSSPY_TEST_PRODUCT_DIR."""
import hashlib
import os
from pathlib import Path
from datetime import date

import numpy as np
import pandas as pd
import pytest

from gnsspy.io.products.sp3 import read_sp3File
from gnsspy.io.products.clk import read_clockFile
from gnsspy.orbit.precise import sp3_interp
from gnsspy.orbit.comparison import run_sp3_interp
from gnsspy.data_access.products import NavigationDownloader

NAMES = ('COD0MGXFIN_20242210000_01D_05M_ORB.SP3',
         'COD0MGXFIN_20242210000_01D_30S_CLK.CLK',
         'EMR0OPSFIN_20242170000_01D_15M_ORB.SP3')


@pytest.fixture(scope='module')
def sample_dir():
    folder = os.environ.get('GNSSPY_TEST_PRODUCT_DIR')
    if not folder:
        pytest.skip('Set GNSSPY_TEST_PRODUCT_DIR to run the three supplied real products')
    folder=Path(folder).resolve()
    for name in NAMES:
        if not (folder/name).is_file():
            pytest.fail(f'Missing requested real-data fixture: {folder/name}')
    return folder


@pytest.fixture(scope='module')
def code_result(sample_dir):
    from unittest.mock import patch
    with patch('requests.sessions.Session.request',side_effect=AssertionError('Network is disabled')):
        return sp3_interp(date(2024,8,8),data_dir=sample_dir,verbose=False)


@pytest.mark.parametrize('name,epochs,satellites,interval',[
    (NAMES[0],289,121,300),(NAMES[2],96,31,900)])
def test_actual_sp3_records_match_independent_text_counts(sample_dir,name,epochs,satellites,interval):
    path=sample_dir/name
    raw=path.read_text().splitlines()
    frame=read_sp3File(path,verbose=False)
    assert len(frame) == sum(line.startswith('P') for line in raw)
    assert frame.index.get_level_values('Epoch').nunique() == epochs
    assert frame.index.get_level_values('SV').nunique() == satellites
    assert frame.attrs['observed_intervals_seconds'] == (float(interval),)

    first=next(line for line in raw if line.startswith('P'))
    key=(frame.index.get_level_values('Epoch').min(),first[1:4])
    expected=[float(first[a:b]) for a,b in [(4,18),(18,32),(32,46)]]
    np.testing.assert_allclose(frame.loc[key,['X','Y','Z']].to_numpy(dtype=float),expected,rtol=0,atol=0)


def test_actual_clock_records_and_units(sample_dir):
    path=sample_dir/NAMES[1]
    frame=read_clockFile(path,verbose=False)
    with path.open() as stream:
        as_rows=[line.split() for line in stream if line.startswith('AS ')]
    assert len(frame) == len(as_rows) == 348471
    assert frame.index.nunique() == 121
    assert frame.DeltaTSV.iloc[0] == float(as_rows[0][9])
    assert frame.attrs['clock_unit'] == 'seconds'


def test_code_full_day_interpolates_30s_without_renaming(code_result,sample_dir):
    assert code_result.shape == (348480,7)
    assert code_result.attrs['missing_orbit_rows'] == 9
    assert code_result[['X','Y','Z','Vx','Vy','Vz']].notna().all(axis=1).sum() == 348471
    assert code_result.index.get_level_values('Epoch').nunique() == 2880
    assert code_result.attrs['sp3_files'] == [str(sample_dir/NAMES[0])]
    assert code_result.attrs['clk_files'] == [str(sample_dir/NAMES[1])]
    radii=np.linalg.norm(code_result[['X','Y','Z']].to_numpy(),axis=1)
    assert np.nanmin(radii) > 2e7 and np.nanmax(radii) < 5e7


def test_nine_missing_clock_records_not_lost_or_fabricated(code_result,sample_dir):
    clocks=read_clockFile(sample_dir/NAMES[1],verbose=False).reset_index().set_index(['Epoch','SV'])
    absent=code_result.index.difference(clocks.index)
    assert len(absent) == 9
    assert code_result.loc[absent,'DeltaTSV'].isna().all()
    assert len(code_result.loc[absent]) == 9
    common=code_result.index.intersection(clocks.index)
    np.testing.assert_array_equal(code_result.loc[common,'DeltaTSV'],clocks.loc[common,'DeltaTSV'])


def test_emr_15m_file_never_extrapolates_beyond_2345(sample_dir):
    with pytest.warns(RuntimeWarning,match='899 orbit rows'):
        frame=sp3_interp(date(2024,8,4),data_dir=sample_dir,clock_product=None,verbose=False)
    assert frame.shape == (89280,7)
    assert frame.attrs['missing_orbit_rows'] == 899
    late=frame.index.get_level_values('Epoch') > pd.Timestamp('2024-08-04 23:45:00')
    assert late.sum() == 899 and frame.loc[late,'X'].isna().all()
    assert frame.loc[~late,['X','Y','Z']].notna().all().all()


def test_real_cache_reports_reuse_and_zero_requests(sample_dir,monkeypatch):
    downloader=NavigationDownloader(None,None,sample_dir)
    monkeypatch.setattr(downloader,'download_file',lambda *a,**k: pytest.fail('network'))
    before={name:hashlib.sha256((sample_dir/name).read_bytes()).hexdigest() for name in NAMES}
    for _ in range(2):
        result=downloader.acquire_precise_products('CODE',date(2024,8,8))
        assert result.sp3.action == result.clk.action == 'reused'
        assert not result.attempted_urls
    after={name:hashlib.sha256((sample_dir/name).read_bytes()).hexdigest() for name in NAMES}
    assert before == after


def test_comparison_wrapper_uses_real_original_products(sample_dir):
    frame=run_sp3_interp(date(2024,8,8),[sample_dir/NAMES[0]],[sample_dir/NAMES[1]],str(sample_dir),poly_degree=16)
    assert frame.attrs['missing_orbit_rows'] == 9 and frame.attrs['missing_clock_rows'] == 9


def test_code_manoeuvre_and_source_epoch_fit_residual(code_result,sample_dir):
    assert code_result.attrs['manoeuvre_boundaries']==[('G13','2024-08-08T15:50:00')]
    absent=code_result[code_result.X.isna()].index
    assert len(absent)==9 and set(absent.get_level_values('SV'))=={'G13'}
    assert absent.get_level_values('Epoch').min()==pd.Timestamp('2024-08-08 15:45:30')
    raw=read_sp3File(sample_dir/NAMES[0],verbose=False)
    common=raw.index.intersection(code_result.index)
    delta=code_result.loc[common,['X','Y','Z']].to_numpy()-raw.loc[common,['X','Y','Z']].to_numpy()*1000.
    residual=np.linalg.norm(delta,axis=1)
    assert np.isfinite(residual).all()
    assert np.sqrt(np.mean(residual**2)) < .001
    assert residual.max() < .005
