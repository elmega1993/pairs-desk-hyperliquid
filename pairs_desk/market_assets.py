"""Available Hyperliquid perp assets and stable local identities."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable
import math

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
    mark_px: float | None = None
    prev_day_px: float | None = None
    day_volume_usd: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AssetUniverseService:
    def __init__(self, fetch: Callable[[dict[str, Any]], Any], catalog: MarketCatalog | None = None):
        self.fetch = fetch
        self.catalog = catalog

    @staticmethod
    def _split_payload(payload: Any) -> tuple[list[Any], list[Any]]:
        """Acepta metaAndAssetCtxs ([meta, ctxs]) y, por compatibilidad, meta ({'universe': [...]})."""
        if isinstance(payload, list) and len(payload) == 2 and isinstance(payload[0], dict):
            universe = payload[0].get('universe', [])
            contexts = payload[1] if isinstance(payload[1], list) else []
        elif isinstance(payload, dict):
            universe, contexts = payload.get('universe', []), []
        else:
            return [], []
        if len(contexts) != len(universe):
            contexts = []  # sin alineación segura no se asignan precios
        return list(universe), list(contexts)

    @staticmethod
    def _positive(value: Any) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) and number > 0 else None

    def list_assets(self, venues: tuple[str, ...] = ('core', 'xyz')) -> tuple[AvailableAsset, ...]:
        assets: dict[str, AvailableAsset] = {}
        for venue in venues:
            # metaAndAssetCtxs pesa igual que meta (20) y agrega precios y volumen sin requests extra.
            request: dict[str, Any] = {'type': 'metaAndAssetCtxs'}
            if venue != 'core':
                request['dex'] = venue
            try:
                payload = self.fetch(request)
            except Exception:
                continue
            universe, contexts = self._split_payload(payload)
            for index, entry in enumerate(universe):
                if not isinstance(entry, dict) or entry.get('isDelisted'):
                    continue
                symbol = str(entry.get('name') or entry.get('coin') or '').strip().upper()
                prefix = f'{venue}:'
                if symbol.startswith(prefix.upper()):
                    symbol = symbol[len(prefix):].strip()
                if not symbol:
                    continue
                ctx = contexts[index] if index < len(contexts) and isinstance(contexts[index], dict) else {}
                mark = self._positive(ctx.get('markPx'))
                volume = self._positive(ctx.get('dayNtlVlm'))
                ident = instrument_id(symbol, venue)
                asset = AvailableAsset(
                    ident, symbol, venue, sector_for_symbol(symbol),
                    mark_px=mark, prev_day_px=self._positive(ctx.get('prevDayPx')), day_volume_usd=volume,
                )
                assets[ident] = asset
                if self.catalog is not None:
                    self.catalog.upsert_instrument(symbol, venue, active=True, metadata={'source': 'hyperliquid_meta'})
        return tuple(sorted(assets.values(), key=lambda asset: (asset.venue, asset.symbol)))
