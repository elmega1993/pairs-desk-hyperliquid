# Fase 1B — Contratos de ratios y calidad histórica Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear un contrato analítico único para construir ratios reproducibles entre las dos patas de un par a partir de velas validadas.

**Architecture:** Un módulo puro de Python recibirá dos `DataFrame` canónicos, validará identidad, intervalo, timestamps y precios, hará una unión temporal exacta y devolverá un `RatioResult` inmutable. No habrá persistencia, endpoints, llamadas de red ni integración con el ciclo de renderizado.

**Tech Stack:** Python 3, pandas 2.x, numpy ya disponible indirectamente, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-fase-1b-ratios-design.md`

## Global Constraints

- No modificar `secure_trade_routes.py`.
- No cambiar `/api/state` ni agregar hooks de startup/render.
- No interpolar datos faltantes.
- No persistir ratios en Parquet en esta fase.
- No agregar dependencias de red ni endpoints.
- Las entradas inválidas deben producir `status='error'` y no ratios parciales.

## Review Focus

- Timestamps presentes en una sola pata: deben quedar identificados, sin interpolación.
- Sin intersección temporal: debe devolverse `empty`, no un DataFrame engañosamente válido.
- Precios cero, negativos o no finitos: deben rechazarse antes de dividir o aplicar logaritmo.
- Series de instrumentos o intervalos incompatibles: deben devolverse como error.
- Timestamps duplicados: no deben multiplicarse por un merge many-to-many.

### Task 1: Contrato de resultado y cálculo básico

**Files:**
- Create: `pairs_desk/market_ratios.py`
- Test: `tests/test_market_ratios.py`

**Interfaces:**
- Produces: `RatioResult` with `pair_id`, `frame`, `matched_rows`, `missing_long`, `missing_short`, `status`, `error`.
- Produces: `build_pair_ratios(long_candles, short_candles, *, pair_id) -> RatioResult`.

- [x] **Step 1: Write failing tests** covering exact timestamp intersection, `price_ratio`, `log_ratio`, `complete`, `partial` and `empty`.
- [x] **Step 2: Run focused tests and verify RED**

  Run: `PYTHONPATH=. uv run --with-requirements requirements.txt pytest -q tests/test_market_ratios.py`

  Expected: FAIL because `pairs_desk.market_ratios` does not exist.

- [x] **Step 3: Implement the minimal immutable result and exact inner alignment**

  Use a dataclass and a merge on `timestamp_ms`; preserve ascending timestamp order and calculate the two ratios from closing prices.

- [x] **Step 4: Run focused tests and verify GREEN**
- [x] **Step 5: Commit**

  `git commit -m "feat: add pair ratio contract"`

### Task 2: Validación de entradas y calidad

**Files:**
- Modify: `pairs_desk/market_ratios.py`
- Modify: `tests/test_market_ratios.py`

**Interfaces:**
- Consumes: canonical candle columns from `market_quality.CANONICAL_COLUMNS`.
- Produces: deterministic `error` results for invalid schemas, incompatible identities/intervals, duplicates and invalid prices.

- [x] **Step 1: Add failing regression tests** for missing columns, duplicate timestamps, mismatched instrument/venue/interval, zero/negative/non-finite closes and missing timestamps.
- [x] **Step 2: Run focused tests and verify RED**
- [x] **Step 3: Implement validation before merge/division**

  Return an error result with an explanatory message; never raise for expected data-quality failures and never emit partial ratios in `error` state.

- [x] **Step 4: Run focused tests and full market-data tests**

  Run: `PYTHONPATH=. uv run --with-requirements requirements.txt pytest -q tests/test_market_ratios.py tests/test_market_catalog.py tests/test_market_market_data.py tests/test_market_ingestion.py`

- [x] **Step 5: Commit**

  `git commit -m "feat: validate pair ratio inputs"`

### Task 3: Documentar Fase 1B y actualizar roadmap

**Files:**
- Modify: `README.md`
- Modify: `ROADMAP_PAIRS_DESK_2_0_EXPANSION.md`
- Modify: `docs/superpowers/plans/2026-10-16-fase-1b-ratios.md`

- [x] **Step 1: Document the internal ratio contract and explicit non-goals**
- [x] **Step 2: Mark Fase 1B as implemented/in progress according to the final verified state**
- [x] **Step 3: Inspect isolation with `rg`**

  Confirm no runtime or trading route imports `market_ratios`.

- [x] **Step 4: Commit documentation**

  `git commit -m "docs: document phase 1B ratio layer"`

### Task 4: Verificación completa y revisión final

- [x] **Step 1: Run the complete Python suite**
- [x] **Step 2: Build React**
- [x] **Step 3: Run `git diff --check` and review the final diff**
- [ ] **Step 4: Push `main` only after all checks pass and verify remote HEAD**
