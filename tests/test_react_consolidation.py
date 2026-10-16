from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
def test_react_no_legacy_chart_bridge():
    html=(BASE/'react_frontend/index.html').read_text()
    app=(BASE/'react_frontend/src/App.tsx').read_text()
    assert 'aurora-trading-chart.js' not in html
    assert 'AuroraTradingChart' not in app
    assert 'RatioChart' in app

def test_react_has_live_refresh_and_sortable_headers():
    app=(BASE/'react_frontend/src/App.tsx').read_text()
    assert '30000' in app
    assert 'visibilitychange' in app
    assert 'onSort={changeSort}' in app
    assert 'onClick={()=>onSort(key)}' in (BASE/'react_frontend/src/components/PositionRadar.tsx').read_text()
    assert 'aria-sort' in (BASE/'react_frontend/src/components/PositionRadar.tsx').read_text()

def test_chart_layers_not_read_from_dom():
    chart=(BASE/'react_frontend/src/RatioChart.tsx').read_text()
    assert 'getElementById' not in chart
    assert 'layers.average' in chart
    assert 'ResizeObserver' in chart
