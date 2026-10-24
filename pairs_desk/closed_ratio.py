"""Ratio references for archived pair cycles."""
from __future__ import annotations

import math
from typing import Any, Iterable


def _signed_qty(fill: dict[str, Any]) -> float:
    try:
        size = float(fill.get('sz') or 0)
    except (TypeError, ValueError):
        return 0.0
    side = str(fill.get('side') or '').upper()
    return size if side == 'B' else -size if side == 'A' else 0.0


def _close_vwap(coin: str, fills: list[dict[str, Any]], opened_at: int, closed_at: int) -> float | None:
    relevant = sorted(
        (f for f in fills if f.get('coin') == coin and opened_at <= int(f.get('time', 0) or 0) <= closed_at),
        key=lambda f: (int(f.get('time', 0) or 0), str(f.get('tid') or f.get('hash') or '')),
    )
    direction = 0
    for fill in relevant:
        try:
            start = float(fill.get('startPosition') or 0)
        except (TypeError, ValueError):
            continue
        signed = _signed_qty(fill)
        if abs(start) <= 1e-9 and signed:
            direction = 1 if signed > 0 else -1
            break
    if not direction:
        return None
    notional = size_total = 0.0
    for fill in relevant:
        signed = _signed_qty(fill)
        if signed * direction >= 0:
            continue
        try:
            px = float(fill.get('px') or 0)
            size = abs(float(fill.get('sz') or 0))
        except (TypeError, ValueError):
            continue
        if px > 0 and size > 0:
            notional += px * size
            size_total += size
    return notional / size_total if size_total > 0 else None


def close_ratio_from_fills(
    long_sym: str, short_sym: str, fills: Iterable[dict[str, Any]], opened_at: int, closed_at: int
) -> float | None:
    """Return the long/short VWAP ratio of the terminal close fills."""
    opened_at, closed_at = int(opened_at or 0), int(closed_at or 0)
    if not opened_at or not closed_at or closed_at < opened_at:
        return None
    rows = [f for f in fills if isinstance(f, dict)]
    long_px = _close_vwap(long_sym, rows, opened_at, closed_at)
    short_px = _close_vwap(short_sym, rows, opened_at, closed_at)
    if long_px is None or short_px is None or short_px <= 0:
        return None
    return long_px / short_px


def ratio_change_since_close(current_ratio: float | None, close_ratio: float | None) -> float | None:
    if current_ratio is None or close_ratio is None:
        return None
    try:
        current, closed = float(current_ratio), float(close_ratio)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(current) or not math.isfinite(closed) or closed <= 0:
        return None
    return (current / closed - 1.0) * 100.0
