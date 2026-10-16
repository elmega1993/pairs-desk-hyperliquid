"""Read-only, account-scoped durable Hyperliquid accounting (no signing)."""
from __future__ import annotations

import json
import math
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

DEFAULT_PATH = Path.home() / '.local/share/crypto-pairs-desk/ledger.sqlite3'
_LOCK = threading.RLock()


class Ledger:
    def __init__(self, path=None):
        self.path = Path(path or DEFAULT_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS events (
                    account TEXT NOT NULL, kind TEXT NOT NULL, identity TEXT NOT NULL,
                    time INTEGER NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(account, kind, identity));
                CREATE INDEX IF NOT EXISTS event_time ON events(account, kind, time);
                CREATE TABLE IF NOT EXISTS sync_state (
                    account TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY(account, kind));
            ''')
        self.path.chmod(0o600)

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def state(self, account, kind):
        with closing(self.connect()) as db:
            row = db.execute('SELECT payload FROM sync_state WHERE account=? AND kind=?',
                             (account.lower(), kind)).fetchone()
        return json.loads(row[0]) if row else {}

    @staticmethod
    def identity(kind, row):
        if kind == 'fills':
            if row.get('tid') is None or not row.get('coin'):
                raise ValueError('Fill sin tid/coin: no se puede deduplicar con certeza')
            # tid may occur on both sides of a self-trade.
            return json.dumps([str(row['tid']), row['coin'], row.get('side'), row.get('oid')])
        delta = row.get('delta')
        if not isinstance(delta, dict) or delta.get('type') != 'funding' or not delta.get('coin'):
            raise ValueError('Registro userFunding inválido')
        amount = float(delta['usdc'])
        if not math.isfinite(amount) or not row.get('hash'):
            raise ValueError('Funding sin importe finito o identificador')
        return json.dumps([row['hash'], int(row['time']), delta['coin']])

    def rows(self, account, kind):
        with closing(self.connect()) as db:
            return [json.loads(r[0]) for r in db.execute(
                'SELECT payload FROM events WHERE account=? AND kind=? ORDER BY time,identity',
                (account.lower(), kind))]

    def _commit(self, account, kind, rows, state):
        with closing(self.connect()) as db, db:
            for row in rows:
                ident = self.identity(kind, row)
                payload = json.dumps(row, sort_keys=True, separators=(',', ':'), allow_nan=False)
                prior = db.execute('SELECT payload FROM events WHERE account=? AND kind=? AND identity=?',
                                   (account, kind, ident)).fetchone()
                if prior and prior[0] != payload:
                    raise ValueError('Evento del ledger cambió: se requiere conciliación')
                db.execute('INSERT OR IGNORE INTO events VALUES (?,?,?,?,?)',
                           (account, kind, ident, int(row['time']), payload))
            db.execute('INSERT OR REPLACE INTO sync_state VALUES (?,?,?)',
                       (account, kind, json.dumps(state)))

    def sync(self, account, fetch, now_ms=None):
        """Bound each sweep; replay the last timestamp to catch page-boundary ties.

        A missing retained anchor or a saturated timestamp permanently marks
        fills partial. Funding coverage advances only after an exhausted sweep.
        Failures never overwrite existing records or advance a checkpoint.
        """
        now = int(time.time()*1000) if now_ms is None else int(now_ms)
        account = account.lower()
        result = {}
        with _LOCK:
            for kind, endpoint, page_size in [('fills', 'userFillsByTime', 2000), ('funding', 'userFunding', 500)]:
                old = self.state(account, kind)
                if old.get('checked_at') is not None and 0 <= now-old['checked_at'] < 30_000:
                    result[kind] = old
                    continue
                cursor = int(old.get('cursor', 0))
                anchor = old.get('anchor')
                seen = {}; exhausted = False; anchor_found = anchor is None
                try:
                    for _ in range(40):
                        payload = dict(type=endpoint, user=account, startTime=cursor, endTime=now)
                        if kind == 'fills':
                            payload['aggregateByTime'] = False
                        page = fetch(**payload)
                        if not isinstance(page, list):
                            raise ValueError(f'{endpoint}: respuesta inválida')
                        times = [int(r['time']) for r in page]
                        if times != sorted(times) or any(t < cursor or t > now for t in times):
                            raise ValueError(f'{endpoint}: timestamps inválidos')
                        for row in page:
                            ident = self.identity(kind, row)
                            anchor_found |= ident == anchor
                            if ident in seen and seen[ident] != row:
                                raise ValueError('Evento duplicado conflictivo')
                            seen[ident] = row
                        if len(page) < page_size:
                            exhausted = True
                            break
                        if not times or times[-1] <= cursor:
                            break  # cannot safely skip a saturated millisecond
                        cursor = times[-1]  # inclusive overlap, never +1
                    rows = list(seen.values())
                    complete = exhausted
                    if kind == 'fills':
                        complete &= anchor_found and len(rows) < 10_000 and old.get('complete', True)
                    state = dict(old, checked_at=now, complete=bool(complete))
                    if exhausted and (kind != 'fills' or anchor_found):
                        last = max(rows, key=lambda r: int(r['time'])) if rows else None
                        # Funding has no retention anchor; overlap one hour for delayed postings.
                        state['cursor'] = int(last['time']) if kind == 'fills' and last else (max(0, now-3_600_000) if kind == 'funding' else old.get('cursor', 0))
                        if kind == 'fills' and last:
                            state['anchor'] = self.identity(kind, last)
                        if complete:
                            state['covered_until'] = now
                    else:
                        # Retry from the old checkpoint, not from a partial sweep.
                        state['cursor'] = old.get('cursor', 0)
                    self._commit(account, kind, rows, state)
                    result[kind] = state
                except Exception as exc:
                    result[kind] = dict(old, error=type(exc).__name__, complete=False)
            result['fills_rows'] = self.rows(account, 'fills')
        return result

    def funding(self, account, intervals):
        """Sum signed userFunding USDC only across fully covered per-leg windows."""
        state = self.state(account, 'funding')
        covered = int(state.get('covered_until', -1))
        if not intervals or any(not start or end < start or end > covered for _, start, end in intervals):
            return None
        total = 0.0
        for row in self.rows(account, 'funding'):
            delta = row['delta']; t = int(row['time'])
            for coin, start, end in intervals:
                if delta['coin'] == coin and start <= t <= end:
                    # With millisecond-only ordering these boundary cases are ambiguous.
                    if t in (start, end):
                        return None
                    total += float(delta['usdc'])
        return total


def closed_accounting(ledger, account, item, fills, fills_complete):
    """Reconstruct each leg separately, rejecting mismatched legacy archives."""
    from .metrics import latest_closed_cycle
    out = dict(item)
    out.update(funding=None, funding_complete=False, total_pnl=None)
    if not fills_complete:
        if (item.get('funding_source') == 'userFunding/ledger-v1'
                and item.get('funding_account') == account.lower()
                and item.get('funding_complete') is True):
            return dict(item)
        return out
    end = int(item.get('closed_at') or 0)
    bounded = [f for f in fills if int(f['time']) <= end]
    cycles = [latest_closed_cycle(bounded, item[leg], 0.0) for leg in ('long', 'short')]
    if not all(cycles):
        return out
    if min(c['opened_at'] for c in cycles) != item.get('opened_at') or max(c['closed_at'] for c in cycles) != end:
        return out
    realized = sum(c['realized'] for c in cycles); fees = sum(c['fees'] for c in cycles)
    if item.get('realized') is None or item.get('fees') is None or not math.isclose(realized, float(item['realized']), abs_tol=1e-6) or not math.isclose(fees, float(item['fees']), abs_tol=1e-6):
        return out
    intervals = [(item[leg], c['opened_at'], c['closed_at']) for leg, c in zip(('long', 'short'), cycles)]
    funding = ledger.funding(account, intervals)
    out.update(funding=funding, funding_complete=funding is not None,
               funding_source='userFunding/ledger-v1', funding_account=account.lower(),
               total_pnl=None if funding is None else realized-fees+funding)
    return out


def active_funding(ledger, account, long_coin, short_coin, fills, long_size, short_size,
                   history_complete, now_ms=None):
    from .metrics import since_open
    now = int(time.time()*1000) if now_ms is None else now_ms
    end = int(ledger.state(account, 'funding').get('covered_until', 0))
    lo, _, _, lc = since_open(fills, long_coin, long_size)
    so, _, _, sc = since_open(fills, short_coin, short_size)
    if not history_complete or not lc or not sc or not lo or not so or not 0 <= now-end <= 60_000:
        return None
    return ledger.funding(account, [(long_coin, lo, end), (short_coin, so, end)])
