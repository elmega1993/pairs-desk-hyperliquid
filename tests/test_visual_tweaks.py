from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def test_summary_keeps_nominals_neutral_and_tones_only_operational_flows():
    source = (BASE / 'react_frontend/src/components/PositionSummary.tsx').read_text()
    assert "['Nominal long',pair.long_usd,true,false]" in source
    assert "['Nominal short',pair.short_usd,true,false]" in source
    assert "label==='Exposición total'||label==='Nominal long'||label==='Nominal short'?'neutral':numeric?tone(value):''" in source


def test_visual_tweaks_keep_mini_chart_on_unrealized_and_event_labels_transparent():
    kpis = (BASE / 'react_frontend/src/components/PortfolioKpis.tsx').read_text()
    chart = (BASE / 'react_frontend/src/RatioChart.tsx').read_text()
    assert "idx===0||idx===2" in kpis
    assert 'unrealizedSeries' in kpis
    assert "event.kind==='add'?'#3ddc97':'#ff7b8f'" in chart
    assert "backgroundColor:'transparent'" in chart


if __name__ == '__main__':
    test_summary_keeps_nominals_neutral_and_tones_only_operational_flows()
    test_visual_tweaks_keep_mini_chart_on_unrealized_and_event_labels_transparent()
