from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_pair_summary_contains_only_operational_values():
    source = (BASE / 'react_frontend/src/components/PositionSummary.tsx').read_text()
    for label in ('Nominal long', 'Nominal short', 'Exposición total', 'PNL flotante', 'PNL long', 'PNL short', 'PNL realizado', 'PNL neto', 'Funding', 'Comisiones'):
        assert label in source
    assert 'tone(value)' in source
    assert 'Analítica del par' not in source


def test_app_uses_compact_pair_summary():
    source = (BASE / 'react_frontend/src/App.tsx').read_text()
    assert "import {PositionSummary}" in source
    assert '<PositionSummary pair={pair||null}/>' in source
    assert '<PairDetail' not in source
