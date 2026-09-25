"""Filename metadata, local resolution and content-reader regression tests."""
from datetime import date, datetime, timedelta
from pathlib import Path
import gzip

import numpy as np
import pandas as pd
import pytest

from conftest import PRECISE_DAY, sp3_text, clk_text
from gnsspy.utils.product_files import (
    parse_product_name, find_product_files, resolve_product_path,
    product_kind, long_product_filename, token_seconds, validate_product_file,
)
from gnsspy.utils.filename import sp3FileName, clockFileName
from gnsspy.io.products.sp3 import read_sp3File
from gnsspy.io.products.clk import read_clockFile


@pytest.mark.parametrize('rate,seconds',[('05M',300),('15M',900),('05m',300),('15m',900),('30S',30)])
@pytest.mark.parametrize('extension',['.SP3','.sp3','.SP3.gz','.sp3.GZ','.SP3.Z','.SP3.bz2','.SP3.xz'])
def test_long_names_sampling_case_and_compression(rate,seconds,extension):
    info = parse_product_name(f'COD0MGXFIN_20242210000_01D_{rate}_ORB{extension}')
    assert info.center == 'COD' and info.project == 'MGX' and info.solution == 'FIN'
    assert info.start == PRECISE_DAY
    assert token_seconds(info.sampling) == seconds
    assert info.end == PRECISE_DAY+timedelta(days=1)


@pytest.mark.parametrize('name',[
 'COD0MGXFIN_20233660000_01D_05M_ORB.SP3',
 'COD0MGXFIN_20240000000_01D_05M_ORB.SP3',
 'COD0MGXFIN_20242212460_01D_05M_ORB.SP3',
 'COD0MGXFIN_20242210000_01D_05M_CLK.SP3',
 'unrelated.txt','COD0MGXFIN_20242210000_01D_05M_ORB.SP3.part',
])
def test_reject_invalid_product_names(name):
    assert parse_product_name(name) is None


def test_legacy_weekly_ultra_and_cross_year():
    assert parse_product_name('igs23264.sp3.Z').start == PRECISE_DAY
    weekly = parse_product_name('igs23267.sp3')
    assert weekly.start == datetime(2024,8,4) and weekly.duration == '07D'
    old = parse_product_name('igu23260_06.sp3.Z')
    new = parse_product_name('IGS0OPSULT_20242160600_02D_15M_ORB.SP3.gz')
    assert old.start == new.start == datetime(2024,8,3,6)
    assert parse_product_name('COD0MGXFIN_20243660000_01D_05M_ORB.SP3').start == datetime(2024,12,31)
    assert product_kind('cod23264.clk_05s.Z') == 'clk'


@pytest.mark.parametrize('center,agency',[('CODE','COD'),('cod','COD'),('EMR','EMR'),('GFZ','GFZ'),('ESA','ESA'),('igs','IGS')])
def test_generators_do_not_change_centres_or_depend_on_age(center,agency):
    assert sp3FileName(date.today(),center).startswith(agency)
    assert clockFileName(PRECISE_DAY,product=center).startswith(agency)
    assert 'OPSRAP' in sp3FileName(date.today(),'igr')
    assert 'OPSULT' in sp3FileName(date.today(),'igu')


def test_generator_full_series_and_custom_tokens():
    assert sp3FileName(PRECISE_DAY,'COD0MGXFIN',sampling='15M') == 'COD0MGXFIN_20242210000_01D_15M_ORB.SP3'
    assert long_product_filename(PRECISE_DAY,center='EMR',solution='ultra-rapid',hour=6) == 'EMR0OPSULT_20242210600_02D_15M_ORB.SP3'
    with pytest.raises(ValueError):
        sp3FileName(PRECISE_DAY,'auto')


@pytest.mark.parametrize('folder',['','sp3/','data/sp3/','output/sp3/','output/data/sp3/'])
def test_flat_and_product_directories(write_product,tmp_path,folder):
    path = write_product(folder+'EMR0OPSFIN_20242210000_01D_15M_ORB.SP3')
    matches = find_product_files(PRECISE_DAY,'sp3',data_dir=tmp_path)
    assert [info.path for info in matches] == [path]


def test_resolution_needs_no_case_or_sampling_rename(write_product,tmp_path):
    path = write_product('sp3/cod0mgxfin_20242210000_01d_05m_orb.sp3.GZ')
    requested = tmp_path/'COD0MGXFIN_20242210000_01D_15M_ORB.SP3'
    assert resolve_product_path(requested,data_dir=tmp_path) == path
    assert not requested.exists()
    assert resolve_product_path('cod23264.sp3',data_dir=tmp_path) == path
    with pytest.raises(FileNotFoundError):
        resolve_product_path('EMR0OPSFIN_20242210000_01D_15M_ORB.SP3',data_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        resolve_product_path('COD0MGXRAP_20242210000_01D_05M_ORB.SP3',data_dir=tmp_path)


def test_discovery_respects_year_week_span_quality_and_centres(write_product,tmp_path):
    final = write_product('sp3/EMR0OPSFIN_20242210000_01D_15M_ORB.SP3')
    rapid = write_product('COD0MGXRAP_20242210000_01D_05M_ORB.SP3')
    write_product('COD0MGXULT_20242210000_02D_05M_ORB.SP3')
    write_product('COD0MGXFIN_20232210000_01D_05M_ORB.SP3')
    weekly = write_product('COD0MGXFIN_20242170000_07D_05M_ORB.SP3')
    found = find_product_files(PRECISE_DAY,'sp3',data_dir=tmp_path)
    assert {info.path for info in found[:2]} == {final,weekly}
    assert find_product_files(PRECISE_DAY,'sp3','COD','rapid',tmp_path)[0].path == rapid


@pytest.mark.parametrize('suffix',['','.gz','.GZ','.bz2','.xz'])
def test_readers_read_content_compressed_or_renamed(write_product,tmp_path,suffix):
    sp3 = write_product('arbitrary_name.sp3'+suffix,interval=900,length=3600)
    clk = write_product('arbitrary_name.clk'+suffix,length=3600)
    orbit = read_sp3File(sp3,verbose=False)
    clocks = read_clockFile(clk,verbose=False)
    assert len(orbit) == 5 and len(clocks) == 120
    assert orbit.attrs['observed_intervals_seconds'] == (900.,)
    assert orbit.attrs['position_unit'] == 'km' and clocks.attrs['clock_unit'] == 'seconds'
    assert validate_product_file(sp3,'sp3') and validate_product_file(clk,'clk')
    assert len(list(tmp_path.iterdir())) == 2


def test_fractional_epochs_and_clock_d_exponents(write_product):
    start = PRECISE_DAY+timedelta(microseconds=500000)
    sp3 = write_product(text=sp3_text(start,length=1800))
    clk = write_product('clock.clk',text=clk_text(start,length=60).replace('E-','D-'))
    assert read_sp3File(sp3,verbose=False).index[0][0] == start
    assert read_clockFile(clk,verbose=False).Epoch.iloc[0] == start
    assert read_clockFile(clk,verbose=False).DeltaTSV.iloc[0] == 1e-4


def test_sp3_optional_fields_blanks_and_missing_clock(write_product):
    text = sp3_text(length=0)
    lines = text.splitlines()
    i = next(i for i,line in enumerate(lines) if line.startswith('PG01'))
    row = lines[i][:46]+' 999999.999999'
    row = row.ljust(61)+' 2'+' '+' 3'+' '+' 4'+' '+'  5'+' '+'EP  MP'
    lines[i] = row
    path = write_product(text='\n'.join(lines)+'\n')
    frame = read_sp3File(path,verbose=False)
    assert np.isnan(frame.deltaT.iloc[0])
    assert frame.sigmaX.iloc[0] == 2
    assert frame.clock_event.iloc[0] and frame.clock_predicted.iloc[0]
    assert frame.orbit_manoeuvre.iloc[0] and frame.orbit_predicted.iloc[0]


@pytest.mark.parametrize('bad',['<html>error</html>','#dP truncated\n','garbage\n'])
def test_bad_sp3_fails_without_unbounded_header_loop(write_product,bad):
    path = write_product(text=bad)
    assert not validate_product_file(path)
    with pytest.raises(ValueError):
        read_sp3File(path,verbose=False)


def test_truncated_sp3_and_malformed_clk_have_line_errors(write_product):
    path = write_product(text='#dP\n*  2024 08 08 00 00 0.000\nPG01   1.0\n')
    with pytest.raises(ValueError,match=r':3:.*truncated'):
        read_sp3File(path,verbose=False)
    clk = write_product('bad.clk',text=clk_text(length=30)+'AS G01 malformed\n')
    with pytest.raises(ValueError,match='invalid CLK AS record'):
        read_clockFile(clk,verbose=False)


def test_missing_clk_behaviour_and_reader_no_network(tmp_path,monkeypatch):
    import requests
    monkeypatch.setattr(requests.sessions.Session,'request',lambda *a,**k: pytest.fail('network'))
    with pytest.warns(RuntimeWarning,match='CLK file not found'):
        assert read_clockFile(tmp_path/'missing.clk',verbose=False).empty
    with pytest.raises(FileNotFoundError):
        read_clockFile(tmp_path/'missing.clk',missing='raise')
    with pytest.raises(FileNotFoundError):
        read_sp3File(tmp_path/'missing.sp3')


@pytest.mark.parametrize('interval,token',[(5,'05S'),(30,'30S'),(60,'01M'),(300,'05M'),(900,'15M')])
def test_clock_filename_sampling_matches_interval(interval,token):
    from gnsspy.utils.filename import clockFileName
    assert f'_{token}_CLK.CLK' in clockFileName(date(2024,8,8),interval=interval)


def test_legacy_helper_never_switches_code_rapid_to_igs():
    from gnsspy.utils.filename import sp3FileName
    with pytest.raises(ValueError,match='only defined here for IGS'):
        sp3FileName(date(2020,1,1),product='CODE',solution='RAP')
