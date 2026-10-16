"""In-memory pair-ratio contracts built from validated candle data."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .market_quality import CANONICAL_COLUMNS


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


def _error(pair_id: str, message: str) -> RatioResult:
    return RatioResult(str(pair_id), _empty_frame(), 0, (), (), 'error', message)


def _validate_candles(frame: pd.DataFrame, role: str) -> tuple[pd.DataFrame | None, str | None]:
    if not isinstance(frame, pd.DataFrame):
        return None, f'Las velas {role} deben ser un DataFrame'
    missing = [column for column in CANONICAL_COLUMNS if column not in frame.columns]
    if missing:
        return None, f'Faltan columnas en las velas {role}: {", ".join(missing)}'
    if frame.empty:
        return frame.copy(), None
    result = frame[CANONICAL_COLUMNS].copy()
    timestamps = pd.to_numeric(result['timestamp_ms'], errors='coerce')
    closes = pd.to_numeric(result['close'], errors='coerce')
    if not np.isfinite(timestamps.to_numpy()).all() or not np.isfinite(closes.to_numpy()).all():
        return None, f'Hay timestamps o cierres no finitos en las velas {role}'
    if (closes <= 0).any():
        return None, f'Hay cierres no positivos en las velas {role}'
    if timestamps.duplicated().any():
        return None, f'Hay timestamps duplicados en las velas {role}'
    if result['instrument_id'].nunique(dropna=False) != 1 or result['venue'].nunique(dropna=False) != 1 or result['interval'].nunique(dropna=False) != 1:
        return None, f'Las velas {role} contienen series incompatibles'
    result['timestamp_ms'] = timestamps.astype('int64')
    result['close'] = closes.astype(float)
    return result, None


def build_pair_ratios(
    long_candles: pd.DataFrame,
    short_candles: pd.DataFrame,
    *,
    pair_id: str,
) -> RatioResult:
    """Build exact-timestamp price and log ratios from two candle frames."""
    long_validated, long_error = _validate_candles(long_candles, 'long')
    short_validated, short_error = _validate_candles(short_candles, 'short')
    if long_error or short_error:
        return _error(pair_id, long_error or short_error or 'Entradas inválidas')
    assert long_validated is not None and short_validated is not None
    if not long_validated.empty and not short_validated.empty:
        long_instrument = str(long_validated['instrument_id'].iloc[0])
        short_instrument = str(short_validated['instrument_id'].iloc[0])
        if long_instrument == short_instrument:
            return _error(pair_id, 'Las patas del par deben ser distintas')
        long_interval = str(long_validated['interval'].iloc[0])
        short_interval = str(short_validated['interval'].iloc[0])
        if long_interval != short_interval:
            return _error(pair_id, 'Las series tienen intervalos incompatibles')
    long_frame = long_validated[['timestamp_ms', 'close']].rename(columns={'close': 'long_close'})
    short_frame = short_validated[['timestamp_ms', 'close']].rename(columns={'close': 'short_close'})
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
