"""Regression checks: Aurora must retain the stable chart's trade context."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_interactive_engine_is_local_and_loaded_before_aurora():
    html=(ROOT/'aurora'/'index.html').read_text()
    assert html.index('/vendor/klinecharts.min.js') < html.index('/aurora/assets/aurora-trading-chart.js') < html.index('/aurora/assets/aurora.js')
    assert (ROOT/'pairs_desk'/'vendor'/'klinecharts.min.js').is_file()
    assert '<div id="ratio-chart"' in html
    assert '<svg id="ratio-chart"' not in html

def test_management_levels_and_verified_trade_markers():
    js=(ROOT/'aurora'/'aurora-trading-chart.js').read_text()
    for token in ('management_entry_ratio','entry_history','entry_ratio','tp1_ratio_pct','tp2_ratio_pct','tp3_ratio_pct','add1_ratio_pct','add2_ratio_pct','pair.events','opened_at','scrollToRealTime','applyNewData'):
        assert token in js
    assert 'OBJETIVO' in js
    assert 'fetch(' not in js and '/api/trade/' not in js

def test_layer_controls_and_interaction():
    html=(ROOT/'aurora'/'index.html').read_text()
    for token in ('layer-average','layer-initial','layer-targets','layer-events','chart-reset'):
        assert f'id="{token}"' in html
    js=(ROOT/'aurora'/'aurora.js').read_text()
    assert 'AuroraTradingChart.draw(pair,bars)' in js
    assert 'AuroraTradingChart?.redraw()' in js
