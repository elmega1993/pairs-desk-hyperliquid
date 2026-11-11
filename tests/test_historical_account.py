import json
import sqlite3

import pytest

from pairs_desk.historical_account import HistoricalAccount, api_symbol, inventory_timeline, ordered_perp_fills, archive_official_history, reconcile_exports, csv_timestamp


def fill(time, start, quantity, price, side='B', closed=0):
    return dict(time=time, startPosition=str(start), sz=str(quantity), px=str(price),
                side=side, closedPnl=str(closed), fee='0', feeToken='USDC',
                dir='Open Long', coin='BTC')


def test_same_millisecond_is_ordered_by_inventory_not_id_or_input_order():
    a, b = fill(100,0,1,10), fill(100,1,2,20)
    assert list(ordered_perp_fills([b,a])) == [a,b]
    assert inventory_timeline([b,a])[-1]['positions']['BTC'] == (3, pytest.approx(50/3))


def test_gap_in_trade_history_is_not_silently_accepted():
    with pytest.raises(ValueError,match='Discontinuous'):
        inventory_timeline([fill(100,0,1,10),fill(200,5,1,10)])


def test_close_and_flip_preserve_realized_and_reset_entry():
    state = inventory_timeline([fill(100,0,2,10),fill(200,2,3,15,'A',10)])[-1]
    assert state['positions']['BTC'] == (-1,15)
    assert state['realized'] == 10


def test_stale_prices_cannot_produce_complete_valuation(tmp_path):
    store=HistoricalAccount(tmp_path/'history.sqlite3')
    store.save_candles('BTC',[dict(s='BTC',t=0,T=3_599_999,c='20')])
    timeline=inventory_timeline([fill(100,0,2,10)])
    assert store.value_at(timeline,3_600_000)['gross'] == 20
    assert store.value_at(timeline,9_000_000)['gross'] is None
    store.db.close()


def test_csv_is_preserved_idempotently_and_account_cannot_change(tmp_path):
    store=HistoricalAccount(tmp_path/'history.sqlite3')
    path=tmp_path/'funding.csv'
    path.write_text('time,coin,sz,side,payment,rate\n23/9/2026 - 00:00:00,BTC,1,Long,0.1,0.001\n')
    store.bind_account('abc')
    store.import_csv(path)
    store.import_csv(path)
    assert store.db.execute('select count(*) from csv_evidence').fetchone()[0] == 1
    assert store.db.execute('select content from source_files').fetchone()[0] == path.read_bytes()
    with pytest.raises(ValueError):
        store.bind_account('other')
    store.db.close()


def test_export_symbols_are_normalized():
    assert api_symbol('S&P500 (xyz)') == 'xyz:SP500'
    assert api_symbol('BTC/USDC') == 'BTC/USDC'


def test_price_at_exact_daily_boundary_is_included(tmp_path):
    store = HistoricalAccount(tmp_path/'history.sqlite3')
    store.save_candles('BTC',[dict(s='BTC',t=0,T=3_599_999,c='20')])
    timeline = inventory_timeline([fill(100,0,2,10)])
    assert store.value_at(timeline,3_599_999)['gross'] == 20
    store.db.close()


def test_live_archive_keeps_official_values_without_importing_estimates(tmp_path):
    path=tmp_path/'history.sqlite3'
    store=HistoricalAccount(path)
    store.bind_account('abc')
    store.db.close()
    archive_official_history(path,tmp_path/'missing-ledger','abc',[{'time':100,'pnl':50}])
    store=HistoricalAccount(path)
    assert store.db.execute('SELECT time,pnl FROM official_points').fetchall() == [(100,50)]
    assert store.db.execute('SELECT count(*) FROM daily').fetchone()[0] == 0
    store.db.close()


def test_exports_reconcile_net_trade_pnl_and_utc_daily_funding(tmp_path):
    store=HistoricalAccount(tmp_path/'history.sqlite3')
    t=csv_timestamp('23/9/2026 - 21:00:00')
    f=fill(t,0,1,10)
    f['fee']='0.2'
    with store.db:
        store.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',('a','fills','fill',t,json.dumps(f)))
        for i,payment in enumerate(['1','2']):
            event={'time':t+i*3_600_000,'delta':{'coin':'BTC','usdc':payment}}
            store.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',('a','funding',str(i),event['time'],json.dumps(event)))
    trades=tmp_path/'trades.csv'
    trades.write_text('time,coin,dir,sz,closedPnl\n23/9/2026 - 21:00:00,BTC,Open Long,1,-0.2\n')
    funding=tmp_path/'funding.csv'
    funding.write_text('time,coin,payment\n23/9/2026 - 21:00:00,BTC,3\n')
    store.import_csv(trades)
    store.import_csv(funding)
    assert reconcile_exports(store,'a') == {'perp_trade_matched':1,'funding_utc_daily_aggregate_matched':1}
    store.db.close()
