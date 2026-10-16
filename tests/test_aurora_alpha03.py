from pathlib import Path
from fastapi.testclient import TestClient
from read_only_server import app

BASE = Path(__file__).resolve().parents[1]

def test_aurora_page_and_assets():
    client = TestClient(app)
    page = client.get('/aurora')
    assert page.status_code == 200
    for token in ('pair-search', 'pair-sort', 'chart-metrics', 'radar-body', 'favorite'):
        assert token in page.text
    assert client.get('/aurora/assets/aurora.css').status_code == 200
    assert client.get('/aurora/assets/aurora.js').status_code == 200
    assert client.get('/').status_code == 200

def test_aurora_is_read_only():
    text = (BASE / 'aurora' / 'aurora.js').read_text()
    assert "fetch('/api/chart/" in text
    assert 'fetch("/api/state"' in text
    assert '/api/trade' not in text
    assert '/api/execute' not in text
