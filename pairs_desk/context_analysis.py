"""Historical ratio context calculations kept independent from network I/O."""
from __future__ import annotations

import math
from typing import Any

import pandas as pd

from .market_ratios import build_pair_ratios
from .metrics import spread_stats


def _rounded(value: float | None) -> float | None:
    return round(value, 2) if value is not None and math.isfinite(value) else None


def analyze_ratio_context(
    long_candles: pd.DataFrame,
    short_candles: pd.DataFrame,
    opened_at: int,
    closed_at: int,
    entry_ratio: float | None,
) -> dict[str, Any]:
    result = {
        'status': 'unavailable', 'entry_zscore': None, 'mfe_pct': None,
        'mae_pct': None, 'close_ratio': None, 'bars_after_entry': 0,
        'reason': None,
    }
    if not opened_at or not closed_at or closed_at < opened_at:
        result['reason'] = 'invalid_interval'
        return result
    ratios = build_pair_ratios(long_candles, short_candles, pair_id='context')
    if ratios.frame.empty:
        result['reason'] = ratios.error or 'no_ratio_bars'
        return result
    frame = ratios.frame.copy()
    before = frame[frame['timestamp_ms'] <= int(opened_at)]
    after = frame[(frame['timestamp_ms'] >= int(opened_at)) & (frame['timestamp_ms'] <= int(closed_at))]
    if after.empty:
        result['reason'] = 'no_bars_after_entry'
        return result
    reference = float(entry_ratio) if entry_ratio and float(entry_ratio) > 0 else float(after.iloc[0]['price_ratio'])
    changes = (after['price_ratio'] / reference - 1.0) * 100.0
    result['mfe_pct'] = _rounded(float(changes.max()))
    result['mae_pct'] = _rounded(float(changes.min()))
    result['close_ratio'] = _rounded(float(after.iloc[-1]['price_ratio']))
    result['bars_after_entry'] = int(len(after))
    if len(before) >= 10:
        stats = spread_stats(before.rename(columns={'price_ratio': 'c'}))
        z = stats.iloc[-1]['z']
        result['entry_zscore'] = _rounded(float(z)) if pd.notna(z) else None
    result['status'] = 'ok'
    if result['entry_zscore'] is None:
        result['reason'] = 'insufficient_pre_entry_bars'
    return result


def analyze_event_context(
    long_candles: pd.DataFrame,
    short_candles: pd.DataFrame,
    event_time: int,
    closed_at: int,
    entry_ratio: float | None,
) -> dict[str, Any]:
    result = {
        'status': 'unavailable', 'event_ratio': None, 'move_from_entry_pct': None,
        'post_event_mfe_pct': None, 'post_event_mae_pct': None, 'reason': None,
    }
    if not event_time or not closed_at or closed_at < event_time:
        result['reason'] = 'invalid_interval'
        return result
    ratios = build_pair_ratios(long_candles, short_candles, pair_id='event')
    frame = ratios.frame
    if frame.empty:
        result['reason'] = ratios.error or 'no_ratio_bars'
        return result
    event_rows = frame[frame['timestamp_ms'] <= int(event_time)]
    after = frame[(frame['timestamp_ms'] >= int(event_time)) & (frame['timestamp_ms'] <= int(closed_at))]
    if event_rows.empty or after.empty:
        result['reason'] = 'no_event_bars'
        return result
    event_ratio = float(event_rows.iloc[-1]['price_ratio'])
    reference = float(entry_ratio) if entry_ratio and float(entry_ratio) > 0 else event_ratio
    changes_from_entry = (after['price_ratio'] / reference - 1.0) * 100.0
    changes_from_event = (after['price_ratio'] / event_ratio - 1.0) * 100.0
    result.update({
        'status': 'ok',
        'event_ratio': _rounded(event_ratio),
        'move_from_entry_pct': _rounded((event_ratio / reference - 1.0) * 100.0),
        'post_event_mfe_pct': _rounded(float(changes_from_event.max())),
        'post_event_mae_pct': _rounded(float(changes_from_event.min())),
    })
    return result
