# Fase 2 — Explorador de pares / Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Incorporar un Scanner React de solo lectura basado en el catálogo, Parquet y ratios compartidos.

**Architecture:** Un servicio Python escaneará pares activos desde almacenamiento local y expondrá un endpoint GET acotado. Un componente React consumirá ese contrato únicamente cuando se seleccione “Explorador”; el Escritorio conservará su flujo actual.

**Tech Stack:** Python, SQLite, pandas/Parquet, FastAPI, React 19, TypeScript, CSS existente, pytest y Vite.

**Spec:** `docs/superpowers/specs/2026-10-16-fase-2-scanner-design.md`

## Global Constraints

- No modificar `secure_trade_routes.py`.
- No llamar Hyperliquid desde `/api/scanner`.
- No modificar el contrato de `/api/state`.
- No agregar botones ni rutas de ejecución al Scanner.
- Mantener la vista del Escritorio funcional y visualmente estable.

### Task 1: Servicio Scanner y contrato de catálogo

**Files:**
- Modify: `pairs_desk/market_catalog.py`
- Create: `pairs_desk/market_scanner.py`
- Test: `tests/test_market_scanner.py`

- [x] Escribir tests RED para listar pares, calcular ratio actual/cambio 24h y distinguir `no_data`.
- [x] Implementar `list_pairs` y `MarketScanner.scan` con dependencias inyectables.
- [x] Ejecutar tests focalizados GREEN.
- [x] Commit `feat: add read-only market scanner service`.

### Task 2: Endpoint read-only

**Files:**
- Modify: `read_only_server.py`
- Test: `tests/test_market_scanner_api.py`

- [x] Escribir tests RED para parámetros, límite y respuesta JSON.
- [x] Agregar `GET /api/scanner` sin red ni órdenes.
- [x] Ejecutar tests focalizados y revisar aislamiento.
- [x] Commit `feat: expose read-only scanner endpoint`.

### Task 3: Vista React Explorador

**Files:**
- Create: `react_frontend/src/components/Scanner.tsx`
- Modify: `react_frontend/src/api.ts`, `react_frontend/src/types.ts`, `react_frontend/src/App.tsx`, `react_frontend/src/style.css`

- [x] Agregar tipos y cliente `fetchScanner`.
- [x] Reemplazar placeholder de “Explorador” por tabla, filtros, selección y detalle.
- [x] Mantener explícitamente el límite analítico/no-trading.
- [x] Ejecutar build React.
- [x] Commit `feat: add React pair explorer`.

### Task 4: Documentación y verificación final

**Files:**
- Modify: `README.md`
- Modify: `ROADMAP_PAIRS_DESK_2_0_EXPANSION.md`

- [x] Documentar endpoint y límites de la primera versión.
- [x] Marcar Fase 2 MVP implementada.
- [x] Ejecutar suite Python, build React, `git diff --check` y revisión de aislamiento.
- [ ] Commit `docs: document pair scanner`.
- [ ] Push `main` y verificar remoto.
