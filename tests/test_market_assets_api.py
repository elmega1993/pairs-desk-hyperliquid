from fastapi.testclient import TestClient

import read_only_server as server


def test_assets_endpoint_returns_live_universe(monkeypatch):
    class FakeService:
        def __init__(self, fetch, catalog):
            pass

        def list_assets(self):
            return [type('Asset', (), {'to_dict': lambda self: {'instrument_id': 'core:HYPE', 'symbol': 'HYPE', 'venue': 'core', 'active': True}})()]

    monkeypatch.setattr(server, 'AssetUniverseService', FakeService)

    response = TestClient(server.app).get('/api/scanner/assets?search=hype')

    assert response.status_code == 200
    assert response.json()['assets'][0]['instrument_id'] == 'core:HYPE'
