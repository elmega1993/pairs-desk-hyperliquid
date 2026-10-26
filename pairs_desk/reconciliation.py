"""Read-only reconciliation between local pairs and Hyperliquid account data."""
from __future__ import annotations

import math
from typing import Any

import requests

from .metrics import position_map

API = 'https://api.hyperliquid.xyz/info'


def _number(value: Any) -> float | None:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _pnl_delta(portfolio: list, key: str) -> float | None:
    windows = {row[0]: row[1] for row in portfolio if isinstance(row, (list, tuple)) and len(row) == 2 and isinstance(row[1], dict)}
    history = (windows.get(key) or {}).get('pnlHistory') or []
    values = []
    for row in history:
        if isinstance(row, (list, tuple)) and len(row) >= 2 and _number(row[1]) is not None:
            values.append(_number(row[1]))
    return values[-1] - values[0] if values else None


def reconcile_payloads(settings: dict[str, Any], portfolio: list, core: dict, xyz: dict) -> dict[str, Any]:
    core_positions = position_map(core)
    xyz_positions = {key if ':' in key else f'xyz:{key}': value for key, value in position_map(xyz).items()}
    positions = {**core_positions, **xyz_positions}
    active = []
    for pair in settings.get('pairs', []):
        if not isinstance(pair, dict):
            continue
        long, short = pair.get('long'), pair.get('short')
        lp, sp = positions.get(long), positions.get(short)
        if not lp or not sp:
            continue
        long_size, short_size = _number(lp.get('szi')), _number(sp.get('szi'))
        if long_size is None or short_size is None or long_size <= 0 or short_size >= 0:
            continue
        pnl = (_number(lp.get('unrealizedPnl')) or 0.0) + (_number(sp.get('unrealizedPnl')) or 0.0)
        active.append({'pair': f'{long}|{short}', 'unrealized_pnl_usd': pnl})
    return {
        'configured_pair_count': len(settings.get('pairs', [])),
        'live_position_count': len(positions),
        'active_pair_count': len(active),
        'active_unrealized_usd': sum(row['unrealized_pnl_usd'] for row in active),
        'active_pairs': active,
        'pnl_windows': {
            '1d_usd': _pnl_delta(portfolio, 'perpDay'),
            '7d_usd': _pnl_delta(portfolio, 'perpWeek'),
            '30d_usd': _pnl_delta(portfolio, 'perpMonth'),
            'all_usd': _pnl_delta(portfolio, 'perpAllTime'),
        },
    }


def fetch_reconciliation(settings: dict[str, Any], timeout: tuple[int, int] = (4, 14)) -> dict[str, Any]:
    account = str(settings.get('address', '')).strip()
    if not account:
        raise ValueError('settings.json no contiene address')

    def request(payload: dict[str, Any]):
        response = requests.post(API, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()

    portfolio = request({'type': 'portfolio', 'user': account})
    core = request({'type': 'clearinghouseState', 'user': account})
    xyz = request({'type': 'clearinghouseState', 'user': account, 'dex': 'xyz'})
    return reconcile_payloads(settings, portfolio, core, xyz)
