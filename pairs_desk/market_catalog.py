"""Stable market identities and catalog metadata for public market data."""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

DEFAULT_MARKET_DB = Path.home() / '.local' / 'share' / 'crypto-pairs-desk' / 'market.sqlite3'


def _clean_symbol(symbol: str) -> str:
    value = str(symbol).strip().upper()
    if not value:
        raise ValueError('El símbolo no puede estar vacío')
    return value


def _clean_venue(venue: str) -> str:
    value = str(venue).strip().lower()
    if not value:
        raise ValueError('El mercado no puede estar vacío')
    return value


def instrument_id(symbol: str, venue: str) -> str:
    """Return a stable ID that keeps identical symbols on different venues apart."""
    clean_venue = _clean_venue(venue)
    clean_symbol = _clean_symbol(symbol)
    prefix = f'{clean_venue}:'
    if clean_symbol.startswith(prefix.upper()):
        clean_symbol = clean_symbol[len(prefix):]
    return f'{clean_venue}:{clean_symbol}'


def _normalize_instrument_ref(value: str) -> str:
    raw = str(value).strip()
    venue, separator, symbol = raw.partition(':')
    if not separator:
        raise ValueError(f'Instrumento inválido: {value}')
    return instrument_id(symbol, venue)


def pair_id(long_instrument_id: str, short_instrument_id: str) -> str:
    long_id = _normalize_instrument_ref(long_instrument_id)
    short_id = _normalize_instrument_ref(short_instrument_id)
    if not long_id or not short_id:
        raise ValueError('Las patas del par no pueden estar vacías')
    if long_id == short_id:
        raise ValueError('Las patas del par deben ser distintas')
    return f'{long_id}__{short_id}'


def _metadata(value: dict[str, Any] | None) -> str:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise TypeError('metadata debe ser un objeto')
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _decode_metadata(value: str) -> dict[str, Any]:
    decoded = json.loads(value)
    return decoded if isinstance(decoded, dict) else {}


class MarketCatalog:
    """SQLite catalog independent from account ledger and order journal."""

    def __init__(self, path: Path | str = DEFAULT_MARKET_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        with closing(self.connect()) as db, db:
            db.executescript(
                '''
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS instruments (
                    instrument_id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    venue TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(venue, symbol)
                );
                CREATE TABLE IF NOT EXISTS pairs (
                    pair_id TEXT PRIMARY KEY,
                    long_instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
                    short_instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
                    label TEXT NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    UNIQUE(long_instrument_id, short_instrument_id)
                );
                CREATE INDEX IF NOT EXISTS instruments_venue_active
                    ON instruments(venue, active);
                CREATE INDEX IF NOT EXISTS pairs_active
                    ON pairs(active);
                '''
            )
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        return db

    @staticmethod
    def _instrument_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            'instrument_id': row['instrument_id'],
            'symbol': row['symbol'],
            'venue': row['venue'],
            'asset_type': row['asset_type'],
            'active': bool(row['active']),
            'metadata': _decode_metadata(row['metadata_json']),
        }

    @staticmethod
    def _pair_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return {
            'pair_id': row['pair_id'],
            'long_instrument_id': row['long_instrument_id'],
            'short_instrument_id': row['short_instrument_id'],
            'label': row['label'],
            'active': bool(row['active']),
            'metadata': _decode_metadata(row['metadata_json']),
        }

    def upsert_instrument(
        self,
        symbol: str,
        venue: str,
        *,
        asset_type: str = 'perp',
        active: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        clean_venue = _clean_venue(venue)
        clean_symbol = _clean_symbol(symbol)
        ident = instrument_id(clean_symbol, clean_venue)
        with closing(self.connect()) as db, db:
            db.execute(
                '''INSERT INTO instruments
                   (instrument_id, symbol, venue, asset_type, active, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(instrument_id) DO UPDATE SET
                     symbol=excluded.symbol, venue=excluded.venue,
                     asset_type=excluded.asset_type, active=excluded.active,
                     metadata_json=excluded.metadata_json''',
                (ident, clean_symbol, clean_venue, str(asset_type).strip() or 'perp', int(bool(active)), _metadata(metadata)),
            )
            row = db.execute('SELECT * FROM instruments WHERE instrument_id=?', (ident,)).fetchone()
        return self._instrument_row(row)  # type: ignore[return-value]

    def get_instrument(self, ident: str) -> dict[str, Any] | None:
        with closing(self.connect()) as db:
            row = db.execute('SELECT * FROM instruments WHERE instrument_id=?', (str(ident).strip(),)).fetchone()
        return self._instrument_row(row)

    def list_instruments(self, *, venue: str | None = None, active_only: bool = False) -> list[dict[str, Any]]:
        clauses: list[str] = []
        args: list[Any] = []
        if venue is not None:
            clauses.append('venue=?')
            args.append(_clean_venue(venue))
        if active_only:
            clauses.append('active=1')
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ''
        with closing(self.connect()) as db:
            rows = db.execute(f'SELECT * FROM instruments{where} ORDER BY instrument_id', args).fetchall()
        return [self._instrument_row(row) for row in rows]  # type: ignore[list-item]

    def upsert_pair(
        self,
        long_instrument_id: str,
        short_instrument_id: str,
        *,
        label: str | None = None,
        active: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        long_id = _normalize_instrument_ref(long_instrument_id)
        short_id = _normalize_instrument_ref(short_instrument_id)
        ident = pair_id(long_id, short_id)
        display_label = str(label).strip() if label is not None else f'{long_id}/{short_id}'
        with closing(self.connect()) as db, db:
            for leg in (long_id, short_id):
                if db.execute('SELECT 1 FROM instruments WHERE instrument_id=?', (leg,)).fetchone() is None:
                    raise ValueError(f'Instrumento inexistente: {leg}')
            db.execute(
                '''INSERT INTO pairs
                   (pair_id, long_instrument_id, short_instrument_id, label, active, metadata_json)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(pair_id) DO UPDATE SET
                     label=excluded.label, active=excluded.active,
                     metadata_json=excluded.metadata_json''',
                (ident, long_id, short_id, display_label, int(bool(active)), _metadata(metadata)),
            )
            row = db.execute('SELECT * FROM pairs WHERE pair_id=?', (ident,)).fetchone()
        return self._pair_row(row)  # type: ignore[return-value]

    def get_pair(self, ident: str) -> dict[str, Any] | None:
        with closing(self.connect()) as db:
            row = db.execute('SELECT * FROM pairs WHERE pair_id=?', (str(ident).strip(),)).fetchone()
        return self._pair_row(row)
