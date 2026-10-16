import math
import numpy as np
from pairs_desk.health import assess_series, pair_health
from pairs_desk.alerts import Watcher, observations


def test_stationary_ar_has_half_life():
    rng=np.random.default_rng(4);x=[0.]
    for _ in range(249):x.append(.7*x[-1]+rng.normal())
    result=assess_series(x)
    assert result['adf_pvalue']<.05
    assert 0<result['half_life_bars']<10


def test_random_walk_does_not_get_half_life_from_phi_alone():
    x=np.random.default_rng(42).normal(size=250).cumsum()
    result=assess_series(x)
    assert result['status']=='inconclusive'
    assert result['half_life_bars'] is None


def test_short_constant_and_invalid_series_unknown():
    for x in ([1]*100,list(range(10)),[math.nan]*100):
        assert assess_series(x)['status']=='unavailable'


def test_health_excludes_open_candle_and_rejects_gaps():
    day=86400000;bars=[dict(timestamp=i*day,close=math.exp(math.sin(i))) for i in range(70)]
    result=pair_health(bars,69*day+1)
    assert result['samples']==69 and result['last_closed_ms']==68*day
    bars[50]['close']=0
    assert pair_health(bars,80*day)['status']=='unavailable'


def test_alert_cooldown_hysteresis_and_restart(tmp_path):
    sent=[];w=Watcher(lambda:None,tmp_path,lambda *args:sent.append(args) or True)
    w.condition('a','neutral',True,False,'warning',1000)
    w.condition('a','neutral',True,False,'warning',1050)
    w.condition('a','neutral',False,False,'warning',1100)
    w.condition('a','neutral',True,False,'warning',1200)
    assert len(sent)==1
    w.condition('a','neutral',False,True,'warning',1300)
    w.condition('a','neutral',True,False,'warning',2000)
    assert len(sent)==2
    w.persist();assert len(Watcher(lambda:None,tmp_path).events)==2


def test_disabled_watcher_does_not_send_and_failures_are_logged(tmp_path):
    def failed():raise ConnectionError()
    sent=[];w=Watcher(failed,tmp_path,lambda *args:sent.append(args) or False)
    w.tick(1000);assert not sent
    w.enabled=True;w.tick(1000);assert not sent
    w.tick(1060);assert len(sent)==1 and not w.events[0]['desktop']
    w.tick(1120);assert len(sent)==1


def test_risk_thresholds_and_missing_legs():
    cfg={'pairs':[{'long':'A','short':'B'}]}
    pos={'A':{'szi':'1','positionValue':'110','liquidationPx':'105'},'B':{'szi':'-1','positionValue':'90','liquidationPx':'150'}}
    obs={x[0]:x for x in observations(cfg,pos,{})}
    assert obs['A|B:neutral'][1] and obs['A|B:liq'][1]
    assert observations(cfg,{}, {})[0][1]


def test_alert_route_requires_csrf_and_local_origin(monkeypatch,tmp_path):
    from fastapi.testclient import TestClient
    import read_only_server as server
    import secure_trade_routes as trade
    w=Watcher(lambda:None,tmp_path)
    monkeypatch.setattr(server,'ALERTS',w)
    monkeypatch.setattr(w,'start',lambda:None)
    client=TestClient(server.app)
    assert client.post('/api/alerts',json={'csrf':'bad','enabled':True}).status_code==403
    r=client.post('/api/alerts',headers={'host':'127.0.0.1:8510','origin':'http://127.0.0.1:8510'},json={'csrf':trade._TOK,'enabled':True})
    assert r.status_code==200 and w.enabled
    assert client.get('/api/alerts').json()['enabled']


def test_restart_preserves_cooldown(tmp_path):
    sent=[];w=Watcher(lambda:None,tmp_path,lambda *a:sent.append(a) or True)
    w.condition('a','risk',True,False,'risk',1000);w.persist()
    fresh=Watcher(lambda:None,tmp_path,lambda *a:sent.append(a) or True)
    fresh.condition('a','risk',True,False,'risk',1100)
    assert len(sent)==1


def test_malformed_account_does_not_report_missing_legs(monkeypatch):
    import read_only_server as server
    monkeypatch.setattr(server,'load_settings',lambda path:({'address':'0x'+'a'*40,'pairs':[]},None))
    monkeypatch.setattr(server,'hl',lambda payload:{'error':'unavailable'})
    import pytest
    with pytest.raises(ValueError):server.alert_poll()


def test_notification_test_is_local_and_csrf_protected(monkeypatch,tmp_path):
    from fastapi.testclient import TestClient
    import read_only_server as server
    import secure_trade_routes as trade
    sent=[];w=Watcher(lambda:None,tmp_path,lambda *a:sent.append(a) or True)
    monkeypatch.setattr(server,'ALERTS',w);client=TestClient(server.app)
    assert client.post('/api/alerts/test',json={'csrf':'wrong'}).status_code==403
    assert not sent
    response=client.post('/api/alerts/test',headers={'host':'127.0.0.1:8510','origin':'http://127.0.0.1:8510'},json={'csrf':trade._TOK})
    assert response.json()['delivered'] and len(sent)==1
