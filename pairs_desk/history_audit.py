"""Offline diagnostics of price timing and funding-derived oracle prices."""
from __future__ import annotations

import json
import math
from bisect import bisect_right

from .historical_account import inventory_timeline


def funding_oracle(row):
    """Infer oracle (not mark) with a bound for payment rounding to 1e-6 USDC."""
    delta = row['delta']
    quantity, rate = float(delta['szi']), float(delta['fundingRate'])
    denominator = quantity*rate
    if not math.isfinite(denominator) or not denominator:
        return None
    price = -float(delta['usdc'])/denominator
    error = 0.000001/abs(denominator)
    if not math.isfinite(price) or price <= 0 or error/price > .001:
        return None
    return {'time': int(row['time']), 'coin':delta['coin'], 'price':price,
            'rounding_error_bound':error,'source':'funding_implied_oracle',
            'price_type':'oracle_not_mark'}


def audit_history(store, account):
    timeline = inventory_timeline(store.events(account,'fills'))
    times = [r['time'] for r in timeline]
    funding = store.events(account,'funding')
    funding.sort(key=lambda r:r['time'])
    funding_times = [r['time'] for r in funding]
    funding_totals = [0.0]
    for row in funding:
        funding_totals.append(funding_totals[-1]+float(row['delta']['usdc']))
    oracle_points = [p for row in funding if (p:=funding_oracle(row)) is not None]
    with store.db:
        store.db.execute('''CREATE TABLE IF NOT EXISTS oracle_evidence(
            account TEXT,coin TEXT,time INTEGER,payload TEXT,PRIMARY KEY(account,coin,time))''')
        store.db.executemany('INSERT OR REPLACE INTO oracle_evidence VALUES (?,?,?,?)',
            [(account,p['coin'],p['time'],json.dumps(p)) for p in oracle_points])

    official = store.db.execute('''SELECT time,pnl FROM official_points
        WHERE account=? AND time>=1790132400000 ORDER BY time''',(account,)).fetchall()
    if not official:
        raise ValueError('No official reference points')

    def evaluate(timestamp):
        index=bisect_right(times,timestamp)-1
        if index<0:
            return {'low':None,'high':None,'details':[]}
        state = timeline[index]
        low = high = state['realized']-state['fees']+funding_totals[bisect_right(funding_times,timestamp)]
        details = []
        for coin,(quantity,entry) in state['positions'].items():
            previous = store.db.execute('''SELECT end_time,close FROM price_candles
                WHERE coin=? AND end_time<=? ORDER BY end_time DESC,interval LIMIT 1''',(coin,timestamp)).fetchone()
            # The containing candle is used only for a retrospective uncertainty range.
            # Its high/low/close are never published as a price known at timestamp.
            containing = store.db.execute('''SELECT payload FROM price_candles
                WHERE coin=? AND interval='15m' AND time<=? AND end_time>=?
                ORDER BY time DESC LIMIT 1''',(coin,timestamp,timestamp)).fetchone()
            if previous is None or containing is None or entry is None:
                return {'low':None,'high':None,'details':[]}
            bar = json.loads(containing[0])
            lo,hi = float(bar['l']),float(bar['h'])
            low += quantity*((lo if quantity>0 else hi)-entry)
            high += quantity*((hi if quantity>0 else lo)-entry)
            details.append({'coin':coin,'price_age_minutes':(timestamp-previous[0])/60000,
                'used_price':previous[1],'bar_low':lo,'bar_high':hi,
                'pnl_change_min':min(quantity*(lo-previous[1]),quantity*(hi-previous[1])),
                'pnl_change_max':max(quantity*(lo-previous[1]),quantity*(hi-previous[1]))})
        return {'low':low,'high':high,'details':details}

    base_t,base_pnl = official[0]
    base = evaluate(base_t)
    base_value = store.value_at(timeline,base_t)
    base_funding = funding_totals[bisect_right(funding_times,base_t)]
    checks = []
    for timestamp,pnl in official:
        value = store.value_at(timeline,timestamp)
        bounds = evaluate(timestamp)
        net_delta = (value['gross']-value['fees']+funding_totals[bisect_right(funding_times,timestamp)]
                     -(base_value['gross']-base_value['fees']+base_funding)) if value['gross'] is not None and base_value['gross'] is not None else None
        lower = bounds['low']-base['high'] if bounds['low'] is not None and base['high'] is not None else None
        upper = bounds['high']-base['low'] if bounds['high'] is not None and base['low'] is not None else None
        official_delta = pnl-base_pnl
        difference = net_delta-official_delta if net_delta is not None else None
        details = sorted(bounds['details'],key=lambda p:max(abs(p['pnl_change_min']),abs(p['pnl_change_max'])),reverse=True)
        check = {'time':timestamp,'difference':difference,'official_delta':official_delta,
                 'trade_range_low':lower,'trade_range_high':upper,
                 'official_inside_trade_range': lower<=official_delta<=upper if lower is not None else None,
                 'largest_price_timing_exposures':details[:5],
                 'interpretation':'plausibility_range_not_mark_price_verification'}
        checks.append(check)
    with store.db:
        for row in checks:
            store.db.execute('INSERT OR REPLACE INTO valuations VALUES (?,?,?,?)',
                (account,row['time'],'free_price_timing_audit',json.dumps(row)))
    compared = [r for r in checks if r['difference'] is not None]
    worst = max(compared,key=lambda r:abs(r['difference'])) if compared else None
    report = {'official_points':len(checks),'points_compared':len(compared),
        'oracle_evidence_points':len(oracle_points),
        'official_points_inside_trade_range':sum(r['official_inside_trade_range'] is True for r in checks),
        'worst':worst,'publication_status':'estimated_view_only',
        'method':'Retrospective OHLC range and funding oracle evidence; no paid data'}
    with store.db:
        store.db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('free_history_audit',json.dumps(report)))
    return report
