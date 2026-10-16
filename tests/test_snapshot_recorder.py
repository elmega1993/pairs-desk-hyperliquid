"""El registrador en segundo plano cubre los huecos de snapshots sin duplicar los del navegador."""
import read_only_server as server


def test_records_when_last_snapshot_is_stale(monkeypatch):
    calls = []
    monkeypatch.setattr(server, 'local_pnl_history', lambda: [{'time': 1_000_000}])
    monkeypatch.setattr(server, 'states', lambda: calls.append(1))
    assert server.record_once(now_ms=1_000_000 + 120_000) is True
    assert calls == [1]


def test_records_when_there_is_no_history(monkeypatch):
    calls = []
    monkeypatch.setattr(server, 'local_pnl_history', lambda: [])
    monkeypatch.setattr(server, 'states', lambda: calls.append(1))
    assert server.record_once(now_ms=5) is True and calls == [1]


def test_skips_when_a_browser_just_recorded(monkeypatch):
    calls = []
    monkeypatch.setattr(server, 'local_pnl_history', lambda: [{'time': 1_000_000}])
    monkeypatch.setattr(server, 'states', lambda: calls.append(1))
    assert server.record_once(now_ms=1_000_000 + 30_000) is False
    assert calls == []

