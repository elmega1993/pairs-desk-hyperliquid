"""Read-only inputs for retrospective operation analysis."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .storage import load_settings


@dataclass(frozen=True)
class DataPaths:
    settings: Path = Path.home() / '.config/crypto-pairs-desk/settings.json'
    ledger: Path = Path.home() / '.local/share/crypto-pairs-desk/ledger.sqlite3'
    orders: Path = Path.home() / '.local/share/crypto-pairs-desk/orders.sqlite3'
    market: Path = Path.home() / '.local/share/crypto-pairs-desk/market.sqlite3'


@dataclass
class SourceStatus:
    available: bool = False
    rows: int = 0
    error: str | None = None


@dataclass
class LearningSnapshot:
    closed_pairs: list[dict[str, Any]] = field(default_factory=list)
    fills: list[dict[str, Any]] = field(default_factory=list)
    funding: list[dict[str, Any]] = field(default_factory=list)
    order_attempts: list[dict[str, Any]] = field(default_factory=list)
    order_events: list[dict[str, Any]] = field(default_factory=list)
    market_pairs: list[dict[str, Any]] = field(default_factory=list)
    sources: dict[str, SourceStatus] = field(default_factory=dict)
    settings_error: str | None = None

    def as_public_dict(self) -> dict[str, Any]:
        """Return diagnostics without account address or raw ledger payloads."""
        return {
            'closed_pairs_count': len(self.closed_pairs),
            'fills_count': len(self.fills),
            'funding_count': len(self.funding),
            'order_attempts_count': len(self.order_attempts),
            'order_events_count': len(self.order_events),
            'market_pairs_count': len(self.market_pairs),
            'sources': {
                name: {'available': status.available, 'rows': status.rows, 'error': status.error}
                for name, status in self.sources.items()
            },
        }


def _read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True)


def _table_rows(db: sqlite3.Connection, table: str, json_columns: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    db.row_factory = sqlite3.Row
    rows = db.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()
    result = []
    for row in rows:
        value = dict(row)
        for column in json_columns:
            if isinstance(value.get(column), str):
                try:
                    value[column] = json.loads(value[column])
                except json.JSONDecodeError:
                    pass
        result.append(value)
    return result


def _read_source(path: Path, reader) -> tuple[list[dict[str, Any]], SourceStatus]:
    status = SourceStatus()
    try:
        with _read_only(path) as db:
            rows = reader(db)
        status.available = True
        status.rows = len(rows)
        return rows, status
    except (OSError, sqlite3.Error, json.JSONDecodeError, TypeError, ValueError) as exc:
        status.error = f'{type(exc).__name__}: {exc}'
        return [], status


def _ledger_rows(db: sqlite3.Connection, kind: str) -> list[dict[str, Any]]:
    return [json.loads(payload) for (payload,) in db.execute(
        'SELECT payload FROM events WHERE kind=? ORDER BY time, identity', (kind,)
    ).fetchall()]


def load_learning_snapshot(paths: DataPaths | None = None) -> LearningSnapshot:
    paths = paths or DataPaths()
    settings, settings_error = load_settings(Path(paths.settings))
    snapshot = LearningSnapshot(
        closed_pairs=list(settings.get('closed_pairs', [])),
        settings_error=settings_error,
        sources={'settings': SourceStatus(available=settings_error is None, rows=len(settings.get('closed_pairs', [])), error=settings_error)},
    )

    snapshot.fills, snapshot.sources['ledger'] = _read_source(
        Path(paths.ledger), lambda db: _ledger_rows(db, 'fills'))
    funding, funding_status = _read_source(
        Path(paths.ledger), lambda db: _ledger_rows(db, 'funding'))
    snapshot.funding = funding
    if snapshot.sources['ledger'].available:
        snapshot.sources['ledger'].rows += funding_status.rows
    elif funding_status.error:
        snapshot.sources['ledger'].error = funding_status.error

    snapshot.order_attempts, attempts_status = _read_source(
        Path(paths.orders), lambda db: _table_rows(db, 'attempts', ('legs_json',)))
    snapshot.order_events, events_status = _read_source(
        Path(paths.orders), lambda db: _table_rows(db, 'events', ('details_json',)))
    snapshot.sources['orders'] = SourceStatus(
        available=attempts_status.available and events_status.available,
        rows=attempts_status.rows + events_status.rows,
        error=attempts_status.error or events_status.error,
    )

    snapshot.market_pairs, snapshot.sources['market'] = _read_source(
        Path(paths.market), lambda db: _table_rows(db, 'pairs', ('metadata_json',)))
    return snapshot
