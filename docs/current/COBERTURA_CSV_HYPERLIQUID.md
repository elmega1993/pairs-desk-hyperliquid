# Cobertura de exportaciones — 2026-11-06

Archivos revisados en `Archivos-Hyperliquid/`, sin importarlos ni modificar contabilidad.

- `trade_history.csv`: 1.267 filas, desde 19/03 hasta 06/11. Columnas: time, coin, dir, px, sz, ntl, fee, closedPnl.
- `funding_history.csv`: 8.274 filas, desde 27/03 hasta 06/11. Columnas: time, coin, sz, side, payment, rate.
- Entre 23/09 y 06/10 inclusive: 194 operaciones (49 nombres de activos) y 354 pagos de funding (51 nombres de activos), con registros de ambos archivos en las 14 fechas.
- No se encontraron filas idénticas duplicadas. Esto no prueba que no falten operaciones.
- Las fechas exportadas no indican zona horaria. Verificar su correspondencia contra timestamps de operaciones conocidas antes de calcular cierres diarios.

## Reconstrucción pendiente

Normalizar símbolos (trade y funding usan formatos distintos), verificar zona horaria, reconstruir inventario con operaciones anteriores al 23/09 y contrastar tamaños/lados con funding. Obtener precios históricos compatibles con la valoración oficial para calcular flotante al cierre local. Conciliar contra puntos oficiales disponibles y conservar diferencias explícitas antes de añadir estimaciones al gráfico. Operaciones y funding por sí solos no constituyen PNL total diario con flotante.

## Gráfico

El umbral de huecos del registro local no se aplica a series oficiales Hyperliquid. Su muestreo variable no representa una interrupción de la app. La línea une muestras oficiales disponibles; los puntos intermedios de la línea no son snapshots recuperados.
