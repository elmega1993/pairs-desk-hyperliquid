# Estado actual

Fecha de referencia: 2026-10-17.

## Confirmado en esta copia

- Rama de trabajo limpia al iniciar esta documentación.
- Último commit observado: `0c6e8f4 feat: add scanner chart timeframe controls`.
- React es la interfaz principal y se sirve en `/react`.
- `/` y `/aurora` permanecen como interfaces legacy/fallback.
- El frontend React incluye explorador de pares, gráficos de ratio y PNL, radar, estados de frescura y acciones de pares.
- KLineCharts se carga como archivo local verificado por SHA-256; todavía no es una dependencia npm importada por TypeScript.
- El backend separa datos de mercado, ledger y órdenes en almacenamientos distintos.

## Riesgos conocidos

- La interfaz contiene rutas de órdenes reales y la UI de órdenes React no está validada en testnet.
- `PairActions` ahora muestra el contador de tickets, bloquea tickets vencidos, refresca el par tras ejecutar y tolera respuestas HTTP no JSON; esto está validado localmente, pero no reemplaza la validación en testnet.
- El plan vigente todavía contempla navegación móvil, separación adicional de `App.tsx` y tareas de backend.
- No se debe tratar el historial local de PNL como continuo: puede contener huecos cuando no hubo registro.

## Fuente de verdad

Para el detalle histórico, consultar `docs/current/FASE_1_ESTADO.md`, `docs/current/PLAN_CONSOLIDACION.md` y `docs/history/CHANGELOG.md`.
