import pytest
from pairs_desk.trading import preview_pair, _rounded_size, _check_response

X = {'long':'LINK','short':'PYTH','long_position':{'szi':'10'},'short_position':{'szi':'-200'},'long_mark':20.,'short_mark':1.}

@pytest.mark.parametrize('action,expected_buy,reduce', [
    ('Aumentar',(True,False),False), ('Reducir',(False,True),True), ('Cerrar',(False,True),True)])
def test_preview(action, expected_buy, reduce):
    rows = preview_pair(X,action,1 if action=='Cerrar' else .25)
    assert tuple(r['is_buy'] for r in rows) == expected_buy
    assert all(r['reduce_only'] == reduce for r in rows)
    assert [r['size'] for r in rows] == ([10,200] if action=='Cerrar' else [2.5,50])

def test_bad_input():
    with pytest.raises(ValueError): preview_pair(X,'Cerrar',.5)
    with pytest.raises(ValueError): preview_pair(X,'Aumentar',0)

def test_round_down():
    assert _rounded_size(1.23999,2)==1.23

def test_api_check():
    _check_response({'status':'ok','response':{'data':{'statuses':[{'filled':{'totalSz':'1'}}]}}},'LINK')
    with pytest.raises(RuntimeError): _check_response({'status':'ok','response':{'data':{'statuses':[{'error':'test'}]}}},'LINK')


def test_core_and_xyz_metadata_are_loaded(monkeypatch):
    """Verify the critical DEX configuration without connecting to mainnet."""
    import sys
    import types
    from pairs_desk.trading import execute_pair
    monkeypatch.setattr('pairs_desk.trading.verify_agent', lambda account, agent: {'role':'agent'})

    seen = {}
    class FakeWallet:
        address = '0x' + '1' * 40
    class FakeAccount:
        @staticmethod
        def from_key(key):
            return FakeWallet()
    class FakeInfo:
        asset_to_sz_decimals = {1: 2, 2: 2}
        def name_to_asset(self, name):
            return {'ETC': 1, 'AVAX': 2}[name]
        def user_state(self, address, dex):
            return {'assetPositions': [{'position': {'coin': 'ETC', 'szi': '10'}}, {'position': {'coin': 'AVAX', 'szi': '-10'}}]}
    class FakeExchange:
        def __init__(self, wallet, base_url, account_address, perp_dexs):
            seen['dexs'] = perp_dexs
            self.info = FakeInfo()
        def market_open(self, coin, is_buy, sz, slippage):
            return {'status': 'ok', 'response': {'data': {'statuses': [{'filled': {'totalSz': str(sz)}}]}}}
    monkeypatch.setitem(sys.modules, 'eth_account', types.SimpleNamespace(Account=FakeAccount))
    monkeypatch.setitem(sys.modules, 'hyperliquid', types.ModuleType('hyperliquid'))
    monkeypatch.setitem(sys.modules, 'hyperliquid.exchange', types.SimpleNamespace(Exchange=FakeExchange))
    monkeypatch.setitem(sys.modules, 'hyperliquid.utils', types.ModuleType('hyperliquid.utils'))
    monkeypatch.setitem(sys.modules, 'hyperliquid.utils.constants', types.SimpleNamespace(MAINNET_API_URL='https://api.hyperliquid.xyz'))
    orders = [{'coin': 'ETC', 'is_buy': True, 'reduce_only': False, 'size': 1, 'original_size': 10},
              {'coin': 'AVAX', 'is_buy': False, 'reduce_only': False, 'size': 1, 'original_size': 10}]
    results = execute_pair(orders, '0x' + '2' * 40, 'unused')
    assert seen['dexs'] == ['', 'xyz']
    assert len(results) == 2 and all(result['ok'] for result in results)


def test_agent_authorization_preflight(monkeypatch):
    import types
    from pairs_desk.trading import verify_agent
    class Resp:
        def __init__(self, body): self.body = body
        def raise_for_status(self): pass
        def json(self): return self.body
    roles = []
    def post(url, json, timeout):
        roles.append(json)
        return Resp({'role':'agent','data':{'user':'0x'+'2'*40}})
    monkeypatch.setattr('requests.post', post)
    assert verify_agent('0x'+'2'*40, '0x'+'1'*40)['role'] == 'agent'
    assert roles == [{'type':'userRole','user':'0x'+'1'*40}]
    with pytest.raises(ValueError, match='asociado'):
        verify_agent('0x'+'3'*40, '0x'+'1'*40)
    monkeypatch.setattr('requests.post', lambda *a,**k: Resp({'role':'missing'}))
    with pytest.raises(ValueError, match='no está registrado'):
        verify_agent('0x'+'2'*40, '0x'+'1'*40)


def test_agent_missing_master_fails_closed(monkeypatch):
    import pytest
    from pairs_desk.trading import verify_agent
    class Response:
        def raise_for_status(self): pass
        def json(self): return {'role': 'agent'}
    monkeypatch.setattr('requests.post', lambda *a, **kw: Response())
    with pytest.raises(ValueError, match='trading bloqueado'):
        verify_agent('0x'+'2'*40, '0x'+'1'*40)
