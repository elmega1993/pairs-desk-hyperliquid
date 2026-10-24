from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_daily_pnl_panel_is_hyperliquid_only_and_responsive():
    chart = (BASE / "react_frontend/src/PnlChart.tsx").read_text()
    panel = (BASE / "react_frontend/src/components/DailyPnlPanel.tsx").read_text()
    styles = (BASE / "react_frontend/src/style.css").read_text()

    assert "DailyPnlPanel" in chart
    assert "dailyPnl" in panel
    assert "PNL diario" in panel
    assert "Hyperliquid" in panel
    assert "daily-pnl-panel" in styles
    assert "daily-pnl-row" in styles
