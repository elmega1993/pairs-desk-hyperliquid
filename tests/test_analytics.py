import math
import numpy as np
from pairs_desk.analytics import ewma_vol,equilibrium,z_log,closed_daily_logs,risk_per_sigma,hit_rates,mae_mfe,pair_status
from pairs_desk.levels_v3 import calculate
from pairs_desk.portfolio_risk import concentration
from pairs_desk.review import review_closed

def test_z_exact():
    assert z_log(3,1,2)==1
    assert z_log(3,1,0) is None

def test_vol_constant_unavailable():
    assert ewma_vol(np.ones(100)) is None

def test_closed_candles_exclude_open():
    day=86400000
    bars=[{'timestamp':i*day,'close':math.exp(i*.01)} for i in range(65)]
    t,x=closed_daily_logs(bars,65*day)
    assert len(t)==65 and len(x)==65
    t,x=closed_daily_logs(bars,64*day)
    assert len(t)==64

def test_risk():
    assert risk_per_sigma(1000,.02,25)==(20,100)

def test_levels_monotonic():
    r=calculate(1,math.log(1.5),.03,14,'stationary','Rango',z=-1)
    l=r['levels']
    assert l['add2']<l['add1']<1<l['tp1']<l['tp2']

def test_add_gate():
    r=calculate(1,math.log(1.5),.03,14,'inconclusive','Tendencia',z=-1)
    assert not r['add_allowed'] and 'bloqueado' in r['level_reasons']['add1']

def test_hit_rates_insufficient():
    assert hit_rates(np.arange(60)*.01,.01,14,{'tp1':1})['tp1']['status']=='unavailable'

def test_mae_mfe():
    result=mae_mfe([0,86400000],[0,math.log(.9)],0,0,math.log(1.1),1000)
    assert round(result['mae_pct'])==-10 and round(result['mfe_pct'])==10

def test_risk_concentration():
    r=concentration([{'id':'A|B','long':'A','short':'B','long_usd':100,'short_usd':100},{'id':'A|C','long':'A','short':'C','long_usd':100,'short_usd':100}])
    assert r['assets']['A']['shared_across_pairs']

def test_review_minimum_sample():
    assert review_closed([{'total_pnl':10}])['summary']['win_rate'] is None

def test_no_trading_imports():
    from pathlib import Path
    for module in ('analytics.py','levels_v3.py','regime.py','review.py','portfolio_risk.py'):
        content=(Path(__file__).resolve().parents[1]/'pairs_desk'/module).read_text()
        assert 'import secure_trade_routes' not in content
        assert 'import trade_journal' not in content

def test_walk_forward_no_lookahead():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).resolve().parents[1]/'scripts'/'backtest_levels.py'
    spec=importlib.util.spec_from_file_location('offline_backtest',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    prices=[math.exp(.002*i+.05*math.sin(i/8)) for i in range(220)]
    a=module.walk_forward(prices)
    changed=prices.copy();changed[-1]*=100
    b=module.walk_forward(changed)
    assert a==b  # last candle outside all evaluated future windows
