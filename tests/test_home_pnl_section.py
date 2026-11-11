from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_home_does_not_mount_the_duplicate_total_pnl_section():
    app = (BASE / 'react_frontend/src/App.tsx').read_text()
    strategy = (BASE / 'react_frontend/src/components/StrategyAccount.tsx').read_text()

    assert 'Evolución del PNL total' not in app
    assert '<PnlChart' not in app
    assert '<PnlChart' in strategy
