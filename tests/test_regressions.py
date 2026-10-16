from pairs_desk.lifecycle import archive_closed_pairs
from pairs_desk.metrics import latest_closed_cycle, management_signals, pair_trade_events, since_open


def _open_close(coin, side_open, side_close, size=10, t0=100, t1=200, pnl=5):
    return [
        {'coin': coin, 'time': t0, 'tid': f'{coin}-1', 'side': side_open, 'sz': str(size), 'px': '1', 'fee': '1', 'closedPnl': '0', 'startPosition': '0'},
        {'coin': coin, 'time': t1, 'tid': f'{coin}-2', 'side': side_close, 'sz': str(size), 'px': '1.1', 'fee': '1', 'closedPnl': str(pnl), 'startPosition': str(size if side_open == 'B' else -size)},
    ]


def test_latest_closed_cycle_requires_flat():
    fills = [
        {'coin': 'X', 'time': 100, 'tid': '1', 'side': 'B', 'sz': '10', 'px': '1', 'fee': '1', 'closedPnl': '0', 'startPosition': '0'},
        {'coin': 'X', 'time': 200, 'tid': '2', 'side': 'A', 'sz': '3', 'px': '1.1', 'fee': '1', 'closedPnl': '5', 'startPosition': '10'},
    ]
    assert latest_closed_cycle(fills, 'X') is None


def test_no_archive_when_xyz_down():
    cfg = {'pairs': [{'long': 'xyz:A', 'short': 'xyz:B'}], 'closed_pairs': []}
    fills = _open_close('xyz:A', 'B', 'A') + _open_close('xyz:B', 'A', 'B')
    out, changed, counts = archive_closed_pairs(
        cfg, {}, fills, {'core_ok': True, 'xyz_ok': False, 'fills_ok': True, 'snapshot_token': 's1'}, {}, 2
    )
    assert not changed
    assert out['pairs'] == cfg['pairs']
    assert not out['closed_pairs']
    assert counts.get('xyz:A|xyz:B', 0) == 0


def test_archive_requires_two_healthy_absent_reads():
    cfg = {'pairs': [{'long': 'A', 'short': 'B'}], 'closed_pairs': []}
    fills = _open_close('A', 'B', 'A') + _open_close('B', 'A', 'B')
    health = {'core_ok': True, 'xyz_ok': True, 'fills_ok': True, 'snapshot_token': 's1'}
    out1, changed1, counts = archive_closed_pairs(cfg, {}, fills, health, {}, 2)
    assert not changed1 and out1['pairs']
    health['snapshot_token'] = 's2'
    out2, changed2, counts = archive_closed_pairs(out1, {}, fills, health, counts, 2)
    assert changed2 and not out2['pairs'] and len(out2['closed_pairs']) == 1


def test_since_open_same_ms_ties_are_order_independent():
    fills = [
        {'coin': 'ETH', 'time': 1000, 'tid': 'a', 'side': 'B', 'sz': '1', 'fee': '1', 'closedPnl': '0', 'startPosition': '0'},
        {'coin': 'ETH', 'time': 1000, 'tid': 'b', 'side': 'B', 'sz': '1', 'fee': '1', 'closedPnl': '0', 'startPosition': '1'},
        {'coin': 'ETH', 'time': 1000, 'tid': 'c', 'side': 'B', 'sz': '1', 'fee': '1', 'closedPnl': '0', 'startPosition': '2'},
    ]
    assert since_open(fills, 'ETH', 3)[1] == 3.0
    assert since_open(list(reversed(fills)), 'ETH', 3)[1] == 3.0


def test_no_spurious_add_when_legs_open_minutes_apart():
    pair = {'long': 'A', 'short': 'B', 'long_position': {'szi': '10'}, 'short_position': {'szi': '-10'}}
    fills = [
        {'coin': 'A', 'time': 1_000_000, 'tid': 'a', 'side': 'B', 'sz': '10', 'px': '1', 'fee': '0', 'closedPnl': '0', 'startPosition': '0'},
        {'coin': 'B', 'time': 1_240_000, 'tid': 'b', 'side': 'A', 'sz': '10', 'px': '2', 'fee': '0', 'closedPnl': '0', 'startPosition': '0'},
    ]
    assert pair_trade_events(pair, fills) == []


def test_signals_with_unknown_z_are_not_watch():
    assert management_signals(-16, None)['add'].startswith('N/D')
    # If TP1/TP2 are already done, TP3 must explicitly say Z is missing.
    assert management_signals(25, None, executed_tp=[1, 2])['tp'].startswith('N/D')


def test_tp_does_not_repeat_after_execution():
    sig = management_signals(12, -1, executed_tp=[1])
    assert sig['tp'] == 'HOLD'
    assert 'TP2' in sig['tp_detail']


def test_archive_same_snapshot_does_not_count_twice():
    cfg = {'pairs': [{'long': 'A', 'short': 'B'}], 'closed_pairs': []}
    fills = _open_close('A', 'B', 'A') + _open_close('B', 'A', 'B')
    health = {'core_ok': True, 'xyz_ok': True, 'fills_ok': True, 'snapshot_token': 'snap-1'}
    out1, changed1, counts = archive_closed_pairs(cfg, {}, fills, health, {}, 2)
    out2, changed2, counts = archive_closed_pairs(out1, {}, fills, health, counts, 2)
    assert not changed1 and not changed2
    assert counts['A|B']['count'] == 1
    health['snapshot_token'] = 'snap-2'
    out3, changed3, _ = archive_closed_pairs(out2, {}, fills, health, counts, 2)
    assert changed3 and not out3['pairs']


def test_since_open_missing_boundary_does_not_attribute_old_tail():
    fills = [
        {'coin': 'ETH', 'time': 100, 'tid': '1', 'side': 'B', 'sz': '1', 'fee': '2', 'closedPnl': '7', 'startPosition': '3'},
        {'coin': 'ETH', 'time': 200, 'tid': '2', 'side': 'A', 'sz': '.5', 'fee': '3', 'closedPnl': '4', 'startPosition': '4'},
    ]
    opened, fees, realized, complete = since_open(fills, 'ETH', 3.5)
    assert opened is None and fees == 0 and realized == 0 and not complete

from pairs_desk.metrics import archived_pair_entry_ratio, closed_pair_trade_events


def test_closed_pair_events_reconstruct_add_and_close():
    fills = [
        {'coin':'A','time':1_000_000,'tid':'a1','side':'B','sz':'10','px':'2','fee':'0','closedPnl':'0','startPosition':'0'},
        {'coin':'B','time':1_010_000,'tid':'b1','side':'A','sz':'10','px':'4','fee':'0','closedPnl':'0','startPosition':'0'},
        {'coin':'A','time':1_400_000,'tid':'a2','side':'B','sz':'5','px':'1.8','fee':'0','closedPnl':'0','startPosition':'10'},
        {'coin':'B','time':1_405_000,'tid':'b2','side':'A','sz':'5','px':'3.9','fee':'0','closedPnl':'0','startPosition':'-10'},
        {'coin':'A','time':2_000_000,'tid':'a3','side':'A','sz':'15','px':'2.2','fee':'0','closedPnl':'20','startPosition':'15'},
        {'coin':'B','time':2_005_000,'tid':'b3','side':'B','sz':'15','px':'3.7','fee':'0','closedPnl':'10','startPosition':'-15'},
    ]
    events = closed_pair_trade_events('A','B',fills,1_000_000,2_005_000)
    assert [e['kind'] for e in events] == ['add','close']
    assert events[-1]['realized'] == 30


def test_archived_entry_ratio_uses_opening_vwap():
    fills = [
        {'coin':'A','time':1_000_000,'side':'B','sz':'2','px':'2','startPosition':'0'},
        {'coin':'B','time':1_010_000,'side':'A','sz':'2','px':'4','startPosition':'0'},
    ]
    assert archived_pair_entry_ratio('A','B',fills,1_000_000) == 0.5

from pairs_desk.lifecycle import pair_leg_conflict


def test_reusing_link_from_incomplete_old_pair():
    old = [{'long': 'LINK', 'short': 'SAND'}]
    positions = {'LINK': {'szi': '12'}, 'PYTH': {'szi': '-300'}}
    assert not pair_leg_conflict('LINK', 'PYTH', old, positions)
    # Old settings and any closed history remain intact until archival is verified.
    assert old == [{'long': 'LINK', 'short': 'SAND'}]


def test_cannot_duplicate_an_actually_live_leg():
    old = [{'long': 'LINK', 'short': 'SAND'}]
    positions = {'LINK': {'szi': '12'}, 'SAND': {'szi': '-500'}, 'PYTH': {'szi': '-300'}}
    assert pair_leg_conflict('LINK', 'PYTH', old, positions)


def test_inverted_or_flat_stale_pair_does_not_block():
    old = [{'long': 'LINK', 'short': 'SAND'}]
    positions = {'LINK': {'szi': '12'}, 'SAND': {'szi': '0'}, 'PYTH': {'szi': '-300'}}
    assert not pair_leg_conflict('LINK', 'PYTH', old, positions)
