"""Normalization and conservative quality checks for market candles."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd

CANONICAL_COLUMNS = [
    'instrument_id', 'venue', 'interval', 'timestamp_ms',
    'open', 'high', 'low', 'close', 'volume', 'source',
]
_INTERVAL_MS = {
    '1m': 60_000,
    '3m': 180_000,
    '5m': 300_000,
    '15m': 900_000,
    '30m': 1_800_000,
    '1h': 3_600_000,
    '2h': 7_200_000,
    '4h': 14_400_000,
    '8h': 28_800_000,
    '12h': 43_200_000,
    '1d': 86_400_000,
    '3d': 259_200_000,
    '1w': 604_800_000,
}


@dataclass(frozen=True)
class QualityReport:
    valid: bool
    row_count: int
    duplicate_count: int
    gaps: tuple[int, ...]
    error: str | None = None


def _number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f'{field} no es numérico') from exc
    return number


def normalize_candles(
    rows: Iterable[dict[str, Any]], instrument_id: str, venue: str, interval: str, *, source: str = 'hyperliquid'
) -> pd.DataFrame:
    """Normalize Hyperliquid candleSnapshot rows without sorting them."""
    normalized = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('La vela no es un objeto')
        normalized.append({
            'instrument_id': str(instrument_id),
            'venue': str(venue).strip().lower(),
            'interval': str(interval).strip(),
            'timestamp_ms': int(_number(row.get('t', row.get('timestamp_ms')), 'timestamp_ms')),
            'open': _number(row.get('o', row.get('open')), 'open'),
            'high': _number(row.get('h', row.get('high')), 'high'),
            'low': _number(row.get('l', row.get('low')), 'low'),
            'close': _number(row.get('c', row.get('close')), 'close'),
            'volume': _number(row.get('v', row.get('volume')), 'volume'),
            'source': str(source),
        })
    return pd.DataFrame(normalized, columns=CANONICAL_COLUMNS)


def validate_candles(frame: pd.DataFrame) -> QualityReport:
    if not isinstance(frame, pd.DataFrame):
        return QualityReport(False, 0, 0, (), 'Las velas deben ser un DataFrame')
    missing = [column for column in CANONICAL_COLUMNS if column not in frame.columns]
    if missing:
        return QualityReport(False, len(frame), 0, (), f'Faltan columnas: {", ".join(missing)}')
    if frame.empty:
        return QualityReport(False, 0, 0, (), 'La ventana no contiene velas')

    timestamps = pd.to_numeric(frame['timestamp_ms'], errors='coerce')
    numeric = frame[['open', 'high', 'low', 'close', 'volume']].apply(pd.to_numeric, errors='coerce')
    duplicate_count = int(frame['timestamp_ms'].duplicated(keep=False).sum())
    if not np.isfinite(timestamps.to_numpy()).all() or not np.isfinite(numeric.to_numpy()).all():
        return QualityReport(False, len(frame), duplicate_count, (), 'Hay timestamps o valores no finitos')
    if not timestamps.is_monotonic_increasing:
        return QualityReport(False, len(frame), duplicate_count, (), 'Los timestamps no están ordenados')
    if duplicate_count:
        return QualityReport(False, len(frame), duplicate_count, (), 'Hay timestamps duplicados')

    invalid_bounds = (
        (numeric['high'] < numeric[['open', 'close', 'low']].max(axis=1))
        | (numeric['low'] > numeric[['open', 'close', 'high']].min(axis=1))
    )
    if invalid_bounds.any():
        return QualityReport(False, len(frame), duplicate_count, (), 'Hay límites OHLC imposibles')
    if (numeric['volume'] < 0).any():
        return QualityReport(False, len(frame), duplicate_count, (), 'Hay volumen negativo')

    interval = str(frame['interval'].iloc[0])
    expected = _INTERVAL_MS.get(interval)
    gaps: tuple[int, ...] = ()
    if expected and len(timestamps) > 1:
        deltas = timestamps.diff().iloc[1:]
        gaps = tuple(int(timestamps.iloc[index]) for index, delta in enumerate(deltas, start=1) if delta > expected)
    return QualityReport(True, len(frame), 0, gaps)
