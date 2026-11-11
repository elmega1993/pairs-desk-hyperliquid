"""Account history reconstruction, separate from the live ledger and order storage."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('America/Argentina/Buenos_Aires')
SPOT_DIRECTIONS = {'Buy', 'Sell', 'Spot Dust Conversion'}


def api_symbol(value):
    match = re.fullmatch(r'(.+) \(([^)]+)\)', value)
    if match:
        symbol, venue = match.groups()
        # Export display names differ from API symbols.
        aliases = {'S&P500': 'SP500', 'WTIOIL': 'CL', 'OPENAI': 'OAI', 'ANT': 'ANTH', 'SKHYNIX': 'SKHX'}
        return f'{venue}:{aliases.get(symbol, symbol)}'
    return value


def csv_timestamp(value):
    return int(datetime.strptime(value, '%d/%m/%Y - %H:%M:%S').replace(tzinfo=ZONE).timestamp()*1000)


def ordered_perp_fills(fills):
    """Trade IDs aren't sequential: chain same-ms fills by startPosition."""
    groups = defaultdict(list)
    for row in fills:
        if row.get('dir') not in SPOT_DIRECTIONS:
            groups[(int(row['time']), row['coin'])].append(row)
    positions = {}
    for (timestamp, coin), group in sorted(groups.items()):
        pending = list(group)
        while pending:
            previous = positions.get(coin)
            candidates = [r for r in pending if Decimal(r['startPosition']) == previous]
            if not candidates:
                ends = {Decimal(r['startPosition']) + Decimal(r['sz'])*(1 if r['side']=='B' else -1) for r in pending}
                candidates = [r for r in pending if Decimal(r['startPosition']) not in ends] or pending
            row = candidates[0]
            start = Decimal(row['startPosition'])
            if previous is not None and abs(previous-start) > Decimal('0.00000001'):
                raise ValueError(f'Discontinuous position for {coin} at {timestamp}')
            positions[coin] = start + Decimal(row['sz'])*(1 if row['side']=='B' else -1)
            yield row
            pending.remove(row)


def inventory_timeline(fills):
    """Reconstruct average entry; realized PNL remains the exchange supplied value."""
    inventory = {}
    realized = fees = 0.0
    snapshots = []
    for row in ordered_perp_fills(fills):
        coin = row['coin']
        start = float(row['startPosition'])
        delta = float(row['sz'])*(1 if row['side']=='B' else -1)
        price, closed = float(row['px']), float(row['closedPnl'])
        entry = inventory.get(coin, (start, None))[1]
        close_qty = min(abs(start), abs(delta)) if start*delta < 0 else 0
        if close_qty and entry is None:
            entry = price - closed/close_qty*(1 if start>0 else -1)
        end = start + delta
        if abs(end) < 1e-8:
            inventory.pop(coin, None)
        elif start == 0 or start*end < 0:
            inventory[coin] = (end, price)
        elif start*delta > 0:
            average = (abs(start)*entry+abs(delta)*price)/abs(end) if entry is not None else None
            inventory[coin] = (end, average)
        else:
            inventory[coin] = (end, entry)
        realized += closed
        if row.get('feeToken') == 'USDC':
            fees += float(row.get('fee', 0))
        snapshots.append({'time': int(row['time']), 'positions': dict(inventory),
                          'realized': realized, 'fees': fees})
    return snapshots


def reconcile_exports(store, account):
    """CSV closedPnl is net of fees; old funding CSV rows can aggregate UTC days."""
    from bisect import bisect_left
    trades = defaultdict(list)
    for row in store.events(account,'fills'):
        trades[(row['time']//1000,row['coin'],row['dir'])].append(row)
    funding = defaultdict(list)
    for row in store.events(account,'funding'):
        funding[row['delta']['coin']].append((row['time']//1000,Decimal(row['delta']['usdc'])))
    funding_times, funding_sums = {}, {}
    for coin, values in funding.items():
        values.sort()
        funding_times[coin] = [t for t,v in values]
        funding_sums[coin] = [Decimal(0)]
        for t,value in values:
            funding_sums[coin].append(funding_sums[coin][-1]+value)
    counts = defaultdict(int)
    for timestamp,coin,payload in store.db.execute('SELECT time,coin,payload FROM csv_evidence'):
        row=json.loads(payload)
        second=timestamp//1000
        if 'dir' in row:
            if row['dir'] in SPOT_DIRECTIONS:
                counts['spot_evidence_not_part_of_perp_curve']+=1
                continue
            key=(second,coin,row['dir'].replace('Market Order Liquidation: ',''))
            group=trades[key]
            quantity=sum(Decimal(r['sz']) for r in group)
            net=sum(Decimal(r['closedPnl'])-Decimal(r['fee']) for r in group)
            ok=abs(quantity-Decimal(row['sz']))<Decimal('.000001') and abs(net-Decimal(row['closedPnl']))<Decimal('.00001')
            counts['perp_trade_matched' if ok else 'perp_trade_unresolved']+=1
        elif 'payment' in row:
            times=funding_times.get(coin,[])
            prefix=funding_sums.get(coin,[Decimal(0)])
            low=bisect_left(times,second)
            hourly=prefix[bisect_left(times,second+1)]-prefix[low]
            daily=prefix[bisect_left(times,second+86400)]-prefix[low]
            target=Decimal(row['payment'])
            if low<len(times) and times[low]==second and abs(hourly-target)<Decimal('.00001'):
                counts['funding_hourly_matched']+=1
            elif datetime.fromtimestamp(timestamp/1000,ZONE).hour==21 and abs(daily-target)<Decimal('.00001'):
                counts['funding_utc_daily_aggregate_matched']+=1
            else:
                counts['funding_unresolved']+=1
    return dict(counts)


class HistoricalAccount:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.path.chmod(0o600)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events(account TEXT,kind TEXT,identity TEXT,time INTEGER,payload TEXT,
              PRIMARY KEY(account,kind,identity));
            CREATE TABLE IF NOT EXISTS source_files(hash TEXT PRIMARY KEY,name TEXT,content BLOB);
            CREATE TABLE IF NOT EXISTS csv_evidence(hash TEXT,row_number INTEGER,time INTEGER,coin TEXT,payload TEXT,
              PRIMARY KEY(hash,row_number));
            CREATE TABLE IF NOT EXISTS candles(coin TEXT,time INTEGER,end_time INTEGER,close REAL,payload TEXT,
              PRIMARY KEY(coin,time));
            CREATE TABLE IF NOT EXISTS price_candles(coin TEXT,interval TEXT,time INTEGER,end_time INTEGER,close REAL,payload TEXT,
              PRIMARY KEY(coin,interval,time));
            CREATE INDEX IF NOT EXISTS price_lookup ON price_candles(coin,end_time);
            CREATE TABLE IF NOT EXISTS official_points(account TEXT,time INTEGER,pnl REAL,
              PRIMARY KEY(account,time));
            CREATE TABLE IF NOT EXISTS valuations(account TEXT,time INTEGER,source TEXT,payload TEXT,
              PRIMARY KEY(account,time,source));
            CREATE TABLE IF NOT EXISTS daily(account TEXT,date TEXT,payload TEXT,PRIMARY KEY(account,date));
        ''')
        if not self.db.execute("SELECT 1 FROM metadata WHERE key='price_schema_v2'").fetchone():
            with self.db:
                self.db.execute('''INSERT OR IGNORE INTO price_candles
                    SELECT coin,coalesce(json_extract(payload,'$.i'),'1h'),time,end_time,close,payload FROM candles''')
                self.db.execute("INSERT INTO metadata VALUES ('price_schema_v2','1')")

    def bind_account(self, account):
        account = account.lower()
        prior = self.db.execute("SELECT value FROM metadata WHERE key='account'").fetchone()
        if prior and prior[0] != account:
            raise ValueError('Historical database belongs to another account')
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('account',?)", (account,))

    def import_ledger(self, source, account):
        with sqlite3.connect(f'file:{Path(source).resolve()}?mode=ro', uri=True) as db:
            rows = db.execute('SELECT account,kind,identity,time,payload FROM events WHERE account=?',
                              (account.lower(),)).fetchall()
        with self.db:
            for row in rows:
                prior = self.db.execute('SELECT payload FROM events WHERE account=? AND kind=? AND identity=?', row[:3]).fetchone()
                if prior and json.loads(prior[0]) != json.loads(row[4]):
                    raise ValueError('Conflicting source event')
                self.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?)', row)
        return len(rows)

    def import_csv(self, path):
        path = Path(path)
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        rows = list(csv.DictReader(raw.decode('utf-8-sig').splitlines()))
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO source_files VALUES (?,?,?)', (digest, path.name, raw))
            for i, row in enumerate(rows, 1):
                self.db.execute('''INSERT INTO csv_evidence VALUES (?,?,?,?,?)
                    ON CONFLICT(hash,row_number) DO UPDATE SET coin=excluded.coin''',
                    (digest, i, csv_timestamp(row['time']), api_symbol(row['coin']), json.dumps(row)))
        return len(rows)

    def import_snapshots(self, path, account):
        count = 0
        with self.db:
            with Path(path).open() as source:
                for line in source:
                    row = json.loads(line)
                    identity = hashlib.sha256(line.strip().encode()).hexdigest()
                    self.db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?)',
                        (account.lower(), 'local_snapshot_evidence', identity,
                         int(row['time']), json.dumps(row)))
                    count += 1
        return count

    def events(self, account, kind):
        return [json.loads(r[0]) for r in self.db.execute(
            'SELECT payload FROM events WHERE account=? AND kind=? ORDER BY time', (account.lower(), kind))]

    def save_candles(self, coin, rows):
        with self.db:
            for row in rows:
                value = float(row['c'])
                if not math.isfinite(value) or value <= 0 or row.get('s') != coin:
                    raise ValueError('Invalid historical price')
                self.db.execute('INSERT OR REPLACE INTO price_candles VALUES (?,?,?,?,?,?)',
                    (coin, row.get('i','1h'), int(row['t']), int(row['T']), value, json.dumps(row)))

    def value_at(self, timeline, timestamp):
        from bisect import bisect_right
        index = bisect_right([r['time'] for r in timeline], timestamp)-1
        if index < 0:
            return {'gross': None, 'missing': ['inventory'], 'time': timestamp}
        state = timeline[index]
        unrealized = 0
        missing = []
        for coin, (quantity, entry) in state['positions'].items():
            price = self.db.execute('SELECT end_time,close FROM price_candles WHERE coin=? AND end_time<=? ORDER BY end_time DESC,interval LIMIT 1',
                                    (coin, timestamp)).fetchone()
            if entry is None or price is None or timestamp-price[0] > 3_600_001:
                missing.append(coin)
            else:
                unrealized += quantity*(price[1]-entry)
        return {'time': timestamp, 'gross': state['realized']+unrealized if not missing else None,
                'realized': state['realized'], 'unrealized': unrealized if not missing else None,
                'fees': state['fees'], 'missing': missing, 'positions': len(state['positions']),
                'source': 'reconstructed_fills_trade_candle_close', 'quality': 'estimated'}


def archive_official_history(path, ledger, account, rows):
    """Archive official samples and new ledger evidence; no price downloads here."""
    if not Path(path).exists():
        return
    store = HistoricalAccount(path)
    try:
        store.bind_account(account)
        if Path(ledger).exists():
            store.import_ledger(ledger, account)
        with store.db:
            store.db.executemany('INSERT OR REPLACE INTO official_points VALUES (?,?,?)',
                [(account.lower(),row['time'],row['pnl']) for row in rows])
            store.db.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',
                             ('last_live_archive_ms',str(int(datetime.now().timestamp()*1000))))
    finally:
        store.db.close()


def reconstructed_daily(path, account, official_history=None):
    """Read derived net daily rows without changing the original official series."""
    if not Path(path).exists():
        return {'daily':[], 'updated_ms':None}
    try:
        with sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True) as db:
            record=db.execute("SELECT value FROM metadata WHERE key='coverage'").fetchone()
            coverage=json.loads(record[0]) if record else {}
            rows=[]
            for payload, in db.execute('SELECT payload FROM daily WHERE account=? ORDER BY date',(account.lower(),)):
                row=json.loads(payload)
                rows.append({'date':row['date'],'pnl':row.get('net_pnl_estimate'),
                    'cumulative':row.get('net_cumulative_estimate'),'partial':row.get('partial',False),
                    'quality':'estimated','source':'fills_funding_trade_candles'})
        # Keep completed estimates, but never freeze the calendar at the date of
        # a manual rebuild. Official samples can complete the stale partial day
        # and subsequent days when they share the reconstruction's anchor.
        if len(rows)>1 and official_history and coverage.get('official_anchor_ms')==official_history[0]['time']:
            latest=official_history[-1]
            date=datetime.fromtimestamp(latest['time']/1000,ZONE).date().isoformat()
            if rows[-1]['date']==date:
                previous=rows[-2]['cumulative']
                if previous is not None:
                    rows[-1].update(pnl=latest['pnl']-previous,cumulative=latest['pnl'],partial=True,
                        source='official_latest_minus_estimated_previous_close')
            elif rows[-1]['date']<date:
                last=rows[-1]
                day=datetime.fromisoformat(last['date']).date()
                if last['partial']:
                    rows.pop()
                else:
                    day+=timedelta(days=1)
                previous=rows[-1]['cumulative']
                closes={}
                for point in official_history:
                    local_date=datetime.fromtimestamp(point['time']/1000,ZONE).date().isoformat()
                    closes[local_date]=point['pnl']
                while day.isoformat()<=date:
                    value=closes.get(day.isoformat())
                    pnl=value-previous if value is not None and previous is not None else None
                    rows.append({'date':day.isoformat(),'pnl':pnl,'cumulative':value,
                        'partial':day.isoformat()==date,'quality':'approximate',
                        'source':'official_samples_minus_previous_close'})
                    previous=value
                    day+=timedelta(days=1)
        return {'daily':rows,'updated_ms':coverage.get('updated_ms')}
    except (sqlite3.Error,OSError,ValueError,KeyError,TypeError):
        return {'daily':[],'updated_ms':None}
