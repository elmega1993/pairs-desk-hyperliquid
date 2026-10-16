from fastapi.testclient import TestClient

import read_only_server as server


def test_scanner_endpoint_is_read_only_and_passes_filters(monkeypatch):
    calls = {}

    class Result:
        def to_dict(self):
            return {'interval': '1h', 'candidates': [], 'total': 0, 'as_of_ms': 123}

    class FakeScanner:
        def __init__(self, catalog, store):
            calls['constructed'] = (catalog, store)

        def scan(self, **kwargs):
            calls['scan'] = kwargs
            return Result()

    monkeypatch.setattr(server, 'MarketScanner', FakeScanner)

    response = TestClient(server.app).get('/api/scanner?interval=1h&search=ETH&venue=core&limit=10')

    assert response.status_code == 200
    assert response.json()['as_of_ms'] == 123
    assert calls['scan'] == {'interval': '1h', 'search': 'ETH', 'venue': 'core', 'limit': 10}


def test_scanner_endpoint_rejects_invalid_limit():
    response = TestClient(server.app).get('/api/scanner?limit=0')

    assert response.status_code == 400
