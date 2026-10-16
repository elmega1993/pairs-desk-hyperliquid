import pytest

from pairs_desk.market_catalog import MarketCatalog, instrument_id, pair_id


def test_instrument_ids_keep_core_and_xyz_separate():
    assert instrument_id('eth', 'core') == 'core:ETH'
    assert instrument_id('ETH', 'xyz') == 'xyz:ETH'
    assert instrument_id('ETH', 'core') != instrument_id('ETH', 'xyz')
    assert pair_id('CORE:ETH', 'core:BTC') == 'core:ETH__core:BTC'


def test_catalog_upsert_preserves_identity_and_lists_normalized_rows(tmp_path):
    catalog = MarketCatalog(tmp_path / 'market.sqlite3')

    first = catalog.upsert_instrument('eth', 'core', asset_type='perp', metadata={'source': 'test'})
    second = catalog.upsert_instrument('ETH', 'CORE', asset_type='perp', metadata={'source': 'updated'})

    assert first['instrument_id'] == 'core:ETH'
    assert second['instrument_id'] == first['instrument_id']
    assert second['metadata']['source'] == 'updated'
    assert catalog.get_instrument('core:ETH')['symbol'] == 'ETH'
    assert [row['instrument_id'] for row in catalog.list_instruments()] == ['core:ETH']


def test_catalog_rejects_pair_with_identical_legs(tmp_path):
    catalog = MarketCatalog(tmp_path / 'market.sqlite3')
    catalog.upsert_instrument('ETH', 'core')

    with pytest.raises(ValueError, match='distintas'):
        catalog.upsert_pair('core:ETH', 'core:ETH')


def test_catalog_upserts_pair_and_returns_it(tmp_path):
    catalog = MarketCatalog(tmp_path / 'market.sqlite3')
    catalog.upsert_instrument('ETH', 'core')
    catalog.upsert_instrument('BTC', 'core')

    row = catalog.upsert_pair('core:ETH', 'core:BTC', label='ETH/BTC')

    assert row['pair_id'] == 'core:ETH__core:BTC'
    assert catalog.get_pair(row['pair_id']) == row


def test_catalog_normalizes_pair_references(tmp_path):
    catalog = MarketCatalog(tmp_path / 'market.sqlite3')
    catalog.upsert_instrument('ETH', 'core')
    catalog.upsert_instrument('BTC', 'core')

    row = catalog.upsert_pair('CORE:ETH', 'CORE:BTC')

    assert row['long_instrument_id'] == 'core:ETH'
    assert row['short_instrument_id'] == 'core:BTC'
