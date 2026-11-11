# Pairs Desk 2.0 — Consolidación

Aplicación de análisis de posiciones y ratios de Hyperliquid. React es la interfaz principal y se sirve en `/react`. La interfaz estable anterior continúa disponible en `/` y Aurora en `/aurora` como fallback legacy.

## Funciones actuales

- Desk: asesor con identidad editable, conversaciones y memoria persistentes. Codex App Server con sesión de ChatGPT y consentimiento de contexto; Ollama local como alternativa. [Guía](docs/current/DESK_MEMORIA.md).
- TWAP nativo de Hyperliquid para aumentar, reducir y cerrar pares, duración en minutos/horas/días hasta 7 días, seguimiento/cancelación por pata y representación temporal en el gráfico. [Guía y límites](docs/current/NATIVE_TWAP.md).
- Cuenta/estrategia, costos, funding, ratio/PNL, explorador y fuentes oficiales/estimadas identificadas. [Estado y verificación](CURRENT_STATE.md).

Bases de datos, settings, memorias personales, credenciales, exportaciones y builds se generan/conservan localmente y no forman parte del repositorio. Las órdenes reales requieren configuración, previsualización y confirmación; las patas no se ejecutan atómicamente.

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

## Datos históricos y ratios de mercado — Fases 1A/1B

La base de mercado está separada de la contabilidad y de la ejecución:

- `~/.local/share/crypto-pairs-desk/market.sqlite3`: catálogo de instrumentos, pares y checkpoints de ingesta.
- `~/.local/share/crypto-pairs-desk/market-data/candles/`: velas validadas en formato Parquet.
- `~/.local/share/crypto-pairs-desk/ledger.sqlite3`: fills y funding de la cuenta.
- `~/.local/share/crypto-pairs-desk/orders.sqlite3`: bitácora de intentos de trading.

La ingesta de velas de Fase 1A y la coordinación controlada de Fase 1C son servicios internos/manuales. `MarketSyncService` reutiliza checkpoints, solicita solo ventanas nuevas o pendientes, mide duración, filas nuevas, huecos y errores, y puede procesar varios instrumentos secuencialmente. No se ejecuta al refrescar el dashboard, no modifica `/api/state` y no tiene acceso a las rutas de órdenes. Un scheduler residente queda para una etapa posterior.

La capa de ratios de Fase 1B recibe las dos series canónicas en memoria y expone `build_pair_ratios(...)`. Alinea por timestamps exactos, sin interpolar, y devuelve `price_ratio`, `log_ratio`, cobertura (`complete`, `partial` o `empty`) y errores de calidad. Todavía no persiste ratios ni agrega endpoints o pantallas.

El Explorador de Fase 2 está disponible en la vista React **Explorador**. Primero consulta los activos disponibles de Core/XYZ mediante metadatos de Hyperliquid; luego permite elegir una pata LONG y otra SHORT y analizar el par bajo demanda. `POST /api/scanner/analyze` descarga las velas faltantes, las guarda en Parquet y devuelve el ratio histórico, cobertura y calidad. No modifica `/api/state` ni envía órdenes.

## Documentación

- `docs/history/CHANGELOG.md`: cambios verificados.
- `docs/current/PLAN_CONSOLIDACION.md`: fases y tareas pendientes.
- `docs/current/FASE_1_ESTADO.md`: estado de la base React.
- `docs/current/REACT_DEPENDENCIES.md`: instalación reproducible y KLineCharts.
- `docs/history/`: entregas, auditorías y notas históricas.
- `docs/legacy/`: documentos históricos, pueden estar desactualizados.
