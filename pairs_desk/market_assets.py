"""Available Hyperliquid perp assets and stable local identities."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable

from .market_catalog import MarketCatalog, instrument_id

SECTOR_SYMBOLS: dict[str, frozenset[str]] = {
    'Energía': frozenset({'CL','WTI','BRENT','XLE','XOM','CVX','COP','OXY','SLB','EOG','USO','UNG'}),
    'Memoria': frozenset({'MU','SNDK','WDC','STX','KIOXIA','RAM','NAND'}),
    'IA y cómputo': frozenset({'NVDA','AMD','ARM','SMCI','PLTR','AI','AVGO','TSM','MRVL','C3AI'}),
    'Semiconductores': frozenset({'INTC','QCOM','ASML','AMAT','LRCX','KLAC','ON','TXN'}),
    'Privacidad': frozenset({'ZEC','XMR','DASH','SCRT','ROSE','DUSK','MINA','AZERO'}),
    'Finanzas y DeFi': frozenset({'AAVE','UNI','MKR','LDO','LINK','SNX','SUSHI','CRV','JUP','DYDX','GMX'}),
    'Índices': frozenset({'SPY500','XYZ100','QQQ','DXY','NASDAQ','SPX','GOLD','SILVER'}),
}


def sector_for_symbol(symbol: str) -> str:
    clean = str(symbol).strip().upper()
    for sector, symbols in SECTOR_SYMBOLS.items():
        if clean in symbols:
            return sector
    return 'Sin clasificar'


@dataclass(frozen=True)
class AvailableAsset:
    instrument_id: str
    symbol: str
    venue: str
    sector: str = 'Sin clasificar'
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
                asset = AvailableAsset(ident, symbol, venue, sector_for_symbol(symbol))
                assets[ident] = asset
                if self.catalog is not None:
                    self.catalog.upsert_instrument(symbol, venue, active=True, metadata={'source': 'hyperliquid_meta'})
        return tuple(sorted(assets.values(), key=lambda asset: (asset.venue, asset.symbol)))
