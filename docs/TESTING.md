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
