from pairs_desk.market_catalog import MarketCatalog
from pairs_desk.market_pair_analysis import PairAnalysisService
from pairs_desk.market_storage import MarketDataStore


ROWS = [
    {'t': 1_000, 'o': '10', 'h': '10', 'l': '10', 'c': '10', 'v': '1'},
    {'t': 2_000, 'o': '20', 'h': '20', 'l': '20', 'c': '20', 'v': '1'},
]


def test_analyze_fetches_selected_assets_and_builds_ratio(tmp_path):
    catalog = MarketCatalog(tmp_path / 'market.sqlite3')
    catalog.upsert_instrument('HYPE', 'core')
    catalog.upsert_instrument('ZEC', 'core')
    calls = []

    def fetch(**payload):
        calls.append(payload)
        return ROWS

    service = PairAnalysisService(catalog, MarketDataStore(tmp_path / 'market-data'), fetch, now_ms=lambda: 2_000)

    result = service.analyze('core:HYPE', 'core:ZEC', interval='1h', lookback_days=1)

    assert result.status == 'complete'
    assert result.pair_id == 'core:HYPE__core:ZEC'
    assert result.matched_rows == 2
    assert result.rows[-1]['price_ratio'] == 1.0
    assert [call['req']['coin'] for call in calls] == ['HYPE', 'ZEC']
