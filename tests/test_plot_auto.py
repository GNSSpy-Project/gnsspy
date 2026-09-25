"""Regression tests deliberately unlike the old all-S1C synthetic fixtures."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pandas as pd
import pytest

from gnsspy.visualization import (skyplot, azelplot, timelplot, bandplot,
                                  time_elevation_plot, snr_time_series_plot)
from gnsspy.visualization._observations import observations, select_snr, snr_columns, geometry


@pytest.fixture
def mixed():
    times = pd.date_range('2025-02-11', periods=7, freq='30s')
    index = pd.MultiIndex.from_product([times, ['G01','E11','C19']], names=['Epoch','SV'])
    frame = pd.DataFrame(np.nan, index=index, columns=['S1C','S1X','S2I','S5Q'])
    for sv, code, values in [('G01','S1C',[31,32,0,34,np.nan,36,37]),
                              ('E11','S1X',[41,42,43,44,45,46,47]),
                              ('C19','S2I',[51,52,53,54,55,56,57])]:
        frame.loc[pd.IndexSlice[:,sv],code] = values
    frame['SYSTEM'] = ['GPS','GALILEO','COMPASS']*7
    frame['SSI'] = 9
    frame.attrs.update(time_system='GPS', signal_strength_unit='DBHZ')
    station = SimpleNamespace(observation=frame, approx_position=[6378137.,0.,0.], filename='MIXED.rnx',
                              interval=30., epoch=times[0], version='3.04')
    orbit = pd.DataFrame({'X':np.repeat(26560000.,len(index)), 'Y':np.tile([1e6,2e6,3e6],7),
                          'Z':np.repeat(5e6,len(index))},index=index)
    orbit.attrs.update(position_unit='m', time_system='GPS')
    return station,orbit


def test_native_code_selection_not_first_column(mixed):
    st,_=mixed
    chosen,details,missing=select_snr(observations(st,'auto'))
    assert chosen=={'C19':'S2I','E11':'S1X','G01':'S1C'}
    assert details['G01']['valid_samples']==5 and not missing
    assert 'SYSTEM' not in snr_columns(st.observation)
    assert 'SSI' not in snr_columns(st.observation)


@pytest.mark.parametrize('fn',[skyplot,azelplot])
def test_auto_sky_markers_match_native_values(mixed,fn):
    st,orb=mixed; before=deepcopy(st.observation)
    fig=fn(st,orb,system='auto',sv_list='auto',color_mode='auto')
    assert fig.layout.coloraxis.cmax==57
    for trace in fig.data:
        if trace.mode!='markers': continue
        sv=trace.legendgroup
        code=fig.layout.meta['snr_selection'][sv]['code']
        expected=st.observation.xs(sv,level='SV')[code]
        expected=expected[np.isfinite(expected)&(expected>0)]
        np.testing.assert_array_equal(trace.marker.color,expected)
        assert trace.marker.coloraxis=='coloraxis'
        assert code in trace.name
    pd.testing.assert_frame_equal(before,st.observation)


@pytest.mark.parametrize('selection',['auto','ALL','G+E+C','G,E,C',None,['G','E','C']])
def test_system_selection_consistent(mixed,selection):
    st,_=mixed
    fig=timelplot(st,system=selection)
    assert len(fig.data)==3
    assert len(bandplot(st,system=selection).data)==3


def test_single_string_satellite_selection(mixed):
    st,orb=mixed
    assert len(skyplot(st,orb,system='auto',sv_list='E11').data)==2


def test_coverage_and_priority_deterministic(mixed):
    st,_=mixed
    st.observation.loc[pd.IndexSlice[:,'G01'],'S5Q']=40.
    chosen,_,_=select_snr(observations(st,'G'))
    assert chosen['G01']=='S5Q'
    st.observation.loc[pd.IndexSlice[:,'G01'],'S1C']=35.
    chosen,_,_=select_snr(observations(st,'G'))
    assert chosen['G01']=='S1C'


def test_explicit_code_is_strict(mixed):
    st,orb=mixed
    with pytest.raises(ValueError,match='requested S1C'):
        skyplot(st,orb,system='E',snr_code='S1C')
    fig=skyplot(st,orb,system='auto',snr_code={'G':'S1C','E':'S1X','C':'S2I'})
    assert len(fig.layout.meta['snr_selection'])==3


@pytest.mark.parametrize('fn',[skyplot,azelplot])
def test_missing_snr_never_falls_back_to_elevation(mixed,fn):
    st,orb=mixed
    st.observation.loc[:,'S1X']=np.nan
    with pytest.warns(RuntimeWarning,match='No usable SNR'):
        fig=fn(st,orb,system='auto')
    assert 'E11' in fig.layout.meta['skipped_snr']
    assert all(t.legendgroup!='E11' for t in fig.data)
    with pytest.warns(RuntimeWarning),pytest.raises(RuntimeError,match='No plottable'):
        fn(st,orb,system='E')


def test_no_smoothing_or_gap_bridging(mixed):
    st,_=mixed
    fig=snr_time_series_plot(st,system='G')
    ys=list(fig.data[0].y)
    assert ys==[31.,32.,None,34.,None,36.,37.]
    assert fig.data[0].connectgaps is False
    assert fig.layout.xaxis.title.text=='Time (GPST)'


def test_missing_epoch_breaks_using_native_interval(mixed):
    st,_=mixed
    st.observation=st.observation.drop((pd.Timestamp('2025-02-11 00:00:30'),'E11'))
    fig=timelplot(st,system='E')
    assert list(fig.data[0].y)[:3]==[41.,None,43.]


def test_named_alias_default_and_snr_overlay(mixed):
    st,orb=mixed
    fig=time_elevation_plot(st,orb,system='E')
    assert fig.layout.yaxis.title.text=='Elevation (°)'
    fig=time_elevation_plot(st,orb,system='E',color_mode='snr')
    np.testing.assert_array_equal(fig.data[1].marker.color,[41,42,43,44,45,46,47])
    assert fig.layout.yaxis.title.text=='Elevation (°)'
    fig=bandplot(st,system='E',color_mode='snr')
    np.testing.assert_array_equal(fig.data[0].marker.color,[41,42,43,44,45,46,47])


@pytest.mark.parametrize('bad',['SNAR','multipath','elevetion'])
def test_invalid_colour_not_silently_elevation(mixed,bad):
    st,orb=mixed
    with pytest.raises(ValueError,match='Mode must'):
        skyplot(st,orb,color_mode=bad)


def test_native_sp3_km_geometry_without_velocity(mixed):
    st,orb=mixed
    reference=geometry(st,orb,observations(st,'auto'))
    km=orb/1000.;km.attrs.update(orb.attrs);km.attrs['position_unit']='km'
    actual=geometry(st,km,observations(st,'auto'))
    np.testing.assert_allclose(actual.Elevation,reference.Elevation)


def test_time_scale_mismatch_stops(mixed):
    st,orb=mixed;orb.attrs['time_system']='UTC'
    with pytest.raises(ValueError,match='time system'):
        skyplot(st,orb)


def test_rinex2_and_legacy_alias_provenance(mixed):
    st,_=mixed
    st.observation=st.observation.rename(columns={'S1C':'S1','S1X':'S5'})
    assert select_snr(observations(st,'G'))[0]['G01']=='S1'
    from gnsspy.io.manipulate import standardize_snr
    st.observation=st.observation.drop(columns='S1')
    import warnings

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        standardize_snr(st, 'auto')

    assert any(
        issubclass(w.category, DeprecationWarning)
        for w in caught
    )
    assert any(
        issubclass(w.category, RuntimeWarning)
        for w in caught
    )
    assert 'S1C' in st.observation.attrs['gnsspy_snr_aliases']
    assert 'S1C' not in snr_columns(st.observation)
    assert select_snr(observations(st,'E'))[0]['E11']=='S5'


def test_groundtrack_auto_system_and_satellite(mixed):
    from gnsspy.visualization._maps import prepare_tracks
    _, orbit = mixed
    actual = prepare_tracks(orbit, system="auto", sv_list="auto")
    assert set(actual) == {"G01", "E11", "C19"}


@pytest.mark.parametrize('view',['skyplot','azelplot','elevation','snr','bandplot'])
def test_observation_plots_can_write_html_and_png(mixed,view,tmp_path,monkeypatch):
    import plotly.graph_objects as go
    station,orbit=mixed
    html=tmp_path/f'{view}.html'

    def fake_write_image(self,file,format=None,scale=None,**kwargs):
        assert format=='png' and scale==2.0
        Path(file).write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')

    monkeypatch.setattr(go.Figure,'write_image',fake_write_image)
    if view=='skyplot':
        skyplot(station,orbit,system='auto',save_path=html,png_path=True)
    elif view=='azelplot':
        azelplot(station,orbit,system='auto',save_path=html,png_path=True)
    elif view=='bandplot':
        bandplot(station,system='auto',save_path=html,png_path=True)
    else:
        timelplot(station,orbit,system='auto',mode=view,save_path=html,png_path=True)
    assert html.stat().st_size>1000
    assert html.with_suffix('.png').read_bytes().startswith(b'\x89PNG')


def test_png_output_validation(mixed,tmp_path):
    station,_=mixed
    with pytest.raises(ValueError,match='requires save_path'):
        bandplot(station,png_path=True)
    with pytest.raises(ValueError,match=r'\.png suffix'):
        bandplot(station,png_path=tmp_path/'plot.jpg')
    with pytest.raises(ValueError,match='png_scale'):
        bandplot(station,png_path=tmp_path/'plot.png',png_scale=0)


def test_png_export_failure_preserves_html(mixed,tmp_path,monkeypatch):
    import plotly.graph_objects as go
    station,_=mixed
    html=tmp_path/'visibility.html'

    def fail_write_image(*args,**kwargs):
        raise RuntimeError('renderer unavailable')

    monkeypatch.setattr(go.Figure,'write_image',fail_write_image)
    with pytest.raises(RuntimeError,match='plotly-png'):
        bandplot(station,save_path=html,png_path=True)
    assert html.stat().st_size>1000
