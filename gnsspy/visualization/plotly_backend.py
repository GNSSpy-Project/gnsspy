"""Interactive observation plots with explicit, auditable signal selection."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd
import plotly.graph_objects as go

from gnsspy.visualization._observations import (
    observations, select_snr, snr_values, geometry, gap_seconds, labels,
)


def _mode(value, allowed, default):
    value = default if value is None else str(value).strip().lower()
    if value == 'auto':
        value = 'snr'
    if value not in allowed:
        raise ValueError(f'Mode must be one of {sorted(allowed)}; got {value!r}')
    return value


def _save(fig, save_path, png_path=None, png_scale=2.0):
    html = None
    if save_path is not None:
        html = Path(save_path)
        if html.suffix.lower() not in {'.html', '.htm'}:
            html = html.with_suffix('.html')

    if png_path is True:
        if html is None:
            raise ValueError('png_path=True requires save_path so the PNG name can be derived')
        png = html.with_suffix('.png')
    elif png_path is None or png_path is False:
        png = None
    elif isinstance(png_path, (str, Path)):
        png = Path(png_path)
        if not png.suffix:
            png = png.with_suffix('.png')
        if png.suffix.lower() != '.png':
            raise ValueError('png_path must use a .png suffix')
    else:
        raise TypeError('png_path must be a path, True, False or None')

    if png is not None:
        png_scale = float(png_scale)
        if not np.isfinite(png_scale) or png_scale <= 0:
            raise ValueError('png_scale must be a positive finite number')
    if html is not None:
        html.parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(str(html), include_plotlyjs=True)
    if png is not None:
        png.parent.mkdir(parents=True, exist_ok=True)
        try:
            fig.write_image(str(png), format='png', scale=png_scale)
        except Exception as exc:
            raise RuntimeError(
                "Plotly PNG export failed. Install the 'plotly-png' extra and ensure "
                "Chrome or Chromium is available; Plotly can install it with "
                "'plotly_get_chrome'. The HTML output, when requested, is still valid."
            ) from exc
    return fig


def _lines(x, y, times, max_gap, valid=None, azimuth=False):
    """Keep a break at every invalid original sample and every time gap."""
    x, y = list(x), np.asarray(y, dtype=float)
    times = pd.DatetimeIndex(times)
    valid = np.isfinite(y) if valid is None else np.asarray(valid, dtype=bool)
    xx, yy = [], []
    previous = None
    for i in range(len(y)):
        if not valid[i]:
            if xx and xx[-1] is not None:
                xx.append(None); yy.append(None)
            previous = None
            continue
        if previous is not None:
            gap = (times[i] - times[previous]).total_seconds() > max_gap
            seam = azimuth and abs(float(x[i]) - float(x[previous])) > 180
            if gap or seam:
                xx.append(None); yy.append(None)
        xx.append(x[i]); yy.append(float(y[i]))
        previous = i
    return xx, yy


def _metadata(details=None, missing=None):
    return {'snr_selection': details or {}, 'skipped_snr': missing or {},
            'snr_policy': 'one native measured code per SV; maximum positive finite coverage, deterministic priority ties; no epoch filling',
            'smoothing': 'none', 'counts': {}, 'omitted': {}}


def _colour(fig, values, label, colour_range=None):
    vals = np.concatenate(values) if values else np.array([])
    vals = vals[np.isfinite(vals)]
    if not len(vals):
        raise RuntimeError('No plottable finite colour values')
    if colour_range is None:
        low, high = float(vals.min()), float(vals.max())
        if high == low:
            low -= .5; high += .5
    else:
        low, high = map(float, colour_range)
        if not np.isfinite([low, high]).all() or low >= high:
            raise ValueError('color_range must be two finite increasing limits')
    fig.update_layout(coloraxis=dict(colorscale='Jet', cmin=low, cmax=high,
                                    colorbar=dict(title=label)))


def _sky_or_azel(kind, station, orbit, system, sv_list, color_mode, save_path,
                 snr_code, cut_off, max_gap, color_range, png_path, png_scale):
    mode = _mode(color_mode, {'snr', 'elevation'}, 'snr')
    source = observations(station, system, sv_list)
    selected, details, missing = select_snr(source, snr_code) if mode == 'snr' else ({}, {}, {})
    frame = geometry(station, orbit, source, cut_off)
    metadata = _metadata(details, missing)
    fig, colours = go.Figure(), []
    for sv, group in frame.groupby(level='SV', sort=True):
        if mode == 'snr' and sv not in selected:
            continue
        times = group.index.get_level_values('Epoch')
        az = group['Azimuth'].to_numpy(dtype=float)
        el = group['Elevation'].to_numpy(dtype=float)
        code = selected.get(sv, 'Elevation')
        vals = snr_values(group, code) if mode == 'snr' else el.copy()
        visible = np.isfinite(az) & np.isfinite(el)
        mask = visible & np.isfinite(vals)
        if not mask.any():
            metadata['omitted'][sv] = 'no finite requested colour at visible, matched geometry epochs'
            continue

        xline, yline = _lines(az, el, times, gap_seconds(station, times, max_gap), visible, kind == 'azel')
        name = f'{sv} [{code}]' if mode == 'snr' else sv
        hover = ('<b>' + name + '</b><br>Az: %{theta:.1f}°<br>El: %{r:.1f}°'
                 '<br>Epoch: %{customdata}<br>Value: %{marker.color:.2f}<extra></extra>')
        marker = dict(color=vals[mask], coloraxis='coloraxis', size=5)
        common = dict(mode='markers', name=name, legendgroup=sv, marker=marker,
                      customdata=[t.isoformat() for t in times[mask]])
        if kind == 'sky':
            fig.add_trace(go.Scatterpolar(theta=xline, r=yline, mode='lines', legendgroup=sv,
                                         line=dict(color='gray', width=1), showlegend=False, hoverinfo='skip', connectgaps=False))
            fig.add_trace(go.Scatterpolar(theta=az[mask], r=el[mask], hovertemplate=hover, **common))
        else:
            fig.add_trace(go.Scatter(x=xline, y=yline, mode='lines', legendgroup=sv,
                                    line=dict(color='gray', width=1), showlegend=False, hoverinfo='skip', connectgaps=False))
            hover = hover.replace('%{theta', '%{x').replace('%{r', '%{y')
            fig.add_trace(go.Scatter(x=az[mask], y=el[mask], hovertemplate=hover, **common))
        colours.append(vals[mask])
        metadata['counts'][sv] = {'geometry_points': int(visible.sum()), 'coloured_points': int(mask.sum()), 'code': code}
    if not colours:
        raise RuntimeError('No plottable observations with finite requested colours and visible geometry')
    _colour(fig, colours, labels(station)[1] if mode == 'snr' else 'Elevation (°)', color_range)
    filename = Path(str(getattr(station, 'filename', 'observations'))).name
    fig.update_layout(title=f'{"Skyplot" if kind == "sky" else "Azimuth–elevation"} — {filename}',
                      template='plotly_white', meta=metadata)
    if kind == 'sky':
        fig.update_layout(polar=dict(radialaxis=dict(range=[90, 0], angle=45),
                                     angularaxis=dict(direction='clockwise', rotation=90)), legend=dict(x=1.15))
    else:
        fig.update_layout(xaxis=dict(title='Azimuth (°)', range=[0, 360], dtick=45),
                          yaxis=dict(title='Elevation (°)', range=[0, 90]))
    return _save(fig, save_path, png_path, png_scale)


def skyplot(station, orbit, system='G', sv_list=None, color_mode='snr', save_path=None,
            *, snr_code='auto', cut_off=0.0, max_gap=None, color_range=None,
            png_path=None, png_scale=2.0):
    return _sky_or_azel('sky', station, orbit, system, sv_list, color_mode, save_path,
                        snr_code, cut_off, max_gap, color_range, png_path, png_scale)


def azelplot(station, orbit, system='G', sv_list=None, color_mode='snr', save_path=None,
             *, snr_code='auto', cut_off=0.0, max_gap=None, color_range=None,
             png_path=None, png_scale=2.0):
    return _sky_or_azel('azel', station, orbit, system, sv_list, color_mode, save_path,
                        snr_code, cut_off, max_gap, color_range, png_path, png_scale)


def timelplot(station, orbit=None, system='G', sv_list=None, mode='snr', save_path=None,
              *, snr_code='auto', color_mode=None, cut_off=0.0, max_gap=None,
              color_range=None, png_path=None, png_scale=2.0):
    mode = _mode(mode, {'snr', 'elevation'}, 'snr')
    colour = _mode(color_mode, {'snr', 'elevation', 'satellite'}, 'satellite')
    if mode == 'snr' and colour == 'elevation':
        raise ValueError('elevation colouring of an observation-only SNR time series is not supported')
    source = observations(station, system, sv_list)
    needs_snr = mode == 'snr' or colour == 'snr'
    chosen, details, missing = select_snr(source, snr_code) if needs_snr else ({}, {}, {})
    frame = geometry(station, orbit, source, cut_off) if mode == 'elevation' else source
    fig, colours = go.Figure(), []
    metadata = _metadata(details, missing)
    for sv, group in frame.groupby(level='SV', sort=True):
        if needs_snr and sv not in chosen:
            continue
        times = group.index.get_level_values('Epoch')
        code = chosen.get(sv)
        vals = snr_values(group, code) if mode == 'snr' else group['Elevation'].to_numpy(dtype=float)
        cvals = snr_values(group, code) if colour == 'snr' else vals
        mask = np.isfinite(vals) & np.isfinite(cvals)
        if not mask.any():
            metadata['omitted'][sv] = 'no finite requested values at the selected epochs/cut-off'
            continue
        tx, ty = _lines(times, vals, times, gap_seconds(station, times, max_gap), np.isfinite(vals))
        name = f'{sv} [{code}]' if needs_snr else sv
        hover = '<b>' + name + '</b><br>Epoch: %{x}<br>Value: %{y:.3f}<extra></extra>'
        if colour in {'snr', 'elevation'}:
            fig.add_trace(go.Scatter(x=tx, y=ty, mode='lines', legendgroup=sv, showlegend=False,
                                    line=dict(color='gray', width=1), hoverinfo='skip', connectgaps=False))
            fig.add_trace(go.Scatter(x=times[mask], y=vals[mask], mode='markers', name=name, legendgroup=sv,
                                    marker=dict(color=cvals[mask], coloraxis='coloraxis', size=4),
                                    hovertemplate=hover.replace('<extra>', '<br>Colour: %{marker.color:.2f}<extra>')))
            colours.append(cvals[mask])
        else:
            fig.add_trace(go.Scatter(x=tx, y=ty, mode='lines+markers', name=name, legendgroup=sv,
                                    marker=dict(size=3), line=dict(width=1), hovertemplate=hover, connectgaps=False))
        metadata['counts'][sv] = {'plotted_points': int(mask.sum()), 'code': code}
    if not fig.data:
        raise RuntimeError('No plottable time-series observations')
    if colours:
        _colour(fig, colours, labels(station)[1] if colour == 'snr' else 'Elevation (°)', color_range)
    filename = Path(str(getattr(station, 'filename', 'observations'))).name
    fig.update_layout(title=f'{mode.capitalize()} time series — {filename}', xaxis_title=labels(station)[0],
                      yaxis_title=labels(station)[1] if mode == 'snr' else 'Elevation (°)',
                      template='plotly_white', meta=metadata)
    return _save(fig, save_path, png_path, png_scale)


def bandplot(station, system='G', sv_list=None, save_path=None, *, color_mode=None,
             snr_code='auto', color_range=None, png_path=None, png_scale=2.0):
    mode = _mode(color_mode, {'snr', 'satellite'}, 'satellite')
    frame = observations(station, system, sv_list)
    chosen, details, missing = select_snr(frame, snr_code) if mode == 'snr' else ({}, {}, {})
    fig, colours = go.Figure(), []
    metadata = _metadata(details, missing)
    for sv, group in frame.groupby(level='SV', sort=True):
        if mode == 'snr' and sv not in chosen:
            continue
        times = group.index.get_level_values('Epoch')
        marker = dict(symbol='line-ns-open', size=10, line=dict(width=2))
        code = chosen.get(sv)
        name = f'{sv} [{code}]' if code else sv
        if code:
            vals = snr_values(group, code)
            mask = np.isfinite(vals)
            times = times[mask]
            marker.update(color=vals[mask], coloraxis='coloraxis')
            colours.append(vals[mask])
        metadata['counts'][sv] = {'plotted_points': len(times), 'code': code}
        fig.add_trace(go.Scatter(x=times, y=[sv]*len(times), mode='markers', name=name, marker=marker,
                                hovertemplate='<b>' + name + '</b><br>Epoch: %{x}<extra></extra>'))
    if not fig.data:
        raise RuntimeError('No plottable visibility observations')
    if colours:
        _colour(fig, colours, labels(station)[1], color_range)
    fig.update_layout(title=f'Observation availability — {Path(str(station.filename)).name}',
                      xaxis_title=labels(station)[0], yaxis_title='Satellite',
                      yaxis=dict(categoryorder='category descending'), template='plotly_white', meta=metadata)
    return _save(fig, save_path, png_path, png_scale)


def groundtrack(orbit, system='G', sv_list=None, save_path=None, **kwargs):
    from gnsspy.visualization.groundtrack import groundtrack as render
    return render(orbit, system, sv_list, save_path, backend='plotly', **kwargs)


azimuth_elevation_plot = azelplot
visibility_plot = bandplot
ground_track = groundtrack


def time_elevation_plot(station, orbit=None, system='G', sv_list=None, mode='elevation', save_path=None, **kwargs):
    return timelplot(station, orbit, system, sv_list, mode, save_path, **kwargs)


def snr_time_series_plot(station, orbit=None, system='G', sv_list=None, mode='snr', save_path=None, **kwargs):
    return timelplot(station, orbit, system, sv_list, mode, save_path, **kwargs)


__all__ = ['skyplot', 'azelplot', 'azimuth_elevation_plot', 'timelplot', 'time_elevation_plot',
           'snr_time_series_plot', 'bandplot', 'visibility_plot', 'groundtrack', 'ground_track']
