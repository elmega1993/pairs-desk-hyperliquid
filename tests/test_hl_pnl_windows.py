import read_only_server as server


def _portfolio():
    return [
        ['perpDay', {'pnlHistory': [[2000, '110.0'], [1000, '100.0'], [3000, '95.5'], [3000, '95.5']]}],
        ['perpAllTime', {'pnlHistory': [[1000, '10'], [2000, '25']]}],
        ['perpWeek', {'pnlHistory': []}],
    ]


def test_each_window_is_ordered_deduplicated_and_rebased_to_zero():
    w = server.hl_pnl_windows(_portfolio())
    assert [r['time'] for r in w['1d']] == [1000, 2000, 3000]
    assert [round(r['pnl'], 2) for r in w['1d']] == [0.0, 10.0, -4.5]
    assert w['all'][-1]['pnl'] == 15.0


def test_missing_or_empty_windows_return_empty_lists():
    w = server.hl_pnl_windows(_portfolio())
    assert w['7d'] == [] and w['30d'] == []
    assert server.hl_pnl_windows([]) == {'1d': [], '7d': [], '30d': [], 'all': []}
    assert server.hl_pnl_windows(None)['1d'] == []


def test_malformed_rows_are_skipped():
    w = server.hl_series([['perpDay', {'pnlHistory': [['x', 'y'], [1, '2'], [2], None, [3, '5']]}]], 'perpDay')
    assert [r['time'] for r in w] == [1, 3] and w[-1]['pnl'] == 3.0


def test_legacy_all_time_history_is_unchanged():
    assert server.pnl_history(_portfolio()) == [{'time': 1000, 'pnl': 0.0}, {'time': 2000, 'pnl': 15.0}]
