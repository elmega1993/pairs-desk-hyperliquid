"""On-demand historical loading and ratio analysis for user-selected legs."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

from .market_catalog import MarketCatalog, pair_id
from .market_ingestion import MarketIngestor
from .market_ratios import build_pair_ratios
from .market_storage import MarketDataStore


@dataclass(frozen=True)
class PairAnalysisResult:
    pair_id: str
    long_instrument_id: str
    short_instrument_id: str
    interval: str
    lookback_days: int
    status: str
    source: str
    rows: tuple[dict[str, Any], ...]
    matched_rows: int
    missing_long: tuple[int, ...]
    missing_short: tuple[int, ...]
    sync: tuple[dict[str, Any], ...]
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PairAnalysisService:
    def __init__(
        self,
        catalog: MarketCatalog,
        store: MarketDataStore,
        fetch: Callable[..., Any],
        *,
        now_ms: Callable[[], int] | None = None,
    ):
        self.catalog = catalog
        self.store = store
        self.fetch = fetch
        self.now_ms = now_ms or (lambda: int(time.time() * 1000))
        self.ingestor = MarketIngestor(catalog, store, fetch)

    def analyze(self, long_instrument_id: str, short_instrument_id: str, *, interval: str = '1h', lookback_days: int = 180) -> PairAnalysisResult:
        if not 1 <= lookback_days <= 730:
            raise ValueError('lookback_days debe estar entre 1 y 730')
        ident = pair_id(long_instrument_id, short_instrument_id)
        long_instrument = self.catalog.get_instrument(long_instrument_id)
        short_instrument = self.catalog.get_instrument(short_instrument_id)
        if long_instrument is None or short_instrument is None:
            raise ValueError('Uno o ambos activos no están disponibles en el catálogo')
        end_ms = int(self.now_ms())
        start_ms = end_ms - lookback_days * 86_400_000
        sync_results = (
            self.ingestor.sync_candles(long_instrument_id, interval, start_ms, end_ms),
            self.ingestor.sync_candles(short_instrument_id, interval, start_ms, end_ms),
        )
        long_frame = self.store.read_candles(long_instrument_id, long_instrument['venue'], interval)
        short_frame = self.store.read_candles(short_instrument_id, short_instrument['venue'], interval)
        if long_frame.empty or short_frame.empty:
            status = 'no_data'
            rows: tuple[dict[str, Any], ...] = ()
            matched_rows, missing_long, missing_short = 0, (), ()
        else:
            ratios = build_pair_ratios(long_frame, short_frame, pair_id=ident)
            status = ratios.status
            rows = tuple(
                {
                    'timestamp_ms': int(row.timestamp_ms),
                    'price_ratio': float(row.price_ratio),
                    'log_ratio': float(row.log_ratio),
                }
                for row in ratios.frame.itertuples(index=False)
            )
            matched_rows, missing_long, missing_short = ratios.matched_rows, ratios.missing_long, ratios.missing_short
        sync = tuple({
            'instrument_id': result_instrument,
            'status': result.status,
            'rows_received': result.rows_received,
            'rows_new': result.rows_new,
            'covered_from_ms': result.covered_from_ms,
            'covered_to_ms': result.covered_to_ms,
            'gaps': result.gaps,
            'error': result.error,
        } for result_instrument, result in zip((long_instrument_id, short_instrument_id), sync_results))
        errors = [item['error'] for item in sync if item['error']]
        if status != 'no_data' and errors and matched_rows == 0:
            status = 'error'
        return PairAnalysisResult(
            ident, long_instrument_id, short_instrument_id, interval, lookback_days,
            status, 'hyperliquid_candles', rows, matched_rows, missing_long, missing_short,
            sync, '; '.join(errors) if errors else None,
        )
