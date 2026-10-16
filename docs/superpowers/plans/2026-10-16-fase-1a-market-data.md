# Fase 1A — Catálogo e históricos de mercado Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear el catálogo de mercado y la ingesta incremental de velas en SQLite + Parquet sin afectar el escritorio, la contabilidad ni la ejecución de órdenes.

**Architecture:** Se agregan módulos internos separados para catálogo, calidad, almacenamiento e ingesta. `market.sqlite3` guardará metadatos y checkpoints; Parquet guardará velas validadas; Hyperliquid se consumirá mediante un adaptador inyectable basado en `candleSnapshot`. Ningún endpoint actual invocará la ingesta.

**Tech Stack:** Python 3, SQLite estándar, pandas 2.x, pyarrow, pytest y el cliente HTTP existente de Hyperliquid.

**Spec:** `docs/superpowers/specs/2026-10-16-fase-1a-market-data-design.md`

## Global Constraints

- No modificar `secure_trade_routes.py`.
- No cambiar el contrato ni el ciclo de `/api/state`.
- No guardar datos de mercado dentro del repositorio ni en `settings.json`.
- No usar keyring, claves privadas ni endpoints de órdenes.
- No ejecutar ingesta durante el renderizado de Streamlit ni el refresco de React.
- No calcular ni persistir ratios históricos en esta fase.
- No interpolar velas faltantes ni convertir respuestas vacías en datos válidos.
- Los errores no avanzan checkpoints.

## Review Focus

- Repetición de la misma ventana: no debe duplicar filas ni cambiar velas existentes silenciosamente.
- Respuesta fuera de orden o con timestamps duplicados: debe rechazarse antes de escribir.
- OHLC imposible o valores no finitos: debe producir error de calidad y no modificar Parquet.
- Fallo después de recibir datos: SQLite y Parquet no deben quedar marcados como cobertura completa.
- Dos instrumentos del mismo símbolo en Core/XYZ: sus IDs y archivos deben permanecer diferenciados.

### Task 1: Catálogo e identidad de mercado

**Files:**
- Create: `pairs_desk/market_catalog.py`
- Test: `tests/test_market_catalog.py`
- Modify: `requirements.txt` only if the implementation needs an undeclared runtime dependency

**Interfaces:**
- Produces: `instrument_id(symbol: str, venue: str) -> str`, `pair_id(long_instrument_id: str, short_instrument_id: str) -> str`, and `MarketCatalog` backed by SQLite.
- `MarketCatalog.upsert_instrument(...)` creates or updates one instrument without changing its ID.
- `MarketCatalog.upsert_pair(...)` creates or updates one normalized pair and rejects identical legs.
- `MarketCatalog.get_instrument(...)`, `get_pair(...)` and `list_instruments(...)` return normalized records.

- [ ] **Step 1: Write failing tests for stable identities**

  Add tests proving that Core and XYZ versions of the same symbol have different IDs, repeated normalization returns the same ID, and a pair cannot use the same leg twice.

- [ ] **Step 2: Run the focused tests and verify RED**

  Run: `pytest -q tests/test_market_catalog.py`

  Expected: FAIL because `pairs_desk.market_catalog` does not exist.

- [ ] **Step 3: Implement the SQLite catalog**

  Create tables `instruments` and `pairs` in a configurable database path whose default is `Path.home() / '.local/share/crypto-pairs-desk/market.sqlite3'`. Use transactions, parameterized SQL, and file permissions consistent with the existing SQLite modules.

- [ ] **Step 4: Run focused tests and the existing storage tests**

  Run: `pytest -q tests/test_market_catalog.py tests/test_storage.py`

  Expected: all selected tests pass.

- [ ] **Step 5: Commit**

  ```bash
  git add pairs_desk/market_catalog.py tests/test_market_catalog.py
  git commit -m "feat: add market instrument catalog"
  ```

### Task 2: Validación y almacenamiento Parquet

**Files:**
- Create: `pairs_desk/market_quality.py`
- Create: `pairs_desk/market_storage.py`
- Test: `tests/test_market_market_data.py`
- Modify: `requirements.txt` to declare `pyarrow>=14,<24`

**Interfaces:**
- Produces: `normalize_candles(rows, instrument_id, venue, interval) -> DataFrame`.
- Produces: `validate_candles(frame) -> QualityReport`.
- Produces: `MarketDataStore(root).merge_candles(frame) -> MergeResult` and `read_candles(...) -> DataFrame`.

- [ ] **Step 1: Write failing tests for OHLC and timestamp validation**

  Cover valid rows, non-finite values, impossible high/low bounds, duplicate timestamps and out-of-order timestamps. Assert that invalid input is rejected before a Parquet file is created or changed.

- [ ] **Step 2: Run focused tests and verify RED**

  Run: `pytest -q tests/test_market_market_data.py`

  Expected: FAIL because the quality and storage modules do not exist.

- [ ] **Step 3: Implement normalization and quality reports**

  Declare `pyarrow>=14,<24` in `requirements.txt`. Normalize Hyperliquid fields `t/o/h/l/c/v` into the documented columns and require finite numeric values. `QualityReport` must expose validity, row count, duplicate count, gap timestamps and an error reason.

- [ ] **Step 4: Implement idempotent Parquet merge**

  Store partitions under `<root>/candles/<venue>/<instrument_id>/<interval>.parquet`. Merge by `timestamp_ms`, reject conflicting existing rows, sort ascending and write atomically through a temporary file plus `os.replace`.

- [ ] **Step 5: Run focused tests**

  Run: `pytest -q tests/test_market_market_data.py`

  Expected: all selected tests pass, including repeated merge without duplicates.

- [ ] **Step 6: Commit**

  ```bash
  git add pairs_desk/market_quality.py pairs_desk/market_storage.py tests/test_market_market_data.py
  git commit -m "feat: add validated market parquet storage"
  ```

### Task 3: Checkpoints e ingesta incremental

**Files:**
- Create: `pairs_desk/market_ingestion.py`
- Test: `tests/test_market_ingestion.py`

**Interfaces:**
- Produces: `SyncResult` with `rows_received`, `rows_new`, `covered_from_ms`, `covered_to_ms`, `gaps`, `status` and `error`.
- Produces: `MarketIngestor(catalog, store, fetch)`.
- Produces: `MarketIngestor.sync_candles(instrument_id, interval, start_ms, end_ms) -> SyncResult`.

- [ ] **Step 1: Write failing tests for successful and failed syncs**

  Use a fake `fetch` that returns candleSnapshot-shaped rows. Test successful first sync, repeated sync, empty response, malformed response and a fetch failure. Assert checkpoint advancement only on a complete valid write.

- [ ] **Step 2: Run focused tests and verify RED**

  Run: `pytest -q tests/test_market_ingestion.py`

  Expected: FAIL because `pairs_desk.market_ingestion` does not exist.

- [ ] **Step 3: Implement the injectable candleSnapshot adapter**

  Build the payload `{'type': 'candleSnapshot', 'req': {'coin': symbol, 'interval': interval, 'startTime': start_ms, 'endTime': end_ms}}`. Do not import or call trade modules. Normalize and validate before invoking the store.

- [ ] **Step 4: Implement SQLite checkpoints transactionally**

  Add a `ingestion_checkpoints` table to `market.sqlite3`. Advance `covered_to_ms` and `last_success_ms` only after the Parquet merge succeeds. Store status and error for failures without claiming coverage.

- [ ] **Step 5: Run focused tests and catalog tests**

  Run: `pytest -q tests/test_market_ingestion.py tests/test_market_catalog.py tests/test_market_market_data.py`

  Expected: all selected tests pass.

- [ ] **Step 6: Commit**

  ```bash
  git add pairs_desk/market_ingestion.py tests/test_market_ingestion.py
  git commit -m "feat: add incremental market candle ingestion"
  ```

### Task 4: Integración documental y verificación de aislamiento

**Files:**
- Modify: `README.md`
- Modify: `docs/current/PLAN_CONSOLIDACION.md` only if it needs a cross-reference
- Test/inspect: `read_only_server.py`, `secure_trade_routes.py`, `react_frontend/src/`

**Interfaces:**
- Consumes: catalog, quality, storage and ingestion modules from Tasks 1–3.
- Produces: documentación de uso interno y evidencia de que ningún refresco actual dispara la ingesta.

- [ ] **Step 1: Inspect runtime isolation before integration**

  Use `rg -n 'MarketIngestor|sync_candles|market_ingestion' read_only_server.py secure_trade_routes.py react_frontend/src` and confirm that the existing runtime does not import or call the ingestion layer.

- [ ] **Step 2: Preserve the isolation boundary**

  Do not add imports, startup hooks or UI calls for `MarketIngestor`; Phase 1A exposes only the internal service and tests.

- [ ] **Step 3: Document manual invocation and runtime paths**

  Add a short README section describing the market database locations, the fact that ingestion is manual/internal in Phase 1A, and that the dashboard does not wait for it.

- [ ] **Step 4: Run the full available verification**

  Run: `pytest -q` and `npm --prefix react_frontend run build`.

  Expected: Python tests pass when pytest is installed; React build exits 0. If pytest is unavailable, record that limitation without installing dependencies automatically.

- [ ] **Step 5: Commit**

  ```bash
  git add README.md docs/current/PLAN_CONSOLIDACION.md requirements.txt tests
  git commit -m "docs: document market data foundation"
  ```
