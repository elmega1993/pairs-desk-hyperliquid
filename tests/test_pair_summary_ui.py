from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_pair_summary_contains_only_operational_values():
    source = (BASE / 'react_frontend/src/components/PositionSummary.tsx').read_text()
    for label in ('Nominal long', 'Nominal short', 'Exposición total', 'PNL flotante', 'PNL realizado', 'PNL neto', 'Funding', 'Comisiones'):
        assert label in source
    assert 'pair.long_pnl' in source and 'pair.short_pnl' in source
    assert 'tone(value)' in source
    assert 'Analítica del par' not in source


def test_app_uses_compact_pair_summary():
    source = (BASE / 'react_frontend/src/App.tsx').read_text()
    assert "import {PositionSummary}" in source
    assert '<PositionSummary pair={pair||null}/>' in source
    assert '<PairDetail' not in source


def test_pair_summary_puts_exposure_first_and_keeps_leg_pnl_on_symbol_rows():
    source = (BASE / 'react_frontend/src/components/PositionSummary.tsx').read_text()
    assert "['Exposición total',pair.size,true" in source
    assert "`LONG ${pair.long}`" in source
    assert "`SHORT ${pair.short}`" in source
    assert "pair.long_pnl" in source and "pair.short_pnl" in source


if __name__ == '__main__':
    test_pair_summary_contains_only_operational_values()
    test_app_uses_compact_pair_summary()
    test_pair_summary_puts_exposure_first_and_keeps_leg_pnl_on_symbol_rows()
