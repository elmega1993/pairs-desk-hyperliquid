# Arquitectura

## Capas

```text
React (`react_frontend/`)
        │ HTTP local
FastAPI (`read_only_server.py`)
        │
Dominio (`pairs_desk/`) ─── Trading (`secure_trade_routes.py`)
        │
Mercado / ledger / órdenes / snapshots
```

## Interfaz

`react_frontend/` es la interfaz principal. Vite compila el código a `react_dist/`. La aplicación contiene vistas de posiciones, PNL, gráficos de ratio, radar, explorador y acciones de pares. `frontend/` y `aurora/` son superficies legacy y no deben confundirse con la fuente React principal.

## API y dominio

`read_only_server.py` sirve la API local y el frontend compilado. `pairs_desk/` contiene ingestión y calidad de mercado, análisis de pares, ratios, niveles, métricas, ledger, almacenamiento y servicios auxiliares. Las rutas de ejecución real están aisladas en `secure_trade_routes.py`.

## Datos

- Mercado: catálogo, checkpoints y velas históricas.
- Ledger: fills y funding de la cuenta.
- Órdenes: bitácora de intentos de trading.
- Snapshots: historial local usado para series y estados.

La separación evita usar una serie de mercado como si fuera contabilidad o convertir un registro local incompleto en una fuente histórica continua.

## Dependencias especiales

KLineCharts se sirve desde `pairs_desk/vendor/klinecharts.min.js` y se verifica mediante `pairs_desk/vendor/klinecharts.sha256`. El plan vigente contempla migrarlo a una dependencia npm.

## Límites importantes

No cambiar rutas de trading, ledger ni contabilidad durante trabajos puramente visuales. Si una modificación cruza esos límites, actualizar pruebas y documentación de estado antes de continuar.
