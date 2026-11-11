"""Cambio 24h / 7d de los activos del Explorador con consumo acotado de Hyperliquid.

Estrategia de bajo consumo (peso Hyperliquid: info = 20, límite 1200/min/IP):

* 24h sale GRATIS: ``metaAndAssetCtxs`` trae ``markPx`` y ``prevDayPx`` y reemplaza
  a los ``meta`` que el Explorador ya pedía (mismo número de requests y mismo peso).
* 7d no existe en ningún endpoint masivo. Se guarda un precio de referencia por
  activo (vela de 1h de hace ~7 días) que se pide UNA vez cada ``ttl`` horas, de a
  un activo por vez y con pausa fija entre requests. El cambio 7d se calcula luego
  contra el ``markPx`` actual sin volver a llamar a la API.

Este módulo no abre conexiones propias: recibe ``fetch(payload) -> json``.
"""
from __future__ import annotations

import json
import math
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable

HOUR_MS = 3_600_000
DAY_MS = 24 * HOUR_MS
WEEK_MS = 7 * DAY_MS
DEFAULT_REF_TTL_MS = 6 * HOUR_MS
UNAVAILABLE_RETRY_MS = DAY_MS          # activos sin 7d de historia: reintentar 1 vez por día
MAX_REF_AGE_MS = WEEK_MS + DAY_MS      # una referencia más vieja que esto no se muestra
DEFAULT_INTERVAL_S = 6.0               # 1 request cada 6 s ≈ 200 de peso/min (~17 % del cupo)
BACKOFF_START_S = 60.0
BACKOFF_MAX_S = 900.0


def pct_change(current: Any, reference: Any) -> float | None:
    """Variación porcentual, o None si algún dato falta o no es válido."""
    try:
        cur, ref = float(current), float(reference)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(cur) and math.isfinite(ref)) or cur <= 0 or ref <= 0:
        return None
    return (cur / ref - 1.0) * 100.0


def coin_for(instrument_id: str) -> str:
    """'core:BTC' -> 'BTC'; 'xyz:MU' -> 'xyz:MU' (nombre que espera candleSnapshot)."""
    venue, _, symbol = str(instrument_id).partition(':')
    return symbol if venue == 'core' else f'{venue}:{symbol}'


class WeeklyReferenceStore:
    """JSON atómico con la referencia de ~7 días por instrumento."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        try:
            raw = json.loads(self.path.read_text())
        except (OSError, ValueError):
            return {}
        return raw if isinstance(raw, dict) else {}

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {key: dict(value) for key, value in self._data.items()}

    def put(self, instrument_id: str, *, ref_px: float | None, ref_ts_ms: int | None, fetched_ms: int) -> None:
        entry = {'ref_px': ref_px, 'ref_ts_ms': ref_ts_ms, 'fetched_ms': int(fetched_ms)}
        with self._lock:
            self._data[instrument_id] = entry
            self._flush_locked()

    def _flush_locked(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            fd, temporary = tempfile.mkstemp(dir=self.path.parent, suffix='.tmp')
            with os.fdopen(fd, 'w') as handle:
                json.dump(self._data, handle, separators=(',', ':'))
            os.replace(temporary, self.path)
            try:
                self.path.chmod(0o600)
            except OSError:
                pass
        except OSError:
            pass  # el caché es descartable: si no se puede guardar, se reconstruye


def _is_rate_limited(exc: Exception) -> bool:
    response = getattr(exc, 'response', None)
    return getattr(response, 'status_code', None) == 429


class WeeklyReferenceWorker:
    """Cola lenta de un activo por vez. ``step`` es determinista y testeable."""

    def __init__(
        self,
        store: WeeklyReferenceStore,
        fetch: Callable[[dict[str, Any]], Any],
        *,
        interval_s: float = DEFAULT_INTERVAL_S,
        ttl_ms: int = DEFAULT_REF_TTL_MS,
        clock_ms: Callable[[], int] = lambda: int(time.time() * 1000),
    ):
        self.store = store
        self.fetch = fetch
        self.interval_s = max(1.0, float(interval_s))
        self.ttl_ms = int(ttl_ms)
        self.clock_ms = clock_ms
        self._queue: list[str] = []
        self._lock = threading.Lock()
        self._backoff_s = 0.0
        self._paused_until_ms = 0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_error: str | None = None

    # ------------------------------------------------------------------ cola
    def is_fresh(self, entry: dict[str, Any] | None, now_ms: int) -> bool:
        if not entry:
            return False
        age = now_ms - int(entry.get('fetched_ms') or 0)
        limit = self.ttl_ms if entry.get('ref_px') else UNAVAILABLE_RETRY_MS
        return age < limit

    def submit(self, ordered_instrument_ids: Iterable[str]) -> int:
        """Reemplaza la cola por los ids vencidos, respetando el orden recibido."""
        now_ms = self.clock_ms()
        refs = self.store.snapshot()
        pending = [i for i in ordered_instrument_ids if not self.is_fresh(refs.get(i), now_ms)]
        with self._lock:
            self._queue = pending
        return len(pending)

    def pending_count(self) -> int:
        with self._lock:
            return len(self._queue)

    # --------------------------------------------------------------- trabajo
    def _reference_from_candles(self, candles: Any, target_ms: int) -> tuple[float, int] | None:
        if not isinstance(candles, list):
            return None
        best: tuple[int, float] | None = None
        for candle in candles:
            try:
                ts, open_px = int(candle['t']), float(candle['o'])
            except (KeyError, TypeError, ValueError):
                continue
            if open_px <= 0 or not math.isfinite(open_px):
                continue
            if best is None or abs(ts - target_ms) < abs(best[0] - target_ms):
                best = (ts, open_px)
        if best is None or abs(best[0] - target_ms) > 2 * HOUR_MS:
            return None
        return best[1], best[0]

    def step(self) -> str:
        """Procesa como máximo un activo. Devuelve 'idle' | 'paused' | 'ok' | 'empty' | 'error' | 'rate_limited'."""
        now_ms = self.clock_ms()
        if now_ms < self._paused_until_ms:
            return 'paused'
        with self._lock:
            if not self._queue:
                return 'idle'
            instrument_id = self._queue.pop(0)
        target = now_ms - WEEK_MS
        request = {'type': 'candleSnapshot', 'req': {'coin': coin_for(instrument_id), 'interval': '1h',
                                                       'startTime': target - HOUR_MS, 'endTime': target + 2 * HOUR_MS}}
        try:
            candles = self.fetch(request)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo de red corta este ciclo
            self.last_error = type(exc).__name__
            if _is_rate_limited(exc):
                self._backoff_s = min(BACKOFF_MAX_S, (self._backoff_s * 2) or BACKOFF_START_S)
                self._paused_until_ms = now_ms + int(self._backoff_s * 1000)
                with self._lock:
                    self._queue.insert(0, instrument_id)  # no se pierde el activo
                return 'rate_limited'
            return 'error'  # se reintenta en el próximo submit; no se guarda nada
        self._backoff_s = 0.0
        self.last_error = None
        found = self._reference_from_candles(candles, target)
        if found is None:
            self.store.put(instrument_id, ref_px=None, ref_ts_ms=None, fetched_ms=now_ms)
            return 'empty'
        self.store.put(instrument_id, ref_px=found[0], ref_ts_ms=found[1], fetched_ms=now_ms)
        return 'ok'

    # ------------------------------------------------------------ hilo diario
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name='weekly-reference-worker', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            status = self.step()
            wait = 5.0 if status in ('idle', 'paused') else self.interval_s
            self._stop.wait(wait)


def weekly_progress(instrument_ids: Iterable[str], refs: dict[str, dict[str, Any]], now_ms: int) -> dict[str, int]:
    ids = list(instrument_ids)
    ready = sum(1 for i in ids if _usable_ref(refs.get(i), now_ms) is not None)
    unavailable = sum(1 for i in ids if refs.get(i) and not refs[i].get('ref_px'))
    return {'ready': ready, 'unavailable': unavailable, 'total': len(ids), 'pending': max(0, len(ids) - ready - unavailable)}


def _usable_ref(entry: dict[str, Any] | None, now_ms: int) -> float | None:
    if not entry or not entry.get('ref_px') or not entry.get('ref_ts_ms'):
        return None
    if now_ms - int(entry['ref_ts_ms']) > MAX_REF_AGE_MS:
        return None
    return float(entry['ref_px'])


def attach_changes(assets: list[dict[str, Any]], refs: dict[str, dict[str, Any]], now_ms: int) -> list[dict[str, Any]]:
    """Agrega change_24h_pct y change_7d_pct a cada dict de activo (sin tocar la red)."""
    result = []
    for asset in assets:
        mark = asset.get('mark_px')
        row = dict(asset)
        row['change_24h_pct'] = pct_change(mark, asset.get('prev_day_px'))
        row['change_7d_pct'] = pct_change(mark, _usable_ref(refs.get(asset['instrument_id']), now_ms))
        result.append(row)
    return result


def priority_order(assets: list[dict[str, Any]]) -> list[str]:
    """Más líquidos primero; los de volumen cero (sin velas útiles) no se piden."""
    liquid = [a for a in assets if (a.get('day_volume_usd') or 0) > 0]
    liquid.sort(key=lambda a: a.get('day_volume_usd') or 0, reverse=True)
    return [a['instrument_id'] for a in liquid]
