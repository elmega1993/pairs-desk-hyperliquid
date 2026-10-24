from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
SRC = BASE / "react_frontend" / "src"


def test_react_loads_position_ratio_changes_periodically():
    app = (SRC / "App.tsx").read_text()
    api = (SRC / "api.ts").read_text()
    position_list = (SRC / "components" / "PositionList.tsx").read_text()

    assert "/api/position-ratio-changes" in api
    assert "fetchPositionRatioChanges" in app
    assert "60000" in app
    assert "document.visibilityState" in app
    assert "1h" in position_list and "24h" in position_list
    assert "Cambio del ratio" in position_list
    assert "tone(p.pnl)" in position_list
