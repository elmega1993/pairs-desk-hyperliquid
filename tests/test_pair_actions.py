from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_pair_actions_has_expiry_guard_and_refresh_contract():
    source = (BASE / "react_frontend/src/components/PairActions.tsx").read_text()
    assert "remainingTicketSeconds" in source
    assert "isTicketExpired" in source
    assert "setInterval" in source
    assert "disabled={ticketExpired" in source
    assert "onAdded(pair.id)" in source


def test_pair_actions_handles_non_json_http_errors():
    source = (BASE / "react_frontend/src/components/PairActions.tsx").read_text()
    assert "Content-Type" in source
    assert "responseText" in source
    assert "HTTP ${r.status}" in source
