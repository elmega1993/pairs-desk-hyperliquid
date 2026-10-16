# Pairs Desk · Analítica v3 (entrega parcial)

## Implementado
- Núcleo puro: `analytics.py`, `regime.py`, `levels_v3.py`.
- API de lectura `/api/analytics`, `/api/levels/{pair_id}`, `/api/review/closed` y respuesta conservadora `/api/portfolio-risk`.
- React: cola de atención, seguimiento y detalle; muestra niveles v3 cuando están disponibles.
- Backtest offline básico: `scripts/backtest_levels.py` con CSV `close`.
- Los cálculos descriptivos no ejecutan operaciones ni guardan settings.

## Pendiente para completar el plan original
- Fase 4: unificación de alertas e histéresis con el motor v3 y switch v2/v3.
- Fase 5: gates de liquidación post-ADD y correlación, marcas bloqueadas y equilibrio en el gráfico; supresión de escalones ejecutados.
- Fase 6: reconstrucción real de MAE/MFE y efectos ADD/TP de cerrados; walk-forward de 730 días con calibración out-of-sample, intervalos bootstrap y resultados reales.
- Fase 7: beta, correlaciones, funding carry y profundidad HIP-3.
- Build React no verificado: npm ci --offline falla por caché ausente de Vite.

## Limitaciones
- `/api/analytics` obtiene posiciones con dos lecturas a Hyperliquid, sin llamar a `states()` ni escribir snapshots. No se reutilizan todavía los fills.
- `funding_per_day_usd` permanece null hasta verificar integridad del ledger.
- El escenario de liquidación v3 es una aproximación, no un cálculo del motor de margen.
- `hit_rates` no estima probabilidades futuras.
- Los niveles no están calibrados con datos reales. No utilizarlos para ejecución automática.
- La interfaz React no está validada mediante build ni pruebas visuales.
