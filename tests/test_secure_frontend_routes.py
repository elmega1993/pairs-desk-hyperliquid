from unittest.mock import patch
from fastapi.testclient import TestClient
import secure_trade_routes as t
from read_only_server import app
from pairs_desk.trade_journal import connect

client=TestClient(app)
ORIGIN={'origin':'http://127.0.0.1:8510','host':'127.0.0.1:8510'}
ACCOUNT='0x'+'a'*40

def test_cross_origin_rejected_without_api_side_effects():
    r=client.post('/api/trade/preview',headers={'origin':'https://evil.example','host':'127.0.0.1:8510'},json={'csrf':t._TOK,'pair_id':'ETH|BTC','operation':'Aumentar','fraction_pct':10,'slippage_pct':0.5})
    assert r.status_code==403

def test_wrong_csrf_rejected():
    r=client.post('/api/trade/preview',headers=ORIGIN,json={'csrf':'wrong','pair_id':'ETH|BTC','operation':'Aumentar','fraction_pct':10,'slippage_pct':0.5})
    assert r.status_code==403

def test_execute_without_ticket_blocked():
    r=client.post('/api/trade/execute',headers=ORIGIN,json={'csrf':t._TOK,'ticket_id':'missing','confirmation':'CONFIRMAR'})
    assert r.status_code==409

def test_preview_happens_without_real_order(tmp_path):
    lp={'szi':'2','positionValue':'20'};sp={'szi':'-3','positionValue':'30'}
    pair={'long':'ETH','short':'BTC','long_position':lp,'short_position':sp,'long_mark':10.0,'short_mark':10.0}
    db=tmp_path/'journal.sqlite3'
    with patch.object(t,'_ARMED',True),patch.object(t,'_account_and_positions',return_value=({'pairs':[]},ACCOUNT,None)),patch.object(t,'_current_pair',return_value=pair),patch.object(t,'connect',side_effect=lambda:connect(db)):
        r=client.post('/api/trade/preview',headers=ORIGIN,json={'csrf':t._TOK,'pair_id':'ETH|BTC','operation':'Reducir','fraction_pct':25,'slippage_pct':0.5})
    assert r.status_code==200,r.text
    data=r.json()
    assert len(data['orders'])==2 and all(o['reduce_only'] for o in data['orders'])
    assert data['total_usd']==12.5
    assert data['ticket_id'] in t._TICKETS
    with patch.object(t,'_ARMED',True):
        assert client.post('/api/trade/execute',headers=ORIGIN,json={'csrf':t._TOK,'ticket_id':data['ticket_id'],'confirmation':'NO'}).status_code==400


def test_live_order_preview_disabled_by_default():
    with patch.object(t,'_ARMED',False):
        r=client.post('/api/trade/preview',headers=ORIGIN,json={'csrf':t._TOK,'pair_id':'ETH|BTC','operation':'Aumentar','fraction_pct':10,'slippage_pct':0.5})
        assert r.status_code==409

def test_confirmed_ticket_is_used_once_and_journaled(tmp_path):
    import sys,types,time
    db=tmp_path/'orders.sqlite3'
    fake=types.ModuleType('eth_account')
    fake.Account=type('Account',(),{'from_key':staticmethod(lambda key:type('Wallet',(),{'address':'0x'+'b'*40})())})
    tid='test-ticket'
    order=[{'coin':'ETH','is_buy':True,'reduce_only':False,'size':1,'mark':100,'notional':100,'original_size':10},
           {'coin':'BTC','is_buy':False,'reduce_only':False,'size':1,'mark':100,'notional':100,'original_size':10}]
    payload={'account':ACCOUNT,'pair':'ETH|BTC','operation':'Aumentar','orders':order,'slippage':0.005,'created':time.monotonic()}
    with patch.object(t,'_ARMED',True),patch.object(t,'_account_and_positions',return_value=({'pairs':[]},ACCOUNT,None)),patch.object(t,'connect',side_effect=lambda:connect(db)),patch.object(t,'load_agent',return_value='test-agent-secret'),patch.object(t,'verify_agent',return_value={'role':'agent'}),patch.object(t,'execute_pair',return_value=[{'coin':'ETH','ok':True,'size':1,'filled_size':1,'oid':101},{'coin':'BTC','ok':True,'size':1,'filled_size':1,'oid':102}]) as send,patch.dict(sys.modules,{'eth_account':fake}):
        t._TICKETS[tid]=payload
        r=client.post('/api/trade/execute',headers=ORIGIN,json={'csrf':t._TOK,'ticket_id':tid,'confirmation':'CONFIRMAR'})
        assert r.status_code==200,r.text
        assert r.json()['complete'] is True
        send.assert_called_once()
        retry=client.post('/api/trade/execute',headers=ORIGIN,json={'csrf':t._TOK,'ticket_id':tid,'confirmation':'CONFIRMAR'})
        assert retry.status_code==409
        conn=connect(db)
        assert conn.execute('select status from attempts').fetchone()[0]=='complete'
        conn.close()
