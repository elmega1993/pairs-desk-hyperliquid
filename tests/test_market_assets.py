from pairs_desk.market_assets import AssetUniverseService, sector_for_symbol
from pairs_desk.market_catalog import MarketCatalog


def test_lists_core_and_xyz_assets_with_distinct_ids(tmp_path):
    requests = []

    def fetch(request):
        requests.append(request)
        if request.get('dex') == 'xyz':
            return [{'universe': [{'name': 'xyz:SPY500'}, {'name': 'xyz:MU'}, {'name': 'xyz:OLD', 'isDelisted': True}]},
                    [{'markPx': '500', 'prevDayPx': '490', 'dayNtlVlm': '9000'}, {'markPx': '100', 'prevDayPx': '110', 'dayNtlVlm': '5'}, {'markPx': '1'}]]
        return [{'universe': [{'name': 'HYPE'}, {'name': 'AERO'}]},
                [{'markPx': '40', 'prevDayPx': '38', 'dayNtlVlm': '1000000'}, {'markPx': '1.5', 'prevDayPx': '1.5', 'dayNtlVlm': '0'}]]

    catalog = MarketCatalog(tmp_path / 'market.sqlite3')
    assets = AssetUniverseService(fetch, catalog).list_assets()

    assert [asset.instrument_id for asset in assets] == ['core:AERO', 'core:HYPE', 'xyz:MU', 'xyz:SPY500']
    assert requests == [{'type': 'metaAndAssetCtxs'}, {'type': 'metaAndAssetCtxs', 'dex': 'xyz'}]
    assert catalog.get_instrument('xyz:SPY500')['metadata']['source'] == 'hyperliquid_meta'
    assert catalog.get_instrument('xyz:SPY500')['symbol'] == 'SPY500'
    assert assets[2].sector == 'Memoria'


def test_sector_classifier_keeps_unknown_assets_explicit():
    assert sector_for_symbol('MU') == 'Memoria'
    assert sector_for_symbol('NVDA') == 'IA y cómputo'
    assert sector_for_symbol('ZEC') == 'Privacidad'
    assert sector_for_symbol('UNKNOWN_ASSET') == 'Sin clasificar'


def test_assets_carry_price_context_aligned_with_universe_before_filtering_delisted():
    def fetch(request):
        return [{'universe': [{'name': 'OLD', 'isDelisted': True}, {'name': 'HYPE'}]},
                [{'markPx': '9', 'prevDayPx': '9', 'dayNtlVlm': '1'}, {'markPx': '40', 'prevDayPx': '38', 'dayNtlVlm': '1000'}]]

    assets = AssetUniverseService(fetch).list_assets(venues=('core',))

    assert [(a.symbol, a.mark_px, a.prev_day_px, a.day_volume_usd) for a in assets] == [('HYPE', 40.0, 38.0, 1000.0)]


def test_misaligned_contexts_never_assign_wrong_prices():
    def fetch(request):
        return [{'universe': [{'name': 'AAA'}, {'name': 'BBB'}]}, [{'markPx': '1'}]]

    assets = AssetUniverseService(fetch).list_assets(venues=('core',))

    assert all(a.mark_px is None for a in assets)


def test_legacy_meta_payload_still_lists_assets_without_prices():
    assets = AssetUniverseService(lambda request: {'universe': [{'name': 'HYPE'}]}).list_assets(venues=('core',))

    assert assets[0].mark_px is None and assets[0].symbol == 'HYPE'
