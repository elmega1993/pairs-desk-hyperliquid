from pathlib import Path
from fastapi.testclient import TestClient
from read_only_server import app
BASE=Path(__file__).resolve().parents[1]

def test_pnl_components_have_separate_labels():
    html=(BASE/'aurora/index.html').read_text()
    for x in ('PNL NO REALIZADO','PNL REALIZADO','PNL NETO TOTAL','kpi-unrealized','kpi-realized','pnl-breakdown'):
        assert x in html

def test_ui_uses_floating_pnl_for_open_positions():
    js=(BASE/'aurora/aurora.js').read_text()
    assert 'pnl.textContent=money(p.pnl)' in js
    assert 'put("pair-pnl",money(pair.pnl),pair.pnl)' in js
    assert 'money(s.realized)' in js and 'money(s.unrealized)' in js
    assert '/api/trade' not in js

def test_aurora_routes_still_available():
    c=TestClient(app)
    assert c.get('/aurora').status_code==200
    assert c.get('/').status_code==200
