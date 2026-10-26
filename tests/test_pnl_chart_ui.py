from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def test_pnl_chart_uses_ratio_palette_and_detailed_ticks():
    source = (BASE / 'react_frontend/src/PnlChart.tsx').read_text()
    assert "const POS='#3ddc97',NEG='#ff7b8f'" in source
    assert 'plotH<200?5:7' in source
    assert 'niceTicks(ddLow,0,4)' in source


if __name__ == '__main__':
    test_pnl_chart_uses_ratio_palette_and_detailed_ticks()
