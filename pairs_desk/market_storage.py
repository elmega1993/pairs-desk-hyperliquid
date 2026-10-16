"""Atomic, idempotent Parquet storage for normalized market candles."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .market_quality import CANONICAL_COLUMNS, validate_candles


@dataclass(frozen=True)
class MergeResult:
    rows_received: int
    rows_new: int
    total_rows: int
    path: Path


class MarketDataStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def path_for(self, instrument_id: str, venue: str, interval: str) -> Path:
        return self.root / 'candles' / str(venue).strip().lower() / str(instrument_id) / f'{str(interval).strip()}.parquet'

    @staticmethod
    def _empty() -> pd.DataFrame:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    def read_candles(self, instrument_id: str, venue: str, interval: str) -> pd.DataFrame:
        path = self.path_for(instrument_id, venue, interval)
        if not path.exists():
            return self._empty()
        frame = pd.read_parquet(path, engine='pyarrow')
        return frame[CANONICAL_COLUMNS].sort_values('timestamp_ms').reset_index(drop=True)

    @staticmethod
    def _same_row(left: pd.Series, right: pd.Series) -> bool:
        for column in CANONICAL_COLUMNS:
            if column in {'open', 'high', 'low', 'close', 'volume'}:
                if not float(left[column]) == float(right[column]):
                    return False
            elif left[column] != right[column]:
                return False
        return True

    def merge_candles(self, frame: pd.DataFrame) -> MergeResult:
        report = validate_candles(frame)
        if not report.valid:
            raise ValueError(report.error or 'Velas inválidas')
        frame = frame[CANONICAL_COLUMNS].copy().reset_index(drop=True)
        instrument = str(frame['instrument_id'].iloc[0])
        venue = str(frame['venue'].iloc[0])
        interval = str(frame['interval'].iloc[0])
        path = self.path_for(instrument, venue, interval)
        existing = self.read_candles(instrument, venue, interval)
        by_timestamp = {int(row['timestamp_ms']): row for _, row in existing.iterrows()}
        rows_new = 0
        for _, row in frame.iterrows():
            timestamp = int(row['timestamp_ms'])
            prior = by_timestamp.get(timestamp)
            if prior is not None:
                if not self._same_row(prior, row):
                    raise ValueError(f'Vela conflictiva en timestamp {timestamp}')
                continue
            by_timestamp[timestamp] = row
            rows_new += 1
        merged = pd.DataFrame(list(by_timestamp.values()), columns=CANONICAL_COLUMNS).sort_values('timestamp_ms').reset_index(drop=True)
        if rows_new:
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, temporary = tempfile.mkstemp(dir=path.parent, suffix='.parquet.tmp')
            os.close(fd)
            try:
                merged.to_parquet(temporary, index=False, engine='pyarrow')
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
        return MergeResult(len(frame), rows_new, len(merged), path)
