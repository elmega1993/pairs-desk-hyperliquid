# Testing

## Validación estándar

Desde la raíz del repositorio:

```bash
pytest tests/
```

La suite incluye pruebas Python y suites JavaScript integradas. Para reconstruir la interfaz:

```bash
(cd react_frontend && npm ci)
(cd react_frontend && npm run build)
```

## Pruebas visuales

`tests/test_visual_smoke.py` usa Playwright y Chromium. Requiere instalar Playwright, sus navegadores y tener `react_dist/` actualizado. Si esas dependencias no están disponibles, la prueba puede omitirse según la lógica de la suite; eso no equivale a validación visual completa.

## Qué revisar según el cambio

- React, navegación u ordenamiento: pruebas de consolidación y suites `.cjs` relacionadas.
- PNL y gráficos: `test_pnl_*`, `test_visual_smoke.py` y la suite de modelo correspondiente.
- Mercado y ratios: `test_market_*`, `test_market_ratios.py` y `test_market_pair_analysis.py`.
- Ledger, órdenes o seguridad: `test_ledger.py`, `test_trading.py`, `test_secure_frontend_routes.py` y pruebas S1.
- KLineCharts: `test_klinecharts_integrity.py`.

## Criterio de cierre

Una modificación no se considera verificada solo porque compila. Hay que ejecutar las pruebas aplicables, registrar cualquier omisión por dependencias y revisar que no se hayan tocado rutas sensibles sin intención.

## Desk persistente

```bash
.venv_frontend/bin/python -m pytest tests/test_desk_memory.py tests/test_desk_context.py tests/test_desk_integration.py tests/test_local_advisor.py tests/test_advisor_routes.py -q
node tests/test_advisor_api_behavior.cjs
node tests/test_desk_ui_behavior.cjs
node tests/test_desk_memory_evidence.cjs
npm --prefix react_frontend run build
```

Pruebas deterministas usan SQLite temporal y transporte Ollama simulado. No ejecutan órdenes ni cambian memorias personales. La aceptación real de memoria debe usar otra base mediante PAIRS_DESK_AI_DATA_DIR para no enseñar preferencias ficticias al usuario; probar reinicio y conversación nueva. Las cifras operativas deben contrastarse con el mismo snapshot del backend, respetando vigencia. Smoke Chromium de Desk registrado en `docs/current/DESK_MEMORIA.md`.

## TWAP nativo

```bash
.venv_frontend/bin/python -m pytest tests/test_native_twap.py tests/test_native_twap_monitor.py tests/test_native_twap_routes.py tests/test_metrics.py -q
node tests/test_twap_model.cjs
node tests/test_twap_chart.cjs
node tests/test_twap_ticket_ui.cjs
node tests/test_twap_orders_ui.cjs
npm --prefix react_frontend run build
```

Transportes y SQLite simulados/temporales: nunca habilitar ni enviar órdenes reales en estas pruebas. Resultado global 2026-11-10: 508 passed, 1 skipped y 2 fallos preexistentes (call_stats y zscore_alignment_ui). Smoke sintético Chromium desktop/móvil, sin mutaciones. Validación contra exchange pendiente: `docs/current/NATIVE_TWAP.md`.

Corrección mínimo TWAP y diagnóstico: 2026-11-10, suite completa 511 passed, 1 skipped, mismos dos fallos preexistentes. Tres regresiones Python y dos casos JS reproducen el mínimo omitido, pérdida del motivo, etiqueta No enviada y falsa marca en el gráfico. Cuatro suites JS de TWAP y build aprobados.

2026-11-11: regresión de firma canónica TWAP y errores de agente: 515 passed, 1 skipped, mismos dos fallos preexistentes; 48 focalizadas, cuatro suites JS y build aprobados. Ninguna orden enviada en pruebas. Servidor reiniciado, endpoints 200, trading deshabilitado.

Diagnóstico TWAP desconocido (2026-11-11): suite 527 passed, 1 skipped, dos fallos conocidos; pruebas adicionales de saneamiento, persistencia, migración preservando trabajo activo y React. Mensajes sintéticos no son errores observados en producción.

Media TWAP 2026-11-11: 531 passed, 1 skipped y mismos dos fallos conocidos. Tests entry_history/native_twap/routes y JS gráfico verifican fusiones, deduplicación, inicio verificable, cantidades/promedios, aislamiento, contabilidad intacta y escala relativa. Build aprobado. Contraste de solo lectura GMX/INJ reconstruye 30 pasos con media actual coherente.

## Cierre de sesión 2026-11-11 — resultado vigente

Python: **534 passed, 1 skipped**. Los fallos antes mencionados de call_stats y zscore_alignment se resolvieron actualizando sus contratos obsoletos: el contador refleja peticiones terminadas; Z-score usa un indicador nativo cuyo resultado conserva la longitud/índices de las velas, con warmup y valores contrastados. **21 suites .cjs aprobadas**, incluido test_zscore_alignment.cjs. Build Vite aprobado. TypeScript estricto conserva errores pendientes; Vite no sustituye ese chequeo. No se operó en el exchange para ejecutar pruebas.

```bash
.venv_frontend/bin/python -m pytest tests/ -q
for test_file in tests/*.cjs; do node "$test_file" || exit 1; done
npm --prefix react_frontend run build
```
