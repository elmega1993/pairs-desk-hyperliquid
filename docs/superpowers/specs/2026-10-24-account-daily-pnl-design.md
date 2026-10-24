# Diseño: PNL diario de la cuenta

## Intención

Agregar al panel de evolución del PNL un resumen lateral con el PNL total de la
cuenta por día, usando exclusivamente la serie de Hyperliquid.

## Alcance

- Derivar una fila diaria a partir de la serie acumulada de Hyperliquid.
- Mostrar fecha, PNL del día y PNL acumulado al cierre de ese día.
- Usar verde/rojo y signo para facilitar la lectura.
- Mantener el gráfico acumulado, sus controles y la conciliación actuales.
- Mostrar un aviso claro si se selecciona la fuente local, porque el panel exige
  datos de Hyperliquid.

## Cálculo

Los puntos se agrupan por fecha de Argentina. Para cada día se toma el último
PNL acumulado disponible y se resta el último acumulado del día anterior. El
primer día visible se marca como parcial porque el rango seleccionado puede
comenzar después del inicio real de la cuenta. No se rellenan días sin datos.

## Presentación

En escritorio, el panel “PNL diario” se ubicará a la derecha del gráfico,
alineado con su altura y con scroll interno si hay muchas filas. En pantallas
angostas pasará debajo del gráfico. La fila más reciente aparecerá primero.

## Fuera de alcance

- No calcular PNL diario por par.
- No mezclar la serie local con Hyperliquid.
- No modificar ledger, funding ni rutas de trading.
- No inventar valores para días sin registros.

## Verificación

Agregar pruebas puras para agrupación, cambio diario, cambio de mes, primer día
parcial y días sin datos. Agregar una prueba de fuente para el panel y ejecutar
la suite completa y el build React.
