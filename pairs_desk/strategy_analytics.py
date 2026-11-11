"""Pure helpers for the fixed-start strategy account view."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from math import isfinite
from zoneinfo import ZoneInfo


def _time_ms(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number * 1000 if number < 100_000_000_000 else number


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def strategy_history(rows, start_ms):
    """Filter, order, deduplicate and rebase PNL rows from ``start_ms``."""
    start = _time_ms(start_ms)
    if start is None:
        return []
    clean = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        time = _time_ms(row.get('time', row.get('timestamp')))
        pnl = _number(row.get('pnl'))
        if time is None or pnl is None or time < start:
            continue
        clean[time] = {'time': time, 'pnl': pnl}
    ordered = [clean[time] for time in sorted(clean)]
    if not ordered:
        return []
    base = ordered[0]['pnl']
    return [{'time': row['time'], 'pnl': row['pnl'] - base} for row in ordered]


def aligned_portfolio_history(windows, local_rows=None):
    """Align rebased portfolio windows at shared timestamps before combining."""
    points = {}
    for key in ('perpAllTime', 'perpMonth', 'perpWeek', 'perpDay'):
        window = {}
        for time, value in (windows.get(key) or {}).get('pnlHistory', []):
            timestamp, pnl = _time_ms(time), _number(value)
            if timestamp is not None and pnl is not None:
                window[timestamp] = pnl
        if not window:
            continue
        if points:
            shared = sorted(points.keys() & window.keys())
            if not shared:
                continue  # No verifiable accounting baseline for this window.
            offsets = [points[t] - window[t] for t in shared]
            offset = offsets[-1]
            if any(abs(value - offset) > 0.01 for value in offsets):
                continue
        else:
            if key != 'perpAllTime':
                continue
            offset = 0
        points.update({t: value + offset for t, value in window.items()})
    if points:
        last = max(points)
        for row in local_rows or []:
            timestamp, pnl = _time_ms(row.get('time')), _number(row.get('pnl'))
            if timestamp is not None and pnl is not None and timestamp <= last:
                points.setdefault(timestamp, pnl)
    return [{'time': t, 'pnl': points[t]} for t in sorted(points)]


def portfolio_strategy_daily(windows, start_ms, history=None):
    points = {r['time']: r['pnl'] for r in (
        aligned_portfolio_history(windows) if history is None else history)}
    zone = ZoneInfo('America/Argentina/Buenos_Aires')
    start = datetime.fromtimestamp(start_ms / 1000, zone).date()
    groups = {}
    for timestamp in sorted(points):
        if timestamp >= start_ms:
            date = datetime.fromtimestamp(timestamp / 1000, zone).date()
            groups[date] = points[timestamp]
    if not groups:
        return []
    base = points[min(t for t in points if t >= start_ms)]
    result = []
    day = start
    previous = base
    while day <= max(groups):
        value = groups.get(day)
        pnl = value - previous if value is not None and previous is not None else None
        result.append({'date': day.isoformat(), 'pnl': pnl,
                       'cumulative': value - base if value is not None else None,
                       'partial': day == start})
        previous = value
        day += timedelta(days=1)
    return result


def daily_strategy_pnl(rows, timezone_name):
    """Aggregate a rebased strategy series into local calendar days."""
    try:
        zone = ZoneInfo(timezone_name)
    except (TypeError, ValueError):
        zone = timezone.utc
    groups = {}
    for row in strategy_history(rows, 0):
        date = datetime.fromtimestamp(row['time'] / 1000, zone).date().isoformat()
        groups.setdefault(date, []).append(row)
    result = []
    previous = None
    for date, group in groups.items():
        last = group[-1]
        baseline = group[0]['pnl'] if previous is None else previous
        result.append({'date': date, 'pnl': last['pnl'] - baseline,
                       'cumulative': last['pnl'], 'partial': previous is None})
        previous = last['pnl']
    return result


def strategy_capital(account_value_history, start_ms):
    """Return the first valid account value at or after strategy start."""
    start = _time_ms(start_ms)
    if start is None:
        return None
    candidates = []
    for row in account_value_history or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        time = _time_ms(row[0])
        value = _number(row[1])
        if time is not None and value is not None and time >= start:
            candidates.append((time, value))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None


def strategy_capital_with_flows(account_value_history, nonfunding_rows, start_ms, account):
    """Reconstruct committed capital using the opening value plus later deposits."""
    start = _time_ms(start_ms)
    candidates = []
    for row in account_value_history or []:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        time = _time_ms(row[0]); value = _number(row[1])
        if time is not None and value is not None and time >= start:
            candidates.append((time, value))
    if not candidates:
        return None
    base_time, capital = min(candidates, key=lambda item: item[0])
    account_id = str(account or '').lower()
    for row in nonfunding_rows or []:
        if not isinstance(row, dict) or (_time_ms(row.get('time')) or -1) <= base_time:
            continue
        delta = row.get('delta') if isinstance(row.get('delta'), dict) else {}
        if delta.get('type') != 'spotTransfer' or str(delta.get('destination') or '').lower() != account_id:
            continue
        value = _number(delta.get('usdcValue'))
        if value is not None and value > 0:
            capital += value
    return capital


def strategy_roi(net_pnl, initial_capital):
    pnl = _number(net_pnl)
    capital = _number(initial_capital)
    if pnl is None or capital is None or capital <= 0:
        return None
    return pnl / capital * 100


def _sum_since(rows, start_ms, field):
    total = 0.0
    for row in rows or []:
        if not isinstance(row, dict) or (_time_ms(row.get('time')) or -1) < start_ms:
            continue
        value = _number(row.get(field))
        if value is None:
            return None
        total += value
    return total


def _funding_sum_since(rows, start_ms):
    total = 0.0
    for row in rows or []:
        if not isinstance(row, dict) or (_time_ms(row.get('time')) or -1) < start_ms:
            continue
        delta = row.get('delta') if isinstance(row.get('delta'), dict) else {}
        value = _number(delta.get('usdc'))
        if value is None:
            return None
        total += value
    return total



def _cost_details(fills, funding_rows, start_ms, fees, funding):
    """Signed flows from the same verified ledger coverage as the totals."""
    assets = {}

    def asset(coin):
        return assets.setdefault(coin or 'Sin activo', {'coin': coin or 'Sin activo',
                                                       'fees': 0.0, 'funding': 0.0})

    paid = received = None
    if funding is not None:
        paid = received = 0.0
        for row in funding_rows or []:
            if not isinstance(row, dict) or (_time_ms(row.get('time')) or -1) < start_ms:
                continue
            delta = row.get('delta') or {}
            value = _number(delta.get('usdc'))
            if value is None:
                continue
            paid += min(value, 0)
            received += max(value, 0)
            asset(delta.get('coin'))['funding'] += value
    if fees is not None and funding is not None:
        for row in fills or []:
            if (_time_ms(row.get('time')) or -1) >= start_ms:
                asset(row.get('coin'))['fees'] += _number(row.get('fee'))
        for row in assets.values():
            row['impact'] = row['funding'] - row['fees']
        breakdown = sorted(assets.values(), key=lambda row: row['impact'])
    else:
        breakdown = None
    return {'funding_paid': paid, 'funding_received': received, 'assets': breakdown}


def strategy_snapshot(history, account_value_history, fills, funding_rows, start_ms,
                      *, fills_complete, funding_complete, unrealized=None,
                      initial_capital_override=None, nonfunding_rows=None, account=None,
                      official_all_time_pnl=None, official_start_pnl=None):
    """Build the read-only strategy accounting block from already loaded data."""
    series = strategy_history(history, start_ms)
    # Portfolio PNL already includes funding and fees. Never deduct them twice.
    net = series[-1]['pnl'] if series else None
    initial = (_number(initial_capital_override) if _number(initial_capital_override) is not None
               else strategy_capital_with_flows(account_value_history, nonfunding_rows, start_ms, account))
    perp_fills = [r for r in fills or [] if isinstance(r, dict) and r.get('dir') not in ('Buy', 'Sell', 'Spot Dust Conversion')]
    realized = _sum_since(perp_fills, start_ms, 'closedPnl') if fills_complete else None
    usdc_fees = all(r.get('feeToken', 'USDC') == 'USDC' for r in perp_fills if (_time_ms(r.get('time')) or -1) >= start_ms)
    fees = _sum_since(perp_fills, start_ms, 'fee') if fills_complete and usdc_fees else None
    funding = _funding_sum_since(funding_rows, _time_ms(start_ms)) if funding_complete else None
    gross = net - funding + fees if None not in (net, funding, fees) else None
    return {
        'start_ms': _time_ms(start_ms),
        'initial_capital': initial,
        'history': series,
        'daily': daily_strategy_pnl(series, 'America/Argentina/Buenos_Aires'),
        'gross_pnl': gross,
        'realized': realized,
        'unrealized': _number(unrealized),
        'funding': funding,
        'fees': fees,
        'cost_details': _cost_details(perp_fills, funding_rows, _time_ms(start_ms), fees, funding),
        'net_pnl': net,
        'roi_pct': strategy_roi(net, initial),
        'official_all_time_pnl': _number(official_all_time_pnl),
        'official_start_pnl': _number(official_start_pnl),
    }
