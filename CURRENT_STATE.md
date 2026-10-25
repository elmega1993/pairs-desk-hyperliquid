# Estado actual

Fecha de referencia: 2026-10-24.

## Confirmado en esta copia

- Rama de trabajo limpia al iniciar esta documentación.
- Último commit observado: `0c6e8f4 feat: add scanner chart timeframe controls`.
- React es la interfaz principal y se sirve en `/react`.
- `/` y `/aurora` permanecen como interfaces legacy/fallback.
- El frontend React incluye explorador de pares, gráficos de ratio y PNL, radar, estados de frescura y acciones de pares.
- El dashboard React tiene `Mis posiciones` compacta (par, PNL y ratio 1h/24h), filtros en un desplegable y `Radar de posiciones` junto a `Pares cerrados` en escritorio.
- `Resumen del par` muestra solo long/short, nominales, exposición total, PNL flotante, PNL long/short, PNL realizado, PNL neto, funding y comisiones; los valores numéricos usan color por signo.
- Los cambios de ratio 1h/24h en `Mis posiciones` tienen tipografía y contraste reforzados para lectura en paneles angostos.
- `Pares cerrados` incluye el cambio del ratio desde el cierre cuando los fills y precios actuales son verificables.
- KLineCharts se carga como archivo local verificado por SHA-256; todavía no es una dependencia npm importada por TypeScript.
- El backend separa datos de mercado, ledger y órdenes en almacenamientos distintos.

## Riesgos conocidos

- La interfaz contiene rutas de órdenes reales y la UI de órdenes React no está validada en testnet.
- `PairActions` ahora muestra el contador de tickets, bloquea tickets vencidos, refresca el par tras ejecutar y tolera respuestas HTTP no JSON; esto está validado localmente, pero no reemplaza la validación en testnet.
- El plan vigente todavía contempla navegación móvil, separación adicional de `App.tsx` y tareas de backend.
- No se debe tratar el historial local de PNL como continuo: puede contener huecos cuando no hubo registro.

## Fuente de verdad

Para el detalle histórico, consultar `docs/current/FASE_1_ESTADO.md`, `docs/current/PLAN_CONSOLIDACION.md` y `docs/history/CHANGELOG.md`.
