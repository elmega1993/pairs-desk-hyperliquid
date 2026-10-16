import pandas as pd
from pairs_desk.metrics import ratio_bars

def test_five_minute_candles_are_supported():
    times=[1760400000000+i*300000 for i in range(4)]
    a=pd.DataFrame([{'time':t,'open':10+i,'high':11+i,'low':9+i,'close':10+i} for i,t in enumerate(times)])
    b=pd.DataFrame([{'time':t,'open':2,'high':2.1,'low':1.9,'close':2} for t in times])
    out=ratio_bars(a,b,'5m')
    assert len(out)==4
    assert abs(out.iloc[0]['c']-5)<1e-10
    assert (out['h']>=out['c']).all()
    assert (out['l']<=out['c']).all()
