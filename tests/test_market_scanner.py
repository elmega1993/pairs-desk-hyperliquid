from pairs_desk.market_catalog import MarketCatalog
from pairs_desk.market_quality import normalize_candles
from pairs_desk.market_scanner import MarketScanner
from pairs_desk.market_storage import MarketDataStore


def candles(instrument_id, closes):
    return normalize_candles(
        [
            {'t': 0, 'o': str(closes[0]), 'h': str(closes[0]), 'l': str(closes[0]), 'c': str(closes[0]), 'v': '1'},
            {'t': 86_400_000, 'o': str(closes[1]), 'h': str(closes[1]), 'l': str(closes[1]), 'c': str(closes[1]), 'v': '1'},
        ],
        instrument_id,
        instrument_id.split(':', 1)[0],
        '1h',
    )


def setup(tmp_path):
    catalog = MarketCatalog(tmp_path / 'market.sqlite3')
    catalog.upsert_instrument('ETH', 'core')
    catalog.upsert_instrument('BTC', 'core')
    catalog.upsert_instrument('SOL', 'core')
    catalog.upsert_pair('core:ETH', 'core:BTC', label='ETH / BTC')
    catalog.upsert_pair('core:SOL', 'core:BTC', label='SOL / BTC')
    store = MarketDataStore(tmp_path / 'market-data')
    store.merge_candles(candles('core:ETH', [10, 30]))
    store.merge_candles(candles('core:BTC', [2, 10]))
    return catalog, store


def test_scanner_returns_ratio_and_24h_change_from_local_data(tmp_path):
    catalog, store = setup(tmp_path)

    result = MarketScanner(catalog, store, now_ms=86_400_000).scan(interval='1h')

    candidate = next(item for item in result.candidates if item.pair_id == 'core:ETH__core:BTC')
    assert candidate.status == 'complete'
    assert candidate.ratio == 3.0
    assert candidate.ratio_change_pct == -40.0
    assert candidate.matched_rows == 2


def test_scanner_filters_and_marks_missing_market_data(tmp_path):
    catalog, store = setup(tmp_path)

    result = MarketScanner(catalog, store, now_ms=86_400_000).scan(search='SOL', limit=1)

    assert len(result.candidates) == 1
    assert result.candidates[0].pair_id == 'core:SOL__core:BTC'
    assert result.candidates[0].status == 'no_data'
    assert result.candidates[0].ratio is None
