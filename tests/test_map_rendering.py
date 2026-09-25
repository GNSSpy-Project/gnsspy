"""Rendering integration; Cartopy tests are explicit skips when it is absent.

No Natural Earth downloads are needed for these automated tests. Run the demo
without --no-features separately to check real coastlines, borders and palette.
"""
import importlib.util
from pathlib import Path
import sys
import numpy as np
import pytest

from test_map_data import tiny_gim, orbit_at
from gnsspy.visualization import groundtrack, ionosphere_map, ionosphere_maps

HAS_CARTOPY=importlib.util.find_spec('cartopy') is not None
HAS_PLOTLY=importlib.util.find_spec('plotly') is not None
cartopy_only=pytest.mark.skipif(not HAS_CARTOPY,reason='Cartopy unavailable: actual map rendering not executed')
plotly_only=pytest.mark.skipif(not HAS_PLOTLY,reason='Plotly unavailable')


@pytest.fixture(scope='module')
def demo():
    import importlib.util
    source=Path(__file__).resolve().parents[1]/'examples'/'synthetic_data.py'
    spec=importlib.util.spec_from_file_location('gnsspy_synthetic_test',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


@plotly_only
def test_plotly_groundtrack_html_seams(tmp_path):
    fig=groundtrack(orbit_at([178,179,-179,-178]),backend='plotly',
                    save_path=tmp_path/'tracks',features=False)
    assert (tmp_path/'tracks.html').stat().st_size>1000
    assert fig.layout.geo.projection.type=='robinson'
    assert list(fig.data[0].lon).count(None)==2
    assert fig.data[0].connectgaps is False


@plotly_only
def test_plotly_gim_values_shared_scale_and_html(tmp_path):
    data=tiny_gim()
    fig=ionosphere_maps(data,backend='plotly',save_path=tmp_path/'tec.html',vmin=0,vmax=40)
    assert len(fig.data)==6
    assert fig.layout.coloraxis.cmin==0 and fig.layout.coloraxis.cmax==40
    for i,trace in enumerate(fig.data):
        np.testing.assert_allclose(trace.marker.color,data.tec[2*i,::-1,:-1].ravel())
        assert trace.marker.coloraxis=='coloraxis'
    assert '<html>' in (tmp_path/'tec.html').read_text()[:100]


@plotly_only
def test_plotly_regional_tec_enables_coordinate_graticules():
    fig=ionosphere_map(tiny_gim(),backend='plotly',projection='platecarree',
                       extent=(20,45,30,50))
    assert fig.layout.geo.lonaxis.showgrid is True
    assert fig.layout.geo.lataxis.showgrid is True
    global_fig=ionosphere_map(tiny_gim(),backend='plotly')
    assert global_fig.layout.geo.lonaxis.showgrid is False


@plotly_only
def test_plotly_rejects_cartopy_only_norm():
    with pytest.raises(ValueError,match='linear limits'):
        ionosphere_map(tiny_gim(),backend='plotly',norm=object())


@plotly_only
def test_synthetic_files_through_native_readers(tmp_path,demo):
    from gnsspy import read_sp3File,read_ionex
    orbit,gim,station=demo.make_demo_data()
    sp3,ionex=demo.write_sample_files(tmp_path,orbit,gim)
    raw=read_sp3File(sp3,verbose=False)
    read=read_ionex(ionex)
    assert raw.attrs['position_unit']=='km'
    np.testing.assert_allclose(read.tec,gim.tec,atol=.051,equal_nan=True)
    with pytest.warns(RuntimeWarning,match='invalid ECEF'):
        fig=groundtrack(raw,system=None,backend='plotly')
    assert sum(trace.name is not None for trace in fig.data)==7


@plotly_only
@pytest.mark.parametrize('view',['skyplot','azelplot','elevation','snr','bandplot'])
def test_non_geographic_figures_preserved(view,tmp_path,demo):
    from gnsspy.visualization import skyplot,azelplot,timelplot,bandplot
    orbit,gim,station=demo.make_demo_data()
    path=tmp_path/(view+'.html')
    if view=='skyplot': fig=skyplot(station,orbit,save_path=str(path))
    elif view=='azelplot': fig=azelplot(station,orbit,save_path=str(path))
    elif view=='bandplot': fig=bandplot(station,save_path=str(path))
    else: fig=timelplot(station,orbit,mode=view,save_path=str(path))
    assert fig is not None and len(fig.data)>0 and path.stat().st_size>1000
    for trace in fig.data:
        if trace.type=='scatter' and trace.x is not None and trace.y is not None:
            assert len(trace.x)==len(trace.y)
            if trace.marker.color is not None and not isinstance(trace.marker.color,str):
                assert len(trace.marker.color)==len(trace.x)


@plotly_only
def test_missing_snr_not_mislabeled_as_elevation(demo):
    from gnsspy.visualization import azelplot,skyplot
    orbit,gim,station=demo.make_demo_data()
    station.observation=station.observation[['SYSTEM']]
    for func in [azelplot,skyplot]:
        with pytest.warns(RuntimeWarning),pytest.raises(RuntimeError,match='No plottable'):
            func(station,orbit,color_mode='snr')


@plotly_only
def test_cli_real_file_round_trip_and_nonzero_failure(tmp_path,demo,capsys):
    from gnsspy.cli.maps import main
    orbit,gim,_=demo.make_demo_data()
    sp3,ionex=demo.write_sample_files(tmp_path/'data',orbit,gim)
    assert main(['groundtrack',str(sp3),'--backend','plotly','--system','G',
                 '--output',str(tmp_path/'g')])==0
    assert (tmp_path/'g.html').exists()
    assert main(['ionosphere',str(ionex),'--backend','plotly','--hours','0','12',
                 '--output',str(tmp_path/'i.html')])==0
    assert main(['ionosphere',str(ionex),'--backend','plotly','--hours','13',
                 '--output',str(tmp_path/'bad.html')])==1
    assert not (tmp_path/'bad.html').exists()
    assert 'not present' in capsys.readouterr().err


@plotly_only
def test_interactive_cli_groundtrack_does_not_require_observations(tmp_path):
    from gnsspy.cli.visualize import render_plots
    config={'map_backend':'plotly','system':'G'}
    paths=render_plots(None,orbit_at([0,1]),tmp_path,'demo',config,['groundtrack'])
    assert paths==[tmp_path/'demo_Groundtrack.html']
    assert config['_generated_files']==[str(paths[0].resolve())]


@plotly_only
def test_interactive_cli_observation_png_option(tmp_path,demo,monkeypatch):
    import plotly.graph_objects as go
    from gnsspy.cli.visualize import render_plots
    orbit,_,station=demo.make_demo_data()

    def fake_write_image(self,file,format=None,scale=None,**kwargs):
        Path(file).write_bytes(b'\x89PNG\r\n\x1a\nsynthetic')

    monkeypatch.setattr(go.Figure,'write_image',fake_write_image)
    config={'system':'G','plotly_png':True,'plotly_png_scale':2.0}
    paths=render_plots(station,orbit,tmp_path,'demo',config,['skyplot'])
    assert paths==[tmp_path/'demo_Skyplot.html',tmp_path/'demo_Skyplot.png']
    assert all(path.stat().st_size>0 for path in paths)
    assert config['_generated_files']==[str(path.resolve()) for path in paths]


@cartopy_only
@pytest.mark.parametrize('projection',['robinson','platecarree','mollweide','equalearth','mercator'])
def test_actual_cartopy_groundtracks(tmp_path,projection):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig=groundtrack(orbit_at([178,179,-179,-178],[30,31,32,33]),projection=projection,
                    features=False,save_path=tmp_path/(projection+'.png'),dpi=80)
    assert isinstance(fig,matplotlib.figure.Figure)
    assert hasattr(fig.axes[0],'projection')
    assert (tmp_path/(projection+'.png')).read_bytes().startswith(b'\x89PNG')
    assert len(fig.axes[0].lines)==3
    plt.close(fig)


@cartopy_only
def test_cartopy_rejects_unavailable_natural_earth_projection():
    with pytest.raises(ValueError, match='use equalearth'):
        groundtrack(orbit_at([0,1]), projection='naturalearth', features=False)


@cartopy_only
@pytest.mark.parametrize('projection,centre',[('robinson',0),('robinson',180),('platecarree',0)])
def test_actual_cartopy_six_panels(tmp_path,projection,centre):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from cartopy.mpl.geocollection import GeoQuadMesh
    data=tiny_gim();data.tec[:,1,2]=np.nan
    fig=ionosphere_maps(data,features=False,cmap='viridis',vmin=0,vmax=40,dpi=80,
                        projection=projection,central_longitude=centre,save_path=tmp_path/'panels.png')
    assert len(fig.axes)==7
    for i,ax in enumerate(fig.axes[:6]):
        meshes=[c for c in ax.collections if isinstance(c,GeoQuadMesh)]
        assert len(meshes)==2
        image=meshes[-1]
        assert image.norm.vmin==0 and image.norm.vmax==40
        assert np.ma.count(image.get_array())<data.tec.shape[1]*(data.tec.shape[2]-1)
    assert (tmp_path/'panels.png').read_bytes().startswith(b'\x89PNG')
    plt.close(fig)


@cartopy_only
def test_actual_cartopy_custom_axes_norm_and_input_immutability(tmp_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.colors import PowerNorm
    import cartopy.crs as ccrs
    data=tiny_gim();before=data.tec.copy()
    fig,ax=plt.subplots(subplot_kw={'projection':ccrs.PlateCarree()})
    norm=PowerNorm(.5,vmin=0,vmax=40)
    out=ionosphere_map(data,ax=ax,features=False,cmap='viridis',norm=norm,
                       save_path=tmp_path/'custom.svg',extent=(-90,90,-60,60))
    assert out is fig and len(fig.axes)==2
    np.testing.assert_array_equal(data.tec,before)
    assert norm.vmin==0 and norm.vmax==40
    assert '<svg' in (tmp_path/'custom.svg').read_text()[:1000]
    plt.close(fig)


@cartopy_only
def test_regional_tec_coordinate_labels_are_automatic_and_optional():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from cartopy.mpl.gridliner import Gridliner
    options=dict(features=False,cmap='viridis',projection='platecarree',
                 extent=(20,45,30,50))
    fig=ionosphere_map(tiny_gim(),**options)
    fig.canvas.draw()
    gridliner=next(item for item in fig.axes[0].get_children()
                    if isinstance(item,Gridliner))
    assert any(label.get_visible() for label in gridliner.xlabel_artists)
    assert any(label.get_visible() for label in gridliner.ylabel_artists)
    plt.close(fig)

    fig=ionosphere_map(tiny_gim(),coordinate_labels=False,**options)
    assert not any(isinstance(item,Gridliner) for item in fig.axes[0].get_children())
    plt.close(fig)

    fig=ionosphere_map(tiny_gim(),features=False,cmap='viridis')
    assert not any(isinstance(item,Gridliner) for item in fig.axes[0].get_children())
    plt.close(fig)


@cartopy_only
def test_actual_cartopy_rejects_wrong_axes_and_cleans_up():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots()
    with pytest.raises(TypeError,match='GeoAxes'):
        groundtrack(orbit_at([0,1]),features=False,ax=ax)
    before=set(plt.get_fignums())
    with pytest.raises(ValueError,match='projection'):
        groundtrack(orbit_at([0,1]),features=False,projection='invalid')
    assert set(plt.get_fignums())==before
    plt.close(fig)


@cartopy_only
@pytest.mark.skipif(importlib.util.find_spec('cmcrameri') is None,reason='cmcrameri unavailable: default palette untested')
def test_actual_cartopy_default_palette(tmp_path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig=ionosphere_map(tiny_gim(),features=False,save_path=tmp_path/'batlow.png')
    from cartopy.mpl.geocollection import GeoQuadMesh
    meshes=[c for c in fig.axes[0].collections if isinstance(c,GeoQuadMesh)]
    assert meshes[-1].cmap.name=='batlow_r'
    plt.close(fig)
