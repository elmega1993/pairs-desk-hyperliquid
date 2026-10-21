from datetime import timezone
from concurrent.futures import ThreadPoolExecutor
import pytest
from pairs_desk.ledger import Ledger, closed_accounting
from pairs_desk.exporting import build_export_rows


def fill(t, tid, coin='A', side='B', start='0', pnl='0'):
    return dict(time=t, tid=tid, coin=coin, side=side, oid=tid, sz='1', px='10',
                startPosition=start, closedPnl=pnl, fee='0.1')


def funding(t, coin='A', amount='-2'):
    return dict(time=t, hash=f'h{t}', delta=dict(type='funding', coin=coin, usdc=amount))


def api(fills=(), funds=()):
    def fetch(**p):
        rows, limit = (fills, 2000) if p['type']=='userFillsByTime' else (funds, 500)
        return [r for r in rows if p['startTime'] <= r['time'] <= p['endTime']][:limit]
    return fetch


def test_restart_incremental_dedup_account_scope(tmp_path):
    path=tmp_path/'ledger.sqlite3'; ledger=Ledger(path)
    rows=[fill(10,1),fill(20,2)]
    assert ledger.sync('ABC',api(rows),100_000)['fills']['complete']
    ledger=Ledger(path)
    rows.append(fill(110_000,3))
    result=ledger.sync('abc',api(rows),150_000)
    assert len(result['fills_rows'])==3 and result['fills']['complete']
    ledger.sync('other',api(rows),150_000)
    assert len(ledger.rows('abc','fills'))==3
    assert len(ledger.rows('other','fills'))==3


def test_boundary_ties_are_not_skipped(tmp_path):
    rows=[fill(i+1,i) for i in range(1999)] + [fill(2000,2000+i) for i in range(5)]
    ledger=Ledger(tmp_path/'db')
    result=ledger.sync('a',api(rows),100_000)
    assert result['fills']['complete'] and len(result['fills_rows'])==2004


def test_funding_boundary_ties(tmp_path):
    funds=[funding(i+1) for i in range(499)]+[funding(500,coin=str(i)) for i in range(8)]
    ledger=Ledger(tmp_path/'db'); result=ledger.sync('a',api([],funds),100_000)
    assert result['funding']['complete'] and len(ledger.rows('a','funding'))==507


def test_saturated_timestamp_partial(tmp_path):
    rows=[fill(10,i) for i in range(2001)]
    result=Ledger(tmp_path/'db').sync('a',api(rows),100_000)
    assert not result['fills']['complete']


def test_missing_anchor_retention_gap_stays_partial(tmp_path):
    ledger=Ledger(tmp_path/'db')
    ledger.sync('a',api([fill(10,1)]),100_000)
    result=ledger.sync('a',api([fill(120_000,2)]),150_000)
    assert not result['fills']['complete'] and len(result['fills_rows'])==2
    assert not ledger.sync('a',api([fill(120_000,2)]),200_000)['fills']['complete']


def test_api_failure_keeps_checkpoint_and_old_rows(tmp_path):
    ledger=Ledger(tmp_path/'db'); ledger.sync('a',api([fill(10,1)]),100_000)
    before=ledger.state('a','fills')
    def fail(**p): raise ConnectionError()
    result=ledger.sync('a',fail,150_000)
    assert result['fills']['error']=='ConnectionError'
    assert ledger.state('a','fills')==before and len(result['fills_rows'])==1


def test_conflicting_event_rolls_back(tmp_path):
    ledger=Ledger(tmp_path/'db'); ledger.sync('a',api([fill(10,1)]),100_000)
    result=ledger.sync('a',api([fill(10,1,pnl='9')]),150_000)
    assert result['fills']['error']=='ValueError'
    assert ledger.rows('a','fills')[0]['closedPnl']=='0'


def test_funding_sign_zero_unknown_and_per_leg_windows(tmp_path):
    ledger=Ledger(tmp_path/'db')
    assert ledger.funding('a',[('A',10,30)]) is None
    ledger.sync('a',api([], [funding(15),funding(25,'B','3'),funding(35,'A','100')]),100_000)
    assert ledger.funding('a',[('A',10,30),('B',20,40)])==1
    assert ledger.funding('a',[('C',10,30)])==0
    assert ledger.funding('a',[('A',10,150_000)]) is None
    assert ledger.funding('a',[('A',15,30)]) is None


def test_closed_reconciliation_and_export(tmp_path):
    rows=[fill(10,1),fill(20,2,'B','A'),fill(30,3,'A','A','1','5'),fill(40,4,'B','B','-1','2')]
    ledger=Ledger(tmp_path/'db'); ledger.sync('a',api(rows,[funding(15),funding(35,'B','3')]),100_000)
    old=dict(long='A',short='B',opened_at=10,closed_at=40,realized=7,fees=.4)
    out=closed_accounting(ledger,'a',old,rows,True)
    assert out['funding']==1 and out['total_pnl']==pytest.approx(7.6)
    exported=build_export_rows([], [out], timezone.utc)[0]
    assert exported['total_pnl_usd']==out['total_pnl'] and exported['funding_usd']==1
    bad=closed_accounting(ledger,'a',dict(old,realized=100),rows,True)
    assert bad['total_pnl'] is None
    assert build_export_rows([], [old], timezone.utc)[0]['total_pnl_usd'] is None


def test_concurrent_sync_is_idempotent(tmp_path):
    ledger=Ledger(tmp_path/'db')
    with ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _: ledger.sync('a',api([fill(10,1)]),100_000),range(4)))
    assert len(ledger.rows('a','fills'))==1
    assert all(r['fills']['complete'] for r in results)


def test_past_10k_local_rows_are_retained(tmp_path):
    ledger=Ledger(tmp_path/'db')
    rows=[fill(i+1,i) for i in range(6000)]
    ledger.sync('a',api(rows),100_000)
    rows += [fill(110_000+i,6000+i) for i in range(6000)]
    result=ledger.sync('a',api(rows),150_000)
    assert result['fills']['complete'] and len(result['fills_rows'])==12000


def test_terminal_state_reconciles_persists_and_reports_net(tmp_path, monkeypatch):
    import read_only_server as server
    import final_read_services as service
    from pairs_desk.storage import save_settings, load_settings
    import time
    now=int(time.time()*1000)
    rows=[fill(now-4000,1),fill(now-3000,2,'B','A'),fill(now-2000,3,'A','A','1','5'),fill(now-1000,4,'B','B','-1','2')]
    funds=[funding(now-3500), funding(now-1500,'B','3')]
    path=tmp_path/'settings.json'; account='0x'+'a'*40
    archive=dict(id='test',long='A',short='B',opened_at=now-4000,closed_at=now-1000,realized=7,fees=.4)
    save_settings(path,dict(address=account,pairs=[],closed_pairs=[archive]))
    ledger=Ledger(tmp_path/'db')
    monkeypatch.setattr(server,'SETTINGS',path)
    monkeypatch.setattr(server,'SNAPSHOTS',tmp_path/'snapshots.jsonl')
    monkeypatch.setattr(server,'Ledger',lambda:ledger)
    monkeypatch.setattr(service,'Ledger',lambda:ledger)
    monkeypatch.setattr(service,'_cache',{})
    def hl(p):
        if p['type']=='clearinghouseState':return {'assetPositions':[], 'marginSummary':{'accountValue':'100','totalMarginUsed':'0'}}
        if p['type']=='portfolio':return []
        return api(rows,funds)(**p)
    monkeypatch.setattr(server,'hl',hl)
    data=server.states()
    assert data['summary']['funding']==1
    assert data['summary']['total']==pytest.approx(7.6)
    assert load_settings(path)[0]['closed_pairs'][0]['funding']==1
    assert server.states()['summary']['total']==pytest.approx(7.6)


def test_active_funding_uses_signed_ledger_and_rejects_stale(tmp_path):
    from pairs_desk.ledger import active_funding
    ledger=Ledger(tmp_path/'db'); rows=[fill(10,1),fill(20,2,'B','A')]
    ledger.sync('a',api(rows,[funding(15),funding(30,'B','3')]),100_000)
    assert active_funding(ledger,'a','A','B',rows,1,-1,True,100_001)==1
    assert active_funding(ledger,'a','A','B',rows,1,-1,True,161_000) is None


def test_unknown_closed_funding_does_not_hide_active_subtotal():
    from final_read_services import funding_summary
    result = funding_summary([{'funding': -12}], [{'funding': None}, {'funding': 3}])
    assert result['known_funding'] == -9
    assert result['active_funding'] == -12
    assert result['archived_funding'] is None
    assert result['archived_funding_missing'] == 1
    assert funding_summary([{'funding': None}], [])['known_funding'] is None
    assert funding_summary([], [])['known_funding'] == 0


def test_management_uses_frozen_reference_and_shared_rules():
    from final_read_services import management_snapshot
    value=management_snapshot({'management_entry_ratio':2},2.3,-1)
    assert value['tp_level']==1
    assert value['ratio_change']==pytest.approx(15)
    value=management_snapshot({'management_entry_ratio':2,'executed_tp':[{'level':1}]},2.3,-1)
    assert value['tp']=='HOLD'
    assert management_snapshot({},2.3,-2)['add']=='N/D'
    assert management_snapshot({'management_entry_ratio':2},1.5,None)['add']=='N/D · sin Z'


def test_chart_retains_history_and_identifies_accounting_basis(tmp_path, monkeypatch):
    import json
    import read_only_server as server
    path=tmp_path/'history.jsonl'
    path.write_text(''.join(json.dumps({'time':i+1,'pnl':i,'basis':'gross'})+'\n' for i in range(1500)))
    monkeypatch.setattr(server,'SNAPSHOTS',path)
    assert len(server.local_pnl_history())==1500
    assert server.local_pnl_history()[0]['basis']=='gross'
    server.save_snapshot({'total':None,'open_plus_realized':2000})
    assert json.loads(path.read_text().splitlines()[-1])['basis']=='gross'


def test_chart_history_retains_snapshot_components_for_context(tmp_path, monkeypatch):
    import json
    import read_only_server as server
    path=tmp_path/'history.jsonl'
    path.write_text(json.dumps({'time':1,'pnl':12,'basis':'net','open':4,'realized':8,'exposure':1000,'margin_used':120,'margin_pct':12})+'\n')
    monkeypatch.setattr(server,'SNAPSHOTS',path)
    row=server.local_pnl_history()[0]
    assert row['open']==4 and row['realized']==8 and row['exposure']==1000
    assert row['margin_used']==120 and row['margin_pct']==12
