"""In-memory pair-ratio contracts built from validated candle data."""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


RATIO_COLUMNS = ['timestamp_ms', 'long_close', 'short_close', 'price_ratio', 'log_ratio']


@dataclass(frozen=True)
class RatioResult:
    pair_id: str
    frame: pd.DataFrame
    matched_rows: int
    missing_long: tuple[int, ...]
    missing_short: tuple[int, ...]
    status: str
    error: str | None = None


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=RATIO_COLUMNS)


def build_pair_ratios(
    long_candles: pd.DataFrame,
    short_candles: pd.DataFrame,
    *,
    pair_id: str,
) -> RatioResult:
    """Build exact-timestamp price and log ratios from two candle frames."""
    long_frame = long_candles[['timestamp_ms', 'close']].rename(columns={'close': 'long_close'})
    short_frame = short_candles[['timestamp_ms', 'close']].rename(columns={'close': 'short_close'})
    long_timestamps = set(long_frame['timestamp_ms'].astype(int))
    short_timestamps = set(short_frame['timestamp_ms'].astype(int))
    missing_long = tuple(sorted(short_timestamps - long_timestamps))
    missing_short = tuple(sorted(long_timestamps - short_timestamps))
    frame = long_frame.merge(short_frame, on='timestamp_ms', how='inner').sort_values('timestamp_ms').reset_index(drop=True)
    if frame.empty:
        return RatioResult(str(pair_id), _empty_frame(), 0, missing_long, missing_short, 'empty')
    frame['price_ratio'] = frame['long_close'] / frame['short_close']
    frame['log_ratio'] = [math.log(long / short) for long, short in zip(frame['long_close'], frame['short_close'])]
    frame = frame[RATIO_COLUMNS]
    status = 'complete' if not missing_long and not missing_short else 'partial'
    return RatioResult(str(pair_id), frame, len(frame), missing_long, missing_short, status)
