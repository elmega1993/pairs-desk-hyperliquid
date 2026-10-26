#!/usr/bin/env python3
"""Generate a local, redacted retrospective operation report."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pairs_desk.learning_data import DataPaths, load_learning_snapshot
from pairs_desk.learning_metrics import summarize_learning
from pairs_desk.operation_learning import build_operation_rows
from pairs_desk.reconciliation import fetch_reconciliation
from pairs_desk.storage import load_settings


def _args() -> argparse.Namespace:
    home = Path.home()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, default=home / '.config/crypto-pairs-desk/settings.json')
    parser.add_argument('--ledger', type=Path, default=home / '.local/share/crypto-pairs-desk/ledger.sqlite3')
    parser.add_argument('--orders', type=Path, default=home / '.local/share/crypto-pairs-desk/orders.sqlite3')
    parser.add_argument('--market', type=Path, default=home / '.local/share/crypto-pairs-desk/market.sqlite3')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--min-sample', type=int, default=10)
    parser.add_argument('--skip-live', action='store_true', help='No consultar el estado actual de Hyperliquid')
    return parser.parse_args()


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = [
        'id', 'long', 'short', 'opened_at', 'closed_at', 'duration_days',
        'entry_ratio', 'close_ratio', 'realized_pnl_usd', 'fees_usd',
        'entry_long_notional_usd', 'entry_short_notional_usd',
        'entry_gross_notional_usd', 'pnl_pct_gross', 'funding_usd',
        'net_pnl_usd', 'won', 'management_event_count', 'data_quality',
        'quality_reasons', 'enrichment_reasons',
    ]
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            clean = dict(row)
            clean['quality_reasons'] = ';'.join(clean.get('quality_reasons') or [])
            clean['enrichment_reasons'] = ';'.join(clean.get('enrichment_reasons') or [])
            writer.writerow({field: clean.get(field) for field in fields})


def _write_markdown(path: Path, snapshot, summary: dict, reconciliation: dict) -> None:
    s = summary['summary']
    lines = [
        '# Análisis retrospectivo de operaciones', '',
        '> Informe local generado desde fuentes locales. No contiene la dirección de cuenta ni fills crudos.', '',
        '## Resumen', '',
        f"- Filas archivadas: {s['n_rows']}",
        f"- Operaciones verificadas: {s['n_verified']}",
        f"- Win rate: {s.get('win_rate') if s.get('status') == 'ok' else 'muestra insuficiente'}",
        f"- PNL medio: {s.get('expectancy_usd')}",
        f"- PNL mediano: {s.get('median_pnl_usd')}", '',
        '## Cobertura de enriquecimiento', '',
        f"- Nocional inicial: {summary['enrichment']['entry_notional_coverage']}",
        f"- Ratio de salida: {summary['enrichment']['close_ratio_coverage']}",
        f"- PNL porcentual: {summary['enrichment']['pnl_pct_coverage']}",
        f"- Mediana de PNL porcentual: {summary['enrichment']['pnl_pct_median']}", '',
        '## Reconciliación de cuenta', '',
        f"- Pares configurados: {reconciliation.get('configured_pair_count', 'N/D')}",
        f"- Pares activos con ambas patas: {reconciliation.get('active_pair_count', 'N/D')}",
        f"- PNL flotante activo: {reconciliation.get('active_unrealized_usd', 'N/D')}",
        f"- PNL Hyperliquid últimos 30 días: {(reconciliation.get('pnl_windows') or {}).get('30d_usd', 'N/D')}", '',
        '## Calidad de fuentes', '',
    ]
    for name, status in snapshot.sources.items():
        state = 'disponible' if status.available else 'no disponible'
        detail = f" ({status.error})" if status.error else ''
        lines.append(f'- {name}: {state}, {status.rows} filas{detail}')
    lines += ['', '## Reglas candidatas', '']
    for rule in summary['candidate_rules']:
        lines.append(f"- `{rule['name']}` — {rule['status']}, n={rule['n']}, win rate={rule.get('win_rate')}")
    lines += ['', '## Limitaciones', '',
              '- Las reglas con menos de 10 casos no se consideran concluyentes.',
              '- Las filas parciales se conservan, pero no entran en las comparaciones verificadas.',
              '- Los efectos de ADD/TP requieren reconstrucción adicional con velas históricas.']
    path.write_text('\n'.join(lines) + '\n')


def main() -> int:
    args = _args()
    if args.min_sample < 1:
        raise SystemExit('--min-sample debe ser positivo')
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    snapshot = load_learning_snapshot(DataPaths(args.settings, args.ledger, args.orders, args.market))
    rows = build_operation_rows(snapshot)
    summary = summarize_learning(rows, min_sample=args.min_sample)
    reconciliation = {'status': 'skipped'}
    if not args.skip_live:
        try:
            live_settings, settings_error = load_settings(args.settings)
            if settings_error:
                raise ValueError(settings_error)
            reconciliation = fetch_reconciliation(live_settings)
            reconciliation['status'] = 'live'
        except Exception as exc:
            reconciliation = {'status': 'unavailable', 'error': type(exc).__name__}
    _write_csv(args.output / 'operations.csv', rows)
    report = {'summary': summary, 'reconciliation': reconciliation}
    (args.output / 'summary.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
    (args.output / 'reconciliation.json').write_text(json.dumps(reconciliation, indent=2, sort_keys=True, allow_nan=False) + '\n')
    _write_markdown(args.output / 'summary.md', snapshot, summary, reconciliation)
    print(f'rows={len(rows)} verified={summary["summary"]["n_verified"]} output={args.output}')
    for name, status in snapshot.sources.items():
        if status.error:
            print(f'warning[{name}]={status.error}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
