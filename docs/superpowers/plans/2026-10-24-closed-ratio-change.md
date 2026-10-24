# Plan: cambio del ratio desde el cierre

## Objetivo

Mostrar en `Pares cerrados` cuánto cambió el ratio desde el momento en que se cerró cada par hasta el precio actual de Hyperliquid.

## Decisión

Usar como referencia el ratio VWAP de los fills de cierre de ambas patas. Para historiales antiguos se reconstruye desde los fills disponibles; si falta una referencia o el precio actual, la UI muestra `N/D`. El precio actual se consulta con `allMids` para Core y XYZ.

## Alcance

- Persistir `close_ratio` al archivar nuevos pares.
- Reconstruir `close_ratio` para pares antiguos cuando sea posible.
- Devolver `ratio_since_close_pct` en `/api/state`.
- Mostrar `DESDE CIERRE` entre `CIERRE` y `REALIZADO`, con signo y color.
- Agregar pruebas unitarias y de contrato UI.

## No alcance

- No modificar órdenes ni rutas de trading.
- No cambiar el gráfico histórico existente.
- No inventar valores cuando faltan fills o precios.
