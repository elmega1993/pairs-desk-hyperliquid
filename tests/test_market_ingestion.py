from pairs_desk.market_catalog import MarketCatalog
from pairs_desk.market_ingestion import MarketIngestor
from pairs_desk.market_storage import MarketDataStore


ROWS = [
    {'t': 1000, 'o': '10', 'h': '12', 'l': '9', 'c': '11', 'v': '3'},
    {'t': 2000, 'o': '11', 'h': '13', 'l': '10', 'c': '12', 'v': '4'},
]


def setup_catalog(tmp_path):
    catalog = MarketCatalog(tmp_path / 'market.sqlite3')
    catalog.upsert_instrument('ETH', 'core')
    return catalog


def test_sync_builds_candle_snapshot_payload_and_advances_checkpoint(tmp_path):
    catalog = setup_catalog(tmp_path)
    calls = []

    def fetch(**payload):
        calls.append(payload)
        return ROWS

    ingestor = MarketIngestor(catalog, MarketDataStore(tmp_path / 'market-data'), fetch)
    result = ingestor.sync_candles('core:ETH', '1m', 1000, 2000)

    assert result.status == 'complete'
    assert result.rows_received == 2
    assert result.rows_new == 2
    assert result.covered_from_ms == 1000
    assert result.covered_to_ms == 2000
    assert calls == [{'type': 'candleSnapshot', 'req': {'coin': 'ETH', 'interval': '1m', 'startTime': 1000, 'endTime': 2000}}]
    assert ingestor.get_checkpoint('core:ETH', '1m')['covered_to_ms'] == 2000


def test_repeated_sync_is_idempotent(tmp_path):
    catalog = setup_catalog(tmp_path)
    ingestor = MarketIngestor(catalog, MarketDataStore(tmp_path / 'market-data'), lambda **payload: ROWS)

    first = ingestor.sync_candles('core:ETH', '1m', 1000, 2000)
    second = ingestor.sync_candles('core:ETH', '1m', 1000, 2000)

    assert first.rows_new == 2
    assert second.rows_new == 0
    assert second.status == 'complete'
    assert ingestor.get_checkpoint('core:ETH', '1m')['covered_to_ms'] == 2000


def test_empty_or_malformed_response_does_not_advance_checkpoint(tmp_path):
    catalog = setup_catalog(tmp_path)
    responses = iter([[], {'unexpected': True}])
    ingestor = MarketIngestor(catalog, MarketDataStore(tmp_path / 'market-data'), lambda **payload: next(responses))

    empty = ingestor.sync_candles('core:ETH', '1m', 1000, 2000)
    malformed = ingestor.sync_candles('core:ETH', '1m', 1000, 2000)

    assert empty.status == 'empty'
    assert malformed.status == 'error'
    checkpoint = ingestor.get_checkpoint('core:ETH', '1m')
    assert checkpoint['covered_to_ms'] is None
    assert checkpoint['status'] == 'error'


def test_fetch_failure_does_not_advance_checkpoint(tmp_path):
    catalog = setup_catalog(tmp_path)

    def fetch(**payload):
        raise RuntimeError('network unavailable')

    ingestor = MarketIngestor(catalog, MarketDataStore(tmp_path / 'market-data'), fetch)
    result = ingestor.sync_candles('core:ETH', '1m', 1000, 2000)

    assert result.status == 'error'
    assert 'network unavailable' in result.error
    checkpoint = ingestor.get_checkpoint('core:ETH', '1m')
    assert checkpoint['covered_to_ms'] is None
    assert checkpoint['status'] == 'error'
