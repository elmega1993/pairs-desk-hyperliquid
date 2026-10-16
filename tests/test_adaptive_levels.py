import numpy as np
import pandas as pd
from pairs_desk.adaptive_levels import calculate, adaptive_signals

def test_missing_history_never_fabricates_levels():
    result = calculate(pd.DataFrame({'c':[1.0]*20}),1.0)
    assert result['status']=='unavailable'
    assert adaptive_signals(1,1,result)['add_level'] is None

def test_adaptive_levels_order_and_no_auto_execution():
    rng=np.random.default_rng(7)
    returns=rng.normal(0,0.008,250)
    prices=np.exp(np.cumsum(returns))
    result=calculate(pd.DataFrame({'c':prices}),float(prices[-1]))
    if result['status']=='ok':
        v=result['levels']
        assert v['add2']<v['add1']<prices[-1]<v['tp1']<v['tp2']
        assert adaptive_signals(float(prices[-1]),float(prices[-1]),result)['add_level'] is None
