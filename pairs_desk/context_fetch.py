"""Small, testable helpers for historical public market-data extraction."""
from __future__ import annotations

import re


def api_coin(value: str) -> str:
    raw = str(value).strip()
    venue, separator, symbol = raw.partition(':')
    if separator:
        return f'{venue.casefold()}:{symbol.upper()}'
    return raw.upper()


def safe_cache_name(value: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]', '_', str(value))
