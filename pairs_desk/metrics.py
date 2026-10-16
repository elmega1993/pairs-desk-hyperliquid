from __future__ import annotations

import math
import time
from typing import Any, Iterable

import pandas as pd

CANDLE_SAMPLES = 4998


def candle_window(minutes: int, n: int = CANDLE_SAMPLES, now_ms: int | None = None) -> tuple[int, int]:
    step = minutes * 60_000
    now_ms = int(time.time() * 1000) if now_ms is None else int(now_ms)
    end = (now_ms // step + 1) * step
    return end - n * step, end


def position_map(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in state.get('assetPositions', []) or []:
        p = (item or {}).get('position') or {}
        coin = p.get('coin')
        if isinstance(coin, str) and float(p.get('szi') or 0):
            out[coin] = p
    return out


def _fill_order_key(fill: dict[str, Any]) -> tuple[int, str]:
    """Stable ordering for fills, including ties on the same millisecond."""
    return int(fill.get('time', 0) or 0), str(fill.get('tid') or fill.get('hash') or '')


def _fill_signed_qty(fill: dict[str, Any]) -> float:
    size = float(fill.get('sz') or 0)
    side = str(fill.get('side') or '').upper()
    if side == 'B':
        return size
    if side == 'A':
        return -size
    return 0.0


def since_open(fills: Iterable[dict[str, Any]], coin: str, szi: float) -> tuple[int | None, float, float, bool]:
    """Opening time and economics of the current uninterrupted position.

    The opening timestamp is located first; fees/PnL are then summed for *all*
    fills at or after that timestamp. This makes same-millisecond chunked orders
    order-independent.
    """
    relevant = sorted((f for f in fills if f.get('coin') == coin), key=_fill_order_key)
    if not relevant:
        return None, 0.0, 0.0, False

    direction = 1 if szi > 0 else -1 if szi < 0 else 0
    candidate_times: list[int] = []
    for f in relevant:
        try:
            start_pos = float(f.get('startPosition') or 0)
        except (TypeError, ValueError):
            continue
        signed = _fill_signed_qty(f)
        if start_pos == 0 and signed * direction > 0:
            candidate_times.append(int(f.get('time', 0) or 0))
        elif direction and start_pos * direction < 0 and (start_pos + signed) * direction > 0:
            candidate_times.append(int(f.get('time', 0) or 0))

    if not candidate_times:
        # History no longer reaches the flat/reversal boundary. Do not attribute
        # an arbitrary tail of older operations to the current position.
        return None, 0.0, 0.0, False

    opened_at = max(candidate_times)
    cycle = [f for f in relevant if int(f.get('time', 0) or 0) >= opened_at]
    fee = sum(float(f.get('fee') or 0) for f in cycle)
    realized = sum(float(f.get('closedPnl') or 0) for f in cycle)
    return opened_at, fee, realized, True


def latest_closed_cycle(
    fills: Iterable[dict[str, Any]], coin: str, current_szi: float = 0.0, epsilon: float = 1e-9
) -> dict[str, Any] | None:
    """Return the latest verified flat-to-flat cycle for a currently flat asset."""
    if abs(float(current_szi or 0)) > epsilon:
        return None
    relevant = sorted((f for f in fills if f.get('coin') == coin), key=_fill_order_key)
    if not relevant:
        return None

    newest = relevant[-1]
    try:
        final_position = float(newest.get('startPosition') or 0) + _fill_signed_qty(newest)
    except (TypeError, ValueError):
        return None
    if abs(final_position) > epsilon:
        return None

    # Find the most recent opening boundary before the final flat fill.
    opening_idx = None
    for idx in range(len(relevant) - 1, -1, -1):
        f = relevant[idx]
        try:
            start_pos = float(f.get('startPosition') or 0)
        except (TypeError, ValueError):
            continue
        if abs(start_pos) <= epsilon and abs(_fill_signed_qty(f)) > epsilon:
            opening_idx = idx
            break
    if opening_idx is None:
        return None

    cycle = relevant[opening_idx:]
    # The selected cycle must actually finish flat.
    last = cycle[-1]
    final_position = float(last.get('startPosition') or 0) + _fill_signed_qty(last)
    if abs(final_position) > epsilon:
        return None
    fee = sum(float(f.get('fee') or 0) for f in cycle)
    realized = sum(float(f.get('closedPnl') or 0) for f in cycle)
    return {
        'opened_at': int(cycle[0].get('time', 0)) or None,
        'closed_at': int(last.get('time', 0)) or None,
        'realized': realized,
        'fees': fee,
        'complete': True,
    }


def _cycle_fills(fills: Iterable[dict[str, Any]], coin: str, current_szi: float) -> tuple[list[dict[str, Any]], bool, int | None]:
    opened_at, _, _, complete = since_open(fills, coin, current_szi)
    relevant = sorted(
        (f for f in fills if f.get('coin') == coin and int(f.get('time', 0) or 0) > 0),
        key=_fill_order_key,
    )
    if opened_at is not None:
        relevant = [f for f in relevant if int(f.get('time', 0)) >= opened_at]
    return relevant, complete, opened_at


def pair_trade_events(
    pair: dict[str, Any], fills: list[dict[str, Any]], group_ms: int = 120_000, opening_grace_ms: int = 300_000
) -> list[dict[str, Any]]:
    """Build ADD/close annotations without mistaking staggered opening fills for adds."""
    long_sym, short_sym = pair['long'], pair['short']
    long_szi = float((pair.get('long_position') or {}).get('szi') or 0)
    short_szi = float((pair.get('short_position') or {}).get('szi') or 0)
    long_fills, long_complete, long_open = _cycle_fills(fills, long_sym, long_szi)
    short_fills, short_complete, short_open = _cycle_fills(fills, short_sym, short_szi)

    combined = []
    for coin, current_szi, coin_fills, opened_at in (
        (long_sym, long_szi, long_fills, long_open),
        (short_sym, short_szi, short_fills, short_open),
    ):
        direction = 1 if current_szi >= 0 else -1
        for fill in coin_fills:
            fill_time = int(fill.get('time', 0) or 0)
            # Ignore every chunk belonging to the opening burst of *that leg*.
            if opened_at is not None and fill_time <= opened_at + opening_grace_ms:
                continue
            signed = _fill_signed_qty(fill)
            if not signed:
                continue
            try:
                px = float(fill.get('px') or 0)
                size = abs(float(fill.get('sz') or 0))
            except (TypeError, ValueError):
                continue
            if size <= 0:
                continue
            effect = 'add' if signed * direction > 0 else 'close' if signed * direction < 0 else 'other'
            if effect == 'other':
                continue
            combined.append({
                'coin': coin,
                'time': fill_time,
                'effect': effect,
                'notional': abs(px * size) if px > 0 else 0.0,
                'realized': float(fill.get('closedPnl') or 0),
                'fee': float(fill.get('fee') or 0),
            })

    if not combined:
        return []
    combined.sort(key=lambda row: row['time'])
    groups: list[list[dict[str, Any]]] = [[combined[0]]]
    for row in combined[1:]:
        if row['time'] - groups[-1][-1]['time'] <= group_ms:
            groups[-1].append(row)
        else:
            groups.append([row])

    events = []
    for group in groups:
        ts = max(item['time'] for item in group)
        add_notional = sum(item['notional'] for item in group if item['effect'] == 'add')
        close_notional = sum(item['notional'] for item in group if item['effect'] == 'close')
        realized = sum(item['realized'] for item in group if item['effect'] == 'close')
        if add_notional <= 0 and close_notional <= 0:
            continue
        if add_notional > close_notional:
            kind, amount = 'add', add_notional
            label = f"ADD +${amount:,.0f}"
            detail = f"Agregado aprox. {amount:,.2f} USD de nocional"
        else:
            kind, amount = 'close', close_notional
            pnl_word = 'Ganancia' if realized >= 0 else 'Pérdida'
            sign = '+' if realized >= 0 else '−'
            label = f"CIERRE {sign}${abs(realized):,.0f}"
            detail = f"Cierre aprox. {amount:,.2f} USD · {pnl_word} {realized:,.2f} USD"
        events.append({
            'time': ts, 'kind': kind, 'amount': amount, 'realized': realized,
            'label': label, 'detail': detail,
            'partial_history': not (long_complete and short_complete),
        })
    return events

def closed_pair_trade_events(
    long_sym: str, short_sym: str, fills: list[dict[str, Any]], opened_at: int, closed_at: int,
    group_ms: int = 120_000, opening_grace_ms: int = 300_000,
) -> list[dict[str, Any]]:
    """Build ADD/close annotations for a verified archived flat-to-flat pair cycle."""
    opened_at, closed_at = int(opened_at or 0), int(closed_at or 0)
    if not opened_at or not closed_at or closed_at < opened_at:
        return []
    combined: list[dict[str, Any]] = []
    for coin in (long_sym, short_sym):
        coin_fills = sorted(
            (f for f in fills if f.get('coin') == coin and opened_at <= int(f.get('time', 0) or 0) <= closed_at),
            key=_fill_order_key,
        )
        if not coin_fills:
            continue
        # Direction comes from the first opening fill of the archived cycle.
        direction = 0
        for f in coin_fills:
            try:
                start_pos = float(f.get('startPosition') or 0)
            except (TypeError, ValueError):
                continue
            signed = _fill_signed_qty(f)
            if abs(start_pos) <= 1e-9 and signed:
                direction = 1 if signed > 0 else -1
                break
        if not direction:
            continue
        for fill in coin_fills:
            fill_time = int(fill.get('time', 0) or 0)
            if fill_time <= opened_at + opening_grace_ms:
                continue
            signed = _fill_signed_qty(fill)
            if not signed:
                continue
            try:
                px = float(fill.get('px') or 0)
                size = abs(float(fill.get('sz') or 0))
            except (TypeError, ValueError):
                continue
            if size <= 0:
                continue
            effect = 'add' if signed * direction > 0 else 'close' if signed * direction < 0 else 'other'
            if effect == 'other':
                continue
            combined.append({
                'coin': coin, 'time': fill_time, 'effect': effect,
                'notional': abs(px * size) if px > 0 else 0.0,
                'realized': float(fill.get('closedPnl') or 0), 'fee': float(fill.get('fee') or 0),
            })
    if not combined:
        return []
    combined.sort(key=lambda row: row['time'])
    groups: list[list[dict[str, Any]]] = [[combined[0]]]
    for row in combined[1:]:
        if row['time'] - groups[-1][-1]['time'] <= group_ms:
            groups[-1].append(row)
        else:
            groups.append([row])
    events = []
    for group in groups:
        ts = max(item['time'] for item in group)
        add_notional = sum(item['notional'] for item in group if item['effect'] == 'add')
        close_notional = sum(item['notional'] for item in group if item['effect'] == 'close')
        realized = sum(item['realized'] for item in group if item['effect'] == 'close')
        if add_notional <= 0 and close_notional <= 0:
            continue
        if add_notional > close_notional:
            kind, amount = 'add', add_notional
            label = f"ADD +${amount:,.0f}"
            detail = f"Agregado aprox. {amount:,.2f} USD de nocional"
        else:
            kind, amount = 'close', close_notional
            pnl_word = 'Ganancia' if realized >= 0 else 'Pérdida'
            sign = '+' if realized >= 0 else '−'
            label = f"CIERRE {sign}${abs(realized):,.0f}"
            detail = f"Cierre aprox. {amount:,.2f} USD · {pnl_word} {realized:,.2f} USD"
        events.append({'time': ts, 'kind': kind, 'amount': amount, 'realized': realized, 'label': label, 'detail': detail, 'partial_history': False})
    return events


def archived_pair_entry_ratio(
    long_sym: str, short_sym: str, fills: list[dict[str, Any]], opened_at: int, opening_grace_ms: int = 300_000
) -> float | None:
    """Approximate original pair entry ratio from the opening burst VWAP of both legs."""
    opened_at = int(opened_at or 0)
    if not opened_at:
        return None
    def opening_vwap(coin: str) -> float | None:
        selected = []
        for f in fills:
            if f.get('coin') != coin:
                continue
            t = int(f.get('time', 0) or 0)
            if not (opened_at - opening_grace_ms <= t <= opened_at + opening_grace_ms):
                continue
            try:
                px, sz = float(f.get('px') or 0), abs(float(f.get('sz') or 0))
            except (TypeError, ValueError):
                continue
            if px > 0 and sz > 0:
                selected.append((px, sz))
        total = sum(sz for _, sz in selected)
        return None if total <= 0 else sum(px * sz for px, sz in selected) / total
    lp, sp = opening_vwap(long_sym), opening_vwap(short_sym)
    if not lp or not sp:
        return None
    return lp / sp


def funding_cashflow(position: dict[str, Any]) -> float | None:
    raw = (position.get('cumFunding') or {}).get('sinceOpen')
    return None if raw is None else -float(raw)



def funding_ledger_cashflow(rows: Iterable[dict[str, Any]], coins: Iterable[str]) -> float:
    wanted = set(coins)
    total = 0.0
    for row in rows:
        delta = (row or {}).get('delta') or {}
        if delta.get('type') != 'funding' or delta.get('coin') not in wanted:
            continue
        try:
            total += float(delta.get('usdc') or 0)
        except (TypeError, ValueError):
            continue
    return total

def mark_from_position(position: dict[str, Any]) -> float | None:
    size = abs(float(position.get('szi') or 0))
    value = abs(float(position.get('positionValue') or 0))
    if size <= 0 or value <= 0:
        return None
    return value / size


def liquidation_distance(position: dict[str, Any], mark: float | None) -> float | None:
    if not mark or mark <= 0 or not position.get('liquidationPx'):
        return None
    liq = float(position['liquidationPx'])
    return abs(mark - liq) / mark * 100


def ratio_bars(left: pd.DataFrame, right: pd.DataFrame, interval: str) -> pd.DataFrame:
    freq = {'5m': '5min', '15m': '15min', '1h': '1h', '4h': '4h', '1d': '1D', '1w': 'W-MON'}[interval]
    l = left.copy().set_index('time').sort_index()
    r = right.copy().set_index('time').sort_index()
    idx = l.index.union(r.index).sort_values()
    def fill_gaps(df: pd.DataFrame) -> pd.DataFrame:
        out = df.reindex(idx)
        missing = out['close'].isna()
        out['close'] = out['close'].ffill()
        for c in ('open', 'high', 'low'):
            out[c] = out[c].where(~missing, out['close'])
        return out

    l = fill_gaps(l)
    r = fill_gaps(r)
    frame = l.join(r, lsuffix='_long', rsuffix='_short', how='inner').reset_index()
    required = ['open_long','high_long','low_long','close_long','open_short','high_short','low_short','close_short']
    frame = frame[(frame[required] > 0).all(axis=1)].copy()
    if frame.empty:
        return pd.DataFrame()
    # Synthetic quotient candle. High/low use the most favorable/adverse combination
    # of the two source candles; intrabar simultaneity is not guaranteed.
    frame['o'] = frame.open_long / frame.open_short
    frame['h'] = frame.high_long / frame.low_short
    frame['l'] = frame.low_long / frame.high_short
    frame['c'] = frame.close_long / frame.close_short
    frame.index = pd.to_datetime(frame.time, unit='ms', utc=True)
    return frame.resample(freq, closed='left', label='left').agg({
        'o': 'first', 'h': 'max', 'l': 'min', 'c': 'last'
    }).dropna()


def spread_stats(frame: pd.DataFrame, window: int = 90) -> pd.DataFrame:
    out = frame.copy()
    out['spread'] = (out['c'] / out['c'].iloc[0] - 1) * 100
    roll = out['spread'].rolling(window=min(window, max(10, len(out)//3)), min_periods=10)
    out['mean'] = roll.mean()
    out['std'] = roll.std(ddof=0)
    out['z'] = (out['spread'] - out['mean']) / out['std'].replace(0, float('nan'))
    return out


def half_life(series: pd.Series) -> float | None:
    from .health import assess_series
    return assess_series(series.dropna().tolist())['half_life_bars']


def pct(value: float | None, base: float | None) -> float | None:
    return None if value is None or not base or base <= 0 else value / base * 100


def pnl_base(pair: dict[str, Any], mode: str) -> float | None:
    if mode == 'Una pata':
        return pair['notional'] / 2 if pair['notional'] > 0 else None
    if mode == 'Margen':
        return pair['margin'] if pair['margin'] > 0 else None
    return pair['notional'] if pair['notional'] > 0 else None



DEFAULT_MANAGEMENT_RULES = {
    'tp1_ratio_pct': 10.0,
    'tp2_ratio_pct': 20.0,
    'tp3_ratio_pct': 20.0,
    'tp3_abs_z': 0.5,
    'add1_ratio_pct': -8.0,
    'add1_z': -2.0,
    'add2_ratio_pct': -15.0,
    'add2_z': -2.5,
}


def management_signals(
    ratio_change: float | None,
    z_score: float | None,
    executed_tp: Iterable[int] | None = None,
    executed_add: Iterable[int] | None = None,
    rules: dict[str, float] | None = None,
) -> dict[str, str | int | None]:
    """Return the next pending TP/add state for a long-ratio mean-reversion trade."""
    cfg = dict(DEFAULT_MANAGEMENT_RULES)
    if isinstance(rules, dict):
        for key in cfg:
            try:
                if key in rules:
                    cfg[key] = float(rules[key])
            except (TypeError, ValueError):
                pass
    done_tp = {int(x) for x in (executed_tp or [])}
    done_add = {int(x) for x in (executed_add or [])}
    if ratio_change is None:
        return {
            'tp': 'N/D', 'tp_detail': 'Sin cambio de ratio disponible', 'tp_level': None,
            'add': 'N/D', 'add_detail': 'Sin cambio de ratio disponible', 'add_level': None,
        }

    rc = float(ratio_change)
    z = None if z_score is None or not math.isfinite(float(z_score)) else float(z_score)

    # Always show the next *pending* TP, never a rung already executed.
    if 1 not in done_tp:
        if rc >= cfg['tp1_ratio_pct']:
            tp, tp_level = 'TP1 · 25%', 1
            tp_detail = f"Ratio ≥ +{cfg['tp1_ratio_pct']:.1f}% desde la referencia"
        else:
            tp, tp_level = 'HOLD', None
            tp_detail = f"Próximo TP1 en +{max(0.0, cfg['tp1_ratio_pct'] - rc):.1f} pp de ratio"
    elif 2 not in done_tp:
        if rc >= cfg['tp2_ratio_pct']:
            tp, tp_level = 'TP2 · 25%', 2
            tp_detail = f"TP1 ejecutado · ratio ≥ +{cfg['tp2_ratio_pct']:.1f}%"
        else:
            tp, tp_level = 'HOLD', None
            tp_detail = f"TP1 ✓ · próximo TP2 en +{max(0.0, cfg['tp2_ratio_pct'] - rc):.1f} pp"
    elif 3 not in done_tp:
        if z is None:
            tp, tp_level = 'N/D · sin Z', None
            tp_detail = 'TP1/TP2 ✓ · TP3 requiere Z-score disponible'
        elif rc >= cfg['tp3_ratio_pct'] and abs(z) <= cfg['tp3_abs_z']:
            tp, tp_level = 'TP3 · 35%', 3
            tp_detail = f"TP1/TP2 ✓ · |Z| ≤ {cfg['tp3_abs_z']:.2f} · dejar 15% runner"
        else:
            tp, tp_level = 'HOLD', None
            tp_detail = f"TP1/TP2 ✓ · esperar convergencia |Z| ≤ {cfg['tp3_abs_z']:.2f}"
    else:
        tp, tp_level = 'TP COMPLETO', None
        tp_detail = 'TP1/TP2/TP3 ✓ · sólo queda el runner'

    # Unknown Z is explicitly unknown, not WATCH. Adds never fire on ratio alone.
    if 1 in done_add and 2 in done_add:
        add, add_level = 'NO ADD · LÍMITE', None
        add_detail = 'ADD1/ADD2 ✓ · no hay tercer agregado'
    elif z is None:
        add, add_level = 'N/D · sin Z', None
        add_detail = 'No se puede evaluar ADD sin Z-score'
    elif 1 not in done_add:
        if rc <= cfg['add1_ratio_pct'] and z <= cfg['add1_z']:
            add, add_level = 'REVISAR ADD 1', 1
            add_detail = f"Ratio ≤ {cfg['add1_ratio_pct']:.1f}% y Z ≤ {cfg['add1_z']:.2f} · +30% sólo si tesis intacta"
        elif rc <= cfg['add1_ratio_pct'] + 3 or z <= cfg['add1_z'] + 0.5:
            add, add_level = 'WATCH', None
            add_detail = 'Se acerca a zona ADD1; todavía no cumple ambos filtros'
        else:
            add, add_level = 'NO ADD', None
            add_detail = 'Fuera de zona de agregado'
    else:
        if rc <= cfg['add2_ratio_pct'] and z <= cfg['add2_z']:
            add, add_level = 'REVISAR ADD 2', 2
            add_detail = f"ADD1 ✓ · ratio ≤ {cfg['add2_ratio_pct']:.1f}% y Z ≤ {cfg['add2_z']:.2f} · +20% con estabilización"
        elif rc <= cfg['add2_ratio_pct'] + 3 or z <= cfg['add2_z'] + 0.5:
            add, add_level = 'WATCH ADD 2', None
            add_detail = 'ADD1 ✓ · se acerca a zona ADD2'
        else:
            add, add_level = 'NO ADD', None
            add_detail = 'ADD1 ✓ · fuera de zona ADD2'

    return {
        'tp': tp, 'tp_detail': tp_detail, 'tp_level': tp_level,
        'add': add, 'add_detail': add_detail, 'add_level': add_level,
    }

def enrich_pair(pair: dict[str, Any], fills: list[dict[str, Any]]) -> dict[str, Any]:
    long_p, short_p = pair['long_position'], pair['short_position']
    long_mark, short_mark = pair['long_mark'], pair['short_mark']
    lf = funding_cashflow(long_p)
    sf = funding_cashflow(short_p)
    funding = None if lf is None or sf is None else lf + sf
    lo, lfee, lreal, lcomplete = since_open(fills, pair['long'], float(long_p['szi']))
    so, sfee, sreal, scomplete = since_open(fills, pair['short'], float(short_p['szi']))
    realized = lreal + sreal
    fees = lfee + sfee
    unrealized = float(long_p.get('unrealizedPnl') or 0) + float(short_p.get('unrealizedPnl') or 0)
    total = None if funding is None else unrealized + funding + realized - fees
    long_usd = abs(float(long_p.get('positionValue') or 0))
    short_usd = abs(float(short_p.get('positionValue') or 0))
    notional = long_usd + short_usd
    margin = float(long_p.get('marginUsed') or 0) + float(short_p.get('marginUsed') or 0)
    imbalance = pct(long_usd - short_usd, notional) or 0.0
    ld = liquidation_distance(long_p, long_mark)
    sd = liquidation_distance(short_p, short_mark)
    dists = [x for x in (ld, sd) if x is not None]
    pair.update({
        'funding': funding, 'unrealized': unrealized, 'realized': realized, 'fees': fees, 'total_pnl': total,
        'history_complete': lcomplete and scomplete, 'opened_long': lo, 'opened_short': so,
        'long_usd': long_usd, 'short_usd': short_usd, 'notional': notional, 'margin': margin,
        'imbalance': imbalance, 'liq_distance': min(dists) if dists else None,
        'long_liq_distance': ld, 'short_liq_distance': sd,
    })
    return pair
