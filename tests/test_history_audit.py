import json
from datetime import datetime

import pytest

from pairs_desk.history_audit import funding_oracle, audit_history
from pairs_desk.historical_account import HistoricalAccount, reconstructed_daily
from pairs_desk.historical_account import ZONE


def stale_daily_history(tmp_path):
    path = tmp_path/'stale.sqlite3'
    anchor = int(datetime(2026, 11, 5, 12, tzinfo=ZONE).timestamp()*1000)
    store = HistoricalAccount(path)
    with store.db:
        store.db.execute('INSERT INTO metadata VALUES (?,?)',
                         ('coverage', json.dumps({'official_anchor_ms': anchor, 'updated_ms': anchor})))
        for date, cumulative, partial in [('2026-11-05', 100, False), ('2026-11-06', 110, True)]:
            row = dict(date=date, net_cumulative_estimate=cumulative,
                       net_pnl_estimate=10, partial=partial)
            store.db.execute('INSERT INTO daily VALUES (?,?,?)', ('a', date, json.dumps(row)))
    store.db.close()
    official = [{'time': anchor, 'pnl': 0}]
    for day, pnl in [(6, 130), (7, 150), (8, 145), (9, 160)]:
        official.append({'time': int(datetime(2026, 11, day, 22, tzinfo=ZONE).timestamp()*1000), 'pnl': pnl})
    return path, official


def test_stale_daily_history_rolls_forward_and_replaces_the_old_partial_day(tmp_path):
    path, official = stale_daily_history(tmp_path)
    before = path.read_bytes()
    result = reconstructed_daily(path, 'a', official)
    rows = result['daily']
    assert [r['date'] for r in rows] == [
        '2026-11-05', '2026-11-06', '2026-11-07', '2026-11-08', '2026-11-09']
    assert [r['pnl'] for r in rows] == [10, 30, 20, -5, 15]
    assert [r['partial'] for r in rows] == [False, False, False, False, True]
    assert rows[0]['quality'] == 'estimated'
    assert all(r['quality'] == 'approximate' for r in rows[1:])
    assert rows[-1]['cumulative'] == 160
    assert path.read_bytes() == before


def test_roll_forward_keeps_missing_days_and_does_not_spread_a_multiday_delta(tmp_path):
    path, official = stale_daily_history(tmp_path)
    official.pop(2)  # No observation for November 7.
    rows = reconstructed_daily(path, 'a', official)['daily']
    assert [(r['date'], r['pnl']) for r in rows[1:]] == [
        ('2026-11-06', 30), ('2026-11-07', None),
        ('2026-11-08', None), ('2026-11-09', 15)]


def test_roll_forward_requires_the_same_official_anchor(tmp_path):
    path, official = stale_daily_history(tmp_path)
    official[0]['time'] += 1
    rows = reconstructed_daily(path, 'a', official)['daily']
    assert [r['date'] for r in rows] == ['2026-11-05', '2026-11-06']
    assert rows[-1]['pnl'] == 10


def test_funding_oracle_has_correct_sign_and_explicit_rounding_uncertainty():
    result=funding_oracle({'time':0,'delta':{'coin':'BTC','szi':'-100','fundingRate':'0.001','usdc':'10'}})
    assert result['price']==100
    assert result['price_type']=='oracle_not_mark'
    assert result['rounding_error_bound']==pytest.approx(.00001)
    assert funding_oracle({'time':0,'delta':{'coin':'BTC','szi':'100','fundingRate':'0','usdc':'0'}}) is None


def test_audit_uses_future_ohlc_only_as_bounds_not_as_known_price(tmp_path):
    store=HistoricalAccount(tmp_path/'h.sqlite3')
    t=1790132400000
    fill=dict(time=t,coin='BTC',dir='Open Short',side='A',sz='1',startPosition='0',
              px='100',closedPnl='0',fee='0',feeToken='USDC')
    with store.db:
        store.db.execute('INSERT INTO events VALUES (?,?,?,?,?)',('a','fills','1',t,json.dumps(fill)))
        store.db.executemany('INSERT INTO official_points VALUES (?,?,?)',[('a',t+1000,0),('a',t+2000,-5)])
    store.save_candles('BTC',[
        dict(s='BTC',i='15m',t=t-900000,T=t-1,o='100',h='100',l='100',c='100'),
        dict(s='BTC',i='15m',t=t,T=t+899999,o='100',h='120',l='80',c='105'),
    ])
    report=audit_history(store,'a')
    assert report['official_points_inside_trade_range']==2
    assert report['worst']['difference']==5
    assert report['publication_status']=='estimated_view_only'
    store.db.close()


def test_daily_reader_keeps_history_estimated_and_uses_official_only_for_latest_day(tmp_path):
    path=tmp_path/'h.sqlite3'
    store=HistoricalAccount(path)
    t=1790132400000
    with store.db:
        store.db.execute('INSERT INTO metadata VALUES (?,?)',('coverage',json.dumps({'official_anchor_ms':t,'updated_ms':t})))
        for date,value,delta in [('2026-09-23',10,10),('2026-09-24',20,10)]:
            row={'date':date,'net_cumulative_estimate':value,'net_pnl_estimate':delta,'partial':True}
            store.db.execute('INSERT INTO daily VALUES (?,?,?)',('a',date,json.dumps(row)))
    store.db.close()
    rows=reconstructed_daily(path,'a',[{'time':t,'pnl':0},{'time':t+86400000+1000,'pnl':25}])['daily']
    assert rows[0]['cumulative']==10
    assert rows[-1]['pnl']==15
    assert rows[-1]['cumulative']==25
    assert all(row['quality']=='estimated' for row in rows)
    assert reconstructed_daily(path,'another-account')['daily']==[]
    assert reconstructed_daily(tmp_path/'nonexistent','a')['daily']==[]
