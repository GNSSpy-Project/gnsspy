"""Actual interpolation tests against an independent synthetic polynomial."""
from datetime import timedelta
from pathlib import Path
import gzip

import numpy as np
import pandas as pd
import pytest

from conftest import PRECISE_DAY, precise_xyz, precise_velocity, sp3_text, clk_text
from gnsspy.orbit.precise import sp3_interp
from gnsspy.orbit.comparison import run_sp3_interp, discover_files, filter_sp3_by_date


@pytest.mark.parametrize('input_interval',[300,900])
@pytest.mark.parametrize('output_interval',[30,37,7.5])
def test_real_epoch_evaluation_and_velocity_not_fixed_15m(write_product,tmp_path,input_interval,output_interval):
    rate = '05M' if input_interval == 300 else '15M'
    path = write_product(f'COD0MGXFIN_20242210000_01D_{rate}_ORB.SP3',interval=input_interval)
    result = sp3_interp(PRECISE_DAY,interval=output_interval,poly_degree=3,
                        data_dir=tmp_path,clock_product=None,verbose=False)
    times = result.index.get_level_values('Epoch')
    seconds = (times-pd.Timestamp(PRECISE_DAY)).total_seconds().to_numpy()
    np.testing.assert_allclose(result[['X','Y','Z']],precise_xyz(seconds),rtol=0,atol=.002)
    np.testing.assert_allclose(result[['Vx','Vy','Vz']],precise_velocity(seconds),rtol=0,atol=2e-6)
    assert len(times) == len(np.arange(0,86400,output_interval))
    assert result.attrs['input_intervals_seconds'][str(path)] == input_interval
    assert not result.attrs['extrapolated'] and result.index.is_unique


def test_name_sampling_not_used_to_interpret_content(write_product,tmp_path):
    write_product('EMR0OPSFIN_20242210000_01D_15M_ORB.SP3',interval=300)
    result = sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,clock_product=None,verbose=False)
    assert list(result.attrs['input_intervals_seconds'].values()) == [300]


def test_no_neighbour_files_no_network_no_renaming(write_product,tmp_path,monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session,'request',lambda *a,**k: pytest.fail('network'))
    path = write_product('EMR0OPSFIN_20242210000_01D_15M_ORB.SP3',interval=900,include_endpoint=False)
    before = path.read_bytes()
    with pytest.warns(RuntimeWarning,match='No extrapolation'):
        result = sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,clock_product=None,verbose=False)
    assert result.attrs['missing_orbit_rows'] == 29
    assert result.loc[(pd.Timestamp('2024-08-08 23:45:00'),'G01'),'X'] == pytest.approx(precise_xyz(85500)[0],abs=.002)
    assert result.loc[(pd.Timestamp('2024-08-08 23:45:30'),'G01'),'X'] != result.loc[(pd.Timestamp('2024-08-08 23:45:30'),'G01'),'X']
    assert path.read_bytes() == before and list(tmp_path.iterdir()) == [path]


def test_gaps_are_not_interpolated_across(write_product,tmp_path):
    write_product(interval=300,missing=((43200,46800),))
    with pytest.warns(RuntimeWarning,match='gaps'):
        result=sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,clock_product=None,verbose=False)
    gap = result.loc[pd.IndexSlice[pd.Timestamp('2024-08-08 12:00'):pd.Timestamp('2024-08-08 13:00'),:],:]
    assert gap.X.isna().all()
    assert np.isfinite(result.loc[(pd.Timestamp('2024-08-08 10:00'),'G01'),'X'])


def test_only_consistent_neighbouring_series_used(write_product,tmp_path):
    primary=write_product('COD0MGXFIN_20242210000_01D_15M_ORB.SP3',interval=900,include_endpoint=False)
    rapid=write_product('COD0MGXRAP_20242220000_01D_05M_ORB.SP3',start=PRECISE_DAY+timedelta(days=1))
    other=write_product('EMR0OPSFIN_20242220000_01D_15M_ORB.SP3',start=PRECISE_DAY+timedelta(days=1),interval=900)
    with pytest.warns(RuntimeWarning):
        result=sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,clock_product=None,verbose=False)
    assert result.attrs['sp3_files'] == [str(primary)] and result.attrs['missing_orbit_rows'] == 29
    next_file=write_product('COD0MGXFIN_20242220000_01D_05M_ORB.SP3',start=PRECISE_DAY+timedelta(days=1))
    result=sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,clock_product=None,verbose=False)
    assert result.attrs['sp3_files'] == [str(primary),str(next_file)]
    assert result.attrs['missing_orbit_rows'] == 0
    seconds=(result.index.get_level_values('Epoch')-pd.Timestamp(PRECISE_DAY)).total_seconds()
    np.testing.assert_allclose(result[['X','Y','Z']],precise_xyz(seconds),rtol=0,atol=.002)


def test_original_paths_full_pipeline_compressed_or_nonstandard(write_product,tmp_path):
    orbit=write_product('my_orbit.sp3.gz')
    clock=write_product('my_clock.clk.gz')
    result=sp3_interp(PRECISE_DAY,sp3_files=[orbit],clk_files=[clock],poly_degree=3,
                      data_dir=tmp_path,verbose=False)
    assert result.attrs['sp3_files'] == [str(orbit)]
    assert result.DeltaTSV.notna().all()
    assert set(tmp_path.iterdir()) == {orbit,clock}


def test_actual_comparison_wrapper_has_no_staging_or_renaming(write_product,tmp_path):
    orbit=write_product('COD0MGXFIN_20242210000_01D_05M_ORB.SP3.gz')
    clock=write_product('COD0MGXFIN_20242210000_01D_30S_CLK.CLK.gz')
    result=run_sp3_interp(PRECISE_DAY,[orbit],[clock],str(tmp_path),poly_degree=3)
    assert result.attrs['missing_orbit_rows'] == 0
    assert set(tmp_path.iterdir()) == {orbit,clock}


def test_clock_missing_records_remain_nan_do_not_remove_orbits(write_product,tmp_path):
    write_product()
    write_product('COD0MGXFIN_20242210000_01D_30S_CLK.CLK',missing=((30.,'G01'),(60.,'G01')))
    result=sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,verbose=False)
    assert len(result) == 2880 and result.X.notna().all()
    assert result.DeltaTSV.isna().sum() == 2
    with pytest.raises(ValueError,match='CLK does not cover'):
        sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,require_clock=True,verbose=False)


def test_clock_auto_does_not_select_other_series(write_product,tmp_path):
    write_product()
    write_product('EMR0OPSFIN_20242210000_01D_30S_CLK.CLK')
    with pytest.warns(RuntimeWarning,match='No matching CLK'):
        result=sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,verbose=False)
    assert result.X.notna().all() and result.DeltaTSV.isna().all()
    with pytest.raises(FileNotFoundError,match='No matching CLK'):
        sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,require_clock=True,verbose=False)


def test_explicit_different_clock_series_warns(write_product,tmp_path):
    write_product()
    write_product('EMR0OPSFIN_20242210000_01D_30S_CLK.CLK')
    with pytest.warns(RuntimeWarning,match='Explicit CLK series differs'):
        result=sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,clock_product='EMR',verbose=False)
    assert result.DeltaTSV.notna().all()


@pytest.mark.parametrize('time_system',['UTC','BDT','GLO'])
def test_time_scale_not_silently_relabelled_gps(write_product,tmp_path,time_system):
    write_product(time_system=time_system)
    with pytest.raises(ValueError,match='time system'):
        sp3_interp(PRECISE_DAY,data_dir=tmp_path,clock_product=None,verbose=False)


@pytest.mark.parametrize('kwargs',[{'interval':0},{'interval':-30},{'interval':float('nan')},
    {'interval':float('inf')},{'poly_degree':17},{'poly_degree':0},{'poly_degree':3.5},
    {'require_clock':True,'clock_product':None}])
def test_bad_arguments_fail_early(tmp_path,kwargs):
    with pytest.raises(ValueError):
        sp3_interp(PRECISE_DAY,data_dir=tmp_path,verbose=False,**kwargs)


def test_no_products_fail_fast_without_network(tmp_path,monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session,'request',lambda *a,**k: pytest.fail('network'))
    with pytest.raises(FileNotFoundError,match='No network request'):
        sp3_interp(PRECISE_DAY,data_dir=tmp_path,verbose=False)


def test_discovery_and_date_filter_support_compressed_and_weekly(write_product,tmp_path):
    orbit=write_product('EMR0OPSFIN_20242170000_07D_15M_ORB.SP3.gz')
    clock=write_product('COD0MGXFIN_20242210000_01D_30S_CLK.CLK.gz')
    nav,sp3,clk=discover_files(str(tmp_path))
    assert not nav and sp3 == [str(orbit)] and clk == [str(clock)]
    assert filter_sp3_by_date(sp3,PRECISE_DAY) == sp3


def test_manoeuvre_flag_splits_orbit_fit(write_product,tmp_path):
    path=write_product(interval=300)
    lines=path.read_text().splitlines()
    marked=False
    for i,line in enumerate(lines):
        if line.startswith('*') and [int(v) for v in line.split()[4:6]] == [12,0]:
            record=lines[i+1].ljust(80)
            lines[i+1]=record[:78]+'M'+record[79:]
            marked=True
            break
    assert marked
    path.write_text('\n'.join(lines)+'\n')
    with pytest.warns(RuntimeWarning):
        result=sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,clock_product=None,verbose=False)
    assert result.attrs['manoeuvre_boundaries'] == [('G01','2024-08-08T12:00:00')]
    gap=result.loc[pd.IndexSlice['2024-08-08 11:55:30':'2024-08-08 11:59:30',:],:]
    assert len(gap)==9 and gap[['X','Y','Z']].isna().all().all()
    assert result.loc[(pd.Timestamp('2024-08-08 12:00:00'),'G01'),'X'] == pytest.approx(precise_xyz(43200)[0],abs=.002)


def test_strict_edges_excluded_but_default_warns(write_product,tmp_path):
    write_product(interval=900)
    with pytest.warns(RuntimeWarning,match='edge fits'):
        default=sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,clock_product=None,verbose=False)
    with pytest.warns(RuntimeWarning,match='strict edge filtering'):
        strict=sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,clock_product=None,
                          edge_policy='strict',verbose=False)
    assert default.X.notna().all() and default.attrs['edge_fit_rows']==119
    assert strict.attrs['strict_edge_rows_removed']==119 and strict.attrs['edge_fit_rows']==0
    assert strict.X.isna().sum()==119
    supported=strict.X.notna()
    np.testing.assert_array_equal(strict.loc[supported,'X'],default.loc[supported,'X'])


def test_neighbours_supply_strict_edge_buffers(write_product,tmp_path):
    for offset,doy in [(-1,220),(0,221),(1,222)]:
        write_product(f'COD0MGXFIN_2024{doy:03d}0000_01D_15M_ORB.SP3',
                      start=PRECISE_DAY+timedelta(days=offset),interval=900)
    result=sp3_interp(PRECISE_DAY,data_dir=tmp_path,poly_degree=3,clock_product=None,
                      edge_policy='strict',verbose=False)
    assert result.X.notna().all() and result.attrs['strict_edge_rows_removed']==0


@pytest.mark.parametrize('kwargs',[{'interval':True},{'edge_policy':'unchecked'}])
def test_additional_bad_arguments(tmp_path,kwargs):
    with pytest.raises(ValueError):
        sp3_interp(PRECISE_DAY,data_dir=tmp_path,verbose=False,**kwargs)
