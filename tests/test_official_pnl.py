import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import read_only_server as server


def test_official_pnl_uses_last_point_of_each_hyperliquid_window():
    windows = {
        '1d': [{'time': 1, 'pnl': 2.0}, {'time': 2, 'pnl': 7.5}],
        '7d': [],
        '30d': [{'time': 3, 'pnl': -366.0}],
        'all': [{'time': 4, 'pnl': 476.13}],
    }
    assert server.official_pnl_from_windows(windows) == {
        '1d': 7.5,
        '7d': None,
        '30d': -366.0,
        'all': 476.13,
    }


def test_official_pnl_does_not_fabricate_empty_windows():
    assert server.official_pnl_from_windows({}) == {
        '1d': None,
        '7d': None,
        '30d': None,
        'all': None,
    }


if __name__ == '__main__':
    test_official_pnl_uses_last_point_of_each_hyperliquid_window()
    test_official_pnl_does_not_fabricate_empty_windows()
