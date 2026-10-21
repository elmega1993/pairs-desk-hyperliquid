"""Funding estimado de un par con las tasas vigentes de Hyperliquid.

Solo lectura y sin red: recibe la respuesta de ``metaAndAssetCtxs`` y los nominales
de cada pata. El resultado es un *estimado* con la tasa actual (cambia cada hora);
no reemplaza al funding realizado del ledger.

Convención de Hyperliquid: ``funding`` es la tasa por hora y, si es positiva, los
largos pagan a los cortos. Flujo por hora de un par = -tasa_long*nominal_long +
tasa_short*nominal_short (positivo = el par cobra).
"""
from __future__ import annotations

import math
from typing import Any

HOURS_PER_DAY = 24
DAYS_PER_YEAR = 365
BASIS = 'estimado_tasa_actual'


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def funding_rates(payload: Any) -> dict[str, float]:
    """Convierte ``[meta, assetCtxs]`` en ``{coin: tasa_por_hora}``.

    Ignora activos delistados, entradas sin tasa finita y respuestas con otro formato.
    """
    if not isinstance(payload, (list, tuple)) or len(payload) < 2:
        return {}
    meta, contexts = payload[0], payload[1]
    universe = meta.get('universe') if isinstance(meta, dict) else None
    if not isinstance(universe, list) or not isinstance(contexts, list):
        return {}
    rates: dict[str, float] = {}
    for asset, ctx in zip(universe, contexts):
        if not isinstance(asset, dict) or not isinstance(ctx, dict) or asset.get('isDelisted'):
            continue
        name, rate = asset.get('name'), _finite(ctx.get('funding'))
        if isinstance(name, str) and name and rate is not None:
            rates[name] = rate
    return rates


def _lookup(rates: dict[str, float], coin: str) -> float | None:
    if coin in rates:
        return rates[coin]
    bare = coin.split(':', 1)[1] if ':' in coin else coin
    return rates.get(bare)


def _unavailable(reason: str) -> dict[str, Any]:
    return {'funding_per_day_usd': None, 'funding_apr_pct': None, 'funding_long_rate_pct_h': None,
            'funding_short_rate_pct_h': None, 'funding_basis': BASIS, 'funding_reason': reason}


def pair_funding_carry(long_coin: str, short_coin: str, long_usd: Any, short_usd: Any,
                       rates: dict[str, float] | None) -> dict[str, Any]:
    """Funding estimado por día (USD) y anualizado (% del nominal medio) para un par."""
    if not rates:
        return _unavailable('Tasas de funding no disponibles')
    long_notional, short_notional = _finite(long_usd), _finite(short_usd)
    if long_notional is None or short_notional is None or long_notional < 0 or short_notional < 0:
        return _unavailable('Nominales del par no verificables')
    long_rate, short_rate = _lookup(rates, long_coin), _lookup(rates, short_coin)
    missing = [c for c, r in ((long_coin, long_rate), (short_coin, short_rate)) if r is None]
    if missing:
        return _unavailable('Sin tasa de funding para ' + ', '.join(missing))
    per_hour = -long_rate * long_notional + short_rate * short_notional
    per_day = per_hour * HOURS_PER_DAY
    average_notional = (long_notional + short_notional) / 2
    apr = per_day * DAYS_PER_YEAR / average_notional * 100 if average_notional > 0 else None
    return {'funding_per_day_usd': per_day, 'funding_apr_pct': apr,
            'funding_long_rate_pct_h': long_rate * 100, 'funding_short_rate_pct_h': short_rate * 100,
            'funding_basis': BASIS, 'funding_reason': 'Estimado con la tasa vigente; cambia cada hora'}
