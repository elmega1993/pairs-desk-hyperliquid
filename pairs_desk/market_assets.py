"""Available Hyperliquid perp assets and stable local identities."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from .market_catalog import MarketCatalog, instrument_id


@dataclass(frozen=True)
class AvailableAsset:
    instrument_id: str
    symbol: str
    venue: str
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AssetUniverseService:
    def __init__(self, fetch: Callable[[dict[str, Any]], Any], catalog: MarketCatalog | None = None):
        self.fetch = fetch
        self.catalog = catalog

    def list_assets(self, venues: tuple[str, ...] = ('core', 'xyz')) -> tuple[AvailableAsset, ...]:
        assets: dict[str, AvailableAsset] = {}
        for venue in venues:
            request: dict[str, Any] = {'type': 'meta'}
            if venue != 'core':
                request['dex'] = venue
            try:
                payload = self.fetch(request)
            except Exception:
                continue
            for entry in (payload or {}).get('universe', []) if isinstance(payload, dict) else []:
                if not isinstance(entry, dict) or entry.get('isDelisted'):
                    continue
                symbol = str(entry.get('name') or entry.get('coin') or '').strip().upper()
                prefix = f'{venue}:'
                if symbol.startswith(prefix.upper()):
                    symbol = symbol[len(prefix):].strip()
                if not symbol:
                    continue
                ident = instrument_id(symbol, venue)
                asset = AvailableAsset(ident, symbol, venue)
                assets[ident] = asset
                if self.catalog is not None:
                    self.catalog.upsert_instrument(symbol, venue, active=True, metadata={'source': 'hyperliquid_meta'})
        return tuple(sorted(assets.values(), key=lambda asset: (asset.venue, asset.symbol)))
