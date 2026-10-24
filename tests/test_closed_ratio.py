import pytest

from pairs_desk.closed_ratio import close_ratio_from_fills, ratio_change_since_close


def test_close_ratio_uses_weighted_close_fills_for_both_legs():
    fills = [
        {'coin': 'LONG', 'time': 100, 'side': 'B', 'sz': '10', 'px': '2', 'startPosition': '0'},
        {'coin': 'SHORT', 'time': 110, 'side': 'A', 'sz': '10', 'px': '4', 'startPosition': '0'},
        {'coin': 'LONG', 'time': 900, 'side': 'A', 'sz': '5', 'px': '2.2', 'startPosition': '10'},
        {'coin': 'LONG', 'time': 910, 'side': 'A', 'sz': '5', 'px': '2.4', 'startPosition': '5'},
        {'coin': 'SHORT', 'time': 920, 'side': 'B', 'sz': '10', 'px': '3.5', 'startPosition': '-10'},
    ]
    assert close_ratio_from_fills('LONG', 'SHORT', fills, 100, 920) == pytest.approx(2.3 / 3.5)


def test_ratio_change_since_close_is_signed_and_explicit_when_missing():
    assert ratio_change_since_close(1.1, 1.0) == pytest.approx(10.0)
    assert ratio_change_since_close(0.9, 1.0) == pytest.approx(-10.0)
    assert ratio_change_since_close(1.1, None) is None
