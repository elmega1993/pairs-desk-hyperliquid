"""Pairs Desk local terminal API. Public read operations plus opt-in signed orders via OS keyring."""
from __future__ import annotations
from fastapi.responses import RedirectResponse
import json, os, re, time, sqlite3, logging, hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import Any
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pairs_desk.local_advisor import Advisor
from pairs_desk.advisor_routes import advisor_router
from pairs_desk.ai.codex_provider import CodexProvider
from pairs_desk.ai.memory import MemoryStore
from pairs_desk.ai.service import DeskService
from pairs_desk.ai.routes import desk_router
from pairs_desk.storage import load_settings
from pairs_desk.frontend_archive import archive_frontend
from pairs_desk.metrics import candle_window, position_map, ratio_bars, liquidation_distance, closed_pair_trade_events, archived_pair_entry_ratio, management_signals
from pairs_desk.closed_ratio import close_ratio_from_fills, ratio_change_since_close
from pairs_desk.ratio_changes import ratio_changes_from_bars
from pairs_desk.ledger import Ledger, active_funding
from pairs_desk.funding_carry import aggregate_funding_projection, funding_rates, pair_funding_carry
from pairs_desk.strategy_analytics import strategy_snapshot, portfolio_strategy_daily, aligned_portfolio_history
from pairs_desk.historical_account import archive_official_history, reconstructed_daily
from pairs_desk.mobile_access import allowed_hosts as mobile_allowed_hosts
from pairs_desk.market_catalog import MarketCatalog
from pairs_desk.market_assets import AssetUniverseService
from pairs_desk.asset_changes import WeeklyReferenceStore, WeeklyReferenceWorker, attach_changes, priority_order, weekly_progress, DEFAULT_INTERVAL_S
import threading
from pairs_desk.market_pair_analysis import PairAnalysisService
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
STRATEGY_START_MS = 1790132400000  # 23/09/2026 00:00 Buenos Aires
FUNDING_RATE_TTL_MS = 300_000
_FUNDING_RATE_CACHE = None
_NONFUNDING_CACHE = None
_OFFICIAL_HISTORY_LOCK = threading.Lock()
app = FastAPI(title='Pairs Desk · Terminal local', docs_url=None, redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=mobile_allowed_hosts(Path.home()/'.config/crypto-pairs-desk/remote_access.json'))
_api_stats_lock = threading.Lock()
_api_stats = {'started_at_ms': int(time.time() * 1000), 'http': {}, 'hyperliquid': {}}

def _record_stat(bucket, key, duration_ms, status=None):
    with _api_stats_lock:
        row = bucket.setdefault(key, {'count': 0, 'errors': 0, 'total_ms': 0.0, 'max_ms': 0.0, 'last_ms': 0.0})
        row['count'] += 1
        row['errors'] += int(status is not None and status >= 400)
        row['total_ms'] += duration_ms
        row['max_ms'] = max(row['max_ms'], duration_ms)
        row['last_ms'] = duration_ms

@app.middleware('http')
async def measure_http_requests(request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        if request.url.path.startswith('/api/'):
            _record_stat(_api_stats['http'], request.url.path, (time.perf_counter() - started) * 1000, status)

from secure_trade_routes import router as trade_router
app.include_router(trade_router)

def _advisor_ledger(kind, account):
    # Open the existing ledger read-only, pinned to the account of this query.
    from contextlib import closing
    from pairs_desk.ledger import DEFAULT_PATH
    if not account or kind not in ('fills', 'funding'):
        raise ValueError('Ledger no disponible')
    with closing(sqlite3.connect(f'file:{DEFAULT_PATH}?mode=ro', uri=True)) as db:
        rows = [json.loads(row[0]) for row in db.execute(
            'SELECT payload FROM events WHERE account=? AND kind=? ORDER BY time,identity',
            (account.lower(), kind))]
        coverage = db.execute('SELECT payload FROM sync_state WHERE account=? AND kind=?',
                              (account.lower(), kind)).fetchone()
    return {'rows': rows, 'coverage': json.loads(coverage[0]) if coverage else {}}

def _advisor_candles(pair_id, interval, limit):
    result = chart(pair_id, interval=interval, limit=max(50, limit))
    return dict(result, bars=result.get('bars', [])[-limit:])

ADVISOR_PROVIDER = os.environ.get('PAIRS_DESK_ADVISOR_PROVIDER', 'codex')
if ADVISOR_PROVIDER not in ('codex', 'ollama'):
    raise ValueError('PAIRS_DESK_ADVISOR_PROVIDER debe ser codex u ollama')
ADVISOR = Advisor(codex=CodexProvider(os.environ.get('PAIRS_DESK_CODEX_MODEL', 'gpt-5.6-sol'))
                  if ADVISOR_PROVIDER == 'codex' else None,
                  model=os.environ.get('PAIRS_DESK_ADVISOR_MODEL', 'qwen3.5:9b'),
                  candles=_advisor_candles, ledger=_advisor_ledger)
def _desk_account():
    return str(load_settings(SETTINGS)[0].get('address') or '').lower()

def _desk_identity():
    # One settings read binds identity and operational data, even across account changes.
    account=_desk_account()
    scope=hashlib.sha256(f'{os.getuid()}:{account}'.encode()).hexdigest()
    return scope,account

def _desk_scope():
    return _desk_identity()[0]

DESK_DATA = Path(os.environ.get('PAIRS_DESK_AI_DATA_DIR', Path.home()/'.local/share/crypto-pairs-desk/desk'))
DESK_EMBEDDER=None
if os.environ.get('PAIRS_DESK_EMBEDDING_MODEL'):
    from pairs_desk.ai.embeddings import OllamaLocalEmbedder
    DESK_EMBEDDER=OllamaLocalEmbedder(os.environ['PAIRS_DESK_EMBEDDING_MODEL'])
DESK_STORE = MemoryStore(DESK_DATA/'desk.sqlite3',embedder=DESK_EMBEDDER)
DESK = DeskService(ADVISOR, DESK_STORE, _desk_scope, identity_provider=_desk_identity)
app.include_router(advisor_router(ADVISOR, desk=DESK))
app.include_router(desk_router(DESK))

@app.middleware('http')
async def guard_desk_requests(request, call_next):
    if request.url.path.startswith('/api/advisor/'):
        from fastapi.responses import JSONResponse
        if request.headers.get('sec-fetch-site') == 'cross-site':
            return JSONResponse({'detail':'Acceso de otro sitio no permitido'},status_code=403)
        # Limit before JSON/Pydantic parsing, including requests without Content-Length.
        maximum = 2_100_000 if request.url.path == '/api/advisor/import' else 32_000
        chunks=[]; size=0
        async for chunk in request.stream():
            size += len(chunk)
            if size > maximum:
                return JSONResponse({'detail':'Petición demasiado grande'},status_code=413)
            chunks.append(chunk)
        request._body=b''.join(chunks)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        return response
    return await call_next(request)
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
    kind = str(payload.get('type', 'unknown'))
    venue = str(payload.get('dex') or 'core')
    started = time.perf_counter()
    status = None
    try:
        r = _http.post(API, json=payload, timeout=(4, 14))
        status = r.status_code
        r.raise_for_status()
        return r.json()
    except Exception:
        status = status or 599
        raise
    finally:
        _record_stat(_api_stats['hyperliquid'], f'{kind}:{venue}', (time.perf_counter() - started) * 1000, status)

@app.get('/api/diagnostics/call-stats')
def api_call_stats():
    with _api_stats_lock:
        snapshot = json.loads(json.dumps(_api_stats))
    for group in ('http', 'hyperliquid'):
        for row in snapshot[group].values():
            row['avg_ms'] = round(row['total_ms'] / row['count'], 1) if row['count'] else 0
            row['total_ms'] = round(row['total_ms'], 1)
            row['max_ms'] = round(row['max_ms'], 1)
            row['last_ms'] = round(row['last_ms'], 1)
    snapshot['captured_at_ms'] = int(time.time() * 1000)
    return snapshot

def current_mids_for_closed(rows):
    """Read current Core/XYZ mids only when the closed-pair table needs them."""
    if not rows:
        return {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        core_future = pool.submit(hl, {'type':'allMids'})
        xyz_future = pool.submit(hl, {'type':'allMids','dex':'xyz'})
        core, xyz = core_future.result(), xyz_future.result()
    mids = {}
    for symbol, value in (core or {}).items():
        try: mids[symbol] = float(value)
        except (TypeError, ValueError): pass
    for symbol, value in (xyz or {}).items():
        try: mids[symbol if ':' in symbol else f'xyz:{symbol}'] = float(value)
        except (TypeError, ValueError): pass
    return mids

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

def account_value_from_portfolio(portfolio):
    windows=portfolio_windows(portfolio)
    rows=(windows.get('allTime') or windows.get('perpAllTime') or {}).get('accountValueHistory') or []
    clean=[]
    for row in rows:
        try:
            if isinstance(row,(list,tuple)) and len(row)>=2:
                clean.append((int(row[0]),float(row[1])))
        except (TypeError,ValueError):
            pass
    return sorted(clean,key=lambda row:row[0])[-1][1] if clean else None

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

def official_pnl_from_windows(windows):
    """Last rebased PNL point per Hyperliquid window, or None when absent."""
    return {key:(rows[-1]['pnl'] if rows else None) for key,rows in (windows or {}).items()} | {
        key:None for key in HL_PNL_WINDOWS if key not in (windows or {})
    }


def _nonfunding_history(account, now_ms=None):
    global _NONFUNDING_CACHE
    now = int(time.time() * 1000) if now_ms is None else int(now_ms)
    if _NONFUNDING_CACHE and now - _NONFUNDING_CACHE[0] < FUNDING_RATE_TTL_MS:
        return _NONFUNDING_CACHE[1]
    try:
        rows = hl({'type': 'userNonFundingLedgerUpdates', 'user': account})
        rows = rows if isinstance(rows, list) else []
    except Exception:
        rows = []
    _NONFUNDING_CACHE = (now, rows)
    return rows


def strategy_data(portfolio, account, fills, fills_complete, ledger, unrealized, active_pairs, positions=None):
    windows = portfolio_windows(portfolio)
    history = retained_official_history(windows, account)
    raw_official = (windows.get('perpAllTime') or {}).get('pnlHistory') or []
    official_points=[]
    for row in raw_official:
        try:
            if isinstance(row,(list,tuple)) and len(row)>=2:
                official_points.append((int(row[0]),float(row[1])))
        except (TypeError,ValueError):
            pass
    official_points.sort(key=lambda item:item[0])
    official_all_time = official_points[-1][1] if official_points else None
    start_points = [value for timestamp,value in official_points if timestamp >= STRATEGY_START_MS]
    account_rows = (windows.get('allTime') or windows.get('perpAllTime') or {}).get('accountValueHistory') or []
    funding_state = ledger.state(account, 'funding')
    strategy = strategy_snapshot(
        history,
        account_rows,
        fills,
        ledger.rows(account, 'funding'),
        STRATEGY_START_MS,
        fills_complete=fills_complete,
        funding_complete=funding_state.get('complete') is True and funding_state.get('covered_until') is not None,
        unrealized=unrealized,
        nonfunding_rows=_nonfunding_history(account),
        account=account,
        official_all_time_pnl=official_all_time,
        official_start_pnl=start_points[0] if start_points else None,
    )
    strategy['daily'] = portfolio_strategy_daily(windows, STRATEGY_START_MS, history)
    reconstruction = reconstructed_daily(SNAPSHOTS.parent/'historical_account.sqlite3', account, strategy['history'])
    strategy['reconstructed_daily'] = reconstruction['daily']
    strategy['reconstructed_as_of_ms'] = reconstruction['updated_ms']
    projection = aggregate_funding_projection(active_pairs, _current_funding_rates(), positions=positions)
    projection['as_of_ms'] = _FUNDING_RATE_CACHE[0] if _FUNDING_RATE_CACHE else None
    strategy['funding_projection'] = projection
    return strategy


def retained_official_history(windows, account):
    """Keep official cumulative samples, separately from local pair accounting."""
    path = SNAPSHOTS.parent / 'official_strategy_history.json'
    with _OFFICIAL_HISTORY_LOCK:
        cached = []
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            if saved.get('account') == account.lower() and saved.get('basis') == 'perpAllTime':
                cached = saved.get('rows', [])
        except (OSError, ValueError, AttributeError):
            pass
        current = aligned_portfolio_history(windows)
        if not current:
            return []
        # Reject stale/incompatible baselines rather than introducing artificial jumps.
        current_map = {r['time']: r['pnl'] for r in current}
        if any(abs(r['pnl']-current_map[r['time']]) > .01
               for r in cached if r.get('time') in current_map):
            cached = []
        rows = [r for r in aligned_portfolio_history(windows, cached)
                if r['time'] >= STRATEGY_START_MS]
        try:
            if not path.exists() or time.time()-path.stat().st_mtime >= 300:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix('.tmp')
                temporary.write_text(json.dumps({'account': account.lower(),
                    'basis': 'perpAllTime', 'rows': rows}), encoding='utf-8')
                temporary.chmod(0o600)
                temporary.replace(path)
                archive_official_history(path.parent/'historical_account.sqlite3',
                                         path.parent/'ledger.sqlite3', account, rows)
        except (OSError, ValueError, sqlite3.Error) as exc:
            logging.getLogger(__name__).warning('Official history archive unavailable: %s', type(exc).__name__)
        return rows

def local_pnl_history():
    if not SNAPSHOTS.exists(): return []
    rows=[]
    try:
        for line in SNAPSHOTS.read_text(encoding='utf-8').splitlines():
            row=json.loads(line)
            if isinstance(row,dict) and row.get('time') and row.get('pnl') is not None:
                item={'time':int(row['time']),'pnl':float(row['pnl']),'source':'local','basis':row.get('basis','legacy')}
                for key in ('open','realized','exposure','margin_used','margin_pct'):
                    if row.get(key) is not None:
                        try:item[key]=float(row[key])
                        except (TypeError,ValueError):pass
                rows.append(item)
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
        row={'basis':'net' if summary.get('total') is not None else 'gross','time':now,'pnl':float(pnl),'open':summary.get('unrealized'),'realized':summary.get('realized'),'funding':summary.get('funding'),'fees':summary.get('fees'),'equity':summary.get('equity_core'),'exposure':summary.get('exposure'),'margin_used':summary.get('margin_used'),'margin_pct':summary.get('margin_pct')}
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
        row['close_ratio']=row.get('close_ratio') or (close_ratio_from_fills(row.get('long',''),row.get('short',''),fills,opened,closed) if fills else None)
        row['events']=row.get('events') or (closed_pair_trade_events(row.get('long',''),row.get('short',''),fills,opened,closed) if fills else [])
        for ev in row['events']:
            item=dict(ev); item['pair']=f"{row.get('long','')}/{row.get('short','')}"; item['status']='closed'; operation_events.append(item)
        row['net_realized']=safe_number(row.get('net_realized'), safe_number(row.get('realized'))-safe_number(row.get('fees')))
        archived.append(row)
    try:
        mids=current_mids_for_closed(archived)
    except Exception:
        mids={}
    for row in archived:
        long_mid=mids.get(row.get('long')); short_mid=mids.get(row.get('short'))
        current_ratio=long_mid/short_mid if long_mid and short_mid else None
        row['ratio_since_close_pct']=ratio_change_since_close(current_ratio,row.get('close_ratio'))
    archived_realized=sum(safe_number(p.get('realized')) for p in archived)
    archived_fees=sum(safe_number(p.get('fees')) for p in archived)
    account_funding=ledger.account_funding(account)
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
    account_value_total=account_value_from_portfolio(portfolio)
    if account_value_total is None:
        account_value_total=sum(equity) if equity else None
    operation_events=sorted(operation_events,key=lambda e:int(e.get('time') or 0),reverse=True)[:200]
    summary={'realized':realized_total,'active_realized':active_realized,'archived_realized':archived_realized,'fees':fees_total,'active_fees':active_fees,'archived_fees':archived_fees,'total':grand_total,'open_plus_realized':open_plus_realized,'unrealized':unreal,'exposure':exposure,'funding':funding_total,'margin_used':margin,'margin_core':core_margin,
        'equity_core':core_equity,'account_value_total':account_value_total,'margin_pct':None if not core_equity or core_equity<=0 else core_margin/core_equity*100,
        'delta':sum(p['long_usd']-p['short_usd'] for p in pairs),
        'account_funding':account_funding}
    # A subtotal is useful but must not masquerade as fully verified net PNL.
    known_funding = sum(v for v in funding_values if v is not None)
    summary['net_known_subtotal'] = (unreal + realized_total - fees_total + known_funding) if realized_total is not None and fees_total is not None else None
    summary['net_missing_funding_count'] = sum(v is None for v in funding_values)
    summary.update(funding_summary(pairs, archived))
    save_snapshot(summary)
    local_history=local_pnl_history()  # una sola lectura del archivo de snapshots
    history=local_history or pnl_history(portfolio)
    hl_windows=hl_pnl_windows(portfolio)
    strategy=strategy_data(portfolio, account, fills, fills_complete, ledger,
                           sum(safe_number(p.get('unrealizedPnl')) for p in pos.values()), pairs, positions=pos)
    result = {'pairs':pairs,'closed_pairs':archived,'pnl_history':history,'hl_pnl':hl_windows,'official_pnl':official_pnl_from_windows(hl_windows),'strategy':strategy,'pnl_source':'local' if local_history else 'hyperliquid','operation_events':operation_events,'summary':summary,'last_updated_ms':int(time.time()*1000),
        'ledger':{kind:ledger.state(account,kind) for kind in ('fills','funding')},
        'warnings':(['Funding activo no verificable o desactualizado: neto N/D.'] if any(p.get('funding') is None for p in pairs) else []) + (['Funding de cerrados incompleto: neto N/D.'] if any(p.get('total_pnl') is None for p in archived) else []) + ([] if fills_complete else [f'Historial de fills incompleto; realizado y comisiones no disponibles con certeza ({fills_error or "límite API"}).'])}

    _attach_native_twap_charts(result,account,fills,pos)
    ADVISOR.observe_state(result, positions=pos, account=account)
    return result

def _attach_native_twap_charts(result, account, fills, positions):
    from secure_trade_routes import native_twap_view, _native_store
    from pairs_desk.metrics import pair_trade_events, closed_pair_trade_events
    try:
        view=native_twap_view(account,limit=100)
        jobs=view['items']
        result['twaps']=jobs
        result['twaps_as_of_ms']=view['as_of_ms']
        if not jobs:
            return
        keys=_native_store().fill_keys(account,job_ids=[job['id'] for job in jobs])
        from pairs_desk.entry_history import entry_history, merge_entry_fills
        coins={coin for pair in result['pairs'] for coin in (pair['long'],pair['short'])}
        native_entry_fills=_native_store().entry_fills(account,coins)
        entry_fills=merge_entry_fills(fills,native_entry_fills)
        native_coins={row['coin'] for row in native_entry_fills}
        for pair in result['pairs']:
            pair_id=pair['id']
            if native_coins.intersection((pair['long'],pair['short'])):
                pair['entry_history']=entry_history(pair['long'],pair['short'],
                    positions.get(pair['long'],{}),positions.get(pair['short'],{}),
                    entry_fills,bool(pair.get('history_complete')))
            selected=[job for job in jobs if job['pair_id']==pair_id and
                      (not pair.get('opened_at') or job['planned_end_ms']>=pair['opened_at'])]
            pair['twaps']=selected
            pair['twaps_as_of_ms']=view['as_of_ms']
            if selected and pair.get('events') is not None:
                data=dict(pair,long_position=positions.get(pair['long'],{}),
                          short_position=positions.get(pair['short'],{}))
                pair['chart_events']=pair_trade_events(data,fills,excluded_fill_keys=keys)
        for pair in result.get('closed_pairs',[]):
            pair_id=pair.get('long','')+'|'+pair.get('short','')
            selected=[job for job in jobs if job['pair_id']==pair_id and
                      job['created_ms']<=int(pair.get('closed_at') or 0) and
                      job['planned_end_ms']>=int(pair.get('opened_at') or 0)]
            pair['twaps']=selected
            pair['twaps_as_of_ms']=view['as_of_ms']
            if selected:
                # Filter only chart annotation rows, retaining full ledger/accounting.
                display_fills=[f for f in fills if (f.get('coin'),str(f.get('tid'))) not in keys]
                pair['chart_events']=closed_pair_trade_events(
                    pair.get('long'),pair.get('short'),display_fills,
                    pair.get('opened_at'),pair.get('closed_at'))
    except Exception:
        result.setdefault('warnings',[]).append('Seguimiento TWAP no disponible; verificá el estado en Hyperliquid.')


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
    from secure_trade_routes import _NATIVE_MONITOR
    _NATIVE_MONITOR.stop()

@app.get('/api/state')
def api_state():
    try:
        with _STATES_LOCK: return states()
    except HTTPException:raise
    except Exception as exc:raise HTTPException(503,f'Error de lectura: {type(exc).__name__}')

@app.get('/api/position-ratio-changes')
def api_position_ratio_changes():
    cfg, err = load_settings(SETTINGS)
    if err:
        raise HTTPException(409, 'Configuración inválida')
    account = cfg.get('address', '').strip()
    if not ADDRESS.fullmatch(account):
        raise HTTPException(400, 'Cuenta no configurada')

    now_ms = int(time.time() * 1000)
    with ThreadPoolExecutor(max_workers=2) as pool:
        core_future = pool.submit(hl, {'type': 'clearinghouseState', 'user': account})
        xyz_future = pool.submit(hl, {'type': 'clearinghouseState', 'user': account, 'dex': 'xyz'})
        core = core_future.result()
        xyz = xyz_future.result()
    positions = position_map(core)
    positions.update({key if ':' in key else f'xyz:{key}': value for key, value in position_map(xyz).items()})

    active = []
    for saved in cfg.get('pairs', []):
        long, short = saved.get('long'), saved.get('short')
        lp, sp = positions.get(long), positions.get(short)
        if not long or not short or not lp or not sp:
            continue
        long_size, short_size = safe_number(lp.get('szi')), safe_number(sp.get('szi'))
        long_mark = abs(safe_number(lp.get('positionValue')) / long_size) if long_size else 0
        short_mark = abs(safe_number(sp.get('positionValue')) / short_size) if short_size else 0
        if long_size <= 0 or short_size >= 0 or long_mark <= 0 or short_mark <= 0:
            continue
        active.append((f'{long}|{short}', long, short, long_mark / short_mark))

    start, end = candle_window(5, n=320, now_ms=now_ms)

    coins = {coin for _, long, short, _ in active for coin in (long, short)}
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(coins)))) as candle_pool:
        candle_futures = {coin: candle_pool.submit(hl, {'type': 'candleSnapshot', 'req': {
            'coin': coin, 'interval': '5m', 'startTime': start, 'endTime': end,
        }}) for coin in coins}

    def read_pair(item):
        pair_id, long, short, current_ratio = item
        try:
            def read(coin):
                raw = candle_futures[coin].result()
                return pd.DataFrame([
                    {'time': int(row['t']), 'open': float(row['o']), 'high': float(row['h']),
                     'low': float(row['l']), 'close': float(row['c'])}
                    for row in raw
                ])

            left, right = read(long), read(short)
            if left.empty or right.empty:
                raise ValueError('historial vacío')
            return pair_id, ratio_changes_from_bars(
                current_ratio, ratio_bars(left, right, '5m'), now_ms
            )
        except Exception:
            return pair_id, {'1h': None, '24h': None}

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(active)))) as pool:
        results = dict(pool.map(read_pair, active))
    return {'as_of_ms': now_ms, 'pairs': results}

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

# --- Explorador: universo de activos con cambio 24h/7d y consumo acotado de Hyperliquid ---------
# El universo (2 requests) se cachea en memoria; las recargas del navegador NO llegan a Hyperliquid.
ASSET_CACHE_TTL_S = 30.0
ASSET_FORCE_MIN_S = 10.0   # incluso con "Actualizar activos" no se consulta más seguido que esto
WEEKLY_REFS = Path.home()/'.local'/'share'/'crypto-pairs-desk'/'asset_week_refs.json'
_ASSET_CACHE: dict[str, Any] = {'at': 0.0, 'assets': None}
_ASSET_LOCK = threading.Lock()
_WEEKLY: dict[str, Any] = {'worker': None}

def _weekly_worker():
    if os.environ.get('PAIRS_DESK_DISABLE_WEEKLY_REFS') == '1':
        return None
    with _ASSET_LOCK:
        if _WEEKLY['worker'] is None:
            try:
                interval = float(os.environ.get('PAIRS_DESK_WEEKLY_INTERVAL_S', DEFAULT_INTERVAL_S))
            except ValueError:
                interval = DEFAULT_INTERVAL_S
            worker = WeeklyReferenceWorker(WeeklyReferenceStore(WEEKLY_REFS), lambda request: hl(request), interval_s=interval)
            worker.start()
            _WEEKLY['worker'] = worker
        return _WEEKLY['worker']

def _asset_universe(force: bool) -> list[dict[str, Any]]:
    now = time.monotonic()
    min_age = ASSET_FORCE_MIN_S if force else ASSET_CACHE_TTL_S
    with _ASSET_LOCK:
        cached = _ASSET_CACHE['assets']
        if cached is not None and now - _ASSET_CACHE['at'] < min_age:
            return cached
    catalog = MarketCatalog(MARKET_DB)
    assets = AssetUniverseService(lambda request: hl(request), catalog).list_assets()
    fresh = [asset.to_dict() for asset in assets]
    with _ASSET_LOCK:
        _ASSET_CACHE['assets'], _ASSET_CACHE['at'] = fresh, now
    worker = _weekly_worker()
    if worker is not None:
        worker.submit(priority_order(fresh))
    return fresh

def _advisor_cached_assets():
    with _ASSET_LOCK:
        cached=_ASSET_CACHE['assets']
        age=time.monotonic()-_ASSET_CACHE['at']
        if cached is None or age>ASSET_CACHE_TTL_S:
            from pairs_desk.local_advisor import AdvisorError
            raise AdvisorError('Catálogo sin lectura reciente. Abrí Explorador para actualizarlo.')
        rows=[{k:row.get(k) for k in ('instrument_id','symbol','venue','mark_px','day_volume_usd')} for row in cached]
    return {'as_of_ms':int((time.time()-age)*1000),'source':'Catálogo cacheado de Pair Desk','assets':rows[:60],
            'total':len(rows),'limit':60}

ADVISOR.assets=_advisor_cached_assets

@app.get('/api/scanner/assets')
def api_scanner_assets(search: str = '', venue: str = '', refresh: bool = False):
    clean_search, clean_venue = search.strip().lower(), venue.strip().lower()
    try:
        now_ms = int(time.time() * 1000)
        universe = _asset_universe(refresh)
        worker = _WEEKLY['worker']
        refs = worker.store.snapshot() if worker is not None else {}
        asset_dicts = attach_changes(universe, refs, now_ms)
        filtered = [asset for asset in asset_dicts if (not clean_search or clean_search in asset['symbol'].lower() or clean_search in asset['instrument_id'].lower()) and (not clean_venue or clean_venue == asset['venue'])]
        liquid = priority_order(universe)
        return {'assets': filtered, 'total': len(filtered), 'as_of_ms': now_ms, 'week': {**weekly_progress(liquid, refs, now_ms), 'enabled': worker is not None, 'rate_limited': bool(worker and worker.last_error)}}
    except Exception as exc:
        raise HTTPException(503, f'No se pudieron leer los activos: {type(exc).__name__}')

@app.post('/api/scanner/analyze')
def api_scanner_analyze(payload: dict[str, Any]):
    interval = str(payload.get('interval') or '1h')
    if interval not in ('15m', '1h', '4h', '1d'):
        raise HTTPException(400, 'Intervalo inválido')
    try:
        lookback_days = int(payload.get('lookback_days') or 180)
        long_id = str(payload.get('long_instrument_id') or '').strip()
        short_id = str(payload.get('short_instrument_id') or '').strip()
        catalog = MarketCatalog(MARKET_DB)
        service = PairAnalysisService(catalog, MarketDataStore(MARKET_DATA), lambda **request: hl(request))
        return service.analyze(long_id, short_id, interval=interval, lookback_days=lookback_days).to_dict()
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        raise HTTPException(503, f'No se pudo analizar el par: {type(exc).__name__}')

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
            'pair_status':status,'pair_status_reason':reason,'hit_rates':hit,
            'levels_v3':levels,**{k:v for k,v in mae.items() if k in ('mae_pct','mfe_pct','mae_usd','mfe_usd')}}

def _current_funding_rates(now_ms=None):
    """Tasas de funding vigentes (core + xyz). Si una consulta falla, se omite sin romper la analítica."""
    global _FUNDING_RATE_CACHE
    now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    if _FUNDING_RATE_CACHE and now_ms - _FUNDING_RATE_CACHE[0] < FUNDING_RATE_TTL_MS:
        return dict(_FUNDING_RATE_CACHE[1])
    rates={}
    for payload in ({'type':'metaAndAssetCtxs'},{'type':'metaAndAssetCtxs','dex':'xyz'}):
        try:rates.update(funding_rates(hl(payload)))
        except Exception:pass
    _FUNDING_RATE_CACHE = (now_ms, dict(rates))
    return rates

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
    rates=_current_funding_rates()
    def compute(pair):
        try:result=_analytic_for_pair(pair,now_ms)
        except Exception as exc:result={'status':'unavailable','reason':'Error analítico: '+type(exc).__name__,'pair_status':'SIN_DATOS'}
        long_coin,short_coin=pair['id'].split('|',1)
        result.update(pair_funding_carry(long_coin,short_coin,pair.get('long_usd'),pair.get('short_usd'),rates))
        return pair['id'],result
    with ThreadPoolExecutor(max_workers=3) as pool: results=dict(pool.map(compute,pairs))
    result = {'as_of_ms':now_ms,'pairs':results}
    ADVISOR.observe_analytics(result, account=account)
    return result

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
