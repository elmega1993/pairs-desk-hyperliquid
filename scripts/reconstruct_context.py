#!/usr/bin/env python3
"""Fetch public candles and reconstruct entry/MAE/MFE context for closed pairs."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pairs_desk.context_analysis import analyze_event_context, analyze_ratio_context
from pairs_desk.context_fetch import api_coin, safe_cache_name
from pairs_desk.learning_data import DataPaths, load_learning_snapshot
from pairs_desk.market_quality import normalize_candles
from pairs_desk.operation_learning import build_operation_rows
from pairs_desk.storage import load_settings

API = 'https://api.hyperliquid.xyz/info'
DAY_MS = 86_400_000


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=2, connect=2, read=2, backoff_factor=0.5,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=frozenset({'POST'}))
    session.mount('https://', HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=8))
    return session


def _parse_args() -> argparse.Namespace:
    home = Path.home()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, default=home / '.config/crypto-pairs-desk/settings.json')
    parser.add_argument('--ledger', type=Path, default=home / '.local/share/crypto-pairs-desk/ledger.sqlite3')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--days-before-entry', type=int, default=120)
    parser.add_argument('--workers', type=int, default=6)
    return parser.parse_args()


def _fetch_one(session: requests.Session, coin: str, start: int, end: int, cache_dir: Path) -> tuple[str, list[dict], str | None]:
    path = cache_dir / f'{safe_cache_name(coin)}.json'
    try:
        if path.exists():
            rows = json.loads(path.read_text())
        else:
            response = session.post(API, json={'type': 'candleSnapshot', 'req': {
                'coin': coin, 'interval': '1d', 'startTime': start, 'endTime': end,
            }}, timeout=(4, 20))
            response.raise_for_status()
            rows = response.json()
            if not isinstance(rows, list):
                raise ValueError('respuesta de velas no es una lista')
            cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_text(json.dumps(rows, separators=(',', ':')))
        return coin, [row for row in rows if isinstance(row, dict)], None
    except Exception as exc:
        return coin, [], f'{type(exc).__name__}: {exc}'


def _frame(rows: list[dict], coin: str) -> pd.DataFrame:
    venue, separator, symbol = coin.partition(':')
    venue = venue if separator else 'core'
    symbol = symbol if separator else coin
    instrument = f'{venue}:{symbol}'
    return normalize_candles(rows, instrument, venue, '1d') if rows else pd.DataFrame()


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = _parse_args()
    if args.days_before_entry < 0 or args.workers < 1:
        raise SystemExit('days-before-entry y workers deben ser positivos')
    settings, settings_error = load_settings(args.settings)
    if settings_error:
        raise SystemExit(f'settings inválido: {settings_error}')
    snapshot = load_learning_snapshot(DataPaths(settings=args.settings, ledger=args.ledger))
    base_rows = build_operation_rows(snapshot)
    closed = snapshot.closed_pairs
    if not closed:
        raise SystemExit('No hay pares cerrados')
    start = min(int(row['opened_at']) for row in closed if row.get('opened_at')) - args.days_before_entry * DAY_MS
    end = max(int(row['closed_at']) for row in closed if row.get('closed_at')) + DAY_MS
    coins = sorted({api_coin(coin) for row in closed for coin in (row.get('long'), row.get('short')) if coin})
    cache_dir = args.output / 'candles'
    frames: dict[str, pd.DataFrame] = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_fetch_one, _session(), coin, start, end, cache_dir) for coin in coins]
        for future in as_completed(futures):
            coin, raw, error = future.result()
            if error:
                errors[coin] = error
            else:
                try:
                    frames[coin] = _frame(raw, coin)
                except Exception as exc:
                    errors[coin] = f'{type(exc).__name__}: {exc}'

    enriched = []
    event_rows = []
    for item, row in zip(closed, base_rows):
        long_coin, short_coin = api_coin(item['long']), api_coin(item['short'])
        context = analyze_ratio_context(
            frames.get(long_coin, pd.DataFrame()), frames.get(short_coin, pd.DataFrame()),
            int(item.get('opened_at') or 0), int(item.get('closed_at') or 0), row.get('entry_ratio'),
        )
        enriched.append({**row, **context})
        for event in item.get('events') or []:
            if not isinstance(event, dict):
                continue
            event_context = analyze_event_context(
                frames.get(long_coin, pd.DataFrame()), frames.get(short_coin, pd.DataFrame()),
                int(event.get('time') or 0), int(item.get('closed_at') or 0), row.get('entry_ratio'),
            )
            event_rows.append({
                'id': row['id'], 'pair': f"{item.get('long')}|{item.get('short')}",
                'kind': event.get('kind') or event.get('event'), 'time': event.get('time'),
                'amount_usd': event.get('amount'), 'realized_usd': event.get('realized'),
                **event_context,
            })
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    _write_csv(args.output / 'historical_context.csv', enriched)
    _write_csv(args.output / 'historical_events.csv', event_rows)
    (args.output / 'historical_context.json').write_text(json.dumps(enriched, indent=2, sort_keys=True, allow_nan=False) + '\n')
    (args.output / 'historical_events.json').write_text(json.dumps(event_rows, indent=2, sort_keys=True, allow_nan=False) + '\n')
    coverage = {
        'pairs': len(enriched), 'context_ok': sum(row['status'] == 'ok' for row in enriched),
        'entry_zscore': sum(row['entry_zscore'] is not None for row in enriched),
        'mae': sum(row['mae_pct'] is not None for row in enriched),
        'mfe': sum(row['mfe_pct'] is not None for row in enriched),
        'close_ratio': sum(row['close_ratio'] is not None for row in enriched),
        'events': len(event_rows), 'event_context_ok': sum(row['status'] == 'ok' for row in event_rows),
        'candles': len(frames), 'candle_errors': errors,
        'days_before_entry': args.days_before_entry,
    }
    (args.output / 'coverage.json').write_text(json.dumps(coverage, indent=2, sort_keys=True) + '\n')
    print(json.dumps({key: value for key, value in coverage.items() if key != 'candle_errors'}, sort_keys=True))
    for coin, error in sorted(errors.items()):
        print(f'warning[{coin}]={error}', file=sys.stderr)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
