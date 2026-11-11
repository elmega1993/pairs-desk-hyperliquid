from datetime import datetime, timezone
import pytest

from pairs_desk.strategy_analytics import (
    daily_strategy_pnl,
    strategy_snapshot,
    strategy_capital,
    strategy_capital_with_flows,
    strategy_history,
    strategy_roi,
)
from pathlib import Path
from pairs_desk.strategy_analytics import portfolio_strategy_daily


def test_official_history_retains_detail_and_keeps_accounts_separate(tmp_path, monkeypatch):
    import read_only_server as server
    monkeypatch.setattr(server, 'SNAPSHOTS', tmp_path / 'snapshots.jsonl')
    start = server.STRATEGY_START_MS
    first = {'perpAllTime': {'pnlHistory': [[start, 100], [start+300_000, 110]]}}
    server.retained_official_history(first, 'account-a')
    second = {'perpAllTime': {'pnlHistory': [[start, 100], [start+600_000, 120]]}}
    rows = server.retained_official_history(second, 'account-a')
    assert [r['pnl'] for r in rows] == [100, 110, 120]
    assert [r['pnl'] for r in server.retained_official_history(second, 'account-b')] == [100, 120]


def test_unaligned_window_is_excluded():
    from pairs_desk.strategy_analytics import aligned_portfolio_history
    assert aligned_portfolio_history({
        'perpAllTime': {'pnlHistory': [[1000000000000, 50]]},
        'perpMonth': {'pnlHistory': [[1000000001000, 900]]},
    }) == [{'time': 1000000000000, 'pnl': 50}]


def test_daily_portfolio_merges_raw_windows_without_rebasing_each_window():
    start = int(datetime(2026, 9, 23, 3, tzinfo=timezone.utc).timestamp()*1000)
    day = 86_400_000
    rows = portfolio_strategy_daily({
        'perpAllTime': {'pnlHistory': [[start, 100], [start+3*day, 160]]},
        'perpMonth': {'pnlHistory': [[start+day, 0], [start+2*day, 10], [start+3*day, 40]]},
    }, start)
    assert [r['pnl'] for r in rows] == [0, 20, 10, 30]
    assert [r['date'] for r in rows] == ['2026-09-23', '2026-09-24', '2026-09-25', '2026-09-26']


def test_daily_portfolio_does_not_label_multiday_delta_as_one_day():
    start = int(datetime(2026, 9, 23, 3, tzinfo=timezone.utc).timestamp()*1000)
    rows = portfolio_strategy_daily({'perpAllTime': {'pnlHistory': [
        [start, 100], [start+2*86_400_000, 160], [start+3*86_400_000, 170],
    ]}}, start)
    assert [r['pnl'] for r in rows] == [0, None, None, 10]


START = int(datetime(2026, 9, 23, tzinfo=timezone.utc).timestamp() * 1000)


def test_strategy_history_filters_before_start_and_rebases_deduplicated_rows():
    rows = [
        {'time': START - 1, 'pnl': 99},
        {'time': START + 2_000, 'pnl': 120},
        {'time': START, 'pnl': 100},
        {'time': START + 2_000, 'pnl': 121},
    ]

    assert strategy_history(rows, START) == [
        {'time': START, 'pnl': 0.0},
        {'time': START + 2_000, 'pnl': 21.0},
    ]


def test_daily_strategy_pnl_marks_first_day_partial_without_inventing_a_full_day():
    rows = [
        {'time': START, 'pnl': 0.0},
        {'time': START + 12 * 60 * 60 * 1000, 'pnl': 10.0},
        {'time': START + 24 * 60 * 60 * 1000, 'pnl': 4.0},
    ]

    assert daily_strategy_pnl(rows, 'UTC') == [
        {'date': '2026-09-23', 'pnl': 10.0, 'cumulative': 10.0, 'partial': True},
        {'date': '2026-09-24', 'pnl': -6.0, 'cumulative': 4.0, 'partial': False},
    ]


def test_strategy_capital_uses_first_available_value_on_or_after_start():
    history = [
        [START - 1, '900'],
        [START + 5_000, '1000'],
        [START + 10_000, '1100'],
    ]

    assert strategy_capital(history, START) == 1000.0
    assert strategy_capital([[START - 1, '900']], START) is None


def test_strategy_roi_requires_positive_initial_capital():
    assert strategy_roi(150.0, 1000.0) == 15.0
    assert strategy_roi(150.0, None) is None
    assert strategy_roi(150.0, 0.0) is None


def test_strategy_snapshot_does_not_deduct_funding_and_fees_twice():
    result = strategy_snapshot(
        [{'time': START, 'pnl': 100}, {'time': START + 1000, 'pnl': 250}],
        [[START, '1000']],
        [{'time': START - 1, 'fee': '99', 'closedPnl': '99'},
         {'time': START + 1, 'fee': '10', 'closedPnl': '200'}],
        [{'time': START + 2, 'delta': {'usdc': '-5'}}],
        START,
        fills_complete=True,
        funding_complete=True,
        unrealized=25,
    )

    assert result['gross_pnl'] == 165.0
    assert result['realized'] == 200.0
    assert result['fees'] == 10.0
    assert result['funding'] == -5.0
    assert result['net_pnl'] == 150.0
    assert result['roi_pct'] == 15.0
    assert result['unrealized'] == 25.0


def test_official_net_remains_available_without_verifiable_cost_breakdown():
    result = strategy_snapshot(
        [{'time': START, 'pnl': 100}, {'time': START+1000, 'pnl': 250}],
        [[START,'1000']], [], [], START, fills_complete=False, funding_complete=False)
    assert result['net_pnl'] == 150
    assert result['gross_pnl'] is None
    assert result['roi_pct'] == 15


def test_perp_costs_exclude_spot_trading():
    result = strategy_snapshot(
        [{'time':START,'pnl':0},{'time':START+1000,'pnl':10}],[[START,'100']],
        [{'time':START+1,'dir':'Buy','fee':'50','closedPnl':'100'},
         {'time':START+2,'dir':'Open Long','fee':'1','closedPnl':'0'}],[],START,
        fills_complete=True,funding_complete=True)
    assert result['fees']==1
    assert result['realized']==0
    assert result['net_pnl']==10
    assert result['gross_pnl']==11


def test_strategy_capital_includes_post_start_deposits_and_excludes_withdrawn_balance():
    result = strategy_capital_with_flows(
        [[START, '1016.114684']],
        [
            {'time': START + 1, 'delta': {'type': 'spotTransfer', 'user': 'system', 'destination': 'acct', 'usdcValue': '2999.716059'}},
            {'time': START + 2, 'delta': {'type': 'spotTransfer', 'user': 'system', 'destination': 'acct', 'usdcValue': '32.570997'}},
            {'time': START + 3, 'delta': {'type': 'send', 'user': 'acct', 'destination': 'system', 'usdcValue': '1980'}},
        ], START, 'acct',
    )
    assert result == pytest.approx(4048.40174)


def test_strategy_snapshot_can_use_configured_initial_capital_after_withdrawal():
    result = strategy_snapshot(
        [{'time': START, 'pnl': 0}, {'time': START + 1_000, 'pnl': 100}],
        [[START, '1016']], [], [], START,
        fills_complete=True, funding_complete=True, initial_capital_override=4100,
    )
    assert result['initial_capital'] == 4100.0
    assert result['roi_pct'] == pytest.approx(2.43902439)


def test_state_contract_exposes_strategy_block():
    server = (Path(__file__).resolve().parents[1] / 'read_only_server.py').read_text()
    assert 'STRATEGY_START_MS = 1790132400000' in server
    assert "'strategy':strategy" in server
    assert 'userNonFundingLedgerUpdates' in server
    assert 'nonfunding_rows=' in server


def test_cost_details_preserve_funding_directions_rebates_and_asset_totals():
    result = strategy_snapshot([], [], [
        {'time': START-1, 'coin': 'OLD', 'fee': '90'},
        {'time': START+1, 'coin': 'BTC', 'fee': '3', 'closedPnl': '0'},
        {'time': START+2, 'coin': 'ETH', 'fee': '-1', 'closedPnl': '0'},
        {'time': START+3, 'coin': '@1', 'dir': 'Buy', 'fee': '50'},
    ], [
        {'time': START-1, 'delta': {'coin': 'OLD', 'usdc': '99'}},
        {'time': START+1, 'delta': {'coin': 'BTC', 'usdc': '-8'}},
        {'time': START+2, 'delta': {'coin': 'BTC', 'usdc': '5'}},
        {'time': START+3, 'delta': {'coin': 'ETH', 'usdc': '4'}},
    ], START, fills_complete=True, funding_complete=True)
    detail = result['cost_details']
    assert detail['funding_paid'] == -8
    assert detail['funding_received'] == 9
    assert sum(r['fees'] for r in detail['assets']) == 2
    assert sum(r['funding'] for r in detail['assets']) == result['funding'] == 1
    assert {r['coin'] for r in detail['assets']} == {'BTC', 'ETH'}
    assert sum(r['impact'] for r in detail['assets']) == -1


@pytest.mark.parametrize('fills_complete,funding_complete', [(False, True), (True, False), (False, False)])
def test_cost_details_do_not_publish_partial_total(fills_complete, funding_complete):
    result = strategy_snapshot([], [], [], [], START,
                               fills_complete=fills_complete, funding_complete=funding_complete)
    detail = result['cost_details']
    assert detail['assets'] is None
    assert detail['funding_paid'] == (0 if funding_complete else None)
    assert detail['funding_received'] == (0 if funding_complete else None)


def test_invalid_funding_hides_both_directions():
    result = strategy_snapshot([], [], [], [
        {'time': START+1, 'delta': {'coin': 'BTC', 'usdc': '4'}},
        {'time': START+2, 'delta': {'coin': 'BTC', 'usdc': 'nan'}},
    ], START, fills_complete=True, funding_complete=True)
    assert result['funding'] is None
    assert result['cost_details']['funding_received'] is None
    assert result['cost_details']['funding_paid'] is None
    assert result['cost_details']['assets'] is None
