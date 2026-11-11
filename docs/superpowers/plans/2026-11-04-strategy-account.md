# Cuenta / Estrategia desde el inicio operativo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Agregar una vista React de Cuenta / Estrategia con historial desde el 23/09/2026, gráfico limpio, PNL diario independiente, ROI basado en capital inicial y proyección de funding cacheada.

**Architecture:** El backend expondrá un bloque `strategy` dentro de `/api/state`, construido desde la serie de Hyperliquid, `accountValueHistory`, fills/ledger y tasas vigentes. Las funciones de corte, rebase, diarios, ROI y agregación de carry serán puras y testeables; React consumirá una sola respuesta y renderizará una vista separada del escritorio operativo.

**Tech Stack:** Python/FastAPI, Hyperliquid portfolio y ledger local, React + TypeScript, Vite, pytest y pruebas estructurales/Node existentes.

**Spec:** `docs/superpowers/specs/2026-11-04-strategy-account-design.md`

## Global Constraints

- Fecha inicial fija: `2026-09-23T00:00:00`.
- No usar el saldo actual como capital inicial.
- Mantener `N/D` cuando funding, comisiones o capital inicial no sean verificables.
- No modificar `secure_trade_routes.py` ni enviar órdenes.
- El gráfico de estrategia no mostrará eventos.
- Las tasas de funding proyectadas deben reutilizarse mediante cache y etiquetarse como estimación.

## Review Focus

- Serie anterior al 23/09: debe eliminarse y la primera muestra válida debe quedar rebasada a cero. (Task 1)
- Día inicial incompleto: debe marcarse parcial y no inventar un día completo. (Task 1)
- Sin capital inicial: ROI debe ser `None`/`N/D`, nunca cero ni saldo actual. (Task 1)
- Cambio de período visual: el PNL diario debe conservar la misma serie completa. (Task 3)
- Tasas o nominales faltantes: la proyección debe ser `N/D` sin convertir falta de datos en cero. (Task 2)

### Task 1: Strategy history and accounting helpers

**Files:**
- Create: `pairs_desk/strategy_analytics.py`
- Modify: `read_only_server.py`
- Test: `tests/test_strategy_analytics.py`

**Interfaces:**
- `strategy_history(rows, start_ms) -> list[dict]`: filtra por fecha, ordena, deduplica y rebasa PNL a cero.
- `daily_strategy_pnl(rows, timezone_name) -> list[dict]`: devuelve fecha, PNL diario, acumulado y parcialidad.
- `strategy_roi(net_pnl, initial_capital) -> float | None`.
- `strategy_capital(account_value_history, start_ms) -> float | None`.
- El bloque backend `strategy` incluirá `start_ms`, `initial_capital`, `history`, `daily`, `gross_pnl`, `realized`, `unrealized`, `funding`, `fees`, `net_pnl` y `roi_pct`.

- [ ] Escribir pruebas fallidas para corte/rebase, diarios, ROI y capital inicial.
- [ ] Ejecutar `pytest tests/test_strategy_analytics.py` y confirmar fallos esperados.
- [ ] Implementar las funciones puras sin red.
- [ ] Incorporar el bloque `strategy` a `states()` usando la fecha fija y datos ya cargados.
- [ ] Ejecutar las pruebas focalizadas y confirmar que pasan.

### Task 2: Cached funding projection

**Files:**
- Modify: `read_only_server.py`
- Modify: `pairs_desk/funding_carry.py` si hace falta una agregación pura
- Test: `tests/test_funding_carry.py` y/o `tests/test_strategy_api.py`

**Interfaces:**
- `strategy.funding_projection` devolverá `per_day_usd`, `per_week_usd`, `per_30d_usd`, `basis`, `as_of_ms` y `available`.
- La lectura de tasas Core/XYZ se cacheará en memoria durante un intervalo definido y no se repetirá por cada tarjeta ni por cada render.

- [ ] Escribir prueba fallida para agregar carry de varios pares y conservar `None` ante datos faltantes.
- [ ] Escribir prueba fallida para reutilizar tasas cacheadas dentro del TTL.
- [ ] Implementar la cache y la agregación read-only.
- [ ] Ejecutar las pruebas de funding y confirmar que pasan.

### Task 3: Clean strategy chart and independent daily panel

**Files:**
- Modify: `react_frontend/src/PnlChart.tsx`
- Modify: `react_frontend/src/components/DailyPnlPanel.tsx`
- Modify: `react_frontend/src/pnlModel.ts`
- Test: `tests/test_pnl_model.cjs` and `tests/test_strategy_account_ui.py`

**Interfaces:**
- `PnlChart` recibirá `strategyHistory`/`strategyDaily` o el bloque equivalente, separado de la serie seleccionada para dibujar.
- El gráfico no recibirá ni renderizará `events` en la vista de estrategia.
- Los controles de período solo filtran la curva visible; el panel diario usa siempre `strategy.daily`.

- [ ] Agregar pruebas estructurales para ausencia de eventos y fuente diaria independiente.
- [ ] Implementar el filtro visual sobre la serie ya recortada y rebasada.
- [ ] Simplificar leyenda/controles al estilo del gráfico de ratios y mantener todo el período visible.
- [ ] Ejecutar pruebas Node/Python focalizadas.

### Task 4: Cuenta / Estrategia view and statistics cards

**Files:**
- Create: `react_frontend/src/components/StrategyAccount.tsx`
- Modify: `react_frontend/src/App.tsx`
- Modify: `react_frontend/src/types.ts`
- Modify: `react_frontend/src/style.css`
- Test: `tests/test_strategy_account_ui.py`

**Interfaces:**
- `StrategyAccount({strategy}: {strategy: StrategyData | null})` renderizará navegación, gráfico, PNL diario, ROI, capital inicial, costos y proyección de funding.
- `Data` incorporará `strategy?: StrategyData`.

- [ ] Escribir prueba estructural para navegación, fecha de inicio, ROI y tarjetas de funding.
- [ ] Implementar tipos y componente sin modificar `PairActions` ni rutas de trading.
- [ ] Agregar la vista `Cuenta / Estrategia` al selector principal.
- [ ] Aplicar layout responsive y estados `N/D`, parcial y estimado.
- [ ] Ejecutar pruebas focalizadas y build React.

### Task 5: Final verification and documentation

**Files:**
- Modify: `CURRENT_STATE.md`
- Modify: `TASKS.md` si corresponde
- Test: suite aplicable y smoke visual si Chromium está disponible

- [ ] Ejecutar `pytest -q` y separar fallos preexistentes de regresiones.
- [ ] Ejecutar `node tests/test_pnl_model.cjs` y `npm run build`.
- [ ] Ejecutar smoke visual disponible.
- [ ] Revisar `git diff --check` y confirmar que `secure_trade_routes.py` no fue modificado.
- [ ] Documentar fecha de inicio, fórmula de ROI, fuente de funding y limitaciones.
