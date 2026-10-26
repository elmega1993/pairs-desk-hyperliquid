from pairs_desk.learning_data import LearningSnapshot, SourceStatus
from pairs_desk.operation_learning import build_operation_rows


def closed(**overrides):
    row = {
        'id': 'AAA|BBB', 'long': 'AAA', 'short': 'BBB',
        'opened_at': 1_000, 'closed_at': 86_401_000,
        'realized': 12.0, 'fees': 1.0, 'funding': -2.0,
        'funding_complete': True, 'total_pnl': 9.0,
        'entry_ratio': 1.1, 'events': [{'event': 'tp'}],
    }
    row.update(overrides)
    return row


def test_verified_operation_contains_net_result_and_duration():
    snapshot = LearningSnapshot(
        closed_pairs=[closed()],
        fills=[{'coin': 'AAA', 'time': 1_000}, {'coin': 'BBB', 'time': 1_000}],
        sources={'ledger': SourceStatus(available=True, rows=2)},
    )

    rows = build_operation_rows(snapshot)

    assert rows[0]['data_quality'] == 'verificada'
    assert rows[0]['duration_days'] == 1
    assert rows[0]['net_pnl_usd'] == 9.0
    assert rows[0]['management_event_count'] == 1


def test_incomplete_funding_is_partial_not_verified():
    snapshot = LearningSnapshot(closed_pairs=[closed(funding_complete=False)])

    row = build_operation_rows(snapshot)[0]

    assert row['data_quality'] == 'parcial'
    assert 'funding_incomplete' in row['quality_reasons']


def test_invalid_timestamps_are_not_comparable():
    snapshot = LearningSnapshot(closed_pairs=[closed(opened_at=10, closed_at=9)])

    row = build_operation_rows(snapshot)[0]

    assert row['data_quality'] == 'no comparable'
    assert 'invalid_interval' in row['quality_reasons']


def test_close_events_are_not_counted_as_management():
    snapshot = LearningSnapshot(closed_pairs=[closed(events=[{'kind': 'close'}])])

    row = build_operation_rows(snapshot)[0]

    assert row['management_event_count'] == 0


def test_operation_enriches_notionals_close_ratio_and_pnl_percent():
    snapshot = LearningSnapshot(
        closed_pairs=[closed()],
        fills=[
            {'coin': 'AAA', 'time': 1_000, 'side': 'B', 'startPosition': '0', 'px': '10', 'sz': '10'},
            {'coin': 'BBB', 'time': 1_000, 'side': 'A', 'startPosition': '0', 'px': '5', 'sz': '20'},
            {'coin': 'AAA', 'time': 86_401_000, 'side': 'A', 'startPosition': '10', 'px': '11', 'sz': '10'},
            {'coin': 'BBB', 'time': 86_401_000, 'side': 'B', 'startPosition': '-20', 'px': '4.5', 'sz': '20'},
        ],
    )

    row = build_operation_rows(snapshot)[0]

    assert row['entry_gross_notional_usd'] == 200.0
    assert row['close_ratio'] == 11 / 4.5
    assert row['pnl_pct_gross'] == 4.5
