# Estado actual

Fecha de referencia: 2026-10-26.

## Confirmado en esta copia

- Rama de trabajo limpia al iniciar esta documentación.
- Último commit observado: `0c6e8f4 feat: add scanner chart timeframe controls`.
- React es la interfaz principal y se sirve en `/react`.
- `/` y `/aurora` permanecen como interfaces legacy/fallback.
- El frontend React incluye explorador de pares, gráficos de ratio y PNL, radar, estados de frescura y acciones de pares.
- El dashboard React tiene `Mis posiciones` compacta (par, PNL y ratio 1h/24h), filtros en un desplegable y `Radar de posiciones` junto a `Pares cerrados` en escritorio.
- `Resumen del par` muestra solo long/short, nominales, exposición total, PNL flotante, PNL long/short, PNL realizado, PNL neto, funding y comisiones; los valores numéricos usan color por signo.
- Los cambios de ratio 1h/24h en `Mis posiciones` tienen tipografía y contraste reforzados para lectura en paneles angostos.
- El PNL total oficial de las cards y la serie principal priorizan Hyperliquid; el cálculo local permanece como fallback y reconciliación.
- La card de PNL total incluye una mini línea de evolución; el gráfico acumulado usa más ticks y la paleta verde/rosa del gráfico de ratio.
- `Resumen del par` muestra exposición primero y las patas como `LONG/SHORT símbolo` con su PNL en la misma fila.
- El detalle del Explorador queda sticky junto a la tabla en escritorio y vuelve al flujo normal en móvil.
- `Pares cerrados` incluye el cambio del ratio desde el cierre cuando los fills y precios actuales son verificables.
- KLineCharts se carga como archivo local verificado por SHA-256; todavía no es una dependencia npm importada por TypeScript.
- El backend separa datos de mercado, ledger y órdenes en almacenamientos distintos.
- Se agregó un análisis retrospectivo local en `scripts/analyze_operations.py`, con módulos puros en `pairs_desk/learning_data.py`, `operation_learning.py` y `learning_metrics.py`. Lee settings/SQLite en modo solo lectura y genera el informe privado en `~/.local/share/crypto-pairs-desk/analysis`.
- El informe también reconcilia en vivo `perpMonth` de Hyperliquid y las patas activas; la última verificación identificó 14 pares activos y aproximadamente USD 2.454 de PNL de 30 días.
- La bitácora de órdenes auto-reconcilia intentos `uncertain` solo cuando hubo únicamente intención, ningún envío/fill y las cantidades actuales coinciden con las originales; los desbalances reales siguen bloqueados. Ver `docs/current/AUTO_RECONCILIACION_TRADING.md`.

## Riesgos conocidos

- La interfaz contiene rutas de órdenes reales y la UI de órdenes React no está validada en testnet; la auto-reconciliación no envía órdenes.
- `PairActions` ahora muestra el contador de tickets, bloquea tickets vencidos, refresca el par tras ejecutar y tolera respuestas HTTP no JSON; esto está validado localmente, pero no reemplaza la validación en testnet.
- El plan vigente todavía contempla navegación móvil, separación adicional de `App.tsx` y tareas de backend.
- No se debe tratar el historial local de PNL como continuo: puede contener huecos cuando no hubo registro.

## Fuente de verdad

Para el detalle histórico, consultar `docs/current/FASE_1_ESTADO.md`, `docs/current/PLAN_CONSOLIDACION.md` y `docs/history/CHANGELOG.md`.
