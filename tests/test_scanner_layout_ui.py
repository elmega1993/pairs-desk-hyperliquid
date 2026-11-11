from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def test_scanner_keeps_analysis_chart_accessible_next_to_long_asset_table():
    css = (BASE / 'react_frontend/src/style.css').read_text()
    source = (BASE / 'react_frontend/src/components/Scanner.tsx').read_text()
    assert '.scanner-layout{display:grid' in css
    assert '.scanner-detail{position:sticky' in css
    assert '@media(max-width:760px)' in css
    assert 'bars.length>1&&<RatioChart' in source


if __name__ == '__main__':
    test_scanner_keeps_analysis_chart_accessible_next_to_long_asset_table()


def test_scanner_shows_24h_and_7d_changes_with_sort_and_volume_filter():
    source = (BASE / 'react_frontend/src/components/Scanner.tsx').read_text()
    assert '>24H' in source and '>7D' in source
    assert 'aria-label="Orden de activos"' in source and 'aria-label="Volumen mínimo 24h"' in source
    # el sondeo del progreso 7d solo consulta el servidor local y solo con la pestaña visible
    assert "document.visibilityState==='visible'" in source
    assert 'loadAssets(true)' in source
