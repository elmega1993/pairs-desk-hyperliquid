# PNL oficial de Hyperliquid y pulido visual — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer que el PNL total oficial de Pair Desk coincida con Hyperliquid y mejorar la lectura visual del dashboard, del gráfico acumulado, del resumen de pares y del Explorador.

**Architecture:** El backend expondrá los últimos valores de las ventanas PNL de Hyperliquid como datos oficiales, sin borrar el desglose local. React resolverá una única serie oficial con fallback explícito y reutilizará esa serie para las cards, mini-gráficos y gráfico principal. Los cambios de layout serán locales a los componentes React existentes.

**Tech Stack:** FastAPI/Python, React + TypeScript, SVG, CSS, pytest y Vite.

**Spec:** `docs/superpowers/specs/2026-10-26-pnl-and-visual-polish-design.md`

## Global Constraints

- Hyperliquid es la fuente oficial del PNL total cuando devuelve datos; el cálculo local queda como reconciliación.
- No modificar `secure_trade_routes.py`, ledger, persistencia ni rutas de órdenes.
- Si falta Hyperliquid, el frontend puede usar local como fallback, pero debe indicarlo.
- No duplicar la carga del gráfico del Explorador.
- Mantener la paleta gris cálida y acentos verde/rosa introducida por Claude.

## Review Focus

- Ventanas Hyperliquid vacías o malformadas: no deben romper el estado ni producir un total falso. Test en `tests/test_hl_pnl_windows.py`.
- Existencia simultánea de serie Hyperliquid y snapshots locales: cards y gráfico deben elegir Hyperliquid; la reconciliación debe conservar la diferencia. Test de helper/fuente y UI.
- PNL oficial negativo, cero y positivo: color, signo y mini-gráfico deben ser coherentes. Test de fuente/UI y smoke visual si está disponible.
- Par con PNL de una pata nulo: el resumen debe mostrar `N/D` sin desplazar la exposición ni mezclar colores. Test de `PositionSummary`.
- Explorador con tabla larga y viewport móvil: el gráfico debe quedar accesible arriba en escritorio y seguir visible en flujo normal en móvil. Test de estructura/CSS y smoke visual.

---

### Task 1: Exponer el PNL oficial de Hyperliquid

**Files:**
- Modify: `read_only_server.py` junto a `hl_pnl_windows()` y el retorno de `states()`.
- Test: `tests/test_hl_pnl_windows.py` y un nuevo `tests/test_official_pnl.py`.

**Interfaces:**
- Produces `official_pnl: {"1d": number|null, "7d": number|null, "30d": number|null, "all": number|null}` en la respuesta de estado.
- Conserva `summary.total`, `summary.net_known_subtotal`, `pnl_history` y `hl_pnl` sin cambiar su significado.

- [ ] **Step 1: Write the failing tests** para obtener el último PNL de cada ventana, devolver `None` en ventanas vacías y comprobar que `states()` conserva el resumen local mientras agrega `official_pnl`.
- [ ] **Step 2: Run the focused tests** y confirmar que fallan porque `official_pnl` todavía no existe.
- [ ] **Step 3: Implement `official_pnl_from_windows()`** y usar una sola lectura de `hl_pnl_windows(portfolio)` dentro de `states()` para construir el nuevo campo.
- [ ] **Step 4: Run the focused tests** y confirmar que pasan, incluyendo datos desordenados, duplicados y ventanas ausentes.

### Task 2: Resolver fuente oficial, cards y mini-gráficos

**Files:**
- Create: `react_frontend/src/pnlSource.ts`.
- Create: `react_frontend/src/components/PnlMiniChart.tsx`.
- Modify: `react_frontend/src/types.ts`.
- Modify: `react_frontend/src/App.tsx`.
- Modify: `react_frontend/src/components/PortfolioKpis.tsx`.
- Test: nuevo `tests/test_pnl_source_ui.py` y, si se incorpora una función pura JavaScript, `tests/test_pnl_source.cjs`.

**Interfaces:**
- `resolveOfficialPnl(data): {value:number|null; source:'hyperliquid'|'local'; series:PnlPoint[]; fallback:boolean}`.
- `PnlMiniChart({points, tone, label})` renderiza un SVG accesible y no hace fetch.
- `PortfolioKpis` recibe la serie oficial y el valor total resuelto, en lugar de inferir el total solo desde `summary.total`.

- [ ] **Step 1: Write failing tests** para preferir `official_pnl.all`/`hl_pnl.all` sobre `summary.total`, usar local solo cuando Hyperliquid está vacío, y mostrar la etiqueta de fallback.
- [ ] **Step 2: Run focused tests** y verificar el fallo esperado.
- [ ] **Step 3: Implementar el resolver puro, ampliar `Data` con `official_pnl`, y conectar una sola serie a `PortfolioKpis` y `PnlChart`**.
- [ ] **Step 4: Implementar `PnlMiniChart`** con línea, área tenue, punto final y colores por signo; agregarlo a las cards de PNL sin agregar consultas.
- [ ] **Step 5: Run focused tests and `npm run build`**.

### Task 3: Reordenar y comprimir `Resumen del par`

**Files:**
- Modify: `react_frontend/src/components/PositionSummary.tsx`.
- Modify: `react_frontend/src/style.css`.
- Test: `tests/test_pair_summary_ui.py`.

**Interfaces:**
- La primera fila será `Exposición total` con valor neutro y más visible.
- Las filas de pata mostrarán `LONG <símbolo>` y `SHORT <símbolo>` con su PNL correspondiente en la misma línea.
- El resto de campos conserva sus valores actuales y `tone()` solo se aplica a valores numéricos que representan PNL/funding/comisiones.

- [ ] **Step 1: Write failing source/UI assertions** para el nuevo orden, etiquetas con símbolo y exposición neutral.
- [ ] **Step 2: Run the focused test** y confirmar el fallo.
- [ ] **Step 3: Implementar la estructura compacta** sin cambiar el modelo `Pair` ni la contabilidad.
- [ ] **Step 4: Run the focused test and build**.

### Task 4: Mejorar escala y estilo del gráfico acumulado de PNL

**Files:**
- Modify: `react_frontend/src/PnlChart.tsx`.
- Modify: `react_frontend/src/style.css`.
- Test: `tests/test_daily_pnl_ui.py`, `tests/test_pnl_model.cjs` y `tests/test_visual_smoke.py` cuando Playwright/Chromium estén disponibles.

**Interfaces:**
- Mantener el contrato actual de `PnlChart` y su selector de fuente.
- Mantener drawdown separado, eventos, gaps, tooltip y navegación por teclado.
- Usar la paleta actual de Pair Desk; destacar cero, ticks y puntos extremos con una escala más granular y legible.

- [ ] **Step 1: Write failing assertions** para colores/estructura visual, cantidad de ticks y presencia de leyenda/escala consistente con el gráfico de ratio.
- [ ] **Step 2: Run focused tests** y confirmar el fallo.
- [ ] **Step 3: Ajustar geometría y render SVG**: área bajo la línea, grilla de ticks más detallada, cero destacado, marcadores de máximo/mínimo/último y drawdown con contraste suficiente.
- [ ] **Step 4: Ajustar CSS** para que el gráfico use el ancho real, conserve legibilidad en 1440/1000/700/390 px y no recorte etiquetas.
- [ ] **Step 5: Run focused tests, `npm run build` y smoke visual si las dependencias están disponibles**.

### Task 5: Llevar el gráfico del Explorador arriba y mantenerlo accesible

**Files:**
- Modify: `react_frontend/src/components/Scanner.tsx` solo si hace falta separar el bloque destacado del detalle.
- Modify: `react_frontend/src/style.css` para `.scanner-layout`, `.scanner-detail` y breakpoints.
- Test: nuevo `tests/test_scanner_layout_ui.py` y `tests/test_visual_smoke.py`.

**Interfaces:**
- En escritorio, la tabla y el detalle se presentan en columnas; el detalle queda sticky debajo del encabezado y muestra el gráfico antes de las métricas.
- En móvil, se conserva el flujo vertical y el gráfico aparece inmediatamente después de la selección/análisis.
- `RatioChart` se instancia una sola vez para el resultado seleccionado.

- [ ] **Step 1: Write failing layout assertions** para la clase/grid sticky y el orden del gráfico antes de las métricas.
- [ ] **Step 2: Run the focused test** y confirmar el fallo.
- [ ] **Step 3: Implementar el layout responsive** y revisar que el gráfico no quede escondido detrás de la tabla.
- [ ] **Step 4: Run focused tests and build**.

### Task 6: Verificación integral y documentación de estado

**Files:**
- Modify: `CURRENT_STATE.md` y `TASKS.md` solo para registrar las mejoras verificadas y las limitaciones restantes.

- [ ] **Step 1: Run `npm run build` desde `react_frontend/`.**
- [ ] **Step 2: Run `pytest tests/` desde la raíz.** Si `pytest` no está instalado, registrar la omisión exacta sin afirmar que la suite pasó.
- [ ] **Step 3: Run `git diff --check` y revisar que no haya cambios en rutas sensibles.**
- [ ] **Step 4: Actualizar estado solo con hechos comprobados.**
