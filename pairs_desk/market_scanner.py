"""Read-only pair discovery over the local market catalog and Parquet cache."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .market_catalog import MarketCatalog
from .market_ratios import build_pair_ratios
from .market_storage import MarketDataStore


@dataclass(frozen=True)
class ScannerCandidate:
    pair_id: str
    label: str
    long: str
    short: str
    venue: str
    status: str
    reason: str | None
    ratio: float | None
    ratio_change_pct: float | None
    matched_rows: int
    missing_long: tuple[int, ...]
    missing_short: tuple[int, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScannerResult:
    interval: str
    candidates: tuple[ScannerCandidate, ...]
    total: int
    as_of_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            'interval': self.interval,
            'candidates': [candidate.to_dict() for candidate in self.candidates],
            'total': self.total,
            'as_of_ms': self.as_of_ms,
        }


def bootstrap_catalog_from_settings(catalog: MarketCatalog, settings: dict[str, Any]) -> int:
    """Seed the public market catalog from configured pair definitions."""
    created = 0
    for saved in settings.get('pairs', []) if isinstance(settings, dict) else []:
        if not isinstance(saved, dict) or not saved.get('long') or not saved.get('short'):
            continue
        try:
            legs = []
            for value in (saved['long'], saved['short']):
                raw = str(value).strip()
                venue, separator, symbol = raw.partition(':')
                legs.append((symbol if separator else raw, venue if separator else 'core'))
            for symbol, venue in legs:
                catalog.upsert_instrument(symbol, venue)
            catalog.upsert_pair(
                f'{legs[0][1]}:{legs[0][0]}',
                f'{legs[1][1]}:{legs[1][0]}',
                label=f'{saved["long"]}/{saved["short"]}',
            )
            created += 1
        except (KeyError, TypeError, ValueError):
            continue
    return created


class MarketScanner:
    def __init__(self, catalog: MarketCatalog, store: MarketDataStore, *, now_ms: int | None = None):
        self.catalog = catalog
        self.store = store
        self.now_ms = now_ms

    def scan(
        self,
        *,
        interval: str = '1h',
        search: str = '',
        venue: str = '',
        limit: int = 50,
    ) -> ScannerResult:
        if not 1 <= limit <= 100:
            raise ValueError('limit debe estar entre 1 y 100')
        clean_search = str(search).strip().lower()
        clean_venue = str(venue).strip().lower()
        pairs = []
        for pair in self.catalog.list_pairs(active_only=True):
            long_instrument = self.catalog.get_instrument(pair['long_instrument_id'])
            short_instrument = self.catalog.get_instrument(pair['short_instrument_id'])
            if not long_instrument or not short_instrument:
                continue
            text = ' '.join((pair['pair_id'], pair['label'], long_instrument['symbol'], short_instrument['symbol'])).lower()
            venues = {long_instrument['venue'], short_instrument['venue']}
            if clean_search and clean_search not in text:
                continue
            if clean_venue and clean_venue not in venues:
                continue
            pairs.append((pair, long_instrument, short_instrument))
        candidates = tuple(
            self._candidate(pair, long_instrument, short_instrument, interval)
            for pair, long_instrument, short_instrument in pairs[:limit]
        )
        as_of_ms = int(self.now_ms if self.now_ms is not None else time.time() * 1000)
        return ScannerResult(interval, candidates, len(pairs), as_of_ms)

    def _candidate(self, pair: dict[str, Any], long_instrument: dict[str, Any], short_instrument: dict[str, Any], interval: str) -> ScannerCandidate:
        long_frame = self.store.read_candles(long_instrument['instrument_id'], long_instrument['venue'], interval)
        short_frame = self.store.read_candles(short_instrument['instrument_id'], short_instrument['venue'], interval)
        venue = '/'.join(sorted({long_instrument['venue'], short_instrument['venue']}))
        if long_frame.empty or short_frame.empty:
            return ScannerCandidate(
                pair['pair_id'], pair['label'], long_instrument['symbol'], short_instrument['symbol'],
                venue, 'no_data', 'Faltan velas locales para una o ambas patas', None, None, 0, (), (),
            )
        ratios = build_pair_ratios(long_frame, short_frame, pair_id=pair['pair_id'])
        if ratios.status == 'error' or ratios.frame.empty:
            return ScannerCandidate(
                pair['pair_id'], pair['label'], long_instrument['symbol'], short_instrument['symbol'],
                venue, 'error' if ratios.status == 'error' else 'no_data', ratios.error, None, None,
                ratios.matched_rows, ratios.missing_long, ratios.missing_short,
            )
        ratio_frame = ratios.frame
        current = float(ratio_frame['price_ratio'].iloc[-1])
        previous = self._previous_ratio(ratio_frame)
        change = ((current / previous) - 1) * 100 if previous and previous > 0 else None
        return ScannerCandidate(
            pair['pair_id'], pair['label'], long_instrument['symbol'], short_instrument['symbol'],
            venue, ratios.status, None, current, change, ratios.matched_rows,
            ratios.missing_long, ratios.missing_short,
        )

    def _previous_ratio(self, frame: pd.DataFrame) -> float | None:
        current_timestamp = int(frame['timestamp_ms'].iloc[-1])
        cutoff = current_timestamp - 86_400_000
        previous = frame.loc[frame['timestamp_ms'] <= cutoff, 'price_ratio']
        return float(previous.iloc[-1]) if not previous.empty else None
