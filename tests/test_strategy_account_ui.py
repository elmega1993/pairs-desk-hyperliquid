from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_pnl_chart_can_use_strategy_daily_rows_without_visible_events():
    chart = (BASE / 'react_frontend/src/PnlChart.tsx').read_text()
    daily = (BASE / 'react_frontend/src/components/DailyPnlPanel.tsx').read_text()
    assert 'daily?:DailyPnlRow[]' in chart
    assert 'eventsVisible?:boolean' in chart
    assert 'daily={props.daily}' in chart
    assert 'daily?:DailyPnlRow[]' in daily
    assert 'eventsVisible' in chart


def test_strategy_chart_periods_filter_only_the_visible_curve():
    model = (BASE / 'react_frontend/src/pnlModel.ts').read_text()
    assert 'filterPnlRange' in model
    assert 'start_ms' in model or 'startTime' in model


def test_strategy_account_view_exposes_independent_daily_panel_and_roi_stats():
    app = (BASE / 'react_frontend/src/App.tsx').read_text()
    view = (BASE / 'react_frontend/src/components/StrategyAccount.tsx').read_text()
    types = (BASE / 'react_frontend/src/types.ts').read_text()
    assert 'Cuenta / Estrategia' in app
    assert 'StrategyAccount' in app
    assert 'strategy' in types
    assert 'ROI desde el inicio' in view
    assert 'Funding proyectado' in view
    assert 'Funding histórico' in view
    assert "timeZone:'UTC'" in view
    assert 'dailyRows=reconstructed?strategy.reconstructed_daily!:strategy.daily' in view
    assert 'daily={dailyRows}' in view
    assert 'eventsVisible={false}' in view
    assert 'filterPnlRange(strategy.history,period)' in view
