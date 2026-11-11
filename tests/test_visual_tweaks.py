from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def test_summary_keeps_nominals_neutral_and_tones_only_operational_flows():
    source = (BASE / 'react_frontend/src/components/PositionSummary.tsx').read_text()
    assert "['Nominal long',pair.long_usd,true,false]" in source
    assert "['Nominal short',pair.short_usd,true,false]" in source
    assert "label==='Exposición total'||label==='Nominal long'||label==='Nominal short'?'neutral':label==='Comisiones'?expenseTone(value):numeric?tone(value):''" in source


def test_visual_tweaks_keep_mini_chart_on_unrealized_and_event_labels_transparent():
    kpis = (BASE / 'react_frontend/src/components/PortfolioKpis.tsx').read_text()
    chart = (BASE / 'react_frontend/src/RatioChart.tsx').read_text()
    assert "idx===0||idx===1" in kpis
    assert 'unrealizedSeries' in kpis
    assert "event.kind==='add'?'#3ddc97':'#ff7b8f'" in chart
    assert "backgroundColor:'transparent'" in chart


def test_portfolio_kpis_use_compact_costs_and_decomposition_card():
    kpis = (BASE / 'react_frontend/src/components/PortfolioKpis.tsx').read_text()
    css = (BASE / 'react_frontend/src/style.css').read_text()
    assert 'COSTOS Y DESCOMPOSICIÓN' in kpis
    assert 'FUNDING HISTÓRICO' in kpis
    assert 'COMISIONES HISTÓRICAS' in kpis
    assert 'PNL LONGS' in kpis and 'PNL SHORTS' in kpis
    assert 'summary.account_funding' in kpis
    assert 'long_pnl' in kpis and 'short_pnl' in kpis
    assert 'kpi-breakdown' in kpis and '.kpi-breakdown' in css


def test_portfolio_kpis_group_account_and_risk_after_costs():
    kpis = (BASE / 'react_frontend/src/components/PortfolioKpis.tsx').read_text()
    css = (BASE / 'react_frontend/src/style.css').read_text()
    assert "['PNL NO REALIZADO',summary.unrealized" in kpis
    assert "[totalLabel,net" in kpis
    assert "['COSTOS Y DESCOMPOSICIÓN',null,null]" in kpis
    assert "CUENTA Y RIESGO" in kpis
    assert 'summary.account_value_total' in kpis
    assert 'MARGEN LIBRE' in kpis
    assert 'kpi-account-risk' in kpis and '.kpi-account-risk' in css


def test_portfolio_kpis_keep_total_before_costs_and_fallback_account_value():
    kpis = (BASE / 'react_frontend/src/components/PortfolioKpis.tsx').read_text()
    assert "['PNL NO REALIZADO',summary.unrealized,'Flotante de posiciones abiertas'],[totalLabel,net" in kpis
    assert "[totalLabel,net,official.fallback?'Fallback local · Hyperliquid sin serie':'Toda la cuenta · fuente oficial'],['COSTOS Y DESCOMPOSICIÓN',null,null]" in kpis
    assert 'const accountValue=summary.account_value_total??summary.equity_core' in kpis
    assert 'accountValue-summary.margin_used' in kpis


def test_commissions_use_expense_tone_in_every_react_accounting_view():
    fmt = (BASE / 'react_frontend/src/format.ts').read_text()
    kpis = (BASE / 'react_frontend/src/components/PortfolioKpis.tsx').read_text()
    summary = (BASE / 'react_frontend/src/components/PositionSummary.tsx').read_text()
    closed = (BASE / 'react_frontend/src/components/ClosedPairs.tsx').read_text()
    recon = (BASE / 'react_frontend/src/components/PnlReconciliation.tsx').read_text()
    assert 'export const expenseTone=' in fmt
    assert "expenseTone(itemValue)" in kpis
    assert "expenseTone(value)" in summary
    assert "expenseTone(p.fees)" in closed
    assert "expenseTone(p.value)" in recon


if __name__ == '__main__':
    test_summary_keeps_nominals_neutral_and_tones_only_operational_flows()
    test_visual_tweaks_keep_mini_chart_on_unrealized_and_event_labels_transparent()


def test_kpi_mini_chart_is_limited_to_24h_and_never_swaps_metric():
    kpis = (BASE / 'react_frontend/src/components/PortfolioKpis.tsx').read_text()
    chart = (BASE / 'react_frontend/src/components/PnlMiniChart.tsx').read_text()
    # la card de no realizado ya no cae al PNL total oficial cuando falta su serie
    assert 'unrealizedSeries.length>1?unrealizedSeries:official.series' not in kpis
    assert "hl_pnl as any)?.['1d']" in kpis
    assert 'buildMiniSeries' in chart and 'Sin historial suficiente de las últimas 24 h' in chart


def test_kpi_mini_chart_has_hover_cursor_with_date_and_pnl():
    chart = (BASE / 'react_frontend/src/components/PnlMiniChart.tsx').read_text()
    assert 'onPointerMove' in chart and 'onPointerLeave' in chart
    assert 'nearestRow' in chart and 'pnl-mini-cursor' in chart
    assert 'toLocaleString' in chart  # fecha y hora del punto bajo el mouse
