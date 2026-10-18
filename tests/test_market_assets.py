from pairs_desk.market_assets import AssetUniverseService, sector_for_symbol
from pairs_desk.market_catalog import MarketCatalog


def test_lists_core_and_xyz_assets_with_distinct_ids(tmp_path):
    requests = []

    def fetch(request):
        requests.append(request)
        if request.get('dex') == 'xyz':
            return {'universe': [{'name': 'xyz:SPY500'}, {'name': 'xyz:MU'}, {'name': 'xyz:OLD', 'isDelisted': True}]}
        return {'universe': [{'name': 'HYPE'}, {'name': 'AERO'}]}

    catalog = MarketCatalog(tmp_path / 'market.sqlite3')
    assets = AssetUniverseService(fetch, catalog).list_assets()

    assert [asset.instrument_id for asset in assets] == ['core:AERO', 'core:HYPE', 'xyz:MU', 'xyz:SPY500']
    assert requests == [{'type': 'meta'}, {'type': 'meta', 'dex': 'xyz'}]
    assert catalog.get_instrument('xyz:SPY500')['metadata']['source'] == 'hyperliquid_meta'
    assert catalog.get_instrument('xyz:SPY500')['symbol'] == 'SPY500'
    assert assets[2].sector == 'Memoria'


def test_sector_classifier_keeps_unknown_assets_explicit():
    assert sector_for_symbol('MU') == 'Memoria'
    assert sector_for_symbol('NVDA') == 'IA y cómputo'
    assert sector_for_symbol('ZEC') == 'Privacidad'
    assert sector_for_symbol('UNKNOWN_ASSET') == 'Sin clasificar'
