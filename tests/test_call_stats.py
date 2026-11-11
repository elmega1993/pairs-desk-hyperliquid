from fastapi.testclient import TestClient

import read_only_server as server


def test_call_stats_records_local_api_request_without_sensitive_fields():
    with server._api_stats_lock:
        server._api_stats['http'].clear()
        server._api_stats['hyperliquid'].clear()

    client = TestClient(server.app)
    # The snapshot precedes middleware accounting of this request.
    first = client.get('/api/diagnostics/call-stats')
    assert first.status_code == 200
    assert '/api/diagnostics/call-stats' not in first.json()['http']
    response = client.get('/api/diagnostics/call-stats')

    assert response.status_code == 200
    data = response.json()
    assert data['http']['/api/diagnostics/call-stats']['count'] == 1
    assert data['http']['/api/diagnostics/call-stats']['avg_ms'] >= 0
    assert data['hyperliquid'] == {}
    assert not any('payload' in key or 'address' in key for key in data)


def test_hyperliquid_counter_groups_by_operation_and_venue(monkeypatch):
    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {'ok': True}

    monkeypatch.setattr(server._http, 'post', lambda *args, **kwargs: Response())
    with server._api_stats_lock:
        server._api_stats['hyperliquid'].clear()

    assert server.hl({'type': 'clearinghouseState', 'user': 'private', 'dex': 'xyz'}) == {'ok': True}

    row = server._api_stats['hyperliquid']['clearinghouseState:xyz']
    assert row['count'] == 1
    assert row['errors'] == 0
