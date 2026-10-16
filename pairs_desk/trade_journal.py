"""Crash-resistant local audit trail for real-money order attempts.

No API keys or signatures are ever persisted. The journal is intentionally
separate from app settings and is not shipped in release archives.
"""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path

DEFAULT_DB = Path.home() / '.local' / 'share' / 'crypto-pairs-desk' / 'orders.sqlite3'


def connect(path: Path = DEFAULT_DB):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    conn = sqlite3.connect(path, timeout=15)
    conn.execute('PRAGMA busy_timeout=15000')
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=FULL')
    conn.execute('''CREATE TABLE IF NOT EXISTS attempts (
        id TEXT PRIMARY KEY, account TEXT NOT NULL, pair TEXT NOT NULL,
        action TEXT NOT NULL, status TEXT NOT NULL, created_ms INTEGER NOT NULL,
        updated_ms INTEGER NOT NULL, legs_json TEXT NOT NULL, note TEXT NOT NULL DEFAULT ''
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT, attempt_id TEXT NOT NULL,
        timestamp_ms INTEGER NOT NULL, event TEXT NOT NULL, leg TEXT,
        details_json TEXT NOT NULL,
        FOREIGN KEY (attempt_id) REFERENCES attempts(id)
    )''')
    conn.commit()
    return conn


def pending(conn, account: str):
    return conn.execute("SELECT id,pair,status,created_ms FROM attempts WHERE account=? AND status NOT IN ('complete','cancelled','reconciled') ORDER BY created_ms DESC", (account.lower(),)).fetchall()


def begin(conn, account: str, pair: str, action: str, legs: list[dict]):
    """Reserve an attempt BEFORE the first external API side effect."""
    now = int(time.time() * 1000)
    attempt_id = uuid.uuid4().hex
    # BEGIN IMMEDIATE serializes competing writers/processes.
    conn.execute('BEGIN IMMEDIATE')
    try:
        existing = pending(conn, account)
        if existing:
            raise RuntimeError('Existe una operación pendiente o de resultado incierto. Verificá Hyperliquid y conciliá la bitácora antes de volver a operar.')
        clean = [{k: row[k] for k in ('coin', 'is_buy', 'reduce_only', 'size', 'original_size') if k in row} for row in legs]
        conn.execute('INSERT INTO attempts VALUES (?,?,?,?,?,?,?, ?,?)',
                     (attempt_id, account.lower(), pair, action, 'pending', now, now, json.dumps(clean, sort_keys=True), ''))
        conn.execute('INSERT INTO events (attempt_id,timestamp_ms,event,leg,details_json) VALUES (?,?,?,?,?)',
                     (attempt_id, now, 'intent', None, json.dumps(clean, sort_keys=True)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return attempt_id


def record(conn, attempt_id: str, event: str, leg: str | None, details: dict):
    now = int(time.time() * 1000)
    # avoid storing keys, arbitrary responses, or account secrets
    permitted = {'size','filled_size','oid','avg_px','error','notional','slippage','reduce_only','is_buy','status'}
    filtered = {k: v for k, v in details.items() if k in permitted}
    conn.execute('INSERT INTO events (attempt_id,timestamp_ms,event,leg,details_json) VALUES (?,?,?,?,?)',
                 (attempt_id, now, event, leg, json.dumps(filtered, default=str, sort_keys=True)))
    conn.execute('UPDATE attempts SET updated_ms=? WHERE id=?', (now, attempt_id))
    conn.commit()


def finish(conn, attempt_id: str, status: str, note: str = ''):
    if status not in ('complete', 'partial', 'uncertain', 'cancelled', 'reconciled'):
        raise ValueError('Invalid final status')
    conn.execute('UPDATE attempts SET status=?, note=?, updated_ms=? WHERE id=?',
                 (status, note[:600], int(time.time() * 1000), attempt_id))
    conn.commit()


def reconcile(conn, attempt_id: str, note: str):
    if len(note.strip()) < 10:
        raise ValueError('Describí qué verificaste en Hyperliquid (mínimo 10 caracteres)')
    status = conn.execute('SELECT status FROM attempts WHERE id=?', (attempt_id,)).fetchone()
    if not status or status[0] == 'complete':
        raise ValueError('Intento no conciliable')
    record(conn, attempt_id, 'manual_reconciliation', None, {'status': 'user_verified'})
    finish(conn, attempt_id, 'reconciled', note.strip())
