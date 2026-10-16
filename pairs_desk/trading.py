"""Explicit, opt-in Hyperliquid pair execution. No keys are persisted by this app."""
from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
import math


def preview_pair(x: dict, action: str, fraction: float) -> list[dict]:
    if action not in ('Aumentar', 'Reducir', 'Cerrar'):
        raise ValueError('Acción inválida')
    if not 0 < fraction <= 1:
        raise ValueError('Porcentaje inválido')
    if action == 'Cerrar' and fraction != 1:
        raise ValueError('Cerrar requiere 100%')
    result = []
    for name, poskey, markkey, direction in (
        (x['long'], 'long_position', 'long_mark', 1),
        (x['short'], 'short_position', 'short_mark', -1),
    ):
        size = float(x[poskey].get('szi') or 0)
        mark = float(x[markkey])
        if not math.isfinite(size) or not math.isfinite(mark) or mark <= 0 or size * direction <= 0:
            raise ValueError(f'Posición o precio inválido: {name}')
        result.append({'coin': name, 'is_buy': direction > 0 if action == 'Aumentar' else direction < 0,
                       'reduce_only': action != 'Aumentar', 'size': abs(size) * fraction,
                       'mark': mark, 'notional': abs(size) * fraction * mark, 'original_size': abs(size)})
    return result


def _rounded_size(size: float, decimals: int) -> float:
    quantum = Decimal(1).scaleb(-decimals)
    return float(Decimal(str(size)).quantize(quantum, rounding=ROUND_DOWN))


def _check_response(response: dict, coin: str) -> float:
    if not isinstance(response, dict) or response.get('status') != 'ok':
        raise RuntimeError(f'{coin}: API rechazó la orden ({str(response)[:300]})')
    statuses = ((response.get('response') or {}).get('data') or {}).get('statuses') or []
    if not statuses or not isinstance(statuses[0], dict):
        raise RuntimeError(f'{coin}: sin estado confirmado, consultar Hyperliquid antes de reintentar')
    status = statuses[0]
    if 'error' in status:
        raise RuntimeError(f'{coin}: {status["error"]}')
    if 'filled' not in status:
        raise RuntimeError(f'{coin}: orden sin ejecución confirmada ({status}). Verificá antes de reintentar')
    return float(status['filled']['totalSz'])


def verify_agent(account_address: str, agent_address: str, *, base_url: str | None = None) -> dict:
    """Read-only preflight: confirm the signer is a registered agent for this master account."""
    import requests
    MAINNET_API_URL = 'https://api.hyperliquid.xyz'

    endpoint = (base_url or MAINNET_API_URL).rstrip('/') + '/info'
    def query(payload):
        response = requests.post(endpoint, json=payload, timeout=12)
        response.raise_for_status()
        return response.json()

    role = query({'type': 'userRole', 'user': agent_address})
    if not isinstance(role, dict) or role.get('role') != 'agent':
        raise ValueError(f'Agent {agent_address} no está registrado como API Wallet en Hyperliquid (rol: {role}). Autorizalo desde la cuenta principal antes de operar.')
    # An agent role is not proof of association with this specific account.
    # Check its master in userRole when provided by Hyperliquid.
    data = role.get('data')
    master = data.get('user') if isinstance(data, dict) else None
    if not isinstance(master, str) or not master:
        raise ValueError('Hyperliquid no informó la cuenta principal del Agent; trading bloqueado por seguridad.')
    if master.lower() != account_address.lower():
        raise ValueError(f'El Agent está asociado a {master}, no a la cuenta pública configurada ({account_address}).')
    return role


def _filled_details(response: dict, coin: str) -> dict:
    if not isinstance(response, dict) or response.get('status') != 'ok':
        raise RuntimeError(f'{coin}: API rechazó la orden ({str(response)[:300]})')
    statuses = ((response.get('response') or {}).get('data') or {}).get('statuses') or []
    if len(statuses) != 1 or not isinstance(statuses[0], dict):
        raise RuntimeError(f'{coin}: respuesta indeterminada. Revisá Hyperliquid antes de reintentar')
    status = statuses[0]
    if 'error' in status:
        raise RuntimeError(f'{coin}: {status["error"]}')
    if 'filled' not in status:
        raise RuntimeError(f'{coin}: estado sin fill confirmado: {status}')
    filled = status['filled']
    return {'filled_size': float(filled['totalSz']), 'oid': filled.get('oid'), 'avg_px': filled.get('avgPx')}


def scaled_second_size(first: dict, first_fill: float, second: dict, second_decimals: int) -> float:
    """Keep the original target USD hedge ratio despite a partial first-leg fill."""
    if first['size'] <= 0 or first_fill <= 0:
        return 0.0
    if first_fill > first['size'] * (1 + 1e-6):
        raise ValueError('Fill excede la cantidad solicitada; operación incierta')
    return _rounded_size(second['size'] * min(1, first_fill / first['size']), second_decimals)


def execute_pair(orders: list[dict], account_address: str, agent_key: str, slippage: float = 0.005,
                 *, journal=None, attempt_id: str | None = None) -> list[dict]:
    """Execute two legs sequentially, journal every stage, stop on any uncertainty.

    The less liquid HIP-3 leg is first when present. An IOC partial first fill
    scales the second leg rather than knowingly over-hedging. This is not atomic.
    """
    if not 0 < slippage <= 0.02:
        raise ValueError('Slippage fuera del límite (0–2%)')
    if len(orders) != 2 or orders[0]['coin'] == orders[1]['coin']:
        raise ValueError('Se requieren dos patas diferentes')
    from eth_account import Account
    from hyperliquid.exchange import Exchange
    MAINNET_API_URL = 'https://api.hyperliquid.xyz'

    def audit(event, leg, **details):
        if journal is not None and attempt_id is not None:
            from pairs_desk.trade_journal import record
            record(journal, attempt_id, event, leg, details)

    wallet = Account.from_key(agent_key)
    verify_agent(account_address, wallet.address)
    ex = Exchange(wallet, base_url=MAINNET_API_URL, account_address=account_address, perp_dexs=['', 'xyz'])
    prepared = []
    for order in orders:
        coin = order['coin']
        dex = coin.split(':', 1)[0] if ':' in coin else ''
        state = ex.info.user_state(account_address, dex)
        positions = {p['position']['coin']: float(p['position']['szi']) for p in state.get('assetPositions', [])}
        live_sz = positions.get(coin, 0.0)
        intended_sign = 1 if order['is_buy'] else -1
        original_sign = intended_sign if not order['reduce_only'] else -intended_sign
        if live_sz * original_sign <= 0:
            raise ValueError(f'{coin}: posición cambió de sentido o desapareció. Actualizá el dashboard')
        if abs(live_sz - original_sign * order['original_size']) > max(1e-8, abs(order['original_size']) * 0.001):
            raise ValueError(f'{coin}: cambió el tamaño desde la vista previa. Actualizá el dashboard')
        try:
            decimals = ex.info.asset_to_sz_decimals[ex.info.name_to_asset(coin)]
        except (KeyError, ValueError) as exc:
            raise ValueError(f'{coin}: activo no disponible en metadata de Hyperliquid') from exc
        size = _rounded_size(order['size'], decimals)
        if size <= 0 or (order['reduce_only'] and size > abs(live_sz)):
            raise ValueError(f'{coin}: tamaño no válido tras redondeo')
        prepared.append((order, size, decimals))

    prepared.sort(key=lambda item: 0 if item[0]['coin'].startswith('xyz:') else 1)
    results = []
    first_order, first_size, _ = prepared[0]
    for i, (order, requested_size, decimals) in enumerate(prepared):
        coin = order['coin']
        size = requested_size
        if i == 1:
            size = scaled_second_size(first_order | {'size': first_size}, results[0]['filled_size'],
                                      order | {'size': requested_size}, decimals)
            if size <= 0:
                results.append({'coin': coin, 'ok': False, 'size': 0, 'filled_size': 0,
                                'message': 'Cobertura demasiado pequeña tras redondeo'})
                audit('skipped', coin, size=0, error='second leg rounds to zero')
                break
        try:
            audit('before_send', coin, size=size, slippage=slippage,
                  reduce_only=order['reduce_only'], is_buy=order['is_buy'])
            response = ex.market_close(coin, sz=size, slippage=slippage) if order['reduce_only'] else ex.market_open(
                coin, is_buy=order['is_buy'], sz=size, slippage=slippage)
            details = _filled_details(response, coin)
            filled = details['filled_size']
            if filled <= 0:
                raise RuntimeError(f'{coin}: fill vacío, revisar exchange')
            complete = filled >= size - 1e-9
            audit('filled', coin, size=size, **details)
            results.append({'coin': coin, 'ok': complete, 'size': size, **details,
                            'message': 'Fill parcial' if not complete else ''})
            # First leg partial is valid for sizing the second, but a partial second is unhedged.
        except Exception as exc:
            detail = str(exc)
            audit('error_or_uncertain', coin, size=size, error=detail[:300])
            results.append({'coin': coin, 'ok': False, 'size': size, 'filled_size': 0, 'message': detail})
            break
    return results
