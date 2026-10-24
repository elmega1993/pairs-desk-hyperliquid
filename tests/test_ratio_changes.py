import pandas as pd
import pytest

from pairs_desk.ratio_changes import ratio_change_pct, ratio_changes_from_bars


def test_ratio_change_pct_handles_direction_and_invalid_reference():
    assert ratio_change_pct(110, 100) == pytest.approx(10.0)
    assert ratio_change_pct(90, 100) == pytest.approx(-10.0)
    assert ratio_change_pct(110, 0) is None
    assert ratio_change_pct(None, 100) is None


def test_ratio_changes_uses_exact_or_latest_previous_ratio_close():
    now = 2_000_000_000
    hour = 3_600_000
    bars = pd.DataFrame(
        {
            "c": [100.0, 105.0, 102.0, 100.0],
        },
        index=pd.to_datetime(
            [
                now - 24 * hour,
                now - hour,
                now - hour - 60_000,
                now - 24 * hour - 60_000,
            ],
            unit="ms",
            utc=True,
        ),
    )

    result = ratio_changes_from_bars(110.0, bars, now)

    assert result["1h"] == pytest.approx(4.761904761904762)
    assert result["24h"] == pytest.approx(10.0)


def test_ratio_changes_returns_none_without_enough_history():
    now = 2_000_000_000
    bars = pd.DataFrame(
        {"c": [100.0]},
        index=pd.to_datetime([now - 30 * 60_000], unit="ms", utc=True),
    )

    assert ratio_changes_from_bars(110.0, bars, now) == {"1h": None, "24h": None}
    assert ratio_changes_from_bars(None, bars, now) == {"1h": None, "24h": None}
