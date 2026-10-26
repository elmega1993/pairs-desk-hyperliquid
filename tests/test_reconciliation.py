from pairs_desk.reconciliation import reconcile_payloads


def test_reconciliation_includes_account_month_pnl_and_live_pairs():
    portfolio = [['perpMonth', {'pnlHistory': [[1000, 10], [2000, 2470.71]]}]]
    core = {'assetPositions': [
        {'position': {'coin': 'AAA', 'szi': '1', 'unrealizedPnl': '20'}},
        {'position': {'coin': 'BBB', 'szi': '-2', 'unrealizedPnl': '5'}},
    ]}

    result = reconcile_payloads(
        {'pairs': [{'long': 'AAA', 'short': 'BBB'}]}, portfolio, core, {'assetPositions': []}
    )

    assert result['pnl_windows']['30d_usd'] == 2460.71
    assert result['active_pair_count'] == 1
    assert result['active_unrealized_usd'] == 25.0


def test_reconciliation_ignores_configured_pair_without_both_live_legs():
    result = reconcile_payloads(
        {'pairs': [{'long': 'AAA', 'short': 'BBB'}, {'long': 'CCC', 'short': 'DDD'}]},
        [],
        {'assetPositions': [{'position': {'coin': 'AAA', 'szi': '1', 'unrealizedPnl': '2'}}]},
        {'assetPositions': []},
    )

    assert result['configured_pair_count'] == 2
    assert result['active_pair_count'] == 0
