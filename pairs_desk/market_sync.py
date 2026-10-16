"""Controlled orchestration for incremental market-data synchronization."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .market_ingestion import MarketIngestor


@dataclass(frozen=True)
class SyncMetrics:
    instrument_id: str
    interval: str
    requested_start_ms: int
    requested_end_ms: int
    effective_start_ms: int | None
    effective_end_ms: int | None
    rows_received: int
    rows_new: int
    covered_from_ms: int | None
    covered_to_ms: int | None
    gaps: tuple[int, ...]
    duration_ms: int
    status: str
    error: str | None = None
    skipped: bool = False


@dataclass(frozen=True)
class BatchSyncResult:
    results: tuple[SyncMetrics, ...]
    rows_received: int
    rows_new: int
    errors: int
    duration_ms: int


class MarketSyncService:
    def __init__(self, ingestor: MarketIngestor, *, clock: Callable[[], float] = time.monotonic):
        self.ingestor = ingestor
        self.clock = clock

    def sync_incremental(
        self,
        instrument_id: str,
        interval: str,
        *,
        end_ms: int,
        initial_start_ms: int,
    ) -> SyncMetrics:
        if end_ms < initial_start_ms:
            raise ValueError('end_ms debe ser mayor o igual que initial_start_ms')
        checkpoint = self.ingestor.get_checkpoint(instrument_id, interval)
        covered_to = checkpoint.get('covered_to_ms') if checkpoint else None
        status = checkpoint.get('status') if checkpoint else None
        if status == 'complete' and covered_to is not None and int(covered_to) >= end_ms:
            return SyncMetrics(
                instrument_id, interval, initial_start_ms, end_ms,
                None, None, 0, 0, checkpoint.get('covered_from_ms'), int(covered_to),
                (), 0, 'up_to_date', skipped=True,
            )
        effective_start = int(covered_to) if covered_to is not None else int(initial_start_ms)
        started = self.clock()
        result = self.ingestor.sync_candles(instrument_id, interval, effective_start, int(end_ms))
        duration_ms = int(round((self.clock() - started) * 1000))
        return SyncMetrics(
            instrument_id, interval, initial_start_ms, end_ms,
            effective_start, int(end_ms), result.rows_received, result.rows_new,
            result.covered_from_ms, result.covered_to_ms, result.gaps,
            duration_ms, result.status, result.error,
        )

    def sync_many(
        self,
        instrument_ids: tuple[str, ...] | list[str],
        interval: str,
        *,
        end_ms: int,
        initial_start_ms: int,
    ) -> BatchSyncResult:
        results: list[SyncMetrics] = []
        for instrument_id in instrument_ids:
            try:
                result = self.sync_incremental(
                    instrument_id,
                    interval,
                    end_ms=end_ms,
                    initial_start_ms=initial_start_ms,
                )
            except Exception as exc:
                result = SyncMetrics(
                    instrument_id, interval, initial_start_ms, end_ms,
                    None, None, 0, 0, None, None, (), 0, 'error', str(exc),
                )
            results.append(result)
        frozen = tuple(results)
        return BatchSyncResult(
            frozen,
            sum(result.rows_received for result in frozen),
            sum(result.rows_new for result in frozen),
            sum(result.status == 'error' for result in frozen),
            sum(result.duration_ms for result in frozen),
        )
