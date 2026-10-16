import pandas as pd

from pairs_desk.metrics import candle_window, latest_closed_cycle, pair_trade_events, position_map, ratio_bars, since_open


def test_position_map_preserves_case():
    state = {'assetPositions': [{'position': {'coin': 'kPEPE', 'szi': '10'}}, {'position': {'coin': 'ETH', 'szi': '0'}}]}
    assert list(position_map(state)) == ['kPEPE']


def test_candle_window_stable_inside_step():
    a = candle_window(5, now_ms=1_000_001)
    b = candle_window(5, now_ms=1_100_000)
    assert a == b


def test_since_open_simple_and_partial():
    fills = [
        {'coin': 'ETH', 'time': 100, 'tid': '1', 'side': 'B', 'sz': '1', 'px': '1', 'fee': '1', 'closedPnl': '0', 'startPosition': '0'},
        {'coin': 'ETH', 'time': 200, 'tid': '2', 'side': 'B', 'sz': '1', 'px': '1.1', 'fee': '2', 'closedPnl': '3', 'startPosition': '1'},
    ]
    ts, fee, realized, complete = since_open(fills, 'ETH', 2)
    assert (ts, fee, realized, complete) == (100, 3.0, 3.0, True)
    ts, fee, realized, complete = since_open([fills[1]], 'ETH', 2)
    assert ts is None and fee == 0.0 and realized == 0.0 and not complete


def test_ratio_bars_forward_fills_missing_timestamp():
    left = pd.DataFrame([(0, 10, 10, 10, 10), (60_000, 11, 11, 11, 11), (120_000, 12, 12, 12, 12)], columns=['time','open','high','low','close'])
    right = pd.DataFrame([(0, 2, 2, 2, 2), (120_000, 3, 3, 3, 3)], columns=['time','open','high','low','close'])
    out = ratio_bars(left, right, '15m')
    assert not out.empty
    assert abs(out.iloc[0]['c'] - 4.0) < 1e-9


def test_rebate_reduces_fees():
    fills = [{'coin': 'ETH', 'time': 100, 'tid': 'r1', 'side': 'B', 'sz': '1', 'fee': '-0.50', 'closedPnl': '0', 'startPosition': '0'}]
    _, fee, _, _ = since_open(fills, 'ETH', 1)
    assert fee == -0.5


def test_ratio_bars_gap_does_not_invent_range():
    H = 3_600_000
    cols = ['time', 'open', 'high', 'low', 'close']
    left = pd.DataFrame([(0, 100, 101, 99, 100), (H, 100, 110, 95, 105), (2 * H, 105, 106, 104, 105)], columns=cols)
    right = pd.DataFrame([(0, 10, 12, 8, 10), (2 * H, 10, 10, 10, 10)], columns=cols)
    out = ratio_bars(left, right, '1h')
    gap = out.iloc[1]
    assert abs(gap['h'] - 110 / 10) < 1e-9
    assert abs(gap['l'] - 95 / 10) < 1e-9


def test_latest_closed_cycle():
    fills = [
        {'coin': 'CRV', 'time': 100, 'tid': '1', 'side': 'B', 'sz': '10', 'px': '1', 'fee': '1', 'closedPnl': '0', 'startPosition': '0'},
        {'coin': 'CRV', 'time': 200, 'tid': '2', 'side': 'A', 'sz': '10', 'px': '1.1', 'fee': '2', 'closedPnl': '8', 'startPosition': '10'},
    ]
    cycle = latest_closed_cycle(fills, 'CRV')
    assert cycle == {'opened_at': 100, 'closed_at': 200, 'realized': 8.0, 'fees': 3.0, 'complete': True}


def test_management_signals_take_profit_ladder():
    from pairs_desk.metrics import management_signals
    assert management_signals(9.9, -1.0)['tp'] == 'HOLD'
    assert management_signals(10.0, -1.0)['tp'].startswith('TP1')
    assert management_signals(20.0, -1.0, executed_tp=[1])['tp'].startswith('TP2')
    assert management_signals(20.0, -0.4, executed_tp=[1, 2])['tp'].startswith('TP3')


def test_management_signals_add_zones_require_both_filters():
    from pairs_desk.metrics import management_signals
    assert management_signals(-9.0, -1.9)['add'] == 'WATCH'
    assert management_signals(-9.0, -2.1)['add'] == 'REVISAR ADD 1'
    assert management_signals(-16.0, -2.4)['add'] == 'REVISAR ADD 1'
    assert management_signals(-16.0, -2.6, executed_add=[1])['add'] == 'REVISAR ADD 2'


def test_pair_trade_events_groups_adds_and_closes():
    pair = {
        'long': 'AERO',
        'short': 'UNI',
        'long_position': {'szi': '15'},
        'short_position': {'szi': '-15'},
        'opened_long': 1_000,
        'opened_short': 1_050,
    }
    fills = [
        {'coin': 'AERO', 'time': 1_000, 'side': 'B', 'sz': '10', 'px': '1', 'closedPnl': '0', 'startPosition': '0'},
        {'coin': 'UNI', 'time': 1_050, 'side': 'A', 'sz': '10', 'px': '2', 'closedPnl': '0', 'startPosition': '0'},
        {'coin': 'AERO', 'time': 400_000, 'side': 'B', 'sz': '5', 'px': '1.2', 'closedPnl': '0', 'startPosition': '10'},
        {'coin': 'UNI', 'time': 400_030, 'side': 'A', 'sz': '5', 'px': '2.1', 'closedPnl': '0', 'startPosition': '-10'},
        {'coin': 'AERO', 'time': 800_000, 'side': 'A', 'sz': '3', 'px': '1.3', 'closedPnl': '7', 'startPosition': '15'},
        {'coin': 'UNI', 'time': 800_020, 'side': 'B', 'sz': '3', 'px': '2.0', 'closedPnl': '2', 'startPosition': '-15'},
    ]
    events = pair_trade_events(pair, fills, group_ms=100)
    assert [e['kind'] for e in events] == ['add', 'close']
    assert events[0]['amount'] == 5 * 1.2 + 5 * 2.1
    assert events[1]['realized'] == 9.0
    assert events[1]['label'].startswith('CIERRE +$')
