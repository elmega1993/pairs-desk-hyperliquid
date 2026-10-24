from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_reconciliation_exposes_account_funding_separately():
    component = (BASE / "react_frontend/src/components/PnlReconciliation.tsx").read_text()
    server = (BASE / "read_only_server.py").read_text()
    assert "summary.account_funding" in component
    assert "Funding cuenta" in component
    assert "'account_funding':" in server
