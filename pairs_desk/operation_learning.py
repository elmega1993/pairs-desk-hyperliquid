"""Pure normalization of archived pairs for operational learning."""
from __future__ import annotations

import math
from typing import Any

from .closed_ratio import close_ratio_from_fills
from .learning_data import LearningSnapshot


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _signed_qty(fill: dict[str, Any]) -> float:
    size = _number(fill.get('sz')) or 0.0
    side = str(fill.get('side') or '').casefold()
    return size if side == 'b' else -size if side == 'a' else 0.0


def _opening_notional(fills: list[dict[str, Any]], coin: str, opened_at: int) -> float | None:
    relevant = sorted((fill for fill in fills if fill.get('coin') == coin), key=lambda x: int(x.get('time', 0) or 0))
    direction = 0
    for fill in relevant:
        timestamp = int(fill.get('time', 0) or 0)
        if not opened_at - 300_000 <= timestamp <= opened_at + 300_000:
            continue
        start = _number(fill.get('startPosition'))
        signed = _signed_qty(fill)
        if start is not None and abs(start) <= 1e-9 and signed:
            direction = 1 if signed > 0 else -1
            break
    if not direction:
        return None
    total = 0.0
    found = False
    for fill in relevant:
        timestamp = int(fill.get('time', 0) or 0)
        if not opened_at - 300_000 <= timestamp <= opened_at + 300_000:
            continue
        px, size = _number(fill.get('px')), abs(_number(fill.get('sz')) or 0.0)
        if px and size and _signed_qty(fill) * direction > 0:
            total += px * size
            found = True
    return total if found else None


def build_operation_rows(snapshot: LearningSnapshot) -> list[dict[str, Any]]:
    rows = []
    for item in snapshot.closed_pairs:
        reasons: list[str] = []
        opened = item.get('opened_at')
        closed = item.get('closed_at')
        try:
            valid_interval = int(opened) > 0 and int(closed) >= int(opened)
        except (TypeError, ValueError):
            valid_interval = False
        if not valid_interval:
            reasons.append('invalid_interval')
        if not isinstance(item.get('long'), str) or not isinstance(item.get('short'), str):
            reasons.append('missing_legs')

        realized = _number(item.get('realized'))
        fees = _number(item.get('fees'))
        funding = _number(item.get('funding'))
        net = _number(item.get('total_pnl'))
        if item.get('funding_complete') is not True:
            reasons.append('funding_incomplete')
        if net is None:
            reasons.append('net_pnl_unavailable')
        if realized is None or fees is None:
            reasons.append('realized_or_fees_unavailable')

        if 'invalid_interval' in reasons or 'missing_legs' in reasons:
            quality = 'no comparable'
        elif not reasons:
            quality = 'verificada'
        else:
            quality = 'parcial'

        duration = (int(closed) - int(opened)) / 86_400_000 if valid_interval else None
        events = item.get('events') if isinstance(item.get('events'), list) else []
        management_events = [event for event in events if isinstance(event, dict)
                             and str(event.get('kind', event.get('event', ''))).casefold() in {
                                 'add', 'tp', 'take_profit', 'stop', 'stop_loss',
                             }]
        entry_long = _opening_notional(snapshot.fills, str(item.get('long')), int(opened or 0)) if valid_interval else None
        entry_short = _opening_notional(snapshot.fills, str(item.get('short')), int(opened or 0)) if valid_interval else None
        entry_gross = entry_long + entry_short if entry_long is not None and entry_short is not None else None
        close_ratio = close_ratio_from_fills(
            str(item.get('long')), str(item.get('short')), snapshot.fills, int(opened or 0), int(closed or 0)
        ) if valid_interval else None
        enrichment_reasons = []
        if entry_gross is None:
            enrichment_reasons.append('entry_notional_unavailable')
        if close_ratio is None:
            enrichment_reasons.append('close_ratio_unavailable')
        rows.append({
            'id': item.get('id') or f"{item.get('long', '')}|{item.get('short', '')}",
            'long': item.get('long'),
            'short': item.get('short'),
            'opened_at': opened,
            'closed_at': closed,
            'duration_days': duration,
            'entry_ratio': _number(item.get('entry_ratio')),
            'close_ratio': _number(item.get('close_ratio')) or close_ratio,
            'entry_long_notional_usd': entry_long,
            'entry_short_notional_usd': entry_short,
            'entry_gross_notional_usd': entry_gross,
            'pnl_pct_gross': net / entry_gross * 100 if net is not None and entry_gross else None,
            'realized_pnl_usd': realized,
            'fees_usd': fees,
            'funding_usd': funding,
            'net_pnl_usd': net,
            'won': net > 0 if quality == 'verificada' and net is not None else None,
            'management_event_count': len(management_events),
            'enrichment_reasons': enrichment_reasons,
            'data_quality': quality,
            'quality_reasons': reasons,
        })
    return rows
