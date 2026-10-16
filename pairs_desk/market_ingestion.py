"""Incremental candle ingestion isolated from the application runtime."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

from .market_catalog import MarketCatalog
from .market_quality import normalize_candles, validate_candles
from .market_storage import MarketDataStore


@dataclass(frozen=True)
class SyncResult:
    rows_received: int
    rows_new: int
    covered_from_ms: int | None
    covered_to_ms: int | None
    gaps: tuple[int, ...]
    status: str
    error: str | None = None


class MarketIngestor:
    def __init__(self, catalog: MarketCatalog, store: MarketDataStore, fetch: Callable[..., Any]):
        self.catalog = catalog
        self.store = store
        self.fetch = fetch
        with self.catalog.connect() as db, db:
            db.execute(
                '''CREATE TABLE IF NOT EXISTS ingestion_checkpoints (
                    instrument_id TEXT NOT NULL,
                    interval TEXT NOT NULL,
                    covered_from_ms INTEGER,
                    covered_to_ms INTEGER,
                    last_success_ms INTEGER,
                    status TEXT NOT NULL,
                    error TEXT,
                    updated_ms INTEGER NOT NULL,
                    PRIMARY KEY(instrument_id, interval)
                )'''
            )

    def get_checkpoint(self, instrument_id: str, interval: str) -> dict[str, Any] | None:
        with self.catalog.connect() as db:
            row = db.execute(
                'SELECT * FROM ingestion_checkpoints WHERE instrument_id=? AND interval=?',
                (instrument_id, interval),
            ).fetchone()
        return dict(row) if row else None

    def _save_checkpoint(
        self,
        instrument_id: str,
        interval: str,
        *,
        status: str,
        error: str | None = None,
        covered_from_ms: int | None = None,
        covered_to_ms: int | None = None,
        last_success_ms: int | None = None,
    ) -> None:
        now = int(time.time() * 1000)
        previous = self.get_checkpoint(instrument_id, interval)
        if previous:
            covered_from_ms = covered_from_ms if covered_from_ms is not None else previous['covered_from_ms']
            covered_to_ms = covered_to_ms if covered_to_ms is not None else previous['covered_to_ms']
            last_success_ms = last_success_ms if last_success_ms is not None else previous['last_success_ms']
        with self.catalog.connect() as db, db:
            db.execute(
                '''INSERT INTO ingestion_checkpoints
                   (instrument_id, interval, covered_from_ms, covered_to_ms,
                    last_success_ms, status, error, updated_ms)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(instrument_id, interval) DO UPDATE SET
                     covered_from_ms=excluded.covered_from_ms,
                     covered_to_ms=excluded.covered_to_ms,
                     last_success_ms=excluded.last_success_ms,
                     status=excluded.status, error=excluded.error,
                     updated_ms=excluded.updated_ms''',
                (instrument_id, interval, covered_from_ms, covered_to_ms, last_success_ms, status, error, now),
            )

    def sync_candles(self, instrument_id: str, interval: str, start_ms: int, end_ms: int) -> SyncResult:
        if end_ms < start_ms:
            raise ValueError('end_ms debe ser mayor o igual que start_ms')
        instrument = self.catalog.get_instrument(instrument_id)
        if instrument is None:
            raise ValueError(f'Instrumento inexistente: {instrument_id}')
        try:
            rows = self.fetch(
                type='candleSnapshot',
                req={
                    'coin': instrument['symbol'] if instrument['venue'] == 'core' else f"{instrument['venue']}:{instrument['symbol']}",
                    'interval': interval,
                    'startTime': int(start_ms),
                    'endTime': int(end_ms),
                },
            )
            if not isinstance(rows, list):
                raise ValueError('candleSnapshot devolvió un formato inesperado')
            if not rows:
                message = 'La ventana no contiene velas'
                self._save_checkpoint(instrument_id, interval, status='empty', error=message)
                return SyncResult(0, 0, None, None, (), 'empty', message)
            frame = normalize_candles(rows, instrument_id, instrument['venue'], interval)
            report = validate_candles(frame)
            if not report.valid:
                raise ValueError(report.error or 'Velas inválidas')
            merged = self.store.merge_candles(frame)
            status = 'partial' if report.gaps else 'complete'
            now = int(time.time() * 1000)
            self._save_checkpoint(
                instrument_id,
                interval,
                status=status,
                covered_from_ms=int(start_ms),
                covered_to_ms=int(end_ms),
                last_success_ms=now,
            )
            return SyncResult(len(rows), merged.rows_new, int(start_ms), int(end_ms), report.gaps, status)
        except Exception as exc:
            message = str(exc)
            self._save_checkpoint(instrument_id, interval, status='error', error=message)
            return SyncResult(0 if 'rows' not in locals() or not isinstance(rows, list) else len(rows), 0, None, None, (), 'error', message)
