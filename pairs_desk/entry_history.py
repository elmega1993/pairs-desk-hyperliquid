"""Verified entry-ratio evolution reconstructed from Hyperliquid fills, read-only."""
from __future__ import annotations
import math
from .metrics import since_open, _fill_signed_qty, _fill_order_key


def entry_history(long: str, short: str, long_pos: dict, short_pos: dict, fills: list[dict], complete: bool) -> dict:
    unavailable = {'available': False, 'reason': 'Historial de fills incompleto o no verificable', 'steps': []}
    if not complete:
        return unavailable
    legs = [(long, float(long_pos.get('szi') or 0)), (short, float(short_pos.get('szi') or 0))]
    if legs[0][1] <= 0 or legs[1][1] >= 0:
        return unavailable
    opening = {}
    for coin, qty in legs:
        t, _, _, ok = since_open(fills, coin, qty)
        if not ok or not t:
            return unavailable
        opening[coin] = t
    timeline = []
    for coin, qty in legs:
        for f in fills:
            if f.get('coin') != coin or int(f.get('time') or 0) < opening[coin]:
                continue
            try:
                signed = _fill_signed_qty(f)
                px = float(f['px'])
                ts = int(f['time'])
                if not (signed and px > 0 and math.isfinite(px)):
                    return unavailable
            except (ValueError, TypeError, KeyError):
                return unavailable
            timeline.append((ts, str(f.get('tid') or f.get('hash') or ''), coin, signed, px))
    timeline.sort()
    if not timeline:
        return unavailable
    # Each leg uses quantity-weighted average entry, with reductions preserving the
    # remaining average. A flip or missing opening fill invalidates the reconstruction.
    state = {long: [0., 0.], short: [0., 0.]}
    steps = []
    for ts, _, coin, signed, px in timeline:
        qty, avg = state[coin]
        next_qty = qty + signed
        direction = 1 if coin == long else -1
        if next_qty * direction < -1e-8:
            return unavailable
        if signed * direction > 0:
            next_avg = (abs(qty)*avg + abs(signed)*px)/abs(next_qty) if next_qty else 0
        else:
            if abs(signed) > abs(qty) + 1e-8:
                return unavailable
            next_avg = avg if abs(next_qty)>1e-8 else 0.
        state[coin] = [next_qty, next_avg]
        a, b = state[long], state[short]
        if a[0]>0 and b[0]<0 and b[1]>0:
            ratio = a[1]/b[1]
            if steps and steps[-1]['time'] == ts:
                steps[-1]['ratio'] = ratio
            elif not steps or abs(steps[-1]['ratio']-ratio)>1e-12:
                steps.append({'time': ts, 'ratio': ratio})
    for coin, expected in legs:
        reconstructed = state[coin][0]
        if abs(reconstructed-expected) > max(1e-6, abs(expected)*1e-5):
            return unavailable
    if not steps:
        return unavailable
    return {'available': True, 'initial_ratio': steps[0]['ratio'], 'current_ratio': steps[-1]['ratio'], 'steps': steps}
