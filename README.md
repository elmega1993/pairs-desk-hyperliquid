# Pairs Desk 2.0 — Consolidación

Aplicación de análisis de posiciones y ratios de Hyperliquid. React es la interfaz principal y se sirve en `/react`. La interfaz estable anterior continúa disponible en `/` y Aurora en `/aurora` como fallback legacy.

## Ubuntu

Ejecutar `./iniciar_frontend.sh` desde la carpeta del proyecto. El lanzador prepara el entorno Python, verifica KLineCharts por SHA-256 y compila React únicamente si el código cambió o falta la compilación. Requiere Python 3 y Node.js 20+ con npm.

El launcher recomendado es `./iniciar_frontend.sh`: inicia la API local y prepara la interfaz React. `./iniciar.sh` conserva la interfaz Streamlit legacy.

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

## Arquitectura breve

- `react_frontend/`: código fuente de la interfaz principal React.
- `read_only_server.py`: API local y servidor FastAPI.
- `pairs_desk/`: lógica de negocio, métricas, ledger e integración con Hyperliquid.
- `secure_trade_routes.py`: rutas de operaciones reales; revisar con especial cuidado.
- `frontend/`: interfaz estable legacy/fallback.
- `aurora/`: interfaz legacy anterior.
- `app.py`: interfaz Streamlit legacy.
- `tests/`: pruebas Python y suites JavaScript.
- `scripts/`: utilidades y backtests.

## Datos históricos de mercado — Fase 1A

La base de mercado está separada de la contabilidad y de la ejecución:

- `~/.local/share/crypto-pairs-desk/market.sqlite3`: catálogo de instrumentos, pares y checkpoints de ingesta.
- `~/.local/share/crypto-pairs-desk/market-data/candles/`: velas validadas en formato Parquet.
- `~/.local/share/crypto-pairs-desk/ledger.sqlite3`: fills y funding de la cuenta.
- `~/.local/share/crypto-pairs-desk/orders.sqlite3`: bitácora de intentos de trading.

La ingesta de velas de Fase 1A es un servicio interno/manual. No se ejecuta al refrescar el dashboard, no modifica `/api/state` y no tiene acceso a las rutas de órdenes. Los módulos de catálogo, calidad, almacenamiento e ingesta se prueban de forma aislada antes de conectarlos a futuras pantallas.

## Documentación

- `docs/history/CHANGELOG.md`: cambios verificados.
- `docs/current/PLAN_CONSOLIDACION.md`: fases y tareas pendientes.
- `docs/current/FASE_1_ESTADO.md`: estado de la base React.
- `docs/current/REACT_DEPENDENCIES.md`: instalación reproducible y KLineCharts.
- `docs/history/`: entregas, auditorías y notas históricas.
- `docs/legacy/`: documentos históricos, pueden estar desactualizados.
