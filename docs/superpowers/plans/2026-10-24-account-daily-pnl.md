# Account Daily PNL Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Mostrar un panel lateral con el PNL total diario de la cuenta usando la serie de Hyperliquid.

**Architecture:** Un helper puro en pnlModel.ts agrupará puntos por fecha de Argentina y calculará el delta diario sin rellenar huecos. PnlChart renderizará un panel hermano al gráfico solo cuando la fuente sea Hyperliquid; en pantallas angostas se apilará debajo.

**Tech Stack:** React, TypeScript, Vite, Node test suite.

**Spec:** docs/superpowers/specs/2026-10-24-account-daily-pnl-design.md

## Global Constraints

- Usar únicamente la serie Hyperliquid para el panel diario.
- No modificar ledger, funding, PNL por par ni rutas de trading.
- No inventar valores para días sin datos.
- Mantener el gráfico acumulado y la conciliación actuales.

## Tasks

### Task 1: Modelo puro de PNL diario

**Files:**
- Modify: react_frontend/src/pnlModel.ts
- Test: tests/test_pnl_model.cjs

- [ ] Agregar prueba para agrupar por fecha de Argentina, calcular delta diario, marcar primer día parcial y conservar días separados por huecos.
- [ ] Ejecutar la prueba y verificar que falla porque la función no existe.
- [ ] Implementar dailyPnl(rows) con salida date, pnl, cumulative y partial.
- [ ] Ejecutar la suite Node de PNL y confirmar PASS.

### Task 2: Panel lateral React

**Files:**
- Modify: react_frontend/src/PnlChart.tsx
- Modify: react_frontend/src/style.css
- Test: tests/test_daily_pnl_ui.py

- [ ] Agregar prueba de fuente para panel, datos diarios y mensaje cuando la fuente no es Hyperliquid.
- [ ] Ejecutar la prueba y verificar FAIL inicial.
- [ ] Renderizar el panel con filas ordenadas de más reciente a más antigua, colores y formato monetario.
- [ ] Mostrar aviso de fuente local sin calcular datos diarios locales.
- [ ] Ajustar layout de escritorio y móvil.
- [ ] Ejecutar la prueba y confirmar PASS.

### Task 3: Verificación integrada

- [ ] Ejecutar pruebas Python y Node aplicables.
- [ ] Ejecutar pytest tests/.
- [ ] Ejecutar npm run build.
- [ ] Ejecutar git diff --check.
