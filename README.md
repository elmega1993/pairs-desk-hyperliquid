# Pairs Desk 2.0 — Consolidación

Aplicación de análisis de posiciones y ratios de Hyperliquid. La interfaz React se encuentra en `/react`; Aurora anterior en `/aurora` y el frontend estable en `/`.

## Ubuntu

Ejecutar `./iniciar_frontend.sh` desde la carpeta del proyecto. El lanzador prepara el entorno Python, verifica KLineCharts por SHA-256 y compila React únicamente si el código cambió o falta la compilación. Requiere Python 3 y Node.js 20+ con npm.

## Pruebas

```bash
pip install -r requirements_frontend.txt pytest httpx
(cd react_frontend && npm ci)
pytest tests/
```

`pytest` también ejecuta las suites de Node (`tests/*.cjs`); si falta `node` o `react_frontend/node_modules`, esas pruebas se omiten.

Para las pruebas de navegador (`tests/test_visual_smoke.py`): `pip install playwright && playwright install chromium` y `(cd react_frontend && npm run build)`. Sin eso, se omiten.

## Precauciones

Este proyecto contiene rutas de trading reales, también desde la interfaz React (**Agregar par** y **Operar par**). No asumir que la aplicación es de solo lectura: comprobar permisos y controles antes de cualquier operación. La UI de órdenes de React no está validada en testnet. No distribuir configuraciones, secretos ni bases de datos personales.

## Documentación

- `CHANGELOG.md`: cambios verificados.
- `docs/PLAN_CONSOLIDACION.md`: fases y tareas pendientes.
- `docs/FASE_1_ESTADO.md`: estado de la base React.
- `docs/REACT_DEPENDENCIES.md`: instalación reproducible y KLineCharts.
- `docs/legacy/`: documentos históricos, pueden estar desactualizados.
