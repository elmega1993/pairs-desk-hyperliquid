"""Deterministic comparisons for operation-learning rows."""
from __future__ import annotations

import math
from collections import defaultdict
from statistics import median
from typing import Any


def _stats(values: list[float], min_sample: int) -> dict[str, Any]:
    n = len(values)
    if not n:
        return {'n': 0, 'status': 'unavailable'}
    result = {
        'n': n,
        'status': 'ok' if n >= min_sample else 'insufficient_sample',
        'wins': sum(value > 0 for value in values),
        'win_rate': sum(value > 0 for value in values) / n,
        'pnl_sum_usd': sum(values),
        'pnl_median_usd': median(values),
    }
    return result


def _verified(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get('data_quality') == 'verificada'
            and isinstance(row.get('net_pnl_usd'), (int, float))
            and math.isfinite(float(row['net_pnl_usd']))]


def _grouped_stats(rows: list[dict[str, Any]], key_fn, min_sample: int) -> list[dict[str, Any]]:
    groups: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        key = key_fn(row)
        if key is not None:
            groups[str(key)].append(float(row['net_pnl_usd']))
    return [{'group': key, **_stats(values, min_sample)} for key, values in sorted(groups.items())]


def summarize_learning(rows: list[dict[str, Any]], min_sample: int = 10) -> dict[str, Any]:
    verified = _verified(rows)
    values = [float(row['net_pnl_usd']) for row in verified]
    by_pair_values: dict[str, list[float]] = defaultdict(list)
    for row in verified:
        by_pair_values[f"{row.get('long', '')}|{row.get('short', '')}"].append(float(row['net_pnl_usd']))
    by_pair = [{'pair': pair, **_stats(values, min_sample)} for pair, values in sorted(by_pair_values.items())]
    by_duration = _grouped_stats(
        verified,
        lambda row: ('<1d' if float(row['duration_days']) < 1 else '1-3d' if float(row['duration_days']) <= 3 else '>3d')
        if isinstance(row.get('duration_days'), (int, float)) else None,
        min_sample,
    )
    by_entry_ratio = _grouped_stats(
        verified,
        lambda row: round(float(row['entry_ratio']), 1) if isinstance(row.get('entry_ratio'), (int, float)) else None,
        min_sample,
    )
    by_management = {}
    for label, predicate in [('without_events', lambda row: not row.get('management_event_count')), ('with_events', lambda row: row.get('management_event_count', 0) > 0)]:
        management_values = [float(row['net_pnl_usd']) for row in verified if predicate(row)]
        by_management[label] = _stats(management_values, min_sample)
    summary = _stats(values, min_sample)
    summary.update({'n_rows': len(rows), 'n_verified': len(verified),
                    'expectancy_usd': sum(values) / len(values) if values else None,
                    'median_pnl_usd': median(values) if values else None})
    rules = []
    for item in by_pair:
        rules.append({
            'name': f"pair={item['pair']}",
            'condition': {'pair': item['pair']},
            'status': item['status'],
            'n': item['n'],
            'win_rate': item.get('win_rate'),
            'pnl_median_usd': item.get('pnl_median_usd'),
            'pnl_sum_usd': item.get('pnl_sum_usd'),
            'counterexamples': item['n'] - item.get('wins', 0),
        })
    pct_values = [float(row['pnl_pct_gross']) for row in rows
                  if isinstance(row.get('pnl_pct_gross'), (int, float)) and math.isfinite(float(row['pnl_pct_gross']))]
    return {
        'summary': summary,
        'entry': {'status': 'descriptive_only', 'n_verified': len(verified)},
        'management': {'status': 'unavailable_without_event_effects'},
        'pair_context': {'status': 'descriptive', 'n_verified': len(verified)},
        'by_pair': by_pair,
        'by_duration': by_duration,
        'by_entry_ratio': by_entry_ratio,
        'by_management': by_management,
        'enrichment': {
            'entry_notional_coverage': sum(row.get('entry_gross_notional_usd') is not None for row in rows),
            'close_ratio_coverage': sum(row.get('close_ratio') is not None for row in rows),
            'pnl_pct_coverage': len(pct_values),
            'pnl_pct_median': median(pct_values) if pct_values else None,
        },
        'candidate_rules': rules,
    }
