from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
SRC = BASE / 'react_frontend/src'


def test_positions_list_is_compact_and_keeps_only_requested_metrics():
    source = (SRC / 'components/PositionList.tsx').read_text()
    assert 'position-ratio-change' in source
    assert "'1h'" in source and "'24h'" in source
    assert 'money(p.size)' not in source
    assert 'liq.' not in source
    assert 'position-filters' in source
    assert '<select' in source


def test_dashboard_promotes_actions_and_puts_bottom_panels_side_by_side():
    app = (SRC / 'App.tsx').read_text()
    css = (SRC / 'style.css').read_text()
    assert 'bottom-grid' in app
    assert '.main>header>div:first-child' in css
    assert '.bottom-grid' in css
    assert '.quick-actions' in css
