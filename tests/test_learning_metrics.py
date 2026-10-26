from pairs_desk.learning_metrics import summarize_learning


def row(pair, pnl, quality='verificada', duration=2, ratio=1.0):
    long, short = pair.split('|')
    return {
        'id': pair, 'long': long, 'short': short, 'net_pnl_usd': pnl,
        'data_quality': quality, 'duration_days': duration, 'entry_ratio': ratio,
    }


def test_summary_excludes_partial_rows_and_groups_by_pair():
    result = summarize_learning([row('A|B', 10), row('A|B', -2), row('C|D', 4, 'parcial')])

    assert result['summary']['n_verified'] == 2
    assert result['summary']['win_rate'] == 0.5
    assert result['by_pair'][0]['pair'] == 'A|B'
    assert result['by_pair'][0]['n'] == 2


def test_candidate_rules_mark_small_samples_unavailable():
    result = summarize_learning([row('A|B', 10)], min_sample=10)

    assert result['candidate_rules'][0]['status'] == 'insufficient_sample'
    assert result['candidate_rules'][0]['n'] == 1


def test_summary_reports_expectancy_and_median():
    result = summarize_learning([row('A|B', 10), row('A|B', -2), row('C|D', 4)] )

    assert result['summary']['expectancy_usd'] == 4.0
    assert result['summary']['median_pnl_usd'] == 4.0


def test_summary_compares_duration_entry_ratio_and_management():
    result = summarize_learning([
        row('A|B', 10, duration=0.5, ratio=1.04) | {'management_event_count': 0},
        row('C|D', -2, duration=2, ratio=1.16) | {'management_event_count': 1},
    ])

    assert result['by_duration']
    assert result['by_entry_ratio']
    assert result['by_management']['with_events']['n'] == 1


def test_summary_reports_phase_two_coverage():
    rows = [row('A|B', 10) | {'entry_gross_notional_usd': 200, 'close_ratio': 1.2, 'pnl_pct_gross': 5}]

    result = summarize_learning(rows)

    assert result['enrichment']['entry_notional_coverage'] == 1
    assert result['enrichment']['close_ratio_coverage'] == 1
    assert result['enrichment']['pnl_pct_median'] == 5
