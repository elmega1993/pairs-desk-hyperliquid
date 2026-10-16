import pandas as pd
import pytest

from pairs_desk.market_quality import normalize_candles, validate_candles
from pairs_desk.market_storage import MarketDataStore


def raw_rows():
    return [
        {'t': 1000, 'o': '10', 'h': '12', 'l': '9', 'c': '11', 'v': '3'},
        {'t': 2000, 'o': '11', 'h': '13', 'l': '10', 'c': '12', 'v': '4'},
    ]


def test_normalize_and_validate_valid_candles():
    frame = normalize_candles(raw_rows(), 'core:ETH', 'core', '1m')

    report = validate_candles(frame)

    assert report.valid is True
    assert list(frame['timestamp_ms']) == [1000, 2000]
    assert list(frame.columns) == [
        'instrument_id', 'venue', 'interval', 'timestamp_ms',
        'open', 'high', 'low', 'close', 'volume', 'source',
    ]


@pytest.mark.parametrize('mutate', ['non_finite', 'bad_bounds', 'duplicate', 'out_of_order'])
def test_invalid_candles_are_rejected_before_storage(tmp_path, mutate):
    frame = normalize_candles(raw_rows(), 'core:ETH', 'core', '1m')
    if mutate == 'non_finite':
        frame.loc[0, 'close'] = float('nan')
    elif mutate == 'bad_bounds':
        frame.loc[0, 'high'] = 8
    elif mutate == 'duplicate':
        frame.loc[1, 'timestamp_ms'] = 1000
    else:
        frame = frame.iloc[::-1].reset_index(drop=True)

    report = validate_candles(frame)
    store = MarketDataStore(tmp_path / 'market-data')

    assert report.valid is False
    with pytest.raises(ValueError):
        store.merge_candles(frame)
    assert not list((tmp_path / 'market-data').rglob('*.parquet'))


def test_repeated_merge_is_idempotent(tmp_path):
    frame = normalize_candles(raw_rows(), 'core:ETH', 'core', '1m')
    store = MarketDataStore(tmp_path / 'market-data')

    first = store.merge_candles(frame)
    second = store.merge_candles(frame)
    loaded = store.read_candles('core:ETH', 'core', '1m')

    assert first.rows_new == 2
    assert second.rows_new == 0
    assert len(loaded) == 2
    pd.testing.assert_frame_equal(loaded.reset_index(drop=True), frame.reset_index(drop=True))


def test_conflicting_existing_candle_is_rejected(tmp_path):
    frame = normalize_candles(raw_rows(), 'core:ETH', 'core', '1m')
    store = MarketDataStore(tmp_path / 'market-data')
    store.merge_candles(frame)
    changed = frame.copy()
    changed.loc[0, 'close'] = 11.5

    with pytest.raises(ValueError, match='conflictiva'):
        store.merge_candles(changed)
