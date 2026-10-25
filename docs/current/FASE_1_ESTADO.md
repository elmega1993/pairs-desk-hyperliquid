# Fase 1 — Estado

## Hecho
- `format.ts`, `sort.ts`, `types.ts` y `api.ts` separados de `main.tsx`; `App.tsx` y componentes en `components/`.
- Polling de estado cada 30 segundos solo con la pestaña visible; refresco al volver.
- Gráfico del ratio como componente TypeScript (`RatioChart.tsx`): no depende de `window.AuroraTradingChart` ni lee checkboxes del DOM. Se reinicializa solo con un par o velas nuevas; los niveles se actualizan por una firma de datos, así que se conserva el zoom.
- Gráfico PNL (`PnlChart.tsx`) con eje temporal, escala USD, línea cero y tooltip. Los datos provienen solo de `/api/state` (`pnl_history`). Normaliza timestamps (segundos/milisegundos), ordena y reduce puntos por buckets preservando extremos.
- Build condicional y `npm ci` con lockfile en el launcher.
- Pulido visual verificado en navegador (ver `docs/visual/` y la entrada de `docs/history/CHANGELOG.md`).
- `Mis posiciones` fue compactada para mostrar par, PNL y cambios de ratio 1h/24h; búsqueda y ordenamiento viven en un único desplegable.
- El encabezado operativo prioriza `Agregar par` y `Operar par`; `Radar de posiciones` y `Pares cerrados` comparten fila en escritorio y se apilan en móvil.
- `Resumen del par` quedó reducido a métricas operativas, incluyendo PNL long/short y color por signo.
- Los indicadores 1h/24h de `Mis posiciones` fueron ajustados para conservar legibilidad en anchos reducidos.
- `Pares cerrados` expone `DESDE CIERRE`, comparando el ratio actual con el VWAP de los fills de cierre cuando hay datos verificables.

## Pendiente
- Cargar KLineCharts como módulo npm (hoy: `<script>` desde `/vendor`, con SHA-256 verificado al iniciar).
- Validar con datos históricos reales que `pnl_history` tiene la definición contable esperada; no mezclar subtotal con PNL neto verificado.
- Pendientes visuales: ver Fase 1c en `docs/current/PLAN_CONSOLIDACION.md`.
- Paridad con Aurora y secciones del estable (ver `docs/current/PLAN_CONSOLIDACION.md`).

## Nota sobre trading
La interfaz React incluye **Agregar par** y **Operar par** (`components/PairActions.tsx`). No hay cambios en `secure_trade_routes.py`, el ledger ni la API, pero la UI de órdenes reales es nueva y **no está validada en testnet** (ver Fase 1b del plan).
