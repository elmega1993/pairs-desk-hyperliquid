import json

import pytest
from fastapi.testclient import TestClient

import read_only_server as server
from pairs_desk.asset_changes import (
    DAY_MS, HOUR_MS, WEEK_MS, WeeklyReferenceStore, WeeklyReferenceWorker,
    attach_changes, coin_for, pct_change, priority_order, weekly_progress,
)

NOW = 1_800_000_000_000


class RateLimited(Exception):
    def __init__(self):
        self.response = type('R', (), {'status_code': 429})()


def make_worker(tmp_path, fetch, clock):
    return WeeklyReferenceWorker(WeeklyReferenceStore(tmp_path / 'refs.json'), fetch, interval_s=6, clock_ms=lambda: clock[0])


def test_pct_change_handles_invalid_inputs():
    assert pct_change(110, 100) == pytest.approx(10.0)
    assert pct_change(90, 100) == pytest.approx(-10.0)
    assert pct_change(None, 100) is None and pct_change(100, 0) is None and pct_change('x', 1) is None
    assert pct_change(float('nan'), 1) is None


def test_coin_names_match_candle_snapshot_convention():
    assert coin_for('core:BTC') == 'BTC'
    assert coin_for('xyz:MU') == 'xyz:MU'


def test_priority_skips_zero_volume_and_orders_by_liquidity():
    assets = [{'instrument_id': 'core:A', 'day_volume_usd': 10}, {'instrument_id': 'core:B', 'day_volume_usd': 0},
              {'instrument_id': 'core:C', 'day_volume_usd': 999}, {'instrument_id': 'core:D'}]
    assert priority_order(assets) == ['core:C', 'core:A']


def test_worker_makes_exactly_one_small_request_per_step(tmp_path):
    clock, calls = [NOW], []
    target = NOW - WEEK_MS

    def fetch(request):
        calls.append(request)
        return [{'t': target - HOUR_MS, 'o': '98'}, {'t': target, 'o': '100'}, {'t': target + HOUR_MS, 'o': '101'}]

    worker = make_worker(tmp_path, fetch, clock)
    assert worker.submit(['core:BTC', 'xyz:MU']) == 2

    assert worker.step() == 'ok'
    assert len(calls) == 1                                    # un solo request por paso
    req = calls[0]['req']
    assert req['coin'] == 'BTC' and req['interval'] == '1h'
    assert req['endTime'] - req['startTime'] == 3 * HOUR_MS   # ventana mínima (≈3 velas)
    assert worker.store.snapshot()['core:BTC']['ref_px'] == 100.0


def test_fresh_references_are_not_requested_again_until_ttl(tmp_path):
    clock, calls = [NOW], []
    target = NOW - WEEK_MS
    worker = make_worker(tmp_path, lambda r: calls.append(r) or [{'t': target, 'o': '100'}], clock)
    worker.submit(['core:BTC']); worker.step()

    assert worker.submit(['core:BTC']) == 0                   # recién pedido: no se vuelve a pedir
    clock[0] += 7 * HOUR_MS                                   # pasó el TTL de 6 h
    assert worker.submit(['core:BTC']) == 1


def test_new_listing_without_week_history_is_marked_and_retried_daily(tmp_path):
    clock = [NOW]
    worker = make_worker(tmp_path, lambda r: [], clock)
    worker.submit(['core:NEW']); assert worker.step() == 'empty'

    assert worker.submit(['core:NEW']) == 0
    clock[0] += DAY_MS + 1
    assert worker.submit(['core:NEW']) == 1


def test_rate_limit_backs_off_without_losing_the_asset(tmp_path):
    clock, calls = [NOW], []

    def fetch(request):
        calls.append(request)
        raise RateLimited()

    worker = make_worker(tmp_path, fetch, clock)
    worker.submit(['core:BTC'])

    assert worker.step() == 'rate_limited'
    assert worker.step() == 'paused' and len(calls) == 1      # en pausa: cero requests
    assert worker.pending_count() == 1
    clock[0] += 61_000
    assert worker.step() == 'rate_limited'                    # reintenta recién tras la pausa
    assert len(calls) == 2


def test_network_error_stores_nothing_so_no_fake_values(tmp_path):
    clock = [NOW]

    def fetch(request):
        raise ConnectionError('down')

    worker = make_worker(tmp_path, fetch, clock)
    worker.submit(['core:BTC'])
    assert worker.step() == 'error'
    assert worker.store.snapshot() == {}


def test_store_persists_between_restarts(tmp_path):
    WeeklyReferenceStore(tmp_path / 'r.json').put('core:BTC', ref_px=100.0, ref_ts_ms=NOW - WEEK_MS, fetched_ms=NOW)
    assert WeeklyReferenceStore(tmp_path / 'r.json').snapshot()['core:BTC']['ref_px'] == 100.0
    (tmp_path / 'r.json').write_text('{corrupto')
    assert WeeklyReferenceStore(tmp_path / 'r.json').snapshot() == {}


def test_attach_changes_uses_current_mark_and_ignores_stale_refs():
    assets = [{'instrument_id': 'core:A', 'mark_px': 110.0, 'prev_day_px': 100.0},
              {'instrument_id': 'core:B', 'mark_px': 50.0, 'prev_day_px': 100.0},
              {'instrument_id': 'core:C', 'mark_px': 50.0, 'prev_day_px': None}]
    refs = {'core:A': {'ref_px': 80.0, 'ref_ts_ms': NOW - WEEK_MS, 'fetched_ms': NOW},
            'core:B': {'ref_px': 80.0, 'ref_ts_ms': NOW - 9 * DAY_MS, 'fetched_ms': NOW - 9 * DAY_MS}}

    a, b, c = attach_changes(assets, refs, NOW)

    assert a['change_24h_pct'] == pytest.approx(10.0) and a['change_7d_pct'] == pytest.approx(37.5)
    assert b['change_24h_pct'] == pytest.approx(-50.0) and b['change_7d_pct'] is None   # referencia vencida
    assert c['change_24h_pct'] is None and c['change_7d_pct'] is None


def test_weekly_progress_counts_ready_unavailable_and_pending():
    refs = {'core:A': {'ref_px': 1.0, 'ref_ts_ms': NOW - WEEK_MS, 'fetched_ms': NOW},
            'core:B': {'ref_px': None, 'ref_ts_ms': None, 'fetched_ms': NOW}}
    assert weekly_progress(['core:A', 'core:B', 'core:C'], refs, NOW) == {'ready': 1, 'unavailable': 1, 'total': 3, 'pending': 1}


def test_endpoint_hits_hyperliquid_once_per_cache_window_and_exposes_changes(monkeypatch, tmp_path):
    monkeypatch.setenv('PAIRS_DESK_DISABLE_WEEKLY_REFS', '1')
    monkeypatch.setattr(server, '_ASSET_CACHE', {'at': 0.0, 'assets': None})
    monkeypatch.setattr(server, 'MARKET_DB', tmp_path / 'market.sqlite3')
    requests = []

    def fake_hl(request):
        requests.append(request)
        return [{'universe': [{'name': 'HYPE'}]}, [{'markPx': '44', 'prevDayPx': '40', 'dayNtlVlm': '1000'}]]

    monkeypatch.setattr(server, 'hl', fake_hl)
    client = TestClient(server.app)

    first = client.get('/api/scanner/assets').json()
    for _ in range(5):                                  # recargas / filtros del navegador
        client.get('/api/scanner/assets?search=hy')
    client.get('/api/scanner/assets?refresh=true')       # "Actualizar activos" pegado: tope de 10 s

    assert len(requests) == 2                            # core + xyz, una sola vez
    asset = first['assets'][0]
    assert asset['change_24h_pct'] == pytest.approx(10.0)
    assert asset['change_7d_pct'] is None
    assert first['week']['enabled'] is False and first['week']['total'] == 2  # core:HYPE y xyz:HYPE
