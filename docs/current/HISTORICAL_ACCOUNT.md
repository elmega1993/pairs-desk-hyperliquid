# Base histórica de cuenta

Implementada el 06/11/2026 en `~/.local/share/crypto-pairs-desk/historical_account.sqlite3`, permisos 0600. Separada del ledger operativo, mercado y órdenes. Datos privados: no incluir la base en Git, reportes públicos ni entregas.

## Fuentes y alcance comprobado

- Copia idempotente de eventos del ledger, con identidad y cuenta originales: 30.729 eventos en la primera importación.
- CSV originales conservados como bytes con SHA-256 y filas consultables: 1.267 trades y 8.274 registros de funding. No se suman al ledger.
- Las 1.216 operaciones de futuros del CSV concilian con el ledger. El `closedPnl` exportado es neto de fees; el del API es bruto. Las otras 51 operaciones son spot y quedan como evidencia.
- Las 8.274 filas de funding concilian: 7.346 horarias y 928 agregadas por día UTC. No interpretar el agregado de las 21:00 locales como un único pago horario.
- Símbolos de exportación normalizados contra operaciones verificadas; zona horaria de CSV confirmada como Buenos Aires con timestamps y precios/cantidades del API.
- Snapshots anteriores y backups importados como evidencia; nunca se mezclan con PNL oficial de cuenta.
- Velas públicas de 86 instrumentos: aproximadamente 463.000 muestras de 1h/15m; se guardan payload, intervalo y tiempo de cierre.
- Puntos oficiales persistidos en tabla propia, sin convertir estimaciones en observaciones oficiales.

## Reconstrucción y límites

La secuencia de fills se encadena por `startPosition`, incluso dentro del mismo milisegundo: `tid` no ordena la ejecución. Se verificó continuidad de inventario y se reconstruyó cantidad y precio medio. Cada cierre diario local se valora con la última vela completada, sin utilizar precios futuros. Precios ausentes, entradas desconocidas o precios de más de una hora impiden calcular ese cierre.

La variación oficial ya representa el neto de la cuenta. Se corrigió la card, que volvía a descontar funding y fees: ahora `net_pnl` coincide con el extremo de la curva oficial y el bruto es neto - funding + fees, cuando esos costos son verificables. Una comprobación viva de realizado + flotante + funding - fees frente al all-time absoluto dio USD 0,28 de diferencia en respuestas no simultáneas. Los costos spot quedan fuera de esta vista de futuros.

Hay 45 fechas del 23/09 al 06/11, con estimaciones para todas. El primer día está rebasado al primer punto oficial disponible y es parcial; el último está en curso. Se conservan realizado, flotante, fees, funding, estimación bruta y estimación neta. La comparación contra Hyperliquid usa `realizado + flotante + funding - fees USDC`, sin afirmar que esto sea una recuperación exacta del mark histórico.

Con precios de 15m, la conciliación observada tuvo unos USD 9 de diferencia absoluta media y USD 173 máxima. Las velas contienen precios negociados; no equivalen necesariamente al mark usado para valorar la cuenta. La auditoría gratuita ubicó el máximo desvío el 11/10 a las 20:56: el precio usado para STRK tenía 11 minutos de antigüedad; el rango de la vela siguiente admitía una variación de -USD 260 a +USD 12 en esa posición. Los 103 puntos oficiales auditados quedaron dentro de los rangos retrospectivos OHLC (incluyendo incertidumbre del punto inicial). Eso verifica plausibilidad, no identidad con el mark ni el momento exacto de cada máximo/mínimo de una vela.

`scripts/audit_account_history.py` guarda ese análisis en `valuations` y `metadata`. También conserva 28.036 evidencias de precio de oráculo inferido desde funding, con límite de error por redondeo, en `oracle_evidence`. El oráculo no es el mark y no se sustituye por él. La auditoría es offline y no requiere datos pagos.

`quality=estimated_not_official`: la vista permite alternar `Estimado diario` (45 fechas desde el 23/09, neto reconstruido) y `Muestras oficiales` (cierres aproximados derivados del muestreo disponible). Por defecto muestra el estimado cuando existe. Se identifica como estimado; las métricas de días positivos, promedio y racha corresponden a la fuente seleccionada. El gráfico conserva la curva oficial. El día en curso usa el último acumulado oficial menos el cierre anterior estimado, siempre que coincidan cuenta y ancla temporal. No se reparten ni ocultan diferencias históricas para forzar coincidencia.

Para investigar coincidencia exacta se requieren precios de valoración históricos. Hyperliquid ofrece archivos de asset contexts en S3; su documentación indica costos a cargo del solicitante, posibles huecos y actualización no garantizada: https://hyperliquid.gitbook.io/hyperliquid-docs/historical-data. No se descargaron archivos de pago.

## Operación

Desde el repo:

```bash
.venv_frontend/bin/python scripts/build_account_history.py
.venv_frontend/bin/python scripts/build_account_history.py --offline
.venv_frontend/bin/python scripts/audit_account_history.py
```

La primera orden importa evidencia nueva, descarga incrementalmente velas de 15m y reconstruye/actualiza el informe de cobertura en `metadata`. La segunda reconstruye solo con información local. Las descargas se conservan por instrumento; un HTTP 429 detiene la ingesta y permite retomarla. Consultar la fecha del informe y los precios disponibles al usar offline.

Mientras la app consulta estado, la rutina de conservación oficial copia las muestras y eventos del ledger a esta base existente cada cinco minutos aproximadamente. No descarga precios ni recalcula estimaciones desde un endpoint de lectura; ejecutar el script para actualizar los cierres reconstruidos.

Desde el 09/11, el diario visible continúa automáticamente después del cálculo guardado usando las muestras oficiales ya disponibles, con el mismo ancla contable. Conserva los cierres estimados completos y sustituye el último día parcial congelado por el último punto oficial de ese día. Los días posteriores se identifican como `Muestra oficial`, con cierre aproximado y último día parcial. La primera variación usa el cierre estimado previo; las siguientes, los cierres oficiales aproximados. Una fecha sin muestra deja PNL null tanto ese día como el siguiente si falta su base. Esta continuación se calcula en memoria, sin escribir SQLite ni alterar la curva oficial. El script manual sigue siendo necesario para recalcular estimaciones con velas.

Tablas principales: `events`, `source_files`, `csv_evidence`, `price_candles`, `official_points`, `valuations`, `daily`, `metadata`. `valuations` registra diferencias brutas y netas con cada punto oficial, no un ajuste artificial para forzar coincidencia.

Pruebas: `tests/test_historical_account.py` y `tests/test_strategy_analytics.py`. Integridad SQLite comprobada con `PRAGMA quick_check`.
