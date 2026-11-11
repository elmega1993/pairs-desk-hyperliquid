import time
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import secure_trade_routes as routes
import pairs_desk.native_twap as native
from pairs_desk.trade_journal import connect, begin

ACCOUNT='0x'+'a'*40
HEADERS={'Origin':'http://127.0.0.1:8510'}


@pytest.fixture
def setup(tmp_path,monkeypatch):
    path=tmp_path/'orders.sqlite3'
    store=native.NativeTwapStore(path)
    monkeypatch.setattr(routes,'_native_store',lambda:store)
    monkeypatch.setattr(routes,'connect',lambda:connect(path))
    monkeypatch.setattr(routes,'_NATIVE_MONITOR',SimpleNamespace(
        ensure=lambda *args:None,
        status=lambda *args,**kw:{'as_of_ms':None,'connected':False,'error':None}))
    monkeypatch.setattr(routes,'_account_and_positions',lambda:({'pairs':[]},ACCOUNT,None))
    monkeypatch.setattr(routes,'_current_pair',lambda *args:{
        'long':'A','short':'B','long_mark':20,'short_mark':20,
        'long_position':{'szi':'10'},'short_position':{'szi':'-20'}})
    monkeypatch.setattr(routes,'_ARMED',True)
    monkeypatch.setattr(routes,'_TICKETS',{})
    app=FastAPI();app.include_router(routes.router)
    return TestClient(app,base_url='http://127.0.0.1:8510'),store,path


def preview(client,**changes):
    body=dict(csrf=routes._TOK,pair_id='A|B',operation='Reducir',fraction_pct=50,
              execution='twap',minutes=30,randomize=True)
    return client.post('/api/trade/preview',headers=HEADERS,json=body|changes)


def test_native_preview_binds_duration_and_omits_price_projection(setup):
    client,_,_=setup
    response=preview(client)
    assert response.status_code==200
    ticket=response.json()
    assert ticket['projection'] is None
    assert ticket['native_slippage_pct']==3
    assert all(leg['reduce_only'] for leg in ticket['orders'])
    saved=routes._TICKETS[ticket['ticket_id']]
    assert saved['minutes']==30 and saved['randomize'] is True
    for minutes in (1,4,10081,5.5,True):
        assert preview(client,minutes=minutes).status_code==422
    assert preview(client,operation='Cerrar',fraction_pct=25).status_code==400


def test_native_execute_dispatches_bound_ticket_once_without_market_order(setup,monkeypatch):
    client,store,_=setup
    ticket=preview(client).json()
    monkeypatch.setattr(routes,'load_agent',lambda account:'unit-test-key')
    from eth_account import Account
    monkeypatch.setattr(Account,'from_key',lambda key:SimpleNamespace(address=ACCOUNT))
    monkeypatch.setattr(routes,'verify_agent',lambda *args:None)
    monkeypatch.setattr(routes,'execute_pair',lambda *args,**kw:pytest.fail('Market execution called'))
    seen=[]
    def submit(store,account,pair,operation,orders,minutes,randomize,key):
        seen.append((minutes,randomize))
        return {'id':'native-test','status':'running','legs':[{'twap_id':10,'status':'running'},{'twap_id':20,'status':'running'}]}
    monkeypatch.setattr(native,'submit_pair',submit)
    body={'csrf':routes._TOK,'ticket_id':ticket['ticket_id'],'confirmation':'CONFIRMAR'}
    response=client.post('/api/trade/execute',headers=HEADERS,json=body)
    assert response.status_code==200 and response.json()['accepted'] is True
    assert seen==[(30,True)]
    assert client.post('/api/trade/execute',headers=HEADERS,json=body).status_code==409


def test_native_mutations_require_origin_csrf_and_confirmation(setup):
    client,_,_=setup
    assert client.post('/api/trade/preview',headers={'Origin':'https://other.invalid'},json={
        'csrf':routes._TOK,'pair_id':'A|B','operation':'Reducir','fraction_pct':25,'execution':'twap'
    }).status_code==403
    assert preview(client,csrf='wrong').status_code==403
    assert client.post('/api/trade/twaps/missing/cancel',headers=HEADERS,json={
        'csrf':routes._TOK,'confirmation':'NO'
    }).status_code==422
    assert client.post('/api/trade/twaps/missing/cancel',headers=HEADERS,json={
        'csrf':'wrong','confirmation':'CONFIRMAR'
    }).status_code==403


def test_cancel_uses_scoped_job_and_remains_available_disarmed(setup,monkeypatch):
    client,store,_=setup
    orders=[{'coin':'A','is_buy':False,'reduce_only':True,'size':1,'asset':1},
            {'coin':'B','is_buy':True,'reduce_only':True,'size':2,'asset':2}]
    job=store.reserve(ACCOUNT,'A|B','Reducir',30,False,orders)
    monkeypatch.setattr(routes,'_ARMED',False)
    monkeypatch.setattr(routes,'load_agent',lambda account:'unit-test-key')
    from eth_account import Account
    monkeypatch.setattr(Account,'from_key',lambda key:SimpleNamespace(address=ACCOUNT))
    monkeypatch.setattr(routes,'verify_agent',lambda *args:None)
    seen=[]
    monkeypatch.setattr(native,'cancel_pair',lambda s,a,j,k:seen.append((a,j)) or job)
    response=client.post('/api/trade/twaps/'+job['id']+'/cancel',headers=HEADERS,json={
        'csrf':routes._TOK,'confirmation':'CONFIRMAR'})
    assert response.status_code==200 and seen==[(ACCOUNT,job['id'])]
    monkeypatch.setattr(routes,'_account_and_positions',lambda:({},'0x'+'b'*40,None))
    assert client.get('/api/trade/twaps/'+job['id']+'/fills').status_code==404


def test_native_reservation_blocks_overlapping_immediate_order_atomically(setup):
    _,store,path=setup
    orders=[{'coin':'A','is_buy':True,'reduce_only':False,'size':1,'asset':1},
            {'coin':'B','is_buy':False,'reduce_only':False,'size':1,'asset':2}]
    store.reserve(ACCOUNT,'A|B','Aumentar',30,False,orders)
    connection=connect(path)
    try:
        with pytest.raises(RuntimeError,match='TWAP'):
            begin(connection,ACCOUNT,'A|C','Reducir',[{'coin':'A'},{'coin':'C'}])
        assert connection.execute('SELECT count(*) FROM attempts').fetchone()[0]==0
    finally:
        connection.close()


def test_twap_preview_rejects_under_minimum_per_leg_but_immediate_unchanged(setup):
    client,_,_=setup
    result=preview(client,fraction_pct=25)
    assert result.status_code==400
    assert '100 USD por pata' in result.json()['detail']
    assert not routes._TICKETS
    assert preview(client,fraction_pct=25,execution='immediate').status_code==200


@pytest.mark.parametrize('minutes',[2880,10080])
def test_preview_allows_native_multi_day_duration(setup,minutes):
    client,_,_=setup
    response=preview(client,minutes=minutes)
    assert response.status_code==200
    assert response.json()['minutes']==minutes
    assert routes._TICKETS[response.json()['ticket_id']]['minutes']==minutes


def test_native_chart_entry_curve_merges_slices_without_touching_accounting(setup):
    import read_only_server as server
    client,store,_=setup
    orders=[dict(coin='A',size=25,is_buy=True,reduce_only=False),dict(coin='B',size=25,is_buy=False,reduce_only=False)]
    job=store.reserve(ACCOUNT,'A|B','Aumentar',30,False,orders,now_ms=1500)
    store._leg(job['id'],0,1500,status='running',twap_id=10)
    store._leg(job['id'],1,1500,status='running',twap_id=20)
    store.ingest_fills(ACCOUNT,[{'twapId':10,'fill':{'coin':'A','tid':3,'sz':'25','px':'8','time':2000}},
                               {'twapId':20,'fill':{'coin':'B','tid':4,'sz':'25','px':'5','time':2001}}],3000)
    regular=[dict(coin='A',time=1000,side='B',sz='100',px='10',startPosition='0',tid=1),
             dict(coin='B',time=1001,side='A',sz='100',px='5',startPosition='0',tid=2)]
    pair=dict(id='A|B',long='A',short='B',entry_ratio=1.92,history_complete=True,fees=7,realized=9,events=[],opened_at=1001)
    result={'pairs':[pair]}
    server._attach_native_twap_charts(result,ACCOUNT,regular,{'A':{'szi':'125','entryPx':'9.6'},'B':{'szi':'-125','entryPx':'5'}})
    assert not result.get('warnings')
    assert pair['entry_history']['available'] and pair['entry_history']['current_ratio']==1.92
    assert pair['entry_ratio']==1.92 and pair['fees']==7 and pair['realized']==9
    assert len(regular)==2
