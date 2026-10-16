import math
import pandas as pd
from final_read_services import zscore_from_bars, add_accounting
from pairs_desk.metrics import spread_stats


def test_z_uses_streamlit_rolling_arithmetic_ratio():
    bars = [{'close': 1.0 + 0.002 * i + 0.03 * math.sin(i / 7)} for i in range(250)]
    expected = float(spread_stats(pd.DataFrame({'c': [b['close'] for b in bars]}))['z'].iloc[-1])
    assert zscore_from_bars(bars) == round(expected, 3)


def test_z_remains_consistent_when_chart_has_more_bars():
    bars = [{'close': 1.0 + 0.0004 * i + 0.02 * math.sin(i / 6)} for i in range(600)]
    assert zscore_from_bars(bars) == zscore_from_bars(bars[-250:])


def test_missing_funding_never_becomes_net_total():
    pair = {'long':'ETH', 'short':'BTC', 'pnl':20, 'funding':None}
    out = add_accounting(pair, {'szi':'1'}, {'szi':'-1'}, [], False)
    assert out['total_pnl'] is None
