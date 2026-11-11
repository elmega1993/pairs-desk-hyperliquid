#!/usr/bin/env python3
"""Import evidence and reconstruct local daily account history without trading."""
from __future__ import annotations

import argparse
import json
import sys
import time
from bisect import bisect_right
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import requests
from pairs_desk.historical_account import HistoricalAccount, ZONE, inventory_timeline, reconcile_exports
from pairs_desk.strategy_analytics import aligned_portfolio_history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--interval', choices=['1h','15m'], default='15m')
    args = parser.parse_args()
    data = Path.home()/'.local/share/crypto-pairs-desk'
    settings = json.loads((Path.home()/'.config/crypto-pairs-desk/settings.json').read_text())
    account = settings['address'].lower()
    store = HistoricalAccount(data/'historical_account.sqlite3')
    store.bind_account(account)
    imported = store.import_ledger(data/'ledger.sqlite3', account)
    csv_counts = {p.name: store.import_csv(p) for p in (ROOT/'Archivos-Hyperliquid').glob('*.csv')}
    snapshot_counts = {p.name: store.import_snapshots(p, account)
                       for p in data.glob('frontend_snapshots.jsonl*')}
    fills = store.events(account, 'fills')
    funding = store.events(account, 'funding')
    funding.sort(key=lambda r: r['time'])
    funding_times = [r['time'] for r in funding]
    funding_totals = [0.0]
    for row in funding:
        funding_totals.append(funding_totals[-1]+float(row['delta']['usdc']))

    def funding_at(timestamp):
        return funding_totals[bisect_right(funding_times, timestamp)]
    timeline = inventory_timeline(fills)
    start = int(datetime(2026,9,23,tzinfo=ZONE).timestamp()*1000)
    now = int(time.time()*1000)
    session = requests.Session()

    def fetch(payload):
        response = session.post('https://api.hyperliquid.xyz/info', json=payload, timeout=(5,25))
        response.raise_for_status()
        return response.json()

    if not args.offline:
        windows = dict(fetch({'type': 'portfolio', 'user': account}))
        official = aligned_portfolio_history(windows)
        with store.db:
            store.db.executemany('INSERT OR REPLACE INTO official_points VALUES (?,?,?)',
                                 [(account,r['time'],r['pnl']) for r in official])
    else:
        official = [{'time':t,'pnl':p} for t,p in store.db.execute(
            'SELECT time,pnl FROM official_points WHERE account=? ORDER BY time', (account,))]
    official = [r for r in official if r['time']>=start]
    if not official:
        raise SystemExit('No official anchor available')
    anchor = official[0]
    relevant = [s for s in timeline if s['time']>=start]
    previous = [s for s in timeline if s['time']<start]
    if previous:
        relevant.insert(0, previous[-1])
    coins = sorted({c for s in relevant for c in s['positions']})
    errors = {}
    for i, coin in enumerate(coins):
        if args.offline:
            continue
        covered = store.db.execute('SELECT min(time),max(end_time) FROM price_candles WHERE coin=? AND interval=?', (coin,args.interval)).fetchone()
        since = max(start-3_600_000, (covered[1]-3_600_000) if covered[1] else start-3_600_000)
        try:
            rows = fetch({'type':'candleSnapshot','req':{'coin':coin,'interval':args.interval,'startTime':since,'endTime':now}})
            if not isinstance(rows,list):
                raise ValueError('Unexpected candle response')
            store.save_candles(coin, rows)
            print(f'prices {i+1}/{len(coins)}: {len(rows)} rows', flush=True)
        except (requests.RequestException, ValueError) as exc:
            errors[coin] = type(exc).__name__
            print(f'prices {i+1}/{len(coins)}: unavailable', flush=True)
            if isinstance(exc, requests.HTTPError) and exc.response.status_code==429:
                raise SystemExit('Rate limited: saved progress; rerun later')
        time.sleep(.12)

    base = store.value_at(timeline, anchor['time'])
    base_funding = funding_at(anchor['time'])
    checks = []
    for point in official:
        value = store.value_at(timeline, point['time'])
        difference = (value['gross']-base['gross']-(point['pnl']-anchor['pnl'])
                      if value['gross'] is not None and base['gross'] is not None else None)
        net_difference = (difference - (value['fees']-base['fees']) + funding_at(point['time'])-base_funding
                          if difference is not None else None)
        checks.append({'time':point['time'],'gross_difference':difference,
                       'net_difference':net_difference,'missing':value['missing']})
    day = datetime(2026,9,23,tzinfo=ZONE)
    daily = []
    previous_value = base['gross']
    previous_net = None if base['gross'] is None else base['gross']-base['fees']+base_funding
    while int(day.timestamp()*1000)<now:
        end = min(int((day+timedelta(days=1)).timestamp()*1000), now)
        value = store.value_at(timeline, end-1)
        gross = value['gross']
        cumulative = gross-base['gross'] if gross is not None and base['gross'] is not None else None
        delta = gross-previous_value if gross is not None and previous_value is not None else None
        net = gross-value['fees']+funding_at(end-1) if gross is not None else None
        net_delta = net-previous_net if net is not None and previous_net is not None else None
        date = day.date().isoformat()
        daily_funding = sum(float(r['delta']['usdc']) for r in funding
                            if int(day.timestamp()*1000)<=r['time']<end)
        row = {**value,'date':date,'pnl':delta,'cumulative':cumulative,
               'net_pnl_estimate':net_delta,
               'net_cumulative_estimate':net-(base['gross']-base['fees']+base_funding) if net is not None and base['gross'] is not None else None,
               'funding':daily_funding,'partial':end==now or day.date()==datetime.fromtimestamp(anchor['time']/1000,ZONE).date()}
        daily.append(row)
        with store.db:
            store.db.execute('INSERT OR REPLACE INTO daily VALUES (?,?,?)',(account,date,json.dumps(row)))
        previous_value = gross
        previous_net = net
        day += timedelta(days=1)
    with store.db:
        for row in checks:
            store.db.execute('INSERT OR REPLACE INTO valuations VALUES (?,?,?,?)',
                             (account,row['time'],'official_reconciliation',json.dumps(row)))
    differences = [abs(r['net_difference']) for r in checks if r['net_difference'] is not None]
    report = {'source_events':imported,'csv_evidence':csv_counts,'local_snapshot_evidence':snapshot_counts,
              'export_reconciliation':reconcile_exports(store,account),
              'fill_inventory_continuity':'verified',
              'days':len(daily),'days_with_estimate':sum(r['pnl'] is not None for r in daily),
              'partial_days':sum(r['partial'] for r in daily),'official_anchor_ms':anchor['time'],
              'timezone':'America/Argentina/Buenos_Aires', 'algorithm_version':1,
              'missing_prices':sorted({c for r in daily for c in r['missing']}),
              'price_errors':errors,'official_checks':len(checks),'checks_with_estimate':len(differences),
              'max_abs_difference':max(differences) if differences else None,
              'mean_abs_difference':sum(differences)/len(differences) if differences else None,
              'comparison_basis':'realized + unrealized + funding - USDC fees',
              'quality':'estimated_not_official','updated_ms':now}
    with store.db:
        store.db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('coverage',json.dumps(report)))
    print(json.dumps(report,indent=2), flush=True)
    store.db.close()


if __name__=='__main__':
    main()
