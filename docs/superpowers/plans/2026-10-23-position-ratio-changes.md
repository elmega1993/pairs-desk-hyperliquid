# Position Ratio Changes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Mostrar en “Mis posiciones” el cambio del ratio de cada par en 1h y 24h, inspirado en la watchlist de DexScreener.

**Architecture:** Un helper puro calculará cambios porcentuales a partir de velas sintéticas del ratio. Un endpoint independiente de solo lectura consultará velas de las dos patas en paralelo y devolverá los cambios por pair_id. React consultará ese endpoint cada 60 segundos y combinará los valores con la lista actual sin modificar /api/state.

**Tech Stack:** Python, FastAPI, pandas, pytest, React, TypeScript, Vite.

**Spec:** docs/superpowers/specs/2026-10-23-position-ratio-changes-design.md

## Global Constraints

- No modificar secure_trade_routes.py.
- No cambiar PNL, ratio desde entrada ni lógica de trading.
- Los cambios son solo de mercado y no son señales ni órdenes.
- Si faltan datos o una consulta falla, mostrar N/D sin ocultar las posiciones.
- Mantener /api/state con su responsabilidad actual.

## Review Focus

- Ratio histórico sin vela exacta en el instante objetivo: usar la última vela disponible anterior o igual al objetivo.
- Histórico insuficiente, precio no válido o ratio base cero: devolver null/N/D.
- Falla parcial de una pata o del endpoint: conservar la lista y mostrar N/D.
- Actualización periódica: no crear múltiples intervalos ni actualizar mientras la pestaña está oculta.
- Cambio visual en filas angostas: mantener la lista legible y el PNL actual visible.

### Task 1: Cálculo puro de cambios del ratio

**Files:**
- Create: pairs_desk/ratio_changes.py
- Test: tests/test_ratio_changes.py

**Interfaces:**
- Produce ratio_change_pct(current_ratio: float | None, reference_ratio: float | None) -> float | None.
- Produce ratio_changes_from_bars(current_ratio: float | None, bars: pandas.DataFrame, now_ms: int) -> dict[str, float | None], con claves 1h y 24h.

- [ ] Escribir pruebas para porcentajes positivos/negativos, base inválida, vela exacta y fallback a la última vela anterior.
- [ ] Ejecutar pytest tests/test_ratio_changes.py -q y confirmar que falla por funciones ausentes.
- [ ] Implementar las funciones usando pairs_desk.metrics.ratio_bars como origen de las columnas c; no inventar velas ni usar una vela futura.
- [ ] Agregar pruebas de histórico insuficiente y current_ratio=None; confirmar None.
- [ ] Ejecutar pytest tests/test_ratio_changes.py -q y confirmar PASS.

### Task 2: Endpoint de cambios de posiciones

**Files:**
- Modify: read_only_server.py
- Modify: pairs_desk/ratio_changes.py
- Test: tests/test_position_ratio_changes_api.py

**Interfaces:**
- Add GET /api/position-ratio-changes.
- Response: { as_of_ms: number, pairs: { pair_id: { 1h: number|null, 24h: number|null } } }.

- [ ] Escribir pruebas del endpoint con TestClient, configuración y hl simulados; verificar que consulta las dos patas y devuelve cambios por pair_id.
- [ ] Probar que un error de velas para una pata devuelve N/D para ese par sin convertir toda la respuesta en error.
- [ ] Ejecutar pytest tests/test_position_ratio_changes_api.py -q y confirmar FAIL inicial.
- [ ] Implementar el endpoint leyendo los pares activos de settings.json, obteniendo velas 5m suficientes para cubrir 24h y un margen, y procesando pares con ThreadPoolExecutor.
- [ ] Usar el ratio de mercado actual de las posiciones verificadas; no consultar ni modificar rutas de trading.
- [ ] Ejecutar pytest tests/test_position_ratio_changes_api.py -q y confirmar PASS.

### Task 3: Integración de la lista React

**Files:**
- Modify: react_frontend/src/api.ts
- Modify: react_frontend/src/types.ts
- Modify: react_frontend/src/App.tsx
- Modify: react_frontend/src/components/PositionList.tsx
- Modify: react_frontend/src/style.css
- Test: tests/test_react_position_ratio_changes.py

**Interfaces:**
- Add fetchPositionRatioChanges(): Promise<PositionRatioChangesResponse> in api.ts.
- Add types for PositionRatioChange and PositionRatioChangesResponse.
- Pass the response map from App to PositionList as an optional prop.

- [ ] Escribir prueba de fuente que verifique el endpoint, el intervalo de 60 segundos, el texto 1h/24h y que no se elimine el PNL actual.
- [ ] Ejecutar pytest tests/test_react_position_ratio_changes.py -q y confirmar FAIL inicial.
- [ ] Implementar la carga separada cada 60 segundos, condicionada a document.visibilityState === visible, con limpieza del intervalo.
- [ ] Renderizar debajo de cada par una línea compacta 1h ... · 24h ..., usando tone y N/D; agregar title Cambio del ratio.
- [ ] Ajustar estilos responsive sin aumentar innecesariamente la altura de cada fila.
- [ ] Ejecutar pytest tests/test_react_position_ratio_changes.py -q y confirmar PASS.

### Task 4: Verificación integrada

**Files:**
- No additional files.

- [ ] Ejecutar pytest tests/test_ratio_changes.py tests/test_position_ratio_changes_api.py tests/test_react_position_ratio_changes.py -q.
- [ ] Ejecutar la suite Python completa pytest tests/.
- [ ] Ejecutar (cd react_frontend && npm run build).
- [ ] Revisar git diff --check y confirmar que no se modificó secure_trade_routes.py.

