# Diseño: cambios del ratio en Mis posiciones

## Intención

Agregar a cada fila de “Mis posiciones” dos indicadores compactos, 1h y 24h,
que muestren cuánto cambió el ratio del par en esos períodos, inspirado en la
watchlist de DexScreener.

## Alcance

- Crear un endpoint separado de solo lectura para calcular los cambios del ratio.
- Calcular cada cambio como (ratio_actual / ratio_historico - 1) * 100.
- Mostrar 1h y 24h debajo del nombre del par, con signo y color según sea
  positivo o negativo.
- Actualizar esos datos aproximadamente cada 60 segundos.
- Mostrar N/D cuando falten velas, haya datos insuficientes o falle la consulta.

## Fuera de alcance

- No mostrar cambios individuales de long/short.
- No cambiar el PNL, el ratio desde la entrada ni la lógica de trading.
- No modificar secure_trade_routes.py.
- No convertir estos cambios en señales u órdenes.

## Enfoque elegido

Se agregará /api/position-ratio-changes como endpoint independiente. El backend
consultará las velas necesarias para ambas patas de cada par en paralelo,
construirá el ratio histórico y devolverá un mapa por pair_id con 1h y 24h.
React lo consultará por separado y combinará la respuesta con las filas
actuales. Así /api/state conserva su responsabilidad actual y una falla del
histórico no impide mostrar las posiciones.

## Decisiones de presentación

La lista conservará el PNL actual a la derecha. Debajo de LONG / SHORT se
mostrará una línea compacta del tipo 1h +0.42% · 24h -1.18%. Los valores
positivos usarán el tono positivo existente y los negativos el tono negativo.
El título aclarará que se trata de “Cambio del ratio”.

## Verificación

Agregar pruebas deterministas para el cálculo de cambios y para la respuesta
del endpoint, además de una prueba de renderizado/comportamiento de la lista.
Ejecutar las pruebas aplicables y el build de React.
