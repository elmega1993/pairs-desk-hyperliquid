from fastapi.testclient import TestClient
import pytest

import read_only_server as server


NOW_MS = 2_000_000_000
ACCOUNT = "0x" + "a" * 40


def _settings():
    return {
        "address": ACCOUNT,
        "pairs": [{"long": "ETH", "short": "BTC"}],
    }


def _state():
    return {
        "assetPositions": [
            {"position": {"coin": "ETH", "szi": "1", "positionValue": "110"}},
            {"position": {"coin": "BTC", "szi": "-1", "positionValue": "-10"}},
        ]
    }


def test_position_ratio_changes_returns_one_hour_and_one_day_ratio_changes(monkeypatch):
    calls = []
    monkeypatch.setattr(server, "load_settings", lambda path: (_settings(), None))
    monkeypatch.setattr(server.time, "time", lambda: NOW_MS / 1000)

    def fake_hl(payload):
        calls.append(payload)
        if payload["type"] == "clearinghouseState":
            return _state()
        coin = payload["req"]["coin"]
        if coin == "ETH":
            return [
                {"t": NOW_MS - 86_400_000, "o": "10", "h": "10", "l": "10", "c": "10"},
                {"t": NOW_MS - 3_600_000, "o": "10.5", "h": "10.5", "l": "10.5", "c": "10.5"},
            ]
        return [
            {"t": NOW_MS - 86_400_000, "o": "1", "h": "1", "l": "1", "c": "1"},
            {"t": NOW_MS - 3_600_000, "o": "1", "h": "1", "l": "1", "c": "1"},
        ]

    monkeypatch.setattr(server, "hl", fake_hl)

    response = TestClient(server.app).get("/api/position-ratio-changes")

    assert response.status_code == 200
    result = response.json()["pairs"]["ETH|BTC"]
    assert result["1h"] == pytest.approx(4.761904761904762)
    assert result["24h"] == pytest.approx(10.0)
    assert sum(call["type"] == "candleSnapshot" for call in calls) == 2


def test_position_ratio_changes_returns_nd_when_one_leg_history_fails(monkeypatch):
    monkeypatch.setattr(server, "load_settings", lambda path: (_settings(), None))
    monkeypatch.setattr(server.time, "time", lambda: NOW_MS / 1000)

    def fake_hl(payload):
        if payload["type"] == "clearinghouseState":
            return _state()
        if payload["req"]["coin"] == "BTC":
            raise RuntimeError("historical data unavailable")
        return [
            {"t": NOW_MS - 86_400_000, "o": "10", "h": "10", "l": "10", "c": "10"},
            {"t": NOW_MS - 3_600_000, "o": "10.5", "h": "10.5", "l": "10.5", "c": "10.5"},
        ]

    monkeypatch.setattr(server, "hl", fake_hl)

    response = TestClient(server.app).get("/api/position-ratio-changes")

    assert response.status_code == 200
    assert response.json()["pairs"]["ETH|BTC"] == {"1h": None, "24h": None}
