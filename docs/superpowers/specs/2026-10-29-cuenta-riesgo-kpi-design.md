# Diseño: card Cuenta y riesgo

## Intención

Reorganizar la fila superior del dashboard para eliminar las cards separadas de exposición y margen, y agrupar la información patrimonial y de riesgo en una sola card.

## Diseño elegido

El orden será:

1. `PNL NO REALIZADO`
2. `PNL TOTAL · HYPERLIQUID`
3. `COSTOS Y DESCOMPOSICIÓN`
4. `CUENTA Y RIESGO`

`CUENTA Y RIESGO` mostrará valor total de cuenta, exposición, margen usado y margen libre. El valor total será la suma de `marginSummary.accountValue` de las cuentas core y XYZ disponibles. El margen libre será valor total menos margen usado agregado.

## Fuente y límites

- El `portfolio` de Hyperliquid se usa para historial de PNL, no para valor patrimonial.
- Si una cuenta no entrega `accountValue`, se omite del total; si ninguna cuenta es verificable, se muestra `N/D`.
- No se modifica ninguna ruta de trading ni la lógica de cálculo del PNL oficial.
- La card conserva la convención de `money`, `num` y colores existentes.

## Criterio de éxito

La fila pasa de cinco cards a cuatro, el PNL total ocupa el segundo lugar, costos el tercero, y la card final presenta patrimonio y riesgo sin duplicar cards independientes.
