from datetime import timezone

from pairs_desk.exporting import build_export_rows
from pairs_desk.hl_client import user_fills_history
from pairs_desk.lifecycle import reset_management_on_reopen
from pairs_desk.metrics import management_signals


def _fill(t, tid):
    return {'coin': 'A', 'time': t, 'tid': tid, 'hash': f'h{tid}', 'oid': tid, 'side': 'B', 'sz': '1', 'px': '1'}


def test_user_fills_paginates_past_2000():
    all_fills = [_fill(10000 + i, i) for i in range(3500)]
    calls = []
    def fetch(**payload):
        calls.append(payload)
        if payload['type'] == 'userFills':
            return all_fills[-2000:]
        return [x for x in all_fills if x['time'] >= payload['startTime']][:2000]
    rows, complete = user_fills_history('0xabc', fetch=fetch)
    assert len(rows) == 3500 and complete
    assert calls[1]['startTime'] == 0
    assert calls[2]['startTime'] == all_fills[1999]['time'] + 1


def test_user_fills_marks_10k_ceiling_partial():
    all_fills = [_fill(100000+i, i) for i in range(10000)]
    def fetch(**payload):
        if payload['type'] == 'userFills':
            return all_fills[-2000:]
        return [x for x in all_fills if x['time'] >= payload['startTime']][:2000]
    rows, complete = user_fills_history('0xabc', fetch=fetch)
    assert len(rows) == 10000 and not complete


def test_fills_marks_incomplete_if_recent_missing():
    oldest = [_fill(1000+i, i) for i in range(1500)]
    def fetch(**payload):
        if payload['type'] == 'userFills':
            return oldest + [_fill(9999, 9999)]
        return oldest
    rows, complete = user_fills_history('0xabc', fetch=fetch)
    assert len(rows) == 1500 and not complete


def test_csv_includes_closed_pairs_and_reconciles_realized():
    active = [{
        'long':'A','short':'B','opened_long':1000,'opened_short':1000,
        'long_usd':100,'short_usd':100,'notional':200,'entry_ratio':1,'current_ratio':1.1,
        'ratio_change':10,'management_entry_ratio':1,'management_ratio_change':10,'management_z':0,
        'tp':'TP1','add':'NO ADD','unrealized':20,'realized':12,'funding':-1,'fees':2,'total_pnl':29,
        'imbalance':0,'liq_distance':30,'long_liq_distance':30,'short_liq_distance':40,'history_complete':True,
    }]
    closed = [{'long':'C','short':'D','opened_at':100,'closed_at':200,'realized':25,'fees':3,'net_realized':22}]
    rows = build_export_rows(active, closed, timezone.utc)
    assert {r['status'] for r in rows} == {'active', 'closed'}
    assert sum(float(r['realized_pnl_usd'] or 0) for r in rows) == 37


def test_tp3_ratio_threshold_is_independent_from_tp2():
    rules = {'tp2_ratio_pct': 20, 'tp3_ratio_pct': 30, 'tp3_abs_z': .5}
    assert management_signals(25, 0.1, executed_tp=[1,2], rules=rules)['tp'] == 'HOLD'
    assert management_signals(31, 0.1, executed_tp=[1,2], rules=rules)['tp'].startswith('TP3')


def test_management_resets_on_new_cycle():
    cfg = {'management_cycle_opened_at':100, 'management_entry_ratio':2, 'executed_tp':[{'level':1}], 'executed_add':[{'level':1}]}
    assert reset_management_on_reopen(cfg, 200)
    assert cfg['management_cycle_opened_at'] == 200
    assert 'management_entry_ratio' not in cfg and 'executed_tp' not in cfg and 'executed_add' not in cfg


def test_management_does_not_reset_same_cycle():
    cfg = {'management_cycle_opened_at':100, 'management_entry_ratio':2, 'executed_tp':[{'level':1}]}
    assert not reset_management_on_reopen(cfg, 100)
    assert cfg['executed_tp'][0]['level'] == 1


def test_closed_export_unknown_funding_keeps_net_unknown():
    rows = build_export_rows([], [{'long':'C','short':'D','realized':50,'fees':7}], timezone.utc)
    assert rows[0]['total_pnl_usd'] is None


def test_first_cycle_marker_preserves_existing_management_state():
    cfg = {'management_entry_ratio':2, 'executed_tp':[{'level':1}]}
    assert not reset_management_on_reopen(cfg, 100)
    assert cfg['management_cycle_opened_at'] == 100
    assert cfg['management_entry_ratio'] == 2 and cfg['executed_tp'][0]['level'] == 1
