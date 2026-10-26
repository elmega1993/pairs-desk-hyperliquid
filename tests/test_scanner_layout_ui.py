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
