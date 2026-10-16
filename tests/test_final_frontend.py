from final_read_services import add_accounting, zscore_from_bars

def test_zscore_requires_history():
    assert zscore_from_bars([{'close':1.0}]) is None

def test_zscore_matches_streamlit_arithmetic_spread():
    values=[{'close':1.01**i} for i in range(25)]
    assert 1 < zscore_from_bars(values) < 2

def test_accounting_missing_fills_displays_unknown_not_zero():
    pair={'long':'ETH','short':'BTC','pnl':10,'funding':-1}
    lp={'szi':'2'};sp={'szi':'-2'}
    out=add_accounting(pair,lp,sp,[],False)
    assert out['realized'] is None
    assert out['fees'] is None
    assert out['total_pnl'] is None
    assert out['history_complete'] is False
    assert 'long_position' not in out
