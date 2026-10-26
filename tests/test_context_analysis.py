import pandas as pd

from pairs_desk.context_analysis import analyze_event_context, analyze_ratio_context


def candles(values, instrument):
    return pd.DataFrame({
        'instrument_id': instrument, 'venue': 'core', 'interval': '1d',
        'timestamp_ms': [i * 86_400_000 for i in range(len(values))],
        'open': values, 'high': values, 'low': values, 'close': values,
        'volume': 1.0, 'source': 'test',
    })


def test_context_returns_mae_mfe_close_ratio_and_entry_zscore():
    long = candles([1] * 16, 'core:A')
    short = candles([1] * 16, 'core:B')
    long.loc[:, 'close'] = [1] * 10 + [1.1, 1.2, 0.9, 1.05, 1, 1]
    long.loc[:, 'open'] = long['close']

    result = analyze_ratio_context(long, short, opened_at=10 * 86_400_000, closed_at=13 * 86_400_000, entry_ratio=1.1)

    assert result['status'] == 'ok'
    assert result['mfe_pct'] == 9.09
    assert result['mae_pct'] == -18.18
    assert result['close_ratio'] == 1.05
    assert result['entry_zscore'] is not None


def test_context_marks_missing_series_unavailable():
    result = analyze_ratio_context(pd.DataFrame(), pd.DataFrame(), 0, 1, 1.0)

    assert result['status'] == 'unavailable'
    assert result['mfe_pct'] is None


def test_event_context_measures_move_and_post_event_excursion():
    long = candles([1] * 16, 'core:A')
    short = candles([1] * 16, 'core:B')
    long.loc[:, 'close'] = [1] * 10 + [1.1, 1.2, 0.9, 1.05, 1, 1]
    long.loc[:, 'open'] = long['close']

    result = analyze_event_context(long, short, event_time=11 * 86_400_000, closed_at=13 * 86_400_000, entry_ratio=1.1)

    assert result['status'] == 'ok'
    assert result['event_ratio'] == 1.2
    assert result['move_from_entry_pct'] == 9.09
    assert result['post_event_mae_pct'] == -25.0
