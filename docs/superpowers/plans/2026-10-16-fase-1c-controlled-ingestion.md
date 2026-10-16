# Fase 1C — Ingesta operativa controlada Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Coordinar sincronizaciones incrementales de mercado reutilizando checkpoints y midiendo su resultado sin conectar la ingesta al dashboard.

**Architecture:** `MarketSyncService` envolverá `MarketIngestor`, decidirá ventanas con checkpoints y devolverá métricas observables. La operación por lote será secuencial; un scheduler futuro podrá invocar esta API desde fuera del proceso de renderizado.

**Tech Stack:** Python 3, SQLite/Parquet existentes, pandas, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-fase-1c-controlled-ingestion-design.md`

## Global Constraints

- No modificar `secure_trade_routes.py`.
- No cambiar `/api/state` ni agregar hooks de startup/render.
- No hacer llamadas si el checkpoint ya cubre la ventana solicitada.
- Reutilizar `MarketIngestor` y `MarketDataStore`; no duplicar persistencia.
- No agregar un scheduler residente en esta fase.

### Task 1: Ventanas incrementales y métricas

**Files:**
- Create: `pairs_desk/market_sync.py`
- Test: `tests/test_market_sync.py`
- Modify: `pairs_desk/market_quality.py` only if an interval helper is needed

- [x] Write failing tests for first sync, checkpoint overlap, up-to-date no-op and duration.
- [x] Run focused tests and verify RED.
- [x] Implement `SyncMetrics` and `MarketSyncService.sync_incremental(...)`.
- [x] Run focused tests and verify GREEN.
- [x] Commit `feat: add controlled incremental market sync`.

### Task 2: Sincronización por lote y aislamiento

**Files:**
- Modify: `pairs_desk/market_sync.py`
- Modify: `tests/test_market_sync.py`

- [x] Write failing tests for `sync_many`, totals and per-instrument failure isolation.
- [x] Run focused tests and verify RED.
- [x] Implement sequential batch orchestration and `BatchSyncResult`.
- [x] Run market and sync tests.
- [x] Inspect that runtime/trading files do not import the new service.
- [x] Commit `feat: add batch market synchronization`.

### Task 3: Documentación, roadmap y verificación

**Files:**
- Modify: `README.md`
- Modify: `ROADMAP_PAIRS_DESK_2_0_EXPANSION.md`

- [x] Document manual/external invocation and metrics.
- [x] Mark Fase 1C as implemented without claiming a resident scheduler.
- [x] Run full Python suite, React build and `git diff --check`.
- [ ] Commit `docs: document controlled market ingestion`.
- [ ] Push `main` and verify remote HEAD.
