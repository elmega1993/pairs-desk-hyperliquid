"""Durable native TWAP intents. Never retries an ambiguous exchange submission.

Only deliberately selected public fields enter this database or the UI. All
mutations use independent SQLite transactions; network calls never hold a lock.
"""
from __future__ import annotations

import json
import math
import os
import re
import stat
import time
import uuid
from decimal import Decimal, ROUND_DOWN
from contextlib import contextmanager
from pathlib import Path

from .trade_journal import DEFAULT_DB, connect, pending

TERMINAL = ('complete', 'incomplete', 'cancelled', 'rejected', 'partial')
LEG_TERMINAL = ('finished', 'cancelled', 'rejected')


def _now():
    return int(time.time() * 1000)


def _coin(value):
    return str(value or '').strip()


def _dex(coin):
    return coin.split(':', 1)[0] if ':' in coin else ''


def _number(value):
    result = float(value)
    if not math.isfinite(result) or result < 0:
        raise ValueError('Cantidad inválida')
    return result


def _validate(minutes, randomize, orders):
    if type(minutes) is not int or not 5 <= minutes <= 10080:
        raise ValueError('TWAP requiere de 5 a 10080 minutos enteros')
    if type(randomize) is not bool:
        raise ValueError('Randomize inválido')
    if len(orders) != 2 or len({_coin(o.get('coin')) for o in orders}) != 2:
        raise ValueError('Se requieren dos activos diferentes')
    for o in orders:
        if not _coin(o.get('coin')) or _number(o['size']) <= 0:
            raise ValueError('Cantidad inválida')
        if type(o.get('is_buy')) is not bool or type(o.get('reduce_only')) is not bool:
            raise ValueError('Sentido inválido')


TWAP_MINIMUM_ERROR = 'TWAP requiere al menos 100 USD por pata; el importe solicitado es menor al mínimo nativo.'


def validate_twap_notional(orders):
    for order in orders:
        mark = _number(order.get('mark', 0))
        if mark <= 0 or Decimal(str(order['size'])) * Decimal(str(mark)) < Decimal('100'):
            raise ValueError(TWAP_MINIMUM_ERROR)


def _error_value(response):
    if not isinstance(response, dict):
        return None
    payload = response.get('response')
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        data = payload.get('data')
        if isinstance(data, dict):
            status = data.get('status')
            return status.get('error', data.get('error')) if isinstance(status, dict) else data.get('error')
    return None


def _safe_error_detail(response):
    """Keep only a bounded error message, never a raw response or credentials."""
    value = _error_value(response)
    if not isinstance(value, str):
        return None
    value = value[:2048]
    if re.search(r'(?i)secret|private.?key|password|passphrase|seed.?phrase|authorization|bearer|api.?key|signature|[<>]', value):
        return None
    value = re.sub(r'(?i)https?://\S+', '[enlace omitido]', value)
    value = re.sub(r'(?i)0x[0-9a-f]+|[a-z0-9_+/=-]{32,}', '[dato omitido]', value)
    value = ' '.join(''.join(c if c.isprintable() else ' ' for c in value).split())
    return value[:320] or None


def _rejection_code(response):
    """Classify public reasons separately from a sanitized diagnostic message."""
    value = _error_value(response)
    text = value.lower() if isinstance(value, str) else ''
    if 'user or api wallet' in text and 'does not exist' in text:
        return 'signer_not_found'
    if 'must deposit before performing actions' in text:
        return 'account_not_funded'
    if 'twap' in text and any(term in text for term in ('minimum', 'too small', 'min notional')):
        return 'twap_min_notional'
    if 'twap' in text and 'duration' in text:
        return 'twap_invalid_duration'
    if 'margin' in text and any(term in text for term in ('insufficient', 'not enough')):
        return 'insufficient_margin'
    return 'exchange_rejected'


def _matches_signature(leg, state):
    """Only a sent leg can match an id-less native history/state signature."""
    if leg['before_send_ms'] is None:
        return False
    try:
        side = str(state['side']).upper()
        return (_coin(state['coin']) == leg['coin'] and side in ('B', 'A', 'BUY', 'SELL')
                and (side in ('B', 'BUY')) == bool(leg['is_buy'])
                and type(state['reduceOnly']) is bool and state['reduceOnly'] == bool(leg['reduce_only'])
                and ('user' not in state or str(state['user']).lower() == leg['account'])
                and abs(_number(state['sz']) - leg['size']) <= max(1e-10, leg['size'] * 1e-8)
                and type(state['minutes']) is int and state['minutes'] == leg['minutes']
                and type(state['randomize']) is bool and state['randomize'] == bool(leg['randomize'])
                and abs(int(state['timestamp']) - leg['before_send_ms']) <= 10000)
    except (KeyError, ValueError, TypeError):
        return False


def overlap_sql(conn, account, coins):
    """Call inside caller's BEGIN IMMEDIATE, before reserving immediate orders."""
    coins = [_coin(c) for c in coins]
    if not coins:
        return False
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='native_twap_jobs'").fetchone():
        return False
    placeholders = ','.join('?' for _ in coins)
    return bool(conn.execute(f'''SELECT 1 FROM native_twap_jobs j
        JOIN native_twap_legs l ON l.job_id=j.id
        WHERE j.account=? AND j.status NOT IN ('complete','incomplete','cancelled','rejected','partial')
        AND l.coin IN ({placeholders}) LIMIT 1''', [account.lower(), *coins]).fetchone())


_SCHEMA = '''
            CREATE TABLE IF NOT EXISTS native_twap_jobs (
                id TEXT PRIMARY KEY, account TEXT NOT NULL, pair_id TEXT NOT NULL,
                operation TEXT NOT NULL, minutes INTEGER NOT NULL, randomize INTEGER NOT NULL,
                created_ms INTEGER NOT NULL, planned_end_ms INTEGER NOT NULL,
                status TEXT NOT NULL, updated_ms INTEGER NOT NULL, error TEXT,
                cancel_intent INTEGER NOT NULL DEFAULT 0
            );
            CREATE INDEX IF NOT EXISTS native_twap_account ON native_twap_jobs(account,created_ms);
            CREATE TABLE IF NOT EXISTS native_twap_legs (
                job_id TEXT NOT NULL, leg_index INTEGER NOT NULL, coin TEXT NOT NULL,
                is_buy INTEGER NOT NULL, reduce_only INTEGER NOT NULL, size REAL NOT NULL,
                asset INTEGER, twap_id INTEGER, status TEXT NOT NULL,
                executed_size REAL, executed_notional REAL, updated_ms INTEGER NOT NULL,
                state_ms INTEGER NOT NULL DEFAULT 0, history_ms INTEGER NOT NULL DEFAULT 0,
                before_send_ms INTEGER, error TEXT, error_detail TEXT, PRIMARY KEY(job_id,leg_index)
            );
            CREATE TABLE IF NOT EXISTS native_twap_fills (
                job_id TEXT NOT NULL, leg_index INTEGER NOT NULL, coin TEXT NOT NULL,
                tid TEXT NOT NULL, size REAL NOT NULL, price REAL NOT NULL,
                time_ms INTEGER NOT NULL, observed_ms INTEGER NOT NULL,
                PRIMARY KEY(job_id,coin,tid)
            );
            '''

class NativeTwapStore:
    def __init__(self, path=DEFAULT_DB):
        self.path = Path(path)
        self._initialized = False

    @contextmanager
    def _connect(self):
        c = connect(self.path)
        if not self._initialized:
            c.executescript(_SCHEMA)
            c.execute('BEGIN IMMEDIATE')
            if 'cancel_intent' not in {r[1] for r in c.execute('PRAGMA table_info(native_twap_jobs)')}:
                c.execute('ALTER TABLE native_twap_jobs ADD COLUMN cancel_intent INTEGER NOT NULL DEFAULT 0')
            if 'error_detail' not in {r[1] for r in c.execute('PRAGMA table_info(native_twap_legs)')}:
                c.execute('ALTER TABLE native_twap_legs ADD COLUMN error_detail TEXT')
            c.commit()
            self._initialized = True
        c.row_factory = __import__('sqlite3').Row
        for path in (self.path, Path(str(self.path) + '-wal'), Path(str(self.path) + '-shm')):
            try:
                info = path.lstat()
                if info.st_uid == os.getuid() and stat.S_ISREG(info.st_mode):
                    path.chmod(0o600)
            except FileNotFoundError:
                pass
        try:
            with c:
                yield c
        finally:
            c.close()

    def _job(self, c, account, job_id):
        row = c.execute('SELECT * FROM native_twap_jobs WHERE id=? AND account=?', (job_id, account.lower())).fetchone()
        if row is None:
            return None
        job = dict(row)
        del job['account']
        job.pop('cancel_intent', None)
        job['randomize'] = bool(job['randomize'])
        job['legs'] = []
        for row in c.execute('SELECT * FROM native_twap_legs WHERE job_id=? ORDER BY leg_index', (job_id,)):
            leg = dict(row)
            for key in ('job_id', 'leg_index'):
                leg.pop(key)
            leg['is_buy'], leg['reduce_only'] = bool(leg['is_buy']), bool(leg['reduce_only'])
            # A crash after durable intent cannot be mistaken for a safe retry.
            if leg['status'] == 'submitting':
                leg['status'] = 'uncertain'
            job['legs'].append(leg)
        if any(l['status'] == 'uncertain' for l in job['legs']):
            job['status'] = 'uncertain'
        if (any(l['status'] == 'pending' for l in job['legs']) and
                any(l['twap_id'] is not None for l in job['legs']) and _now() - job['updated_ms'] > 60000):
            job['status'] = 'uncertain'
            job['error'] = 'submission_incomplete_review_required'
        return job

    def get(self, account, job_id):
        with self._connect() as c:
            return self._job(c, account, job_id)

    def list(self, account, pair_id=None, limit=50, offset=0):
        limit, offset = max(1, min(500, int(limit))), max(0, int(offset))
        with self._connect() as c:
            query, args = 'SELECT id FROM native_twap_jobs WHERE account=?', [account.lower()]
            if pair_id is not None:
                query += ' AND pair_id=?'
                args.append(pair_id)
            rows = c.execute(query + " ORDER BY CASE WHEN status IN ('complete','incomplete','cancelled','rejected','partial') THEN 1 ELSE 0 END,created_ms DESC,id DESC LIMIT ? OFFSET ?", [*args, limit, offset]).fetchall()
            return [self._job(c, account, r['id']) for r in rows]

    def overlap(self, account, coins):
        with self._connect() as c:
            return overlap_sql(c, account, coins)

    def reserve(self, account, pair_id, operation, minutes, randomize, orders, now_ms=None):
        _validate(minutes, randomize, orders)
        if operation not in ('Aumentar', 'Reducir', 'Cerrar'):
            raise ValueError('Acción inválida')
        now = _now() if now_ms is None else int(now_ms)
        job_id = uuid.uuid4().hex
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if pending(c, account) or overlap_sql(c, account, [o['coin'] for o in orders]):
                raise RuntimeError('Existe una operación pendiente o incierta para estos activos')
            c.execute('''INSERT INTO native_twap_jobs
                (id,account,pair_id,operation,minutes,randomize,created_ms,planned_end_ms,status,updated_ms,error)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                      (job_id, account.lower(), pair_id, operation, minutes, int(randomize), now,
                       now + minutes * 60000, 'submitting', now, None))
            for i, o in enumerate(orders):
                c.execute('''INSERT INTO native_twap_legs
                    (job_id,leg_index,coin,is_buy,reduce_only,size,asset,status,updated_ms)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                          (job_id, i, _coin(o['coin']), int(o['is_buy']), int(o['reduce_only']),
                           float(o['size']), o.get('asset'), 'pending', now))
        return self.get(account, job_id)

    def _aggregate(self, c, job_id, now):
        legs = [dict(r) for r in c.execute('SELECT * FROM native_twap_legs WHERE job_id=?', (job_id,))]
        states = [l['status'] for l in legs]
        if any(s in ('uncertain', 'submitting') for s in states):
            status = 'uncertain'
        elif 'pending' in states:
            status = 'uncertain' if any(s in LEG_TERMINAL for s in states) else 'submitting'
        elif all(s == 'rejected' for s in states):
            status = 'rejected'
        elif all(s in LEG_TERMINAL for s in states):
            if all(s == 'finished' for s in states):
                status = 'complete' if all(l['executed_size'] is not None and l['executed_size'] >= l['size'] - max(1e-10, l['size'] * 1e-8) for l in legs) else 'incomplete'
            elif any((l['executed_size'] or 0) > 0 for l in legs):
                status = 'partial'
            else:
                status = 'cancelled'
        elif all(s == 'pending' for s in states):
            status = 'submitting'
        else:
            status = 'running'
        c.execute('UPDATE native_twap_jobs SET status=?,updated_ms=MAX(updated_ms,?) WHERE id=?', (status, now, job_id))

    def _leg(self, job_id, index, now, **fields):
        allowed = {'asset', 'size', 'twap_id', 'status', 'before_send_ms', 'error', 'error_detail'}
        if not fields or set(fields) - allowed:
            raise ValueError('Campos inválidos')
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            current = c.execute('SELECT status,twap_id FROM native_twap_legs WHERE job_id=? AND leg_index=?',
                                (job_id, index)).fetchone()
            if current is None:
                raise ValueError('Pata TWAP no encontrada')
            if current['status'] in LEG_TERMINAL:
                fields['status'] = current['status']
                fields['error'] = None
                fields['error_detail'] = None
            elif current['status'] == 'cancel_requested' and fields.get('status') == 'running':
                fields['status'] = 'cancel_requested'
            elif (current['status'] == 'running' and current['twap_id'] is not None and
                  fields.get('error') == 'submission_outcome_unknown'):
                # A native snapshot may arrive before the HTTP response times out.
                fields['status'], fields['error'] = 'running', None
            if current['twap_id'] is not None and fields.get('twap_id') is None:
                fields.pop('twap_id', None)
            c.execute('UPDATE native_twap_legs SET ' + ','.join(f'{k}=?' for k in fields) + ',updated_ms=MAX(updated_ms,?) WHERE job_id=? AND leg_index=?', [*fields.values(), now, job_id, index])
            self._aggregate(c, job_id, now)

    def _request_cancel(self, account, job_id, now):
        """Serialize cancel intent against the next leg's durable send claim."""
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute('SELECT 1 FROM native_twap_jobs WHERE id=? AND account=?',
                             (job_id, account.lower())).fetchone():
                raise ValueError('TWAP no encontrado')
            c.execute('UPDATE native_twap_jobs SET cancel_intent=1,updated_ms=MAX(updated_ms,?) WHERE id=?',
                      (now, job_id))
            # Pending legs have never crossed before_send. In-flight claims remain
            # uncertain until their native acknowledgement or history is known.
            c.execute("""UPDATE native_twap_legs SET status='cancelled',error='not_submitted',updated_ms=MAX(updated_ms,?)
                WHERE job_id=? AND status='pending'""", (now, job_id))
            self._aggregate(c, job_id, now)

    def _cancel_intended(self, job_id):
        with self._connect() as c:
            row = c.execute('SELECT cancel_intent FROM native_twap_jobs WHERE id=?', (job_id,)).fetchone()
            return bool(row and row[0])

    def _claim_submission(self, job_id, index, now):
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            result = c.execute("""UPDATE native_twap_legs SET status='submitting',before_send_ms=?,updated_ms=MAX(updated_ms,?)
                WHERE job_id=? AND leg_index=? AND status='pending'
                AND EXISTS (SELECT 1 FROM native_twap_jobs j WHERE j.id=job_id AND j.cancel_intent=0)""",
                               (now, now, job_id, index))
            self._aggregate(c, job_id, now)
            return result.rowcount == 1

    def _skip_pending(self, job_id, now):
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute("""UPDATE native_twap_legs SET status='rejected',error='not_submitted',updated_ms=MAX(updated_ms,?)
                WHERE job_id=? AND status='pending'""", (now, job_id))
            self._aggregate(c, job_id, now)

    def _claim_cancel(self, job_id, index, now):
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            result = c.execute("""UPDATE native_twap_legs SET status='cancel_requested',updated_ms=MAX(updated_ms,?)
                WHERE job_id=? AND leg_index=? AND twap_id IS NOT NULL
                AND status NOT IN ('finished','cancelled','rejected','cancel_requested')""", (now, job_id, index))
            self._aggregate(c, job_id, now)
            return result.rowcount == 1

    def _known(self, c, account):
        return c.execute('''SELECT l.*,j.minutes,j.randomize,j.created_ms,j.account FROM native_twap_legs l
            JOIN native_twap_jobs j ON j.id=l.job_id WHERE j.account=?''', (account.lower(),)).fetchall()

    def ingest_state(self, account, dex, states, as_of_ms, is_snapshot=True):
        """Exchange states are [id,state] tuples (dict wrappers also accepted)."""
        if isinstance(states, dict):
            states = states.get('states', [])
        parsed = {}
        for item in states:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                tid, state = item
            elif isinstance(item, dict):
                tid, state = item.get('twapId', item.get('id')), item.get('state', item)
            else:
                continue
            if tid is not None and isinstance(state, dict):
                parsed[str(tid)] = state
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            jobs = set()
            known = self._known(c, account)
            for leg in known:
                if _dex(leg['coin']) != dex or as_of_ms < max(leg['state_ms'], leg['history_ms']):
                    continue
                if leg['twap_id'] is None:
                    matches = [(tid, state) for tid, state in parsed.items() if _matches_signature(leg, state)]
                    if len(matches) != 1:
                        continue
                    tid, state = matches[0]
                    # The signature must identify exactly one local sent intent.
                    if sum(_matches_signature(other, state) for other in known) != 1:
                        continue
                    try:
                        recovered_id = int(tid)
                    except (TypeError, ValueError):
                        continue
                    c.execute('UPDATE native_twap_legs SET twap_id=? WHERE job_id=? AND leg_index=?',
                              (recovered_id, leg['job_id'], leg['leg_index']))
                else:
                    state = parsed.get(str(leg['twap_id']))
                if state is None:
                    if not is_snapshot or leg['status'] in LEG_TERMINAL:
                        continue
                    status, size, ntl = 'uncertain', leg['executed_size'], leg['executed_notional']
                else:
                    if (state.get('coin') and _coin(state['coin']) != leg['coin']) or ('user' in state and str(state['user']).lower() != account.lower()):
                        continue
                    try:
                        size = _number(state['executedSz']) if 'executedSz' in state else leg['executed_size']
                        ntl = _number(state['executedNtl']) if 'executedNtl' in state else leg['executed_notional']
                    except (ValueError, TypeError):
                        continue
                    size = max(size or 0, leg['executed_size'] or 0) if size is not None else None
                    ntl = max(ntl or 0, leg['executed_notional'] or 0) if ntl is not None else None
                    status = leg['status'] if leg['status'] in LEG_TERMINAL or leg['status'] == 'cancel_requested' else 'running'
                c.execute('''UPDATE native_twap_legs SET status=?,executed_size=?,executed_notional=?,state_ms=?,updated_ms=MAX(updated_ms,?)
                    WHERE job_id=? AND leg_index=?''', (status, size, ntl, as_of_ms, as_of_ms, leg['job_id'], leg['leg_index']))
                jobs.add(leg['job_id'])
            for job in jobs:
                self._aggregate(c, job, as_of_ms)

    def ingest_history(self, account, events, as_of_ms):
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            known, jobs = self._known(c, account), set()
            for event in events:
                if not isinstance(event, dict):
                    continue
                state, status = event.get('state') or {}, event.get('status') or {}
                if not isinstance(state, dict) or ('user' in state and str(state['user']).lower() != account.lower()):
                    continue
                word = status.get('status') if isinstance(status, dict) else status
                target = {'activated': 'running', 'terminated': 'cancelled', 'finished': 'finished', 'error': 'rejected'}.get(word)
                if target is None:
                    continue
                candidates = []
                for leg in known:
                    tid = event.get('twapId', state.get('twapId'))
                    if tid is not None:
                        match = leg['twap_id'] is not None and str(leg['twap_id']) == str(tid)
                        match = match and (not state.get('coin') or _coin(state['coin']) == leg['coin'])
                    else:
                        match = _matches_signature(leg, state)
                    if match:
                        candidates.append(leg)
                if len(candidates) != 1:
                    continue
                leg = candidates[0]
                try:
                    event_time = int(event.get('time', as_of_ms))
                except (ValueError, TypeError):
                    continue
                if event_time < leg['history_ms'] or (target == 'running' and
                        (event_time < leg['state_ms'] or leg['status'] in LEG_TERMINAL)):
                    continue
                if leg['status'] in LEG_TERMINAL and target != leg['status']:
                    continue
                try:
                    size = _number(state['executedSz']) if 'executedSz' in state else leg['executed_size']
                    ntl = _number(state['executedNtl']) if 'executedNtl' in state else leg['executed_notional']
                except (TypeError, ValueError):
                    continue
                size = max(size or 0, leg['executed_size'] or 0) if size is not None else None
                ntl = max(ntl or 0, leg['executed_notional'] or 0) if ntl is not None else None
                c.execute('''UPDATE native_twap_legs SET status=?,executed_size=?,executed_notional=?,history_ms=?,updated_ms=MAX(updated_ms,?)
                    WHERE job_id=? AND leg_index=?''', (target, size, ntl, event_time, as_of_ms, leg['job_id'], leg['leg_index']))
                jobs.add(leg['job_id'])
                known = self._known(c, account)
            for job in jobs:
                self._aggregate(c, job, as_of_ms)

    def ingest_fills(self, account, rows, as_of_ms):
        with self._connect() as c:
            c.execute('BEGIN IMMEDIATE')
            known, jobs = self._known(c, account), set()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                fill = row.get('fill') or {}
                if not isinstance(fill, dict) or row.get('twapId') is None or fill.get('tid') is None:
                    continue
                matches = [l for l in known if l['twap_id'] is not None and str(l['twap_id']) == str(row['twapId']) and l['coin'] == _coin(fill.get('coin'))]
                if len(matches) != 1:
                    continue
                leg = matches[0]
                try:
                    size, price, timestamp = _number(fill['sz']), _number(fill['px']), int(fill['time'])
                    if size <= 0 or price <= 0:
                        continue
                except (KeyError, ValueError, TypeError):
                    continue
                c.execute('INSERT OR IGNORE INTO native_twap_fills VALUES (?,?,?,?,?,?,?,?)',
                          (leg['job_id'], leg['leg_index'], leg['coin'], str(fill['tid']), size, price, timestamp, as_of_ms))
                jobs.add(leg['job_id'])
            for job in jobs:
                for leg in c.execute('SELECT * FROM native_twap_legs WHERE job_id=?', (job,)).fetchall():
                    sums = c.execute('SELECT SUM(size),SUM(size*price) FROM native_twap_fills WHERE job_id=? AND leg_index=?', (job, leg['leg_index'])).fetchone()
                    if sums[0] is not None:
                        # State totals can cover fills older than retained slice history.
                        c.execute('''UPDATE native_twap_legs SET executed_size=MAX(COALESCE(executed_size,0),?),
                            executed_notional=MAX(COALESCE(executed_notional,0),?),updated_ms=MAX(updated_ms,?) WHERE job_id=? AND leg_index=?''',
                                  (sums[0], sums[1], as_of_ms, job, leg['leg_index']))
                self._aggregate(c, job, as_of_ms)

    def fills(self, account, job_id, limit=30, offset=0):
        limit, offset = max(1, min(200, int(limit))), max(0, int(offset))
        with self._connect() as c:
            if self._job(c, account, job_id) is None:
                return None
            total = c.execute('SELECT COUNT(*) FROM native_twap_fills WHERE job_id=?', (job_id,)).fetchone()[0]
            rows = c.execute('''SELECT coin,tid,size AS sz,price AS px,time_ms AS time,leg_index,
                (SELECT twap_id FROM native_twap_legs l WHERE l.job_id=native_twap_fills.job_id AND l.leg_index=native_twap_fills.leg_index) AS twap_id FROM native_twap_fills
                WHERE job_id=? ORDER BY time_ms DESC,coin,tid LIMIT ? OFFSET ?''', (job_id, limit, offset)).fetchall()
            return {'items': [dict(r) for r in rows], 'total': total, 'limit': limit, 'offset': offset}


    def entry_fills(self, account, coins):
        """Minimal observed fills for the entry curve, never accounting inputs."""
        coins = sorted(set(coins))
        if not coins:
            return []
        placeholders = ','.join('?' for _ in coins)
        with self._connect() as c:
            return [dict(row) for row in c.execute(f"""SELECT f.coin,f.tid,f.size AS sz,
                f.price AS px,f.time_ms AS time,CASE WHEN l.is_buy=1 THEN 'B' ELSE 'A' END AS side
                FROM native_twap_fills f JOIN native_twap_jobs j ON j.id=f.job_id
                JOIN native_twap_legs l ON l.job_id=f.job_id AND l.leg_index=f.leg_index
                WHERE j.account=? AND f.coin IN ({placeholders}) ORDER BY f.time_ms,f.coin,f.tid""",
                [account.lower(), *coins])]

    def fill_keys(self, account, pair_id=None, job_ids=None):
        with self._connect() as c:
            query = """SELECT f.coin,f.tid FROM native_twap_fills f
                JOIN native_twap_jobs j ON j.id=f.job_id WHERE j.account=?"""
            args = [account.lower()]
            if pair_id is not None:
                query += ' AND j.pair_id=?'
                args.append(pair_id)
            if job_ids is not None:
                job_ids = list(job_ids)
                if not job_ids:
                    return set()
                query += ' AND j.id IN (' + ','.join('?' for _ in job_ids) + ')'
                args.extend(job_ids)
            return {(r[0], str(r[1])) for r in c.execute(query, args)}


def _exchange(account, agent_key):
    from eth_account import Account
    from hyperliquid.exchange import Exchange
    from .trading import verify_agent
    wallet = Account.from_key(agent_key)
    verify_agent(account, wallet.address)
    return Exchange(wallet, base_url='https://api.hyperliquid.xyz', account_address=account,
                    perp_dexs=['', 'xyz'], timeout=12)


def _sign(ex, action, nonce):
    from hyperliquid.utils.signing import sign_l1_action
    nonce = max(int(nonce), getattr(ex, '_native_twap_nonce', 0) + 1)
    ex._native_twap_nonce = nonce
    signature = sign_l1_action(ex.wallet, action, ex.vault_address, nonce,
                               ex.expires_after, ex.base_url == 'https://api.hyperliquid.xyz')
    return signature, nonce


def _send(ex, action, nonce):
    signature, nonce = _sign(ex, action, nonce)
    return ex._post_action(action, signature, nonce)


def _answer(response, cancel=False):
    """Return known ack/reject/unknown. Never persist arbitrary API strings."""
    if not isinstance(response, dict):
        return 'uncertain', None
    if response.get('status') == 'err':
        return 'rejected', None
    if response.get('status') != 'ok':
        return 'uncertain', None
    payload = response.get('response')
    if not isinstance(payload, dict):
        return 'uncertain', None
    data = payload.get('data')
    if not isinstance(data, dict):
        return 'uncertain', None
    status = data.get('status')
    if status == 'error' or 'error' in data:
        return 'rejected', None
    if cancel:
        return ('cancel_requested', None) if status in ('success', 'ok') else ('uncertain', None)
    if isinstance(status, dict):
        if 'error' in status:
            return 'rejected', None
        if isinstance(status.get('running'), dict):
            tid = status['running'].get('twapId')
            if type(tid) is int and tid >= 0:
                return 'running', tid
    return 'uncertain', None


def _prepare(ex, account, orders):
    prepared = []
    for order in orders:
        coin = order['coin']
        state = ex.info.user_state(account, _dex(coin))
        position_rows = {p['position']['coin']: p['position'] for p in state.get('assetPositions', [])}
        positions = {c: float(p['szi']) for c, p in position_rows.items()}
        live = positions.get(coin, 0)
        sign = (1 if order['is_buy'] else -1) * (-1 if order['reduce_only'] else 1)
        original = _number(order['original_size'])
        if not math.isfinite(live) or original <= 0 or live * sign <= 0 or abs(live - sign * original) > max(1e-8, original * .001):
            raise ValueError('Posición cambió desde la vista previa')
        asset = ex.info.name_to_asset(coin)
        decimals = ex.info.asset_to_sz_decimals[asset]
        size = Decimal(str(order['size'])).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_DOWN)
        if size <= 0 or (order['reduce_only'] and size > Decimal(str(abs(live)))):
            raise ValueError('Cantidad inválida tras redondeo')
        position_value = position_rows.get(coin, {}).get('positionValue')
        mark = abs(float(position_value) / live) if position_value is not None and live else order.get('mark', 0)
        prepared.append(dict(order, asset=asset, size=float(size), mark=mark))
    validate_twap_notional(prepared)
    return sorted(prepared, key=lambda o: 0 if o['coin'].startswith('xyz:') else 1)


def submit_pair(store, account, pair_id, operation, orders, minutes, randomize, agent_key,
                *, exchange_factory=None, clock=None):
    _validate(minutes, randomize, orders)
    now = clock or _now
    ex = (exchange_factory or _exchange)(account, agent_key)
    prepared = _prepare(ex, account, orders)  # Both metadata/positions before ANY POST.
    from hyperliquid.utils.signing import float_to_wire
    signed = []
    for order in prepared:
        action = {'type': 'twapOrder', 'twap': {'a': order['asset'], 'b': order['is_buy'],
                  's': float_to_wire(order['size']), 'r': order['reduce_only'], 'm': minutes, 't': randomize}}
        signature, nonce = _sign(ex, action, int(now()))
        signed.append((action, signature, nonce))
    job = store.reserve(account, pair_id, operation, minutes, randomize, prepared, now_ms=now())
    for index, (action, signature, nonce) in enumerate(signed):
        stamp = int(now())
        if not store._claim_submission(job['id'], index, stamp):
            break
        try:
            response = ex._post_action(action, signature, nonce)
            status, tid = _answer(response)
            rejection_code = _rejection_code(response)
            error_detail = _safe_error_detail(response) if status == 'rejected' else None
        except Exception:
            status, tid = 'uncertain', None
            error_detail = None
        store._leg(job['id'], index, int(now()), status=status, twap_id=tid, error_detail=error_detail,
                   error=None if status == 'running' else (rejection_code if status == 'rejected' else 'submission_outcome_unknown'))
        if store._cancel_intended(job['id']):
            _cancel_known(store, account, job['id'], ex, now)
            break
        if status != 'running':
            store._skip_pending(job['id'], int(now()))
            if index:
                store._request_cancel(account, job['id'], int(now()))
                _cancel_known(store, account, job['id'], ex, now)
            break
    return store.get(account, job['id'])


def _cancel_known(store, account, job_id, ex, now):
    job = store.get(account, job_id)
    if job is None:
        raise ValueError('TWAP no encontrado')
    for index, leg in enumerate(job['legs']):
        if leg['twap_id'] is None or leg['status'] in LEG_TERMINAL or leg['status'] == 'cancel_requested':
            continue
        stamp = int(now())
        if not store._claim_cancel(job_id, index, stamp):
            continue
        try:
            status, _ = _answer(_send(ex, {'type': 'twapCancel', 'a': leg['asset'], 't': leg['twap_id']}, stamp), cancel=True)
        except Exception:
            status = 'uncertain'
        # Even a definitive cancel rejection does not establish execution termination.
        if status != 'cancel_requested':
            status = 'uncertain'
        store._leg(job_id, index, int(now()), status=status,
                   error=None if status == 'cancel_requested' else 'cancel_outcome_unknown')


def cancel_pair(store, account, job_id, agent_key, *, exchange_factory=None, clock=None):
    now = clock or _now
    store._request_cancel(account, job_id, int(now()))
    job = store.get(account, job_id)
    if job is None:
        raise ValueError('TWAP no encontrado')
    if any(l['twap_id'] is not None and l['status'] not in LEG_TERMINAL and l['status'] != 'cancel_requested' for l in job['legs']):
        ex = (exchange_factory or _exchange)(account, agent_key)
        _cancel_known(store, account, job_id, ex, now)
    return store.get(account, job_id)
