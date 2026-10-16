"""Public mark-price snapshots with short caching; no account or order access."""
import math
import time
from threading import Lock
from concurrent.futures import ThreadPoolExecutor

_lock = Lock()
_cache = {}

def snapshot(coins, fetch):
    dexes = sorted({coin.split(':', 1)[0] if ':' in coin else '' for coin in coins})
    def read(dex):
        with _lock:
            cached = _cache.get(dex)
            if cached and time.monotonic() - cached[0] < 4:
                return cached[1]
        try:
            raw = fetch({'type': 'metaAndAssetCtxs', 'dex': dex})
            universe, contexts = raw[0]['universe'], raw[1]
            if len(universe) != len(contexts):
                raise ValueError('Incomplete price response')
            prices = {}
            for meta, ctx in zip(universe, contexts):
                coin = meta['name']
                if dex and not coin.startswith(dex + ':'):
                    coin = dex + ':' + coin
                price = float(ctx['markPx'])
                if math.isfinite(price) and price > 0:
                    prices[coin] = price
            result = {'prices': prices, 'fetched_at_ms': int(time.time() * 1000)}
            with _lock:
                _cache[dex] = (time.monotonic(), result)
            return result
        except Exception as exc:
            return {'prices': {}, 'error': f'{dex or "core"}: {type(exc).__name__}'}
    prices, errors = {}, []
    with ThreadPoolExecutor(max_workers=min(4, len(dexes) or 1)) as pool:
        for result in pool.map(read, dexes):
            if result.get('error'):
                errors.append(result['error'])
            for coin, price in result['prices'].items():
                if coin in coins:
                    prices[coin] = {'price': price, 'time': result['fetched_at_ms']}
    missing = sorted(coins - prices.keys())
    if missing:
        errors.append('Sin cotización: ' + ', '.join(missing))
    return {'prices': prices, 'errors': errors}
