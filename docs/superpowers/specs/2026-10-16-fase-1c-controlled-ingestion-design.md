# Fase 1C — Ingesta operativa controlada

## Objetivo

Agregar una capa de coordinación sobre la ingesta de Fase 1A para actualizar únicamente ventanas nuevas o pendientes, medir cada sincronización y permitir una futura programación externa sin involucrar el refresco de la interfaz.

## Contrato

El módulo `pairs_desk.market_sync` expondrá:

```python
sync_incremental(instrument_id, interval, end_ms, initial_start_ms) -> SyncMetrics
sync_many(instrument_ids, interval, end_ms, initial_start_ms) -> BatchSyncResult
```

`SyncMetrics` conservará el `SyncResult` de Fase 1A y agregará `duration_ms`, ventana solicitada y si la corrida fue omitida por estar actualizada. `BatchSyncResult` contendrá las métricas por instrumento y totales de filas nuevas, errores y duración.

## Reglas

- Si existe checkpoint, la siguiente ventana comenzará en `covered_to_ms` para revalidar la última vela y cubrir huecos sin perder datos.
- Si no existe checkpoint, se usará `initial_start_ms`.
- Si la ventana ya está actualizada, se devolverá `up_to_date` sin llamar a Hyperliquid.
- Las sincronizaciones de un lote serán secuenciales y aisladas por instrumento.
- La caché existente de Parquet y los checkpoints serán la fuente compartida.
- La duración se medirá con reloj monotónico y no afectará el timestamp de cobertura.

## Aislamiento

La capa será invocable manualmente o desde un scheduler externo. No se agregará al render de React, `/api/state`, startup de FastAPI ni a las rutas de trading.

## Verificación

- Primera corrida usa la ventana inicial.
- Corridas posteriores reutilizan el checkpoint con solapamiento seguro.
- Una corrida al día devuelve `up_to_date` sin fetch.
- Se registran duración, filas nuevas, huecos, errores y cobertura.
- Un error de un instrumento no cancela los demás del lote.
