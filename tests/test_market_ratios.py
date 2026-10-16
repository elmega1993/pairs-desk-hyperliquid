import math

import pandas as pd
import pytest

from pairs_desk.market_ratios import build_pair_ratios


def candles(instrument_id, closes, timestamps=(1000, 2000, 3000)):
    return pd.DataFrame({
        'instrument_id': instrument_id,
        'venue': 'core',
        'interval': '1m',
        'timestamp_ms': list(timestamps),
        'open': closes,
        'high': closes,
        'low': closes,
        'close': closes,
        'volume': [1.0] * len(closes),
        'source': 'test',
    })


def test_builds_price_and_log_ratios_on_exact_timestamp_intersection():
    result = build_pair_ratios(
        candles('core:ETH', [10.0, 20.0, 30.0]),
        candles('core:BTC', [2.0, 4.0, 10.0]),
        pair_id='core:ETH__core:BTC',
    )

    assert result.status == 'complete'
    assert result.matched_rows == 3
    assert result.missing_long == ()
    assert result.missing_short == ()
    assert list(result.frame['timestamp_ms']) == [1000, 2000, 3000]
    assert list(result.frame['price_ratio']) == [5.0, 5.0, 3.0]
    assert math.isclose(result.frame.loc[0, 'log_ratio'], math.log(5.0))


def test_partial_alignment_reports_unmatched_timestamps_without_interpolation():
    result = build_pair_ratios(
        candles('core:ETH', [10.0, 20.0], timestamps=(1000, 2000)),
        candles('core:BTC', [2.0, 4.0], timestamps=(2000, 3000)),
        pair_id='core:ETH__core:BTC',
    )

    assert result.status == 'partial'
    assert result.matched_rows == 1
    assert result.missing_long == (3000,)
    assert result.missing_short == (1000,)
    assert list(result.frame['timestamp_ms']) == [2000]


def test_empty_intersection_is_distinguished_from_partial_data():
    result = build_pair_ratios(
        candles('core:ETH', [10.0], timestamps=(1000,)),
        candles('core:BTC', [2.0], timestamps=(2000,)),
        pair_id='core:ETH__core:BTC',
    )

    assert result.status == 'empty'
    assert result.matched_rows == 0
    assert result.frame.empty


@pytest.mark.parametrize('bad_close', [0.0, -1.0, float('nan'), float('inf')])
def test_rejects_non_positive_or_non_finite_closes(bad_close):
    long_frame = candles('core:ETH', [10.0, 20.0, 30.0])
    long_frame.loc[1, 'close'] = bad_close

    result = build_pair_ratios(
        long_frame,
        candles('core:BTC', [2.0, 4.0, 10.0]),
        pair_id='core:ETH__core:BTC',
    )

    assert result.status == 'error'
    assert result.frame.empty
    assert result.error


def test_rejects_duplicate_timestamps_before_many_to_many_merge():
    long_frame = candles('core:ETH', [10.0, 20.0, 30.0])
    long_frame.loc[2, 'timestamp_ms'] = 2000

    result = build_pair_ratios(
        long_frame,
        candles('core:BTC', [2.0, 4.0, 10.0]),
        pair_id='core:ETH__core:BTC',
    )

    assert result.status == 'error'
    assert result.frame.empty
    assert 'duplicados' in result.error


def test_rejects_incompatible_instrument_and_interval_series():
    long_frame = candles('core:ETH', [10.0, 20.0, 30.0])
    short_frame = candles('xyz:BTC', [2.0, 4.0, 10.0])
    short_frame['interval'] = '5m'

    result = build_pair_ratios(long_frame, short_frame, pair_id='pair')

    assert result.status == 'error'
    assert result.frame.empty
    assert 'incompatibles' in result.error
