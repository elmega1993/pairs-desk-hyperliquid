"""Read-only accounting and signals for the independent Pairs Desk frontend."""
from __future__ import annotations
import math
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pairs_desk.entry_history import entry_history
from pairs_desk.ledger import Ledger
from pairs_desk.metrics import since_open, pair_trade_events, management_signals, DEFAULT_MANAGEMENT_RULES

_cache = {}
def recent_fills(address, hl):
    key=address.lower(); now=time.time()
    cached=_cache.get(key)
    if cached and now-cached[0]<40:return cached[1:]
    def query(**payload):return hl(payload)
    result=Ledger().sync(address, query)
    if result['fills'].get('error'):
        raise RuntimeError('No se pudo sincronizar el ledger de fills')
    fills=result['fills_rows']; complete=result['fills'].get('complete',False)
    _cache[key]=(now,fills,complete)
    return fills,complete

def add_accounting(pair, long_pos, short_pos, fills, history_complete):
    lp,sp=long_pos,short_pos
    lo,lfee,lreal,lc=since_open(fills,pair['long'],float(lp.get('szi') or 0))
    so,sfee,sreal,sc=since_open(fills,pair['short'],float(sp.get('szi') or 0))
    valid=bool(history_complete and lc and sc)
    pair['realized']=lreal+sreal if valid else None
    pair['fees']=lfee+sfee if valid else None
    pair['history_complete']=valid
    pair['opened_at']=max(t for t in (lo,so) if t) if lo and so else None
    pair['total_pnl']=(pair['pnl']+pair['funding']+pair['realized']-pair['fees']) if valid and pair['funding'] is not None else None
    pair['long_position']=lp;pair['short_position']=sp
    pair['events']=pair_trade_events(pair,fills) if lc and sc else []
    pair['entry_history']=entry_history(pair['long'],pair['short'],lp,sp,fills,valid)
    # Avoid browser-side duplication of sensitive raw position internals.
    pair.pop('long_position',None);pair.pop('short_position',None)
    return pair

def zscore_from_bars(bars, lookback=250):
    """Same daily arithmetic-ratio rolling Z used by Streamlit.

    Streamlit requests 250 bars and spread_stats chooses min(90, len//3),
    with population std. Always use the final 250 bars, even on larger charts.
    """
    import pandas as pd
    from pairs_desk.metrics import spread_stats
    try:
        tail = bars[-lookback:]
        closes = [float(item['close']) for item in tail]
        if len(closes) < 20 or any(not math.isfinite(v) or v <= 0 for v in closes):
            return None
        data = spread_stats(pd.DataFrame({'c': closes}))
        z = float(data['z'].iloc[-1])
        return round(z, 3) if math.isfinite(z) else None
    except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError):
        return None


def funding_summary(active, closed):
    """Expose verified subtotals without presenting partial coverage as a total."""
    av = [p.get('funding') for p in active]
    cv = [p.get('funding') for p in closed]
    known = [v for v in av + cv if v is not None]
    return {
        'active_funding': sum(av) if all(v is not None for v in av) else None,
        'archived_funding': sum(cv) if all(v is not None for v in cv) else None,
        'known_funding': sum(known) if known or not av + cv else None,
        'active_funding_missing': sum(v is None for v in av),
        'archived_funding_missing': sum(v is None for v in cv),
    }


def management_snapshot(pair_cfg, ratio, z):
    ref=pair_cfg.get('management_entry_ratio')
    try:
        ref=float(ref)
        change=(float(ratio)/ref-1)*100 if ref>0 and math.isfinite(ref) else None
        if change is not None and not math.isfinite(change):change=None
    except (TypeError,ValueError,ZeroDivisionError):
        change=None
    def levels(key):
        return [int(x['level']) for x in pair_cfg.get(key,[]) if isinstance(x,dict) and str(x.get('level','')).isdigit()]
    result=management_signals(change,z,levels('executed_tp'),levels('executed_add'),pair_cfg.get('management_rules'))
    result.update(reference=ref,ratio_change=change,z=z,computed_at=int(time.time()*1000))
    if change is None:
        result['tp_detail']=result['add_detail']='Falta una referencia de gestión congelada válida; no se evalúan señales.'
    return result
