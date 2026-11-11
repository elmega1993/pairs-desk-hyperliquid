"""Public exchange observations for persisted native TWAPs, isolated by account."""
from __future__ import annotations

import json
import threading
import time

import websocket


class NativeTwapMonitor:
    def __init__(self, connect=None):
        self._connect = connect or websocket.create_connection
        self._lock = threading.RLock()
        self._account = None
        self._dex_as_of = {}
        self._stop = None
        self._thread = None
        self._socket = None
        self._status = {"connected": False, "as_of_ms": None, "error": None}

    def ensure(self, account, store):
        account = account.lower()
        with self._lock:
            if self._account == account and self._thread and self._thread.is_alive():
                return
            self.stop()
            self._account = account
            self._dex_as_of = {}
            self._stop = threading.Event()
            self._status = {"connected": False, "as_of_ms": None, "error": None}
            self._thread = threading.Thread(
                target=self._run, args=(account, store, self._stop),
                daemon=True, name="native-twap-observer",
            )
            self._thread.start()

    def stop(self):
        # Never join while holding this lock: the socket worker also publishes state.
        with self._lock:
            if self._stop:
                self._stop.set()
            if self._socket:
                try:
                    self._socket.close()
                except OSError:
                    pass
                self._socket = None

    def status(self, account, dexes=None):
        with self._lock:
            if account.lower() != self._account:
                return {"connected": False, "as_of_ms": None, "error": None}
            result = dict(self._status)
            required = set(dexes) if dexes is not None else {'', 'xyz'}
            stamps = [self._dex_as_of.get(dex) for dex in required]
            result['as_of_ms'] = min(stamps) if stamps and all(stamp is not None for stamp in stamps) else None
            return result

    @staticmethod
    def ingest(account, store, message, as_of_ms):
        channel = message.get("channel")
        data = message.get("data")
        if not isinstance(data, dict) or str(data.get("user", "")).lower() != account.lower():
            return False
        if channel == "twapStates":
            dex = data.get("dex", "")
            if dex not in ("", "xyz") or not isinstance(data.get("states"), list):
                return False
            store.ingest_state(account, dex, data["states"], as_of_ms)
        elif channel == "userTwapHistory":
            if not isinstance(data.get("history"), list):
                return False
            store.ingest_history(account, data["history"], as_of_ms)
        elif channel == "userTwapSliceFills":
            if not isinstance(data.get("twapSliceFills"), list):
                return False
            store.ingest_fills(account, data["twapSliceFills"], as_of_ms)
        else:
            return False
        return True

    def _run(self, account, store, stop):
        delay = 1
        while not stop.is_set():
            socket = None
            try:
                socket = self._connect("wss://api.hyperliquid.xyz/ws", timeout=10)
                with self._lock:
                    if self._stop is not stop:
                        return
                    self._socket = socket
                for dex in ("", "xyz"):
                    socket.send(json.dumps({"method": "subscribe", "subscription": {
                        "type": "twapStates", "user": account, "dex": dex,
                    }}))
                for channel in ("userTwapHistory", "userTwapSliceFills"):
                    socket.send(json.dumps({"method": "subscribe", "subscription": {
                        "type": channel, "user": account,
                    }}))
                last_ping = time.monotonic()
                while not stop.is_set():
                    try:
                        raw = socket.recv()
                    except websocket.WebSocketTimeoutException:
                        socket.send('{"method":"ping"}')
                        continue
                    if not raw:
                        raise OSError("Exchange observation disconnected")
                    if len(raw) > 4_000_000:
                        raise ValueError("Exchange observation too large")
                    now_ms = int(time.time() * 1000)
                    message = json.loads(raw)
                    if self.ingest(account, store, message, now_ms):
                        with self._lock:
                            if self._stop is stop:
                                self._status = {"connected": True, "as_of_ms": now_ms, "error": None}
                                if message.get('channel') == 'twapStates':
                                    self._dex_as_of[message['data'].get('dex','')] = now_ms
                        delay = 1
                    if time.monotonic() - last_ping > 25:
                        socket.send('{"method":"ping"}')
                        last_ping = time.monotonic()
            except Exception:
                with self._lock:
                    if self._stop is stop:
                        self._status["connected"] = False
                        self._status["error"] = "Seguimiento sin conexión. Los TWAP nativos continúan en Hyperliquid."
            finally:
                if socket:
                    try:
                        socket.close()
                    except OSError:
                        pass
            stop.wait(delay)
            delay = min(30, delay * 2)
