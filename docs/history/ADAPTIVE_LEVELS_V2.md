# Adaptive Levels v2 — React

- ADD/TP calculados de forma independiente, sin invalidar el conjunto por una cola ausente.
- 60 velas diarias mínimas; requiere al menos 8 observaciones de cada signo para cada familia de objetivos.
- Régimen estructural extremo: se suprimen ADD; TP solo descriptivos.
- Referencia: management_entry_ratio guardado o ratio derivado de los entryPx de ambas posiciones activas verificadas. Nunca precio actual como entrada ficticia.
- React recarga niveles al actualizar cartera y representa también resultados parciales.
- `level_reasons` explica los niveles omitidos. El endpoint es de solo lectura y no ejecuta órdenes.
- Los percentiles de movimientos de 14 días no constituyen probabilidades de alcanzar el nivel; no se han validado con backtesting.
