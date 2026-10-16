# Fase 1A — Catálogo e históricos de mercado

## Objetivo

Crear una base de datos de mercado separada de la contabilidad y de la ejecución, con catálogo estable de instrumentos y pares, ingesta incremental de velas y almacenamiento Parquet reutilizable por el escritorio, el futuro Laboratorio, el Scanner y el backtesting.

## Resultado esperado

La aplicación podrá actualizar y consultar datos históricos sin descargar nuevamente todo Hyperliquid ni bloquear el refresco normal del dashboard. La primera entrega será una infraestructura interna; no agregará pantallas nuevas ni enviará órdenes.

## Arquitectura aprobada

Los datos públicos de mercado vivirán separados de los datos operativos:

```text
~/.local/share/crypto-pairs-desk/
├── market.sqlite3       # catálogo, pares y checkpoints de ingesta
├── ledger.sqlite3       # fills y funding de la cuenta
├── orders.sqlite3       # bitácora de intentos de trading
└── market-data/
    ├── candles/         # series de velas Parquet
    └── ratios/          # reservado para una fase posterior
```

La ruta será configurable mediante una dependencia explícita de los módulos, con el valor anterior como default. Nunca se guardarán estos datos dentro del repositorio ni en `settings.json`.

## Modelo mínimo

### Instrumentos

Cada instrumento tendrá un ID estable y conservará el mercado de origen:

```text
instrument_id, symbol, venue, asset_type, active, metadata_json
```

`venue` distinguirá como mínimo `core` y `xyz`. La identidad no dependerá de la posición actual de la cuenta.

### Pares

Cada par tendrá una identidad reproducible:

```text
pair_id, long_instrument_id, short_instrument_id, label, active, metadata_json
```

El `pair_id` se construirá a partir de los IDs normalizados de ambas patas y no se reutilizará para representar una operación histórica distinta.

### Ingesta

Cada combinación instrumento/intervalo tendrá un checkpoint:

```text
instrument_id, interval, covered_from_ms, covered_to_ms,
last_success_ms, status, error, updated_ms
```

La ingesta será idempotente: repetir una ventana no creará duplicados ni modificará silenciosamente una vela ya almacenada con otro contenido.

## Formato Parquet de velas

Cada archivo contendrá como mínimo:

```text
instrument_id, venue, interval, timestamp_ms,
open, high, low, close, volume, source
```

Se validará que los precios y el volumen sean finitos, que `high >= max(open, close, low)`, que `low <= min(open, close, high)` y que los timestamps estén ordenados y sin duplicados.

La partición inicial será por instrumento e intervalo. No se calcularán ratios históricos en esta fase; la carpeta `ratios/` queda reservada para una etapa posterior, cuando el contrato de pares esté probado.

## Flujo de ingesta

```text
Hyperliquid candleSnapshot
        ↓
adaptador de respuesta
        ↓
normalización + validación
        ↓
merge idempotente de ventana
        ↓
Parquet + checkpoint SQLite
```

La ingesta no se ejecutará dentro de `/api/state`, no se ejecutará automáticamente durante cada refresco del escritorio y no tendrá acceso a `secure_trade_routes.py`.

La primera interfaz será de servicio interno y podrá ejecutarse manualmente o desde una tarea futura:

```python
sync_candles(instrument_id, interval, start_ms, end_ms) -> SyncResult
```

`SyncResult` informará filas recibidas, filas nuevas, ventana cubierta, huecos detectados y estado final. Los errores no avanzarán el checkpoint.

## Calidad y ausencia de datos

- No se interpolarán velas faltantes.
- Una respuesta vacía no se convertirá en una serie válida.
- Los huecos quedarán registrados como calidad incompleta.
- Las respuestas inválidas no se escribirán en Parquet.
- El consumidor deberá poder distinguir `sin datos`, `datos parciales` y `datos completos`.

## Seguridad y límites

- No se modificará `secure_trade_routes.py`.
- No se usarán claves privadas, keyring ni endpoints de órdenes.
- No se cambiará el contrato de `/api/state` en esta fase.
- No se añadirá ingesta al ciclo de renderizado de Streamlit ni al refresco de React.
- No se migrarán todavía `settings.json`, `ledger.sqlite3` ni `orders.sqlite3`.

## Verificación

- Pruebas unitarias con respuestas simuladas de `candleSnapshot`.
- Repetir la misma ventana produce el mismo Parquet y no duplica filas.
- Una respuesta inválida no avanza el checkpoint.
- Los límites de OHLC y timestamps se validan antes de escribir.
- La suite existente continúa pasando.
- La compilación de React continúa pasando.

## Fuera de alcance

- Scanner de pares.
- Watchlist.
- Laboratorio visual.
- Cálculo y persistencia de ratios históricos.
- Backtesting nuevo.
- Automatización periódica en segundo plano.
- Cualquier cambio en el flujo de órdenes.
