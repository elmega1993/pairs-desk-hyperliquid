from pathlib import Path


BASE = Path(__file__).resolve().parents[1]


def test_closed_pairs_places_ratio_change_between_close_and_realized():
    source = (BASE / 'react_frontend/src/components/ClosedPairs.tsx').read_text()
    assert "['DESDE CIERRE','ratio_since_close_pct']" in source
    assert "signedPct(p.ratio_since_close_pct)" in source
    assert "tone(p.ratio_since_close_pct)" in source


def test_closed_ratio_is_returned_by_account_state():
    source = (BASE / 'read_only_server.py').read_text()
    assert 'ratio_since_close_pct' in source
    assert "type':'allMids" in source
