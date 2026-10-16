from __future__ import annotations

from datetime import datetime
from typing import Any


def _iso_ms(value: Any, tz) -> str:
    try:
        ms = int(value or 0)
    except (TypeError, ValueError):
        return ''
    return datetime.fromtimestamp(ms / 1000, tz).isoformat() if ms > 0 else ''


def build_export_rows(active: list[dict[str, Any]], closed_history: list[dict[str, Any]], tz) -> list[dict[str, Any]]:
    """CSV rows for active and archived pairs so realized totals reconcile."""
    rows: list[dict[str, Any]] = []
    for x in active:
        known_open = [v for v in (x.get('opened_long'), x.get('opened_short')) if v]
        opened_at = _iso_ms(max(known_open), tz) if known_open else ''
        rows.append({
            'status': 'active',
            'pair': f"{x['long']}/{x['short']}", 'long_asset': x['long'], 'short_asset': x['short'],
            'opened_at': opened_at, 'closed_at': '',
            'long_notional_usd': x.get('long_usd'), 'short_notional_usd': x.get('short_usd'),
            'total_notional_usd': x.get('notional'), 'entry_ratio': x.get('entry_ratio'), 'current_ratio': x.get('current_ratio'),
            'ratio_change_pct': x.get('ratio_change'), 'management_reference_ratio': x.get('management_entry_ratio'),
            'management_ratio_change_pct': x.get('management_ratio_change'), 'zscore_1d': x.get('management_z'),
            'take_profit_state': x.get('tp'), 'add_state': x.get('add'),
            'unrealized_pnl_usd': x.get('unrealized'), 'realized_pnl_usd': x.get('realized'),
            'funding_usd': x.get('funding'), 'fees_usd': x.get('fees'), 'total_pnl_usd': x.get('total_pnl'),
            'neutrality_pct': x.get('imbalance'), 'liq_distance_pct': x.get('liq_distance'),
            'long_liq_distance_pct': x.get('long_liq_distance'), 'short_liq_distance_pct': x.get('short_liq_distance'),
            'history_complete': x.get('history_complete'),
        })
    for item in closed_history:
        realized = float(item.get('realized') or 0)
        fees = float(item.get('fees') or 0)
        rows.append({
            'status': 'closed',
            'pair': f"{item.get('long','')}/{item.get('short','')}",
            'long_asset': item.get('long', ''), 'short_asset': item.get('short', ''),
            'opened_at': _iso_ms(item.get('opened_at'), tz), 'closed_at': _iso_ms(item.get('closed_at'), tz),
            'long_notional_usd': None, 'short_notional_usd': None, 'total_notional_usd': None,
            'entry_ratio': None, 'current_ratio': None, 'ratio_change_pct': None,
            'management_reference_ratio': None, 'management_ratio_change_pct': None, 'zscore_1d': None,
            'take_profit_state': '', 'add_state': '', 'unrealized_pnl_usd': 0.0,
            'realized_pnl_usd': realized, 'funding_usd': item.get('funding'), 'fees_usd': fees,
            'total_pnl_usd': item.get('total_pnl'), 'neutrality_pct': None, 'liq_distance_pct': None,
            'long_liq_distance_pct': None, 'short_liq_distance_pct': None, 'history_complete': bool(item.get('funding_complete')),
        })
    return rows
