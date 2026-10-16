from __future__ import annotations

import json
import time
from typing import Any, Callable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
try:
    import streamlit as st
except ModuleNotFoundError:  # lightweight fallback for pure unit tests
    class _Cache:
        def __call__(self, *args, **kwargs):
            def deco(fn):
                fn.clear = lambda: None
                return fn
            return deco
    class _StreamlitShim:
        cache_resource = _Cache()
        cache_data = _Cache()
    st = _StreamlitShim()

API = 'https://api.hyperliquid.xyz/info'
MAX_RECENT_FILLS = 10_000
FILLS_PAGE_SIZE = 2_000


@st.cache_resource
def session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=2, connect=2, read=2, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset({'POST'}))
    s.mount('https://', HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8))
    return s


@st.cache_data(ttl=20, show_spinner=False)
def query_cached(payload_json: str) -> dict[str, Any]:
    """Cache API responses together with the instant they were actually fetched.

    Streamlit returns the cached envelope unchanged on reruns, so callers can
    distinguish a rerender from a new network read and report honest freshness.
    """
    res = session().post(API, json=json.loads(payload_json), timeout=(3, 10))
    res.raise_for_status()
    return {'data': res.json(), 'fetched_at_ms': int(time.time() * 1000)}


def query_with_meta(**payload: Any) -> tuple[Any, int]:
    env = query_cached(json.dumps(payload, sort_keys=True))
    return env['data'], int(env['fetched_at_ms'])


def query(**payload: Any) -> Any:
    data, _ = query_with_meta(**payload)
    return data


def _fill_identity(fill: dict[str, Any]) -> tuple[Any, ...]:
    return (
        fill.get('tid'), fill.get('hash'), fill.get('oid'), fill.get('time'),
        fill.get('coin'), fill.get('side'), fill.get('sz'), fill.get('px'),
    )


def user_fills_history(
    address: str,
    fetch: Callable[..., Any] = query,
    max_fills: int = MAX_RECENT_FILLS,
) -> tuple[list[dict[str, Any]], bool]:
    """Return up to Hyperliquid's 10k recent-fill retention window.

    ``complete`` means pagination reached a page shorter than 2k before the
    retention ceiling. If 10k rows are reached, older fills may exist and the
    caller must treat realized PnL/opening attribution as partial.
    """
    # Time-range endpoint pages forward, retaining the OLDEST 2000 in range.
    # Walking backwards with endTime=oldest-1 skips fills on busy accounts.
    recent = fetch(type='userFills', user=address, aggregateByTime=False)
    if not isinstance(recent, list):
        raise ValueError('userFills devolvió un formato inesperado')
    recent = [x for x in recent if isinstance(x, dict)]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    cursor = 0
    complete = False
    while len(rows) < max_fills:
        page = fetch(type='userFillsByTime', user=address, startTime=cursor, aggregateByTime=False)
        if not isinstance(page, list):
            raise ValueError('userFillsByTime devolvió un formato inesperado')
        page = [x for x in page if isinstance(x, dict)]
        if not page:
            complete = True
            break
        times = [int(x.get('time') or 0) for x in page]
        if any(t < cursor for t in times) or times != sorted(times):
            raise ValueError('userFillsByTime: página desordenada o cursor inválido')
        for item in page:
            ident = _fill_identity(item)
            if ident not in seen:
                seen.add(ident)
                rows.append(item)
                if len(rows) >= max_fills:
                    break
        if len(page) < FILLS_PAGE_SIZE:
            complete = True
            break
        # Same-millisecond groups at a page boundary are ambiguous: refusing
        # to silently skip them is safer than claiming a complete ledger.
        next_cursor = times[-1] + 1
        if next_cursor <= cursor:
            break
        if times[-1] == times[0] or (len(page) == FILLS_PAGE_SIZE and times[-1] == times[-2]):
            break
        cursor = next_cursor
    if len(rows) >= max_fills:
        complete = False
    # Cross-check recent endpoint against the range-pagination result.
    # Missing recent fills means history cannot be trusted for realized PnL.
    if not {_fill_identity(x) for x in recent}.issubset(seen):
        complete = False
    rows.sort(key=lambda x: (int(x.get('time', 0) or 0), str(x.get('tid') or x.get('hash') or '')))
    return rows[:max_fills], complete


def user_funding_history(
    address: str, start_time: int, fetch: Callable[..., Any] = query, max_rows: int = 20_000
) -> tuple[list[dict[str, Any]], bool]:
    """Paginate userFunding from start_time. Time-range endpoints return ~500 rows."""
    cursor = int(start_time)
    rows: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    complete = False
    while len(rows) < max_rows:
        page = fetch(type='userFunding', user=address, startTime=cursor)
        if not isinstance(page, list):
            raise ValueError('userFunding devolvió un formato inesperado')
        page = [x for x in page if isinstance(x, dict)]
        if not page:
            complete = True
            break
        added = 0
        max_time = cursor
        for item in page:
            delta = item.get('delta') or {}
            ident = (item.get('hash'), item.get('time'), delta.get('coin'), delta.get('usdc'))
            if ident not in seen:
                rows.append(item); seen.add(ident); added += 1
                if len(rows) >= max_rows:
                    break
            try:
                max_time = max(max_time, int(item.get('time') or 0))
            except (TypeError, ValueError):
                pass
        if len(page) < 500:
            complete = True
            break
        if max_time <= cursor or added == 0:
            break
        cursor = max_time + 1
    rows.sort(key=lambda x: int(x.get('time', 0) or 0))
    return rows[:max_rows], complete


@st.cache_data(ttl=300, show_spinner=False)
def candles(coin: str, interval: str, start: int, end: int):
    rows = query(type='candleSnapshot', req={'coin': coin, 'interval': interval, 'startTime': start, 'endTime': end})
    if not isinstance(rows, list):
        raise ValueError(f'Sin velas válidas para {coin}')
    import pandas as pd
    return pd.DataFrame([(int(x['t']), float(x['o']), float(x['h']), float(x['l']), float(x['c'])) for x in rows], columns=['time', 'open', 'high', 'low', 'close']).drop_duplicates('time').sort_values('time')
