# Fixes aplicados según Auditoría de Pairs Desk — 29/09/2026

## Corregido
- Fallo parcial de `xyz`: ya no se interpreta como “0 posiciones xyz”; se muestra error global, los pares afectados quedan “sin datos” y un snapshot degradado no reemplaza al último snapshot bueno.
- Fallo de `userFills`: se propaga el estado parcial a la UI y al KPI agregado de PnL.
- Rebates maker: los fees conservan el signo; un fee negativo reduce las comisiones netas.
- Huecos de velas: solo se forward-fillea el `close`; `open/high/low` del hueco se igualan al cierre previo para no inventar mechas.
- `settings.json`: se validan tipos de raíz, `address` y `pairs`; ante estructura inesperada se bloquea el guardado.
- Selección de pares: tabla con key estable, selección persistida por id del par y widgets asociados al id en vez del índice.
- Gráfico: `uirevision` incluye rango, línea de entrada usa datetime compatible con el eje y D/1W se muestran por fecha UTC para evitar el desplazamiento visual a las 21:00 del día anterior.
- Botón Actualizar: ya no vacía la caché de velas, reduciendo el riesgo de rate limit.
- HTTP: timeouts separados de conexión/lectura y menos reintentos.
- Equity: cuando Core y xyz reportan ambos valores, la app evita agregarlos con `max()`/suma arbitraria y muestra ambas fuentes por separado.
- Launcher: hash de requirements con Python en vez de `sha256sum`, mejorando compatibilidad con macOS.
- Código muerto `read_positions()` eliminado e import no usado removido.

## Tests
- Suite original + tests de regresión de auditoría: 10 passed.
- `py_compile`: OK.
- `bash -n iniciar.sh`: OK.

## Pendiente para una siguiente iteración
- Funding real vía `userFunding` por pata desde apertura.
- Paginación incremental de `userFillsByTime` para historiales >2000 fills.
- Refactor de `app.py`, CI, dataclasses y separación de lógica/UI.
- Log-ratio / hedge ratio / cointegración y mejoras operativas avanzadas.
