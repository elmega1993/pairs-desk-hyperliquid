from pathlib import Path
import pytest
from pairs_desk.trade_journal import connect, begin, record, finish, pending, reconcile
from pairs_desk.trading import scaled_second_size

LEGS = [dict(coin='LINK',is_buy=True,reduce_only=False,size=2.5,original_size=10),
        dict(coin='PYTH',is_buy=False,reduce_only=False,size=50,original_size=200)]


def test_durable_pending_and_reconciliation(tmp_path):
    path = tmp_path / 'journal.sqlite3'
    conn = connect(path)
    attempt = begin(conn, '0xABC', 'LINK/PYTH', 'Aumentar', LEGS)
    record(conn, attempt, 'before_send', 'LINK', {'size':2.5, 'private_key':'MUST_NOT_STORE'})
    conn.close()
    db = connect(path)
    assert pending(db, '0xabc')[0][0] == attempt
    with pytest.raises(RuntimeError, match='pendiente'):
        begin(db, '0xABC', 'LINK/PYTH', 'Aumentar', LEGS)
    assert 'MUST_NOT_STORE' not in str(db.execute('SELECT details_json FROM events').fetchall())
    with pytest.raises(ValueError):
        reconcile(db, attempt, 'si')
    reconcile(db, attempt, 'Verifiqué fills y ambas posiciones en Hyperliquid')
    assert pending(db, '0xabc') == []
    assert begin(db, '0xABC', 'LINK/PYTH', 'Aumentar', LEGS)


def test_success_finishes_without_manual_reconciliation(tmp_path):
    db = connect(tmp_path/'log.db')
    attempt = begin(db, '0xab', 'A/B', 'Cerrar', LEGS)
    finish(db, attempt, 'complete')
    assert not pending(db, '0xab')


def test_second_leg_scaled_to_first_fill():
    first = dict(size=10)
    second = dict(size=200)
    assert scaled_second_size(first, 2.5, second, 2) == 50
    assert scaled_second_size(first, 10, second, 2) == 200
    assert scaled_second_size(first, 0, second, 2) == 0
    with pytest.raises(ValueError):
        scaled_second_size(first, 11, second, 2)


def test_prepared_partial_execution_is_logged(monkeypatch, tmp_path):
    import sys, types
    from pairs_desk.trading import execute_pair
    db = connect(tmp_path/'orders.db')
    monkeypatch.setattr('pairs_desk.trading.verify_agent', lambda *args: {'role':'agent'})
    class Wallet: address='0x'+'1'*40
    class Account:
        @staticmethod
        def from_key(_): return Wallet()
    calls = []
    class Info:
        asset_to_sz_decimals = {1: 2, 2: 2}
        def name_to_asset(self, name): return {'LINK': 1, 'xyz:TEST': 2}[name]
        def user_state(self, *args):
            return {'assetPositions':[{'position':{'coin':'LINK','szi':'10'}}, {'position':{'coin':'xyz:TEST','szi':'-200'}}]}
    class Exchange:
        def __init__(self, *args, **kwargs): self.info=Info()
        def market_open(self, coin, is_buy, sz, slippage):
            calls.append((coin, sz))
            filled = sz/2 if coin=='xyz:TEST' else sz
            return {'status':'ok','response':{'data':{'statuses':[{'filled':{'totalSz':str(filled),'oid':99}}]}}}
    monkeypatch.setitem(sys.modules,'eth_account',types.SimpleNamespace(Account=Account))
    monkeypatch.setitem(sys.modules,'hyperliquid',types.ModuleType('hyperliquid'))
    monkeypatch.setitem(sys.modules,'hyperliquid.exchange',types.SimpleNamespace(Exchange=Exchange))
    legs = [dict(coin='LINK', is_buy=True, reduce_only=False, size=5, original_size=10),
            dict(coin='xyz:TEST', is_buy=False, reduce_only=False, size=100, original_size=200)]
    attempt = begin(db, '0xabc','LINK/xyz:TEST','Aumentar', legs)
    result = execute_pair(legs,'0xabc','fake',journal=db,attempt_id=attempt)
    assert calls == [('xyz:TEST',100), ('LINK',2.5)]
    assert result[0]['ok'] is False and result[1]['ok'] is True
    assert db.execute("SELECT COUNT(*) FROM events WHERE event='filled'").fetchone()[0] == 2
