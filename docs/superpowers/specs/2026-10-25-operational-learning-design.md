# Diseño: aprendizaje a partir de operaciones

## Intención

Usar el historial disponible de Pair Desk para encontrar patrones repetibles en tres áreas: condiciones de entrada, gestión/cierre y selección de pares o contexto. El resultado inicial será un análisis retrospectivo reproducible; las reglas solo se propondrán cuando tengan evidencia suficiente.

## Objetivos

- Construir una fila analítica por operación cerrada o evento reconstruible.
- Medir resultado neto, duración, ratio de entrada/salida, neutralidad, funding, comisiones y eventos de gestión.
- Comparar operaciones ganadoras y perdedoras por par, dirección, duración, ratio, z-score/regimen cuando estén disponibles y calidad de ejecución.
- Identificar patrones candidatos y expresarlos como reglas comprobables, con tamaño de muestra y limitaciones.
- Dejar una base reutilizable para incorporar nuevas operaciones sin rehacer el análisis.

## No objetivos

- No crear una estrategia automática ni habilitar órdenes.
- No tratar correlación como causalidad ni convertir una muestra pequeña en una regla definitiva.
- No mezclar datos incompletos con operaciones verificadas sin marcar su calidad.
- No modificar `secure_trade_routes.py` ni alterar contabilidad existente.

## Datos y calidad

Fuentes previstas: `settings.json` para pares cerrados y eventos archivados; `ledger.sqlite3` para fills/funding; `orders.sqlite3` para intentos y eventos de ejecución; `market.sqlite3` y snapshots para contexto de mercado. La línea base observada contiene 28 pares cerrados, 19 activos, 20.872 eventos de ledger, 85 intentos, 424 eventos de órdenes y un CSV recuperado de 1.068 registros.

Cada observación tendrá una clasificación de calidad: `verificada`, `parcial` o `no comparable`. Historial truncado, timestamps ausentes, legs desbalanceadas o PNL sin desglose impedirán conclusiones fuertes, pero no se ocultarán.

## Análisis inicial

1. **Entrada:** par, lado, ratio inicial, neutralidad, tamaño, hora/día, régimen y z-score si existen.
2. **Gestión:** duración, adds/TPs, cambios de neutralidad, funding, comisiones y eventos de ejecución.
3. **Cierre:** ratio final, PNL realizado/neto, drawdown o excursión disponible, motivo y calidad del cierre.
4. **Selección/contexto:** rendimiento por par, familia de activos, liquidez/disponibilidad de datos y condiciones del mercado.

Se reportarán distribuciones y comparaciones simples antes de probar reglas. Las reglas candidatas deberán indicar condición, resultado esperado, número de casos, tasa de éxito, PNL agregado/mediano y casos contrarios.

## Entrega

Primero, un informe local reproducible y una exportación tabular anonimizada. Después de revisar los hallazgos, integrar en Pair Desk solo las métricas que hayan demostrado utilidad. Las pruebas cubrirán reconstrucción, clasificación de calidad y cálculos puros.

## Decisión propuesta

Usar el enfoque híbrido: análisis fuera de la UI para explorar y validar; integración posterior para seguimiento continuo. Es el camino con menor riesgo de fijar reglas basadas en coincidencias o en datos incompletos.
