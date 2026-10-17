"""Pairs Desk local terminal API. Public read operations plus opt-in signed orders via OS keyring."""
from __future__ import annotations
from fastapi.responses import RedirectResponse
import json, os, re, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pairs_desk.storage import load_settings
from pairs_desk.frontend_archive import archive_frontend
from pairs_desk.metrics import position_map, ratio_bars, liquidation_distance, closed_pair_trade_events, archived_pair_entry_ratio, management_signals
from pairs_desk.ledger import Ledger, active_funding
from pairs_desk.market_catalog import MarketCatalog
from pairs_desk.market_scanner import MarketScanner, bootstrap_catalog_from_settings
from pairs_desk.market_storage import MarketDataStore
from final_read_services import recent_fills, add_accounting, zscore_from_bars, funding_summary

BASE = Path(__file__).resolve().parent
SETTINGS = Path.home()/'.config'/'crypto-pairs-desk'/'settings.json'
SNAPSHOTS = Path.home()/'.local'/'share'/'crypto-pairs-desk'/'frontend_snapshots.jsonl'
MARKET_DB = Path.home()/'.local'/'share'/'crypto-pairs-desk'/'market.sqlite3'
MARKET_DATA = Path.home()/'.local'/'share'/'crypto-pairs-desk'/'market-data'
ADDRESS = re.compile(r'^0x[a-fA-F0-9]{40}$')
API = 'https://api.hyperliquid.xyz/info'
app = FastAPI(title='Pairs Desk · Terminal local', docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['localhost', '127.0.0.1', '[::1]', 'testserver'])
from secure_trade_routes import router as trade_router
app.include_router(trade_router)
class LocalAssets(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers['Cache-Control'] = 'no-cache, must-revalidate'
        return response

app.mount('/assets', LocalAssets(directory=BASE/'frontend'), name='assets')
# Aurora Alpha: read-only parallel interface; stable / and execution routes are unchanged.
app.mount('/aurora/assets', LocalAssets(directory=BASE/'aurora'), name='aurora-assets')
# React build is optional; launcher builds it when npm is available.
REACT_DIST = BASE / 'react_dist'
if (REACT_DIST / 'index.html').exists():
    app.mount('/react/assets', LocalAssets(directory=REACT_DIST), name='react-assets')

@app.get('/react')
@app.get('/react/')
def react_home():
    if not (REACT_DIST / 'index.html').exists():
        return RedirectResponse('/aurora', status_code=302)
    return FileResponse(REACT_DIST / 'index.html', headers={'Cache-Control': 'no-store', 'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; frame-src 'self'; object-src 'none'; frame-ancestors 'none'"})


@app.get('/aurora')
@app.get('/aurora/')
def aurora_home():
    return FileResponse(BASE/'aurora'/'index.html', headers={'Cache-Control':'no-store', 'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"})

app.mount('/vendor', StaticFiles(directory=BASE/'pairs_desk'/'vendor'), name='vendor')
_http = requests.Session()

def hl(payload):
    r = _http.post(API, json=payload, timeout=(4, 14))
    r.raise_for_status()
    return r.json()

def safe_number(value, fallback=0):
    try: return float(value)
    except (TypeError, ValueError): return fallback

def portfolio_windows(portfolio):
    if not isinstance(portfolio, list): return {}
    out={}
    for item in portfolio:
        if isinstance(item,(list,tuple)) and len(item)==2 and isinstance(item[0],str) and isinstance(item[1],dict):
            out[item[0]]=item[1]
    return out

HL_PNL_WINDOWS={'1d':'perpDay','7d':'perpWeek','30d':'perpMonth','all':'perpAllTime'}

def hl_series(portfolio,key,limit=1500):
    """PNL de perps de la cuenta (portfolio de Hyperliquid) para una ventana, reajustado a 0 en su primer punto."""
    rows=(portfolio_windows(portfolio).get(key) or {}).get('pnlHistory') or []
    clean=[]
    for row in rows:
        try:
            if isinstance(row,(list,tuple)) and len(row)>=2:
                clean.append({'time':int(row[0]),'pnl':float(row[1])})
        except (TypeError,ValueError):
            pass
    clean=sorted({r['time']:r for r in clean}.values(),key=lambda r:r['time'])
    if not clean:return []
    base=clean[0]['pnl']
    return [{'time':r['time'],'pnl':r['pnl']-base} for r in clean[-limit:]]

def pnl_history(portfolio):
    return hl_series(portfolio,'perpAllTime',800)

def hl_pnl_windows(portfolio):
    return {key:hl_series(portfolio,window) for key,window in HL_PNL_WINDOWS.items()}

def local_pnl_history():
    if not SNAPSHOTS.exists(): return []
    rows=[]
    try:
        for line in SNAPSHOTS.read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            if isinstance(row,dict) and row.get('time') and row.get('pnl') is not None:
                rows.append({'time':int(row['time']),'pnl':float(row['pnl']),'source':'local','basis':row.get('basis','legacy')})
    except (OSError,TypeError,ValueError,json.JSONDecodeError):
        return []
    return sorted({r['time']:r for r in rows}.values(),key=lambda r:r['time'])

def save_snapshot(summary):
    pnl=summary.get('total')
    if pnl is None: pnl=summary.get('open_plus_realized')
    if pnl is None: return
    now=int(time.time()*1000)
    try:
        SNAPSHOTS.parent.mkdir(parents=True,exist_ok=True)
        previous=local_pnl_history()
        if previous and now-previous[-1]['time']<60_000: return
        row={'basis':'net' if summary.get('total') is not None else 'gross','time':now,'pnl':float(pnl),'open':summary.get('unrealized'),'realized':summary.get('realized'),'funding':summary.get('funding'),'fees':summary.get('fees'),'equity':summary.get('equity_core')}
        with SNAPSHOTS.open('a',encoding='utf-8') as handle:
            handle.write(json.dumps(row,separators=(',',':'))+'\n')
    except (OSError,TypeError,ValueError):
        return

def states():
    cfg, err = load_settings(SETTINGS)
    account = cfg.get('address','').strip()
    if err: raise HTTPException(409, 'Configuración inválida: no se mostrarán cifras hasta resolver el error')
    if not ADDRESS.fullmatch(account): raise HTTPException(400, 'Configurá primero la dirección pública en la versión estable de Pairs Desk')
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(hl, {'type':'clearinghouseState','user':account})
        b = pool.submit(hl, {'type':'clearinghouseState','user':account,'dex':'xyz'})
        core = a.result(); xyz = b.result()
    core_pos = position_map(core)
    xyz_pos = {k if ':' in k else f'xyz:{k}': v for k, v in position_map(xyz).items()}
    pos = {**core_pos, **xyz_pos}
    fills=[]; fills_complete=False; fills_error=None
    try:
        fills,fills_complete=recent_fills(account,hl)
    except Exception as exc:
        fills_error=type(exc).__name__
    # Archive completed cycles in the SAME settings.json used by Streamlit.
    # Never archive from an incomplete fill history or a failed XYZ read.
    ledger = Ledger()
    cfg, _ = archive_frontend(SETTINGS, account, pos, fills, fills_complete, ledger=ledger,
                              snapshot_token=str(time.time_ns()))
    pairs=[]
    operation_events=[]
    for p in cfg.get('pairs',[]):
        long,short=p['long'],p['short']
        lp,sp=pos.get(long),pos.get(short)
        if not lp or not sp or safe_number(lp.get('szi'))<=0 or safe_number(sp.get('szi'))>=0:continue
        a=safe_number(lp.get('entryPx')); b=safe_number(sp.get('entryPx'))
        mark_a=abs(safe_number(lp.get('positionValue'))/safe_number(lp.get('szi'),1)) if safe_number(lp.get('szi')) else 0
        mark_b=abs(safe_number(sp.get('positionValue'))/safe_number(sp.get('szi'),1)) if safe_number(sp.get('szi')) else 0
        entry=a/b if b else None
        ratio=mark_a/mark_b if mark_b else None
        lu=abs(safe_number(lp.get('positionValue'))); su=abs(safe_number(sp.get('positionValue')))
        pnl=safe_number(lp.get('unrealizedPnl'))+safe_number(sp.get('unrealizedPnl'))
        liqs=[v for v in (liquidation_distance(lp,mark_a),liquidation_distance(sp,mark_b)) if v is not None]
        fu = lp.get('cumFunding') or {}; fs=sp.get('cumFunding') or {}
        funding=active_funding(ledger, account, long, short, fills, float(lp['szi']), float(sp['szi']), fills_complete)
        pairs.append({'id':f'{long}|{short}','long':long,'short':short,'ratio':ratio,'entry_ratio':entry,'ratio_change':(ratio/entry-1)*100 if ratio is not None and entry else None,
            'size':lu+su,'long_usd':lu,'short_usd':su,'imbalance':(lu-su)/(lu+su)*100 if lu+su else None,
            'pnl':pnl,'long_pnl':safe_number(lp.get('unrealizedPnl')),'short_pnl':safe_number(sp.get('unrealizedPnl')),'funding':funding,'management_entry_ratio':p.get('management_entry_ratio') or entry,'executed_tp':p.get('executed_tp') or [],'executed_add':p.get('executed_add') or [],'pnl_pct':pnl/(lu+su)*100 if lu+su else 0,'z':None,'liq':min(liqs) if liqs else None,'management_rules':p.get('management_rules') or {},'trade_note':p.get('trade_note') or '', 'invalidation_note':p.get('invalidation_note') or ''})
        add_accounting(pairs[-1],lp,sp,fills,fills_complete)
        for ev in pairs[-1].get('events') or []:
            item=dict(ev); item['pair']=f'{long}/{short}'; item['status']='active'; operation_events.append(item)
    exposure=sum(p['size'] for p in pairs)
    unreal=sum(p['pnl'] for p in pairs)
    margins=[(s.get('marginSummary') or {}) for s in (core,xyz)]
    margin=sum(safe_number(s.get('totalMarginUsed')) for s in margins)
    core_margin=safe_number(margins[0].get('totalMarginUsed'))
    equity=[safe_number(s.get('accountValue')) for s in margins if s.get('accountValue') is not None]
    core_equity=safe_number(margins[0].get('accountValue')) if margins[0].get('accountValue') is not None else None
    totals=[p['total_pnl'] for p in pairs]
    archived=[]
    for item in cfg.get('closed_pairs',[]):
        row=dict(item)
        opened=int(row.get('opened_at') or 0); closed=int(row.get('closed_at') or 0)
        row['entry_ratio']=row.get('entry_ratio') or (archived_pair_entry_ratio(row.get('long',''),row.get('short',''),fills,opened) if fills else None)
        row['events']=row.get('events') or (closed_pair_trade_events(row.get('long',''),row.get('short',''),fills,opened,closed) if fills else [])
        for ev in row['events']:
            item=dict(ev); item['pair']=f"{row.get('long','')}/{row.get('short','')}"; item['status']='closed'; operation_events.append(item)
        row['net_realized']=safe_number(row.get('net_realized'), safe_number(row.get('realized'))-safe_number(row.get('fees')))
        archived.append(row)
    archived_realized=sum(safe_number(p.get('realized')) for p in archived)
    archived_fees=sum(safe_number(p.get('fees')) for p in archived)
    active_realized=0 if not pairs else sum(p['realized'] for p in pairs) if all(p['realized'] is not None for p in pairs) else None
    active_fees=0 if not pairs else sum(p['fees'] for p in pairs) if all(p['fees'] is not None for p in pairs) else None
    realized_total=None if active_realized is None else active_realized+archived_realized
    fees_total=None if active_fees is None else active_fees+archived_fees
    funding_values=[p.get('funding') for p in pairs+archived]
    funding_total=sum(funding_values) if all(v is not None for v in funding_values) else None
    closed_totals=[p.get('total_pnl') for p in archived]
    grand_total=sum(totals+closed_totals) if all(t is not None for t in totals+closed_totals) else None
    open_plus_realized=None if realized_total is None else unreal+realized_total
    try:
        portfolio=hl({'type':'portfolio','user':account})
    except Exception:
        portfolio=[]
    operation_events=sorted(operation_events,key=lambda e:int(e.get('time') or 0),reverse=True)[:200]
    summary={'realized':realized_total,'active_realized':active_realized,'archived_realized':archived_realized,'fees':fees_total,'active_fees':active_fees,'archived_fees':archived_fees,'total':grand_total,'open_plus_realized':open_plus_realized,'unrealized':unreal,'exposure':exposure,'funding':funding_total,'margin_used':margin,'margin_core':core_margin,
        'equity_core':core_equity,'margin_pct':None if not core_equity or core_equity<=0 else core_margin/core_equity*100,
        'delta':sum(p['long_usd']-p['short_usd'] for p in pairs)}
    # A subtotal is useful but must not masquerade as fully verified net PNL.
    known_funding = sum(v for v in funding_values if v is not None)
    summary['net_known_subtotal'] = (unreal + realized_total - fees_total + known_funding) if realized_total is not None and fees_total is not None else None
    summary['net_missing_funding_count'] = sum(v is None for v in funding_values)
    summary.update(funding_summary(pairs, archived))
    save_snapshot(summary)
    local_history=local_pnl_history()  # una sola lectura del archivo de snapshots
    history=local_history or pnl_history(portfolio)
    return {'pairs':pairs,'closed_pairs':archived,'pnl_history':history,'hl_pnl':hl_pnl_windows(portfolio),'pnl_source':'local' if local_history else 'hyperliquid','operation_events':operation_events,'summary':summary,'last_updated_ms':int(time.time()*1000),
        'ledger':{kind:ledger.state(account,kind) for kind in ('fills','funding')},
        'warnings':(['Funding activo no verificable o desactualizado: neto N/D.'] if any(p.get('funding') is None for p in pairs) else []) + (['Funding de cerrados incompleto: neto N/D.'] if any(p.get('total_pnl') is None for p in archived) else []) + ([] if fills_complete else [f'Historial de fills incompleto; realizado y comisiones no disponibles con certeza ({fills_error or "límite API"}).'])}

@app.get('/')
def home():return FileResponse(BASE/'frontend'/'index.html',headers={'Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' wss://api.hyperliquid.xyz; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'"})

_STATES_LOCK=__import__('threading').Lock()
RECORD_EVERY_S=60

def record_once(now_ms:int|None=None)->bool:
    """Takes a snapshot when no browser has recorded one recently. Returns True if it ran states()."""
    now_ms=int(time.time()*1000) if now_ms is None else now_ms
    previous=local_pnl_history()
    if previous and now_ms-previous[-1]['time']<RECORD_EVERY_S*1500: return False
    with _STATES_LOCK: states()
    return True

def _record_loop(stop):
    # La app solo registraba snapshots mientras una pestaña consultaba /api/state: con la pestaña
    # dormida o cerrada quedaban huecos en el gráfico. Este hilo los cubre mientras el servidor corra.
    while not stop.wait(RECORD_EVERY_S):
        try: record_once()
        except Exception: continue

_RECORDER_STOP=__import__('threading').Event()

@app.on_event('startup')
def start_recorder():
    if os.environ.get('PAIRS_DESK_RECORDER','1')=='0': return
    __import__('threading').Thread(target=_record_loop,args=(_RECORDER_STOP,),daemon=True,name='pnl-recorder').start()

@app.on_event('shutdown')
def stop_recorder():
    _RECORDER_STOP.set()

@app.get('/api/state')
def api_state():
    try:
        with _STATES_LOCK: return states()
    except HTTPException:raise
    except Exception as exc:raise HTTPException(503,f'Error de lectura: {type(exc).__name__}')

@app.get('/api/scanner')
def api_scanner(interval: str = '1h', search: str = '', venue: str = '', limit: int = 50):
    if interval not in ('5m', '15m', '1h', '4h', '1d', '1w'):
        raise HTTPException(400, 'Intervalo inválido')
    if not 1 <= limit <= 100:
        raise HTTPException(400, 'Límite inválido (1-100)')
    try:
        settings, settings_error = load_settings(SETTINGS)
        if settings_error:
            raise HTTPException(409, 'Configuración inválida')
        catalog = MarketCatalog(MARKET_DB)
        bootstrap_catalog_from_settings(catalog, settings)
        scanner = MarketScanner(catalog, MarketDataStore(MARKET_DATA))
        return scanner.scan(interval=interval, search=search, venue=venue, limit=limit).to_dict()
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(503, f'No se pudo leer el Scanner: {type(exc).__name__}')

@app.get('/api/chart/{pair_id}')
def chart(pair_id:str,interval:str='1d',before:int|None=None,limit:int=600):
    if interval not in ('5m','15m','1h','4h','1d','1w'):raise HTTPException(400,'Intervalo inválido')
    cfg,err=load_settings(SETTINGS)
    if err:raise HTTPException(409,'Configuración inválida')
    found=next((p for p in cfg.get('pairs',[]) if f"{p['long']}|{p['short']}"==pair_id),None)
    if not found:
        found=next((p for p in cfg.get('closed_pairs',[]) if str(p.get('id') or '')==pair_id or f"{p.get('long')}|{p.get('short')}"==pair_id),None)
    if not found:raise HTTPException(404,'Par no guardado')
    from pairs_desk.metrics import candle_window
    ms={'5m':5,'15m':15,'1h':60,'4h':240,'1d':1440,'1w':10080}[interval]
    if not 50 <= limit <= 1200:raise HTTPException(400,'Límite inválido (50-1200)')
    start,end=candle_window(ms,limit,now_ms=before if before is not None else None)
    def read(coin):
        raw=hl({'type':'candleSnapshot','req':{'coin':coin,'interval':interval,'startTime':start,'endTime':end}})
        return pd.DataFrame([{'time':int(r['t']),'open':float(r['o']),'high':float(r['h']),'low':float(r['l']),'close':float(r['c'])} for r in raw])
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(read,found['long']);b=pool.submit(read,found['short']); left=a.result();right=b.result()
        if left.empty or right.empty:return {'bars':[]}
        frame=ratio_bars(left,right,interval)
        bars=[{'timestamp':int(t.timestamp()*1000),'open':float(row['o']),'high':float(row['h']),'low':float(row['l']),'close':float(row['c'])} for t,row in frame.tail(limit).iterrows()]
        z = zscore_from_bars(bars) if len(bars) >= 30 else None
        from pairs_desk.health import pair_health
        return {'bars':bars,'z':z,'health':pair_health(bars) if interval=='1d' else None,'has_more':bool(bars and len(bars)>=limit),'synthetic_extremes':True}
    except Exception as exc:raise HTTPException(503,f'No se pudieron cargar velas: {type(exc).__name__}')

@app.get('/api/adaptive-levels/{pair_id}')
def api_adaptive_levels(pair_id: str):
    """Read-only, daily-history-based levels for the React terminal."""
    from pairs_desk.adaptive_levels import calculate
    cfg, err = load_settings(SETTINGS)
    if err: raise HTTPException(409, 'Configuración inválida')
    saved = next((p for p in cfg.get('pairs', []) if f"{p['long']}|{p['short']}" == pair_id), None)
    if not saved: raise HTTPException(404, 'Par activo no guardado')
    result = daily_analysis(pair_id)
    # Treat cached candle data as immutable.
    bars = [dict(bar) for bar in (result.get('bars') or [])]
    if not bars:
        return {'status':'unavailable','regime':'N/D','reason':'Sin velas diarias verificables','levels':{}}
    reference = safe_number(saved.get('management_entry_ratio'))
    reference_source = 'management_entry_ratio'
    if reference <= 0:
        # Derive a verified entry ratio from the two actual open positions.
        # Do not use current market price or an invented reference.
        try:
            account = cfg.get('address', '').strip()
            legs = [saved['long'], saved['short']]
            if not ADDRESS.fullmatch(account):
                raise ValueError('Dirección no configurada')
            dexes = {leg.split(':', 1)[0] if ':' in leg else '' for leg in legs}
            positions = {}
            for dex in dexes:
                request = {'type':'clearinghouseState','user':account}
                if dex: request['dex'] = dex
                payload = position_map(hl(request))
                positions.update({(key if ':' in key or not dex else f'{dex}:{key}'):value for key,value in payload.items()})
            lp, sp = positions.get(legs[0]), positions.get(legs[1])
            if not lp or not sp or safe_number(lp.get('szi')) <= 0 or safe_number(sp.get('szi')) >= 0:
                raise ValueError('Posiciones abiertas no verificables')
            long_entry, short_entry = safe_number(lp.get('entryPx')), safe_number(sp.get('entryPx'))
            if long_entry <= 0 or short_entry <= 0:
                raise ValueError('Precios de entrada inválidos')
            reference = long_entry / short_entry
            reference_source = 'verified_position_entry'
        except Exception:
            return {'status':'unavailable','regime':'N/D','reason':'Sin referencia de gestión ni entradas verificables','levels':{}}
    frame = pd.DataFrame({'c':[b['close'] for b in bars]})
    result = calculate(frame, reference)
    result['reference_ratio'] = reference
    result['reference_source'] = reference_source
    result['as_of_ms'] = bars[-1]['timestamp']
    return result



def _analytic_for_pair(pair, now_ms):
    """Read-only analytics; exceptions isolated by the caller."""
    import math
    from pairs_desk.analytics import (closed_daily_logs,ewma_vol,equilibrium,z_log,age_days,
        age_vs_half_life,risk_per_sigma,mae_mfe,pair_status,hit_rates)
    from pairs_desk.regime import classify_regime
    from pairs_desk.levels_v3 import calculate as calculate_levels
    key=pair['id']
    daily=daily_analysis(key)
    times,x=closed_daily_logs(daily.get('bars') or [],now_ms)
    if not times:return {'status':'unavailable','reason':'Velas cerradas insuficientes, vencidas o inválidas','pair_status':'SIN_DATOS'}
    sigma=ewma_vol(x);mu,s=equilibrium(x)
    ratio=pair.get('ratio');reference=pair.get('management_entry_ratio') or pair.get('entry_ratio')
    if sigma is None or mu is None or not ratio or ratio<=0 or not reference or reference<=0:
        return {'status':'unavailable','reason':'Sin volatilidad, ratio o entrada verificable','pair_status':'SIN_DATOS'}
    live=math.log(ratio);z=z_log(live,mu,s)
    health=daily.get('health') or {}
    half=health.get('half_life_days')
    horizon=max(7,min(30,round(half))) if half is not None and half>0 else 14
    age=age_days(pair.get('opened_at'),now_ms)
    age_ratio=age_vs_half_life(age,half)
    n_eff=(pair.get('long_usd',0)+pair.get('short_usd',0))/2
    risk_day,risk_h=risk_per_sigma(n_eff,sigma,horizon)
    regime=classify_regime(x)
    levels=calculate_levels(reference,mu,sigma,horizon,health.get('status'),regime,z,age_ratio,pair.get('liq'),n_eff)
    hit=hit_rates(x,sigma,horizon,{'tp1':.5,'tp2':1.,'add1':-1.,'add2':-1.75})
    mae=mae_mfe(times,x,pair.get('opened_at'),math.log(reference),live,n_eff)
    reached_tp=any(ratio>=v for k,v in levels['levels'].items() if k.startswith('tp'))
    reached_add=any(ratio<=v for k,v in levels['levels'].items() if k.startswith('add'))
    status,reason=pair_status(z,regime,health.get('status'),age_ratio,pair.get('pnl'),pair.get('liq'),reached_add,levels.get('add_allowed',False),reached_tp)
    return {'status':'ok','reason':'','z_log':z,'regime':regime,'sigma_daily_pct':100*sigma,
            'horizon_days':horizon,'health':health,'age_days':age,'age_vs_half_life':age_ratio,
            'risk_usd_per_sigma_day':risk_day,'risk_usd_per_sigma_h':risk_h,
            'liq_distance_pct':pair.get('liq'),'imbalance_pct':pair.get('imbalance'),
            'funding_per_day_usd':None,'funding_reason':'Ledger de 7 días no verificado',
            'pair_status':status,'pair_status_reason':reason,'hit_rates':hit,
            'levels_v3':levels,**{k:v for k,v in mae.items() if k in ('mae_pct','mfe_pct','mae_usd','mfe_usd')}}

@app.get('/api/analytics')
def api_analytics():
    """Read-only batch endpoint. Never calls states(), which archives/snapshots."""
    cfg,err=load_settings(SETTINGS)
    if err:raise HTTPException(409,'Configuración inválida')
    account=cfg.get('address','').strip()
    if not ADDRESS.fullmatch(account):raise HTTPException(400,'Cuenta no configurada')
    with ThreadPoolExecutor(max_workers=2) as pool:
        core_f=pool.submit(hl,{'type':'clearinghouseState','user':account})
        xyz_f=pool.submit(hl,{'type':'clearinghouseState','user':account,'dex':'xyz'})
        core=position_map(core_f.result());xyz=position_map(xyz_f.result())
    positions={**core,**{k if ':' in k else 'xyz:'+k:v for k,v in xyz.items()}}
    pairs=[]
    for saved in cfg.get('pairs',[]):
        long,short=saved['long'],saved['short'];lp=positions.get(long);sp=positions.get(short)
        if not lp or not sp or safe_number(lp.get('szi'))<=0 or safe_number(sp.get('szi'))>=0:continue
        lmark=abs(safe_number(lp.get('positionValue'))/safe_number(lp.get('szi'),1))
        smark=abs(safe_number(sp.get('positionValue'))/safe_number(sp.get('szi'),1))
        lu=abs(safe_number(lp.get('positionValue')));su=abs(safe_number(sp.get('positionValue')))
        entry=safe_number(lp.get('entryPx'))/safe_number(sp.get('entryPx'),1)
        liqs=[v for v in (liquidation_distance(lp,lmark),liquidation_distance(sp,smark)) if v is not None]
        pairs.append({'id':long+'|'+short,'ratio':lmark/smark if smark else None,
                      'entry_ratio':entry,'management_entry_ratio':saved.get('management_entry_ratio') or entry,
                      'long_usd':lu,'short_usd':su,'imbalance':100*(lu-su)/(lu+su) if lu+su else None,
                      'liq':min(liqs) if liqs else None,
                      'pnl':safe_number(lp.get('unrealizedPnl'))+safe_number(sp.get('unrealizedPnl')),
                      'opened_at':saved.get('opened_at')})
    now_ms=int(time.time()*1000)
    def compute(pair):
        try:return pair['id'],_analytic_for_pair(pair,now_ms)
        except Exception as exc:return pair['id'],{'status':'unavailable','reason':'Error analítico: '+type(exc).__name__,'pair_status':'SIN_DATOS'}
    with ThreadPoolExecutor(max_workers=3) as pool: results=dict(pool.map(compute,pairs))
    return {'as_of_ms':now_ms,'pairs':results}

@app.get('/api/levels/{pair_id}')
def api_levels_v3(pair_id:str):
    data=api_analytics()['pairs']
    if pair_id not in data:raise HTTPException(404,'Par activo no encontrado')
    return data[pair_id].get('levels_v3') or {'status':'unavailable','reason':data[pair_id].get('reason'),'levels':{}}

@app.get('/api/live-prices')
def live_prices():
    from live_prices import snapshot
    cfg, err = load_settings(SETTINGS)
    if err:
        raise HTTPException(status_code=503, detail='No se pudo leer la configuración de pares')
    coins = {str(p[leg]) for p in cfg.get('pairs', []) for leg in ('long', 'short') if p.get(leg)}
    return snapshot(coins, hl)


@app.get('/api/management/{pair_id}')
def management(pair_id: str):
    from final_read_services import management_snapshot
    cfg, err = load_settings(SETTINGS)
    if err: raise HTTPException(409, 'Configuración inválida')
    saved = next((p for p in cfg.get('pairs', []) if f"{p['long']}|{p['short']}" == pair_id), None)
    if not saved: raise HTTPException(404, 'Par no guardado')
    account = cfg.get('address', '').strip()
    def position(coin):
        dex = coin.split(':', 1)[0] if ':' in coin else ''
        payload = {'type':'clearinghouseState', 'user':account}
        if dex: payload['dex'] = dex
        positions = position_map(hl(payload))
        return positions.get(coin) or positions.get(coin.split(':')[-1])
    try:
        lp, sp = position(saved['long']), position(saved['short'])
        if not lp or not sp or float(lp['szi']) <= 0 or float(sp['szi']) >= 0:
            return management_snapshot(saved, None, None)
        ratio = abs(float(lp['positionValue'])/float(lp['szi'])) / abs(float(sp['positionValue'])/float(sp['szi']))
        try:
            daily = daily_analysis(pair_id)
            z, health = daily.get('z'), daily.get('health')
        except Exception:
            z, health = None, None
        result = management_snapshot(saved, ratio, z)
        result['health'] = health
        return result
    except Exception as exc:
        raise HTTPException(503, f'Señales no disponibles: {type(exc).__name__}')


_ANALYSIS_CACHE = {}
_ANALYSIS_LOCK = __import__('threading').RLock()
def daily_analysis(pair_id):
    # One daily-candle fetch per pair per five minutes, shared by UI and watcher.
    cfg, err = load_settings(SETTINGS)
    if err: raise HTTPException(409, 'Configuración inválida')
    key=(cfg.get('address','').lower(), pair_id)
    with _ANALYSIS_LOCK:
        cached=_ANALYSIS_CACHE.get(key)
        if cached and time.time()-cached[0]<300:return cached[1]
        result=chart(pair_id, '1d')
        _ANALYSIS_CACHE[key]=(time.time(),result)
        return result

# Opt-in watcher lives with the local server, not the browser tab.
from pairs_desk.alerts import Watcher, observations
from fastapi import Request
from pydantic import BaseModel, StrictBool


def alert_poll():
    cfg, err=load_settings(SETTINGS)
    if err:raise ValueError('Settings inválidos')
    account=cfg.get('address','').strip()
    if not ADDRESS.fullmatch(account):raise ValueError('Cuenta inválida')
    core_raw=hl({'type':'clearinghouseState','user':account})
    xyz_raw=hl({'type':'clearinghouseState','user':account,'dex':'xyz'})
    if not all(isinstance(raw,dict) and isinstance(raw.get('assetPositions'),list) for raw in (core_raw,xyz_raw)):
        raise ValueError('Estado de cuenta incompleto')
    core=position_map(core_raw);xyz=position_map(xyz_raw)
    positions={**core,**{k if ':' in k else 'xyz:'+k:v for k,v in xyz.items()}}
    signals={}
    from final_read_services import management_snapshot
    for pair in cfg.get('pairs',[]):
        key=pair['long']+'|'+pair['short']
        lp,sp=positions.get(pair['long']),positions.get(pair['short'])
        if not lp or not sp:continue
        try:
            ratio=abs(float(lp['positionValue'])/float(lp['szi']))/abs(float(sp['positionValue'])/float(sp['szi']))
            daily=daily_analysis(key)
            signals[key]=management_snapshot(pair,ratio,daily.get('z'))
        except Exception:pass
    return account.lower(),observations(cfg,positions,signals)


ALERTS=Watcher(alert_poll)

@app.on_event('startup')
def start_alerts():
    if ALERTS.enabled:ALERTS.start()

@app.on_event('shutdown')
def stop_alerts():
    ALERTS.stop_event.set()

class AlertInput(BaseModel):
    csrf:str
    enabled:StrictBool

@app.get('/api/alerts')
def alert_status():return ALERTS.status()

@app.post('/api/alerts')
def alert_config(body:AlertInput, request:Request):
    from secure_trade_routes import _request_ok
    _request_ok(request,body.csrf)
    ALERTS.configure(body.enabled)
    return ALERTS.status()


class AlertTestInput(BaseModel):
    csrf:str

@app.post('/api/alerts/test')
def alert_test(body:AlertTestInput, request:Request):
    from secure_trade_routes import _request_ok
    _request_ok(request,body.csrf)
    return {'delivered':ALERTS.notify('Pairs Desk', 'Aviso de prueba. El vigilante no envía órdenes.')}

@app.get('/api/review/closed')
def api_review_closed():
    """Read-only closed-pair metadata; incomplete event effects remain N/D."""
    from pairs_desk.review import review_closed
    cfg,err=load_settings(SETTINGS)
    if err:raise HTTPException(409,'Configuración inválida')
    return review_closed(cfg.get('closed_pairs') or [])

@app.get('/api/portfolio-risk')
def api_portfolio_risk():
    """Read-only concentration; unavailable correlations are explicit."""
    from pairs_desk.portfolio_risk import concentration
    cfg,err=load_settings(SETTINGS)
    if err:raise HTTPException(409,'Configuración inválida')
    data=api_analytics()['pairs']
    # Analytics endpoint does not expose leg notionals. Do not manufacture them.
    return {'status':'unavailable','reason':'Exposición por pata requiere snapshot compartido verificable','pairs_analytics':len(data)}
