import math

import pandas as pd

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
