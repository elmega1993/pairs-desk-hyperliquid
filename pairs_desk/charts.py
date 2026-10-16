from __future__ import annotations
import math

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

from .hl_client import candles
from .metrics import candle_window, ratio_bars, spread_stats, half_life

TZ = ZoneInfo('America/Argentina/Buenos_Aires')

VENDOR_ENGINE = Path(__file__).with_name('vendor') / 'lightweight-charts.standalone.production.js'


def _chart_engine_script() -> str:
    if VENDOR_ENGINE.exists():
        return '<script>' + VENDOR_ENGINE.read_text(encoding='utf-8') + '</script>'
    raise RuntimeError("Falta lightweight-charts local en pairs_desk/vendor: CDN externo bloqueado por seguridad")



def load_ratio_frame(long: str, short: str, interval: str, samples: int | None = None):
    # Use coarser native candles for D/W so the chart can reach much further back.
    # Intraday keeps finer samples for a smoother synthetic ratio.
    sample, minutes = {
        '15m': ('5m', 5),
        '1h': ('15m', 15),
        '4h': ('1h', 60),
        '1d': ('1d', 1440),
        '1w': ('1d', 1440),
    }[interval]
    start, end = candle_window(minutes, n=samples or 4998)
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(candles, long, sample, start, end)
        b = pool.submit(candles, short, sample, start, end)
        left, right = a.result(), b.result()
    raw = ratio_bars(left, right, interval)
    return spread_stats(raw), sample


def _apply_range(frame: pd.DataFrame, interval: str, range_mode: str, opened_ms: int | None):
    if frame.empty:
        return frame
    if range_mode == 'Desde apertura' and opened_ms:
        opened = datetime.fromtimestamp(opened_ms / 1000, frame.index.tz)
        visible = frame[frame.index >= opened]
        if len(visible) >= 3:
            return visible
    elif range_mode == '1M':
        cutoff = frame.index[-1] - pd.Timedelta(days=30)
        return frame[frame.index >= cutoff]
    elif range_mode == '3M':
        cutoff = frame.index[-1] - pd.Timedelta(days=90)
        return frame[frame.index >= cutoff]
    return frame


def _lightweight_candles(frame: pd.DataFrame, entry_ratio: float, opened_ms: int | None, key: str, events: list[dict] | None = None, management_ratio: float | None = None, rules: dict | None = None):
    candles_data = []
    for ts, row in frame.iterrows():
        candles_data.append({
            'time': int(ts.timestamp()),
            'open': float(row['o']),
            'high': float(row['h']),
            'low': float(row['l']),
            'close': float(row['c']),
        })

    entry_time = int(opened_ms / 1000) if opened_ms else None
    payload = json.dumps(candles_data, separators=(',', ':'))
    entry = json.dumps(float(entry_ratio))
    entry_ts = 'null' if entry_time is None else str(entry_time)
    event_payload = []
    for item in (events or []):
        try:
            event_payload.append({
                'time': int(item.get('time', 0) / 1000),
                'kind': str(item.get('kind') or ''),
                'label': str(item.get('label') or ''),
                'detail': str(item.get('detail') or ''),
                'realized': float(item.get('realized') or 0),
            })
        except (TypeError, ValueError):
            continue
    events_json = json.dumps(event_payload, separators=(',', ':'))
    z_data = [
        {'time': int(ts.timestamp()), 'value': float(row['z'])}
        for ts, row in frame.iterrows() if pd.notna(row.get('z'))
    ]
    z_json = json.dumps(z_data, separators=(',', ':'))
    management_ratio = float(management_ratio or entry_ratio)
    cfg = {
        'tp1_ratio_pct': 10.0, 'tp2_ratio_pct': 20.0, 'tp3_ratio_pct': 20.0,
        'tp3_abs_z': 0.5, 'add1_ratio_pct': -8.0, 'add1_z': -2.0,
        'add2_ratio_pct': -15.0, 'add2_z': -2.5,
    }
    if isinstance(rules, dict):
        for name in cfg:
            try:
                if name in rules: cfg[name] = float(rules[name])
            except (TypeError, ValueError):
                pass
    levels = {
        'TP1': management_ratio * (1 + cfg['tp1_ratio_pct'] / 100),
        'TP2': management_ratio * (1 + cfg['tp2_ratio_pct'] / 100),
        'TP3': management_ratio * (1 + cfg['tp3_ratio_pct'] / 100),
        'ADD1': management_ratio * (1 + cfg['add1_ratio_pct'] / 100),
        'ADD2': management_ratio * (1 + cfg['add2_ratio_pct'] / 100),
    }
    levels_json = json.dumps(levels, separators=(',', ':'))
    z_rules_json = json.dumps({'add1': cfg['add1_z'], 'add2': cfg['add2_z'], 'tp3': cfg['tp3_abs_z']}, separators=(',', ':'))

    engine_script = _chart_engine_script()
    html = f'''<!doctype html>
<html>
<head>
<meta charset="utf-8" />
{engine_script}
<style>
html,body,#wrap{{margin:0;width:100%;height:100%;background:#121712;color:#a0ad9d;font-family:Inter,system-ui,sans-serif;overflow:hidden}}
#wrap{{position:relative}}
#chart{{width:100%;height:520px}}
#legend{{position:absolute;z-index:5;left:12px;top:8px;background:rgba(18,23,18,.86);border:1px solid #293129;border-radius:5px;padding:5px 8px;font-size:12px;pointer-events:none;white-space:nowrap}}
#help{{position:absolute;z-index:5;right:12px;top:8px;color:#7f8b7c;font-size:11px;pointer-events:none;background:rgba(18,23,18,.75);padding:3px 6px;border-radius:4px}}
</style>
</head>
<body>
<div id="wrap"><div id="chart"></div><div id="legend">Mové el mouse sobre una vela</div><div id="help">rueda: zoom · arrastrar: mover · eje derecho: escala</div></div>
<script>
(function(){{
  const data = {payload};
  const entryRatio = {entry};
  const entryTime = {entry_ts};
  const tradeEvents = {events_json};
  const zData = {z_json};
  const managementLevels = {levels_json};
  const zRules = {z_rules_json};
  const container = document.getElementById('chart');
  if (!window.LightweightCharts) {{
    document.getElementById('legend').textContent = 'No se pudo cargar el motor del gráfico. Revisá la conexión a Internet.';
    return;
  }}
  const chart = LightweightCharts.createChart(container, {{
    width: container.clientWidth,
    height: 520,
    layout: {{ background: {{ type: 'solid', color: '#121712' }}, textColor: '#a0ad9d' }},
    grid: {{ vertLines: {{ color: '#293129' }}, horzLines: {{ color: '#293129' }} }},
    crosshair: {{
      mode: LightweightCharts.CrosshairMode.Normal,
      vertLine: {{ color: '#687166', width: 1, style: 2, labelBackgroundColor: '#293129' }},
      horzLine: {{ color: '#687166', width: 1, style: 2, labelBackgroundColor: '#293129' }}
    }},
    rightPriceScale: {{ borderColor: '#293129', autoScale: true, scaleMargins: {{ top: .08, bottom: .08 }} }},
    timeScale: {{ borderColor: '#293129', timeVisible: true, secondsVisible: false, rightOffset: 4, barSpacing: 7, minBarSpacing: 1.5 }},
    handleScale: {{ mouseWheel: true, pinch: true, axisPressedMouseMove: true }},
    handleScroll: {{ mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false }},
  }});
  const series = chart.addSeries(LightweightCharts.CandlestickSeries, {{
    upColor: '#44d7a8', downColor: '#fa7885', borderVisible: false,
    wickUpColor: '#44d7a8', wickDownColor: '#fa7885',
    priceLineVisible: true, lastValueVisible: true,
  }});
  series.setData(data);
  series.createPriceLine({{
    price: entryRatio, color: '#d8ad63', lineWidth: 1, lineStyle: LightweightCharts.LineStyle.Dashed,
    axisLabelVisible: true, title: 'Entrada media'
  }});
  const levelColors = {{TP1:'#44d7a8',TP2:'#44d7a8',TP3:'#44d7a8',ADD1:'#fa7885',ADD2:'#fa7885'}};
  for (const [name, price] of Object.entries(managementLevels)) {{
    series.createPriceLine({{price:Number(price), color:levelColors[name], lineWidth:1, lineStyle:LightweightCharts.LineStyle.Dotted, axisLabelVisible:true, title:name}});
  }}
  if (zData.length) {{
    const zSeries = chart.addSeries(LightweightCharts.LineSeries, {{color:'#e3e7df',lineWidth:2,priceLineVisible:false,lastValueVisible:true}}, 1);
    zSeries.setData(zData);
    zSeries.createPriceLine({{price:0,color:'#687166',lineWidth:1,lineStyle:LightweightCharts.LineStyle.Solid,axisLabelVisible:false,title:'Z 0'}});
    zSeries.createPriceLine({{price:Number(zRules.add1),color:'#d8ad63',lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title:'ADD1 Z'}});
    zSeries.createPriceLine({{price:Number(zRules.add2),color:'#fa7885',lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dashed,axisLabelVisible:true,title:'ADD2 Z'}});
    zSeries.createPriceLine({{price:Number(zRules.tp3),color:'#44d7a8',lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dotted,axisLabelVisible:true,title:'TP3 |Z|'}});
    zSeries.createPriceLine({{price:-Number(zRules.tp3),color:'#44d7a8',lineWidth:1,lineStyle:LightweightCharts.LineStyle.Dotted,axisLabelVisible:false,title:''}});
    try {{ const panes = chart.panes(); if (panes.length > 1) panes[1].setHeight(115); }} catch(e) {{}}
  }}
  const markers = [];
  if (entryTime !== null) {{
    markers.push({{ time: entryTime, position: 'belowBar', color: '#d8ad63', shape: 'arrowUp', text: 'Entrada' }});
  }}
  for (const ev of tradeEvents) {{
    if (!ev || !ev.time || !ev.kind) continue;
    if (ev.kind === 'add') {{
      markers.push({{ time: ev.time, position: 'belowBar', color: '#44d7a8', shape: 'circle', text: ev.label }});
    }} else if (ev.kind === 'close') {{
      const good = Number(ev.realized || 0) >= 0;
      markers.push({{ time: ev.time, position: 'aboveBar', color: good ? '#44d7a8' : '#fa7885', shape: 'arrowDown', text: ev.label }});
    }}
  }}
  if (markers.length) {{
    try {{ LightweightCharts.createSeriesMarkers(series, markers); }} catch(e) {{}}
  }}
  chart.timeScale().fitContent();

  function fmt(v) {{
    if (v === undefined || v === null || !Number.isFinite(Number(v))) return '—';
    const n = Number(v); return n >= 1 ? n.toFixed(4) : n.toPrecision(6);
  }}
  const legend = document.getElementById('legend');
  chart.subscribeCrosshairMove(param => {{
    if (!param || !param.time || !param.seriesData) {{ legend.textContent = 'Mové el mouse sobre una vela'; return; }}
    const bar = param.seriesData.get(series);
    if (!bar) return;
    const d = new Date(Number(param.time) * 1000);
    const ds = d.toLocaleString('es-AR', {{ timeZone: 'America/Argentina/Buenos_Aires', day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' }});
    const timeSec = Number(param.time);
    const event = tradeEvents.find(ev => Math.abs(Number(ev.time) - timeSec) < 1);
    const eventText = event ? ` · ${{event.detail}}` : '';
    legend.textContent = `${{ds}}  O ${{fmt(bar.open)}}  H ${{fmt(bar.high)}}  L ${{fmt(bar.low)}}  C ${{fmt(bar.close)}}${{eventText}}`;
  }});
  new ResizeObserver(entries => {{
    if (!entries.length) return;
    chart.applyOptions({{ width: Math.floor(entries[0].contentRect.width) }});
  }}).observe(container);
}})();
</script>
</body></html>'''
    components.html(html, height=528, scrolling=False)


KLINE_BUNDLE = Path(__file__).with_name('vendor') / 'klinecharts.min.js'


def _kline_candles(frame: pd.DataFrame, entry_ratio: float, opened_ms: int | None, events: list[dict] | None, management_ratio: float | None, rules: dict | None):
    """Render local KLineChart v9 UMD, without fetching third-party scripts."""
    if not KLINE_BUNDLE.is_file():
        raise FileNotFoundError('Falta el motor local de KLineChart')
    bars = [dict(timestamp=int(ts.timestamp()*1000), open=float(row['o']),
                 high=float(row['h']), low=float(row['l']), close=float(row['c']), volume=0)
            for ts,row in frame.iterrows()]
    if not bars:
        return
    base = float(management_ratio or entry_ratio)
    cfg = {'tp1_ratio_pct':10.0,'tp2_ratio_pct':20.0,'tp3_ratio_pct':20.0,
           'add1_ratio_pct':-8.0,'add2_ratio_pct':-15.0}
    if isinstance(rules,dict):
        for field in cfg:
            try:
                if field in rules: cfg[field] = float(rules[field])
            except (TypeError,ValueError): pass
    levels=[{'label':'ENTRADA MEDIA','value':float(entry_ratio),'color':'#d8ad63'}]
    adaptive = rules.get('adaptive_absolute_levels') if isinstance(rules, dict) else None
    if adaptive is not None:
        for name, value in adaptive.items():
            if isinstance(value, (int, float)) and math.isfinite(value) and value > 0:
                levels.append({'label':name.upper(),'value':float(value),'color':'#44d7a8' if name.startswith('tp') else '#fa7885'})
    else:
        for label,field in [('TP1','tp1_ratio_pct'),('TP2','tp2_ratio_pct'),('TP3','tp3_ratio_pct'),('ADD1','add1_ratio_pct'),('ADD2','add2_ratio_pct')]:
            levels.append({'label':label,'value':base*(1+cfg[field]/100),'color':'#44d7a8' if label.startswith('TP') else '#fa7885'})
    markers=[]
    if opened_ms:
        markers.append({'timestamp':int(opened_ms),'label':'ENTRADA','detail':'Apertura inicial','color':'#d8ad63','side':'below'})
    for ev in events or []:
        if ev.get('kind') not in ('add','close'): continue
        try:
            pnl=float(ev.get('realized') or 0)
            kind=ev.get('kind')
            markers.append({'timestamp':int(ev['time']),'label':str(ev.get('label') or ('ADD' if kind=='add' else 'CIERRE'))[:40],
                            'detail':str(ev.get('detail') or '')[:250], 'color':'#44d7a8' if kind=='add' or pnl>=0 else '#fa7885',
                            'side':'below' if kind=='add' else 'above'})
        except (TypeError,ValueError,KeyError): continue
    data=json.dumps({'bars':bars,'levels':levels,'markers':markers},separators=(',',':')).replace('</','<\\/')
    # Never load scripts from CDN. HTML runs in the Streamlit components iframe.
    script=KLINE_BUNDLE.read_text(encoding='utf-8').replace('</script', '<\\/script')
    html='''<!doctype html><html><head><meta charset="utf-8"><style>
    body{margin:0;background:#101510;color:#d5e2d3;font:12px system-ui}
    #chart{height:540px;width:100%}#legend{position:absolute;top:10px;left:12px;z-index:3;
    background:#101510dc;padding:6px 10px;border:1px solid #344137;border-radius:5px}
    #help{position:absolute;bottom:10px;left:12px;color:#a0ad9d;pointer-events:none}
    </style><script>'''+script+'''</script></head><body><div id="chart"></div><div id="legend">KLineChart · ratio</div>
    <div id="help">Rueda: zoom · arrastrar: mover · clic en marcas: detalles</div><script>
    const data=__DATA__;
    try {
      const chart=klinecharts.init('chart',{styles:{grid:{show:true,horizontal:{color:'#273329'},vertical:{color:'#273329'}},
        candle:{bar:{upColor:'#44d7a8',downColor:'#fa7885',noChangeColor:'#b7c2b7'}},
        xAxis:{axisLine:{color:'#344137'}},yAxis:{axisLine:{color:'#344137'}}}});
      chart.applyNewData(data.bars);
      klinecharts.registerOverlay({name:'pd_price_line',totalStep:1,lock:true,needDefaultPointFigure:false,
        createPointFigures:({coordinates,bounding,overlay})=>{
          if(!coordinates.length)return [];
          const y=coordinates[0].y, meta=overlay.extendData||{};
          return [{type:'line',attrs:{coordinates:[{x:0,y},{x:bounding.width,y}]},styles:{color:meta.color||'#d8ad63',size:1,dashedValue:[5,4]}},
                  {type:'text',attrs:{x:8,y:y-7,text:meta.label||''},styles:{color:meta.color||'#d8ad63',size:11}}];
        }});
      klinecharts.registerOverlay({name:'pd_event',totalStep:1,lock:true,needDefaultPointFigure:false,
        createPointFigures:({coordinates,overlay})=>{
          if(!coordinates.length)return [];
          const {x,y}=coordinates[0],m=overlay.extendData||{};
          return [{type:'circle',attrs:{x,y,r:5},styles:{color:m.color||'#d8ad63',style:'fill'}},
                  {type:'text',attrs:{x:x+8,y:y+(m.side==='below'?18:-8),text:m.label||''},styles:{color:m.color||'#d8ad63',size:11}}];
        },onClick:({overlay})=>{
          const m=overlay.extendData||{};
          document.getElementById('legend').textContent=(m.label||'Evento')+' · '+(m.detail||'');
          return true;
        }});
      for(const level of data.levels){
        chart.createOverlay({name:'pd_price_line',lock:true,points:[{timestamp:data.bars[data.bars.length-1].timestamp,value:level.value}],extendData:level});
      }
      for(const m of data.markers){
        const index=data.bars.findIndex(b=>b.timestamp>=m.timestamp);
        if(index<0)continue;
        const b=data.bars[index];
        chart.createOverlay({name:'pd_event',lock:true,points:[{timestamp:b.timestamp,value:m.side==='below'?b.low:b.high}],extendData:m});
      }
      chart.scrollToRealTime();
      new ResizeObserver(()=>chart.resize()).observe(document.getElementById('chart'));
    }catch(err){ document.getElementById('legend').textContent='Error al iniciar KLineChart: '+String(err); }
    </script></body></html>'''.replace('__DATA__',data)
    components.html(html,height=546,scrolling=False)


def ratio_chart(long: str, short: str, interval: str, entry_ratio: float, view: str, range_mode: str, opened_ms: int | None, events: list[dict] | None = None, management_ratio: float | None = None, rules: dict | None = None, closed_ms: int | None = None):
    full, sample = load_ratio_frame(long, short, interval)
    if full.empty:
        st.info('Sin velas coincidentes para estos mercados en el período disponible.')
        return None
    if interval in ('1d', '1w'):
        # Keep daily/weekly candles labeled by UTC date.
        full.index = full.index.tz_convert('UTC')
    else:
        full.index = full.index.tz_convert(TZ)
    frame = _apply_range(full, interval, range_mode, opened_ms)
    if closed_ms:
        closed_dt = datetime.fromtimestamp(closed_ms / 1000, frame.index.tz)
        frame = frame[frame.index <= closed_dt]
    range_fallback = False
    if range_mode == 'Desde apertura' and opened_ms:
        opened = datetime.fromtimestamp(opened_ms / 1000, full.index.tz)
        range_fallback = len(full[full.index >= opened]) < 3

    if view == 'z-score':
        fig = go.Figure()
        y = frame['z']
        fig.add_hline(y=0, line_color='#a0ad9d', line_width=1)
        fig.add_hline(y=2, line_color='#d8ad63', line_dash='dash')
        fig.add_hline(y=-2, line_color='#d8ad63', line_dash='dash')
        fig.add_trace(go.Scatter(x=frame.index, y=y, mode='lines', line=dict(color='#e3e7df', width=2), name='z-score'))
        if y.notna().any():
            fig.add_trace(go.Scatter(x=[frame.index[-1]], y=[y.iloc[-1]], mode='markers', marker=dict(size=7, color='#e3e7df'), showlegend=False))
        fig.update_layout(
            height=430, showlegend=False, margin=dict(l=8, r=18, t=22, b=10),
            paper_bgcolor='#121712', plot_bgcolor='#121712', font_color='#a0ad9d',
            hovermode='x unified', dragmode='pan', uirevision=f'{long}/{short}/{interval}/{view}/{range_mode}',
            xaxis=dict(showgrid=True, gridcolor='#293129', rangeslider_visible=False, title=None),
            yaxis=dict(side='right', showgrid=True, gridcolor='#293129', title='z-score', fixedrange=False)
        )
        st.plotly_chart(fig, width='stretch', config={'scrollZoom': True, 'displaylogo': False})
    else:
        if KLINE_BUNDLE.is_file():
            _kline_candles(frame, entry_ratio, opened_ms, events, management_ratio, rules)
        elif VENDOR_ENGINE.is_file():
            _lightweight_candles(frame, entry_ratio, opened_ms, f'{long}_{short}_{interval}_{range_mode}', events, management_ratio, rules)
        else:
            # No remote scripts on a page that accepts API wallet credentials.
            # Preserve entry/ADD/CLOSE overlays even when the local lightweight engine is absent.
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=frame.index, open=frame['o'], high=frame['h'], low=frame['l'], close=frame['c'],
                increasing=dict(line=dict(color='#44d7a8'), fillcolor='#44d7a8'),
                decreasing=dict(line=dict(color='#fa7885'), fillcolor='#fa7885'), name='Ratio',
                hoverinfo='x+y',
            ))
            fig.add_hline(y=float(entry_ratio), line_dash='dash', line_color='#d8ad63', line_width=2,
                          annotation_text='Entrada media', annotation_position='top left', annotation_font_color='#d8ad63')
            management_ratio_value = float(management_ratio or entry_ratio)
            cfg = {'tp1_ratio_pct': 10.0, 'tp2_ratio_pct': 20.0, 'tp3_ratio_pct': 20.0,
                   'add1_ratio_pct': -8.0, 'add2_ratio_pct': -15.0}
            if isinstance(rules, dict):
                for key in cfg:
                    try:
                        if key in rules: cfg[key] = float(rules[key])
                    except (ValueError, TypeError):
                        pass
            for tag, setting, color in [
                ('TP1','tp1_ratio_pct','#44d7a8'), ('TP2','tp2_ratio_pct','#44d7a8'),
                ('TP3','tp3_ratio_pct','#44d7a8'), ('ADD1','add1_ratio_pct','#fa7885'),
                ('ADD2','add2_ratio_pct','#fa7885')]:
                price = management_ratio_value * (1 + cfg[setting] / 100)
                fig.add_hline(y=price, line_dash='dot', line_color=color, line_width=1,
                              annotation_text=tag, annotation_position='top right', annotation_font_color=color)
            # Snap event timestamps to the closest displayed candle (never silently discard them).
            if opened_ms and len(frame):
                entry_dt = pd.Timestamp(opened_ms, unit='ms', tz='UTC').tz_convert(frame.index.tz)
                ix = frame.index.get_indexer([entry_dt], method='nearest')[0]
                if ix >= 0 and frame.index.min() <= entry_dt <= frame.index.max():
                    fig.add_trace(go.Scatter(x=[frame.index[ix]], y=[float(frame['l'].iloc[ix])],
                        mode='markers+text', marker=dict(symbol='triangle-up', size=13, color='#d8ad63'),
                        text=['ENTRADA'], textposition='bottom center', name='Entrada',
                        hovertemplate='Entrada inicial<br>%{x}<extra></extra>'))
            for ev in events or []:
                try:
                    ts = pd.Timestamp(int(ev['time']), unit='ms', tz='UTC').tz_convert(frame.index.tz)
                    if not (frame.index.min() <= ts <= frame.index.max()):
                        continue
                    ix = frame.index.get_indexer([ts], method='nearest')[0]
                    is_add = ev.get('kind') == 'add'
                    if not is_add and ev.get('kind') != 'close':
                        continue
                    pnl = float(ev.get('realized') or 0)
                    color = '#44d7a8' if is_add or pnl >= 0 else '#fa7885'
                    label = str(ev.get('label') or ('ADD' if is_add else 'CIERRE'))
                    detail = str(ev.get('detail') or '')
                    fig.add_trace(go.Scatter(x=[frame.index[ix]],
                        y=[float(frame['l'].iloc[ix] if is_add else frame['h'].iloc[ix])],
                        mode='markers+text', marker=dict(symbol='circle' if is_add else 'triangle-down', size=12, color=color),
                        text=[label], textposition='bottom center' if is_add else 'top center',
                        name=label, customdata=[detail],
                        hovertemplate='%{text}<br>%{x}<br>%{customdata}<extra></extra>'))
                except (ValueError, TypeError, KeyError, IndexError):
                    continue
            fig.update_layout(
                height=555, showlegend=False, margin=dict(l=8,r=38,t=22,b=12),
                paper_bgcolor='#121712', plot_bgcolor='#121712', font_color='#a0ad9d',
                uirevision=f'{long}/{short}/{interval}/{range_mode}', dragmode='pan', hovermode='x unified',
                xaxis=dict(rangeslider_visible=False, showgrid=True, gridcolor='#293129'),
                yaxis=dict(side='right', showgrid=True, gridcolor='#293129', fixedrange=False),
            )
            st.plotly_chart(fig, width='stretch', config={'scrollZoom': True, 'displaylogo': False})

    hl = half_life(full['c'].map(lambda value: math.log(value) if value > 0 else float('nan')))
    first, last = full.index[0], full.index[-1]
    zone_label = 'UTC' if interval in ('1d', '1w') else 'ART'
    history = f'Histórico disponible: {first:%d/%m/%Y} → {last:%d/%m/%Y} {zone_label}.'
    if view == 'Velas':
        caveat = 'Mechas sintéticas del ratio: high = high long / low short y low = low long / high short; los extremos pueden no haber ocurrido exactamente al mismo instante.'
    else:
        caveat = 'z-score calculado sobre el histórico cargado.'
    hl_txt = f'Half-life informativa: {hl:.1f} velas.' if hl else 'Half-life: no disponible/no revierte.'
    if range_fallback:
        st.warning('No hay al menos 3 velas desde la apertura; se muestra todo el histórico disponible.')
    st.caption(f'{history} · muestras base {sample}. {caveat} {hl_txt}')
    return {
        'z': None if full['z'].isna().all() else float(full['z'].iloc[-1]),
        'spread': float(full['spread'].iloc[-1]),
        'first': first, 'last': last
    }
