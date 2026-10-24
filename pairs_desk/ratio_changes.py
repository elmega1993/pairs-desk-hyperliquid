from __future__ import annotations

import math

import pandas as pd


def ratio_change_pct(current_ratio: float | None, reference_ratio: float | None) -> float | None:
    try:
        current = float(current_ratio)
        reference = float(reference_ratio)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(current) or not math.isfinite(reference) or current <= 0 or reference <= 0:
        return None
    return (current / reference - 1) * 100


def ratio_changes_from_bars(
    current_ratio: float | None, bars: pd.DataFrame, now_ms: int
) -> dict[str, float | None]:
    result: dict[str, float | None] = {'1h': None, '24h': None}
    if current_ratio is None or not isinstance(bars, pd.DataFrame) or bars.empty or 'c' not in bars:
        return result
    try:
        current = float(current_ratio)
        now = int(now_ms)
    except (TypeError, ValueError):
        return result
    if not math.isfinite(current) or current <= 0:
        return result

    index_ms = pd.to_datetime(bars.index, utc=True).astype('int64') // 1_000_000
    for label, offset_ms in (('1h', 3_600_000), ('24h', 86_400_000)):
        target = now - offset_ms
        eligible = [
            (i, int(timestamp)) for i, timestamp in enumerate(index_ms) if int(timestamp) <= target
        ]
        if not eligible:
            continue
        row = bars.iloc[max(eligible, key=lambda item: item[1])[0]]
        result[label] = ratio_change_pct(current, row.get('c'))
    return result
