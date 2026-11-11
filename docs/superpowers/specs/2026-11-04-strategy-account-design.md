# Cuenta / Estrategia desde el inicio operativo — Diseño

## Intención

Agregar una vista propia de Cuenta / Estrategia dentro de React para analizar la operación de pares desde el 23/09/2026, sin mezclarla visualmente con el escritorio operativo ni depender del saldo actual de la cuenta.

## Objetivos

- Mostrar un gráfico limpio, completo y sin eventos marcados.
- Permitir seleccionar el período visible (`1D`, `7D`, `30D`, `Todo`) sin modificar el PNL diario.
- Excluir todos los datos anteriores al 23/09/2026 y rebasar la serie al comienzo de la estrategia.
- Mantener el panel de PNL diario calculado siempre sobre la serie completa desde el inicio.
- Mostrar PNL bruto, realizado, flotante, funding, comisiones, resultado neto, drawdown y ROI.
- Proyectar funding a 1, 7 y 30 días con tasas vigentes y nominales actuales, usando cache para no multiplicar llamadas.
- Calcular ROI con capital inicial de estrategia, no con el saldo actual.

## Criterio contable propuesto

- Fecha inicial fija de esta iteración: `2026-09-23T00:00:00` en la zona horaria de la estrategia.
- Capital inicial: último `accountValueHistory` disponible en o inmediatamente después de esa fecha.
- Resultado bruto: variación de PNL de Hyperliquid desde la fecha inicial, rebasada a cero.
- Costos: funding y comisiones verificables desde la fecha inicial.
- Resultado neto conocido: bruto + funding firmado - comisiones, manteniendo `N/D` cuando la cobertura no sea verificable. Un funding negativo reduce el resultado y uno positivo lo mejora.
- ROI: resultado neto conocido / capital inicial × 100.
- Si no existe un capital inicial verificable, ROI muestra `N/D`; nunca se reemplaza por el saldo actual.

## Diseño de interfaz

- Nueva opción de navegación `Cuenta / Estrategia`.
- La vista conserva el estilo visual de los gráficos de ratio: fondo limpio, leyenda mínima, controles de período y todo el rango visible.
- Los marcadores de operaciones quedan desactivados y no se renderizan en esta vista.
- El panel `PNL diario` recibe la serie completa desde el backend y no depende del período elegido para el gráfico.
- Las tarjetas estadísticas se agrupan junto al gráfico; si crecen en futuras iteraciones podrán extraerse a una página analítica separada sin cambiar el contrato de datos.

## Funding proyectado

- Reutilizar la lógica existente de `pair_funding_carry`.
- Consultar tasas vigentes de Core y XYZ mediante una respuesta backend cacheada durante un intervalo corto.
- Calcular el carry agregado de los pares activos con nominales actuales.
- Mostrar cada horizonte como estimación, con signo y aclaración de que la tasa cambia.
- No usar la proyección para alterar el funding histórico ni el PNL oficial.

## API y rendimiento

- Extender la respuesta analítica existente o agregar un bloque específico para estrategia; no crear una llamada por tarjeta.
- La UI hará una sola consulta para la vista y reutilizará los datos para gráfico, diario, ROI y funding proyectado.
- La carga de la vista no ejecutará rutas de trading ni modificará ledger.

## No objetivos

- No cambiar `secure_trade_routes.py`.
- No reconstruir el historial completo de fills en el navegador.
- No tratar el saldo actual como capital inicial.
- No mezclar PNL de la cuenta con PNL local de pares sin indicar la fuente.
- No agregar eventos al gráfico principal.

## Alternativas consideradas

1. Parchear la sección actual: menor esfuerzo, pero mantiene demasiadas responsabilidades juntas.
2. Vista Cuenta / Estrategia dentro del dashboard: elegida porque separa el análisis sin crear todavía una nueva superficie de navegación compleja.
3. Endpoint y página analítica independientes: mejor para una expansión futura, pero sobredimensionado para esta iteración.

## Pendientes para implementación

- Definir el contrato de datos histórico y de funding proyectado.
- Agregar pruebas para corte/rebase desde el 23/09, PNL diario independiente, ROI y cache de tasas.
- Implementar la vista y los controles sin alterar el escritorio operativo.
- Ejecutar build, pruebas focalizadas y smoke visual si Chromium está disponible.
