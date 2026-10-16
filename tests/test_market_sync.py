from pairs_desk.market_catalog import MarketCatalog
from pairs_desk.market_ingestion import MarketIngestor
from pairs_desk.market_storage import MarketDataStore
from pairs_desk.market_sync import MarketSyncService


ROWS = [
    {'t': 1000, 'o': '10', 'h': '12', 'l': '9', 'c': '11', 'v': '3'},
    {'t': 2000, 'o': '11', 'h': '13', 'l': '10', 'c': '12', 'v': '4'},
]


def setup(tmp_path, fetch, clock):
    catalog = MarketCatalog(tmp_path / 'market.sqlite3')
    catalog.upsert_instrument('ETH', 'core')
    catalog.upsert_instrument('BTC', 'core')
    ingestor = MarketIngestor(catalog, MarketDataStore(tmp_path / 'market-data'), fetch)
    return MarketSyncService(ingestor, clock=clock)


def test_first_incremental_sync_uses_initial_window_and_measures_duration(tmp_path):
    calls = []

    def fetch(**payload):
        calls.append(payload)
        return ROWS

    service = setup(tmp_path, fetch, iter([10.0, 10.25]).__next__)

    metrics = service.sync_incremental('core:ETH', '1m', end_ms=2000, initial_start_ms=1000)

    assert metrics.status == 'complete'
    assert metrics.effective_start_ms == 1000
    assert metrics.effective_end_ms == 2000
    assert metrics.rows_new == 2
    assert metrics.duration_ms == 250
    assert calls[0]['req']['startTime'] == 1000


def test_next_sync_reuses_checkpoint_with_safe_overlap(tmp_path):
    calls = []

    def fetch(**payload):
        calls.append(payload)
        return ROWS

    service = setup(tmp_path, fetch, iter([1.0, 1.1, 2.0, 2.1]).__next__)
    service.sync_incremental('core:ETH', '1m', end_ms=2000, initial_start_ms=1000)
    second = service.sync_incremental('core:ETH', '1m', end_ms=3000, initial_start_ms=1000)

    assert second.effective_start_ms == 2000
    assert second.effective_end_ms == 3000
    assert calls[1]['req']['startTime'] == 2000


def test_up_to_date_window_does_not_call_fetch(tmp_path):
    calls = []

    def fetch(**payload):
        calls.append(payload)
        return ROWS

    service = setup(tmp_path, fetch, iter([1.0, 1.1]).__next__)
    service.sync_incremental('core:ETH', '1m', end_ms=2000, initial_start_ms=1000)
    skipped = service.sync_incremental('core:ETH', '1m', end_ms=2000, initial_start_ms=1000)

    assert skipped.status == 'up_to_date'
    assert skipped.skipped is True
    assert skipped.rows_new == 0
    assert len(calls) == 1


def test_sync_many_isolates_instrument_errors_and_aggregates_metrics(tmp_path):
    def fetch(**payload):
        if payload['req']['coin'] == 'BTC':
            raise RuntimeError('BTC unavailable')
        return ROWS

    service = setup(tmp_path, fetch, iter([1.0, 1.1, 2.0, 2.2]).__next__)

    batch = service.sync_many(
        ('core:ETH', 'core:BTC'),
        '1m',
        end_ms=2000,
        initial_start_ms=1000,
    )

    assert [result.status for result in batch.results] == ['complete', 'error']
    assert batch.rows_new == 2
    assert batch.errors == 1
    assert batch.duration_ms == 300
