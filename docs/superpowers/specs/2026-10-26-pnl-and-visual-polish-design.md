# PNL oficial de Hyperliquid y pulido visual — Diseño

## Intención

Usar los datos de cuenta de Hyperliquid como fuente oficial del PNL total, evitando que un cierre desordenado de las patas de un par distorsione el resultado mostrado por Pair Desk. Mantener el cálculo local como reconciliación y diagnóstico. Al mismo tiempo, mejorar la lectura de cards, gráficos, resumen de pares y explorador.

## Alcance

- Las cards de PNL total y el gráfico histórico principal usarán la serie de Hyperliquid cuando esté disponible.
- El dato local seguirá visible como base alternativa o reconciliación, sin reemplazar el total oficial.
- Las cards principales incorporarán una mini línea de evolución usando la misma serie oficial.
- El gráfico acumulado de PNL tendrá una escala y lectura más cercanas al gráfico de ratio: área/línea, ejes legibles, cero destacado, puntos relevantes y drawdown separado.
- `Resumen del par` mostrará `LONG <símbolo> · PNL`, `SHORT <símbolo> · PNL`, exposición total primero y en color neutro.
- En `Explorador`, el gráfico del par seleccionado aparecerá arriba del contenido secundario, cerca de la selección.

## Fuera de alcance

- No modificar rutas de órdenes, ledger, persistencia ni `secure_trade_routes.py`.
- No corregir manualmente el historial ni inventar una atribución por pata para una operación cerrada fuera de orden.
- No retirar el cálculo local ni ocultar las diferencias de reconciliación.
- No cambiar la paleta general ya aplicada por Claude salvo ajustes necesarios para legibilidad.

## Enfoques considerados

1. Hyperliquid como fuente única: simple, pero elimina visibilidad sobre diferencias locales.
2. Híbrido — elegido: Hyperliquid manda en el total y el gráfico; datos locales explican pares, cierres y diferencias. Es el equilibrio correcto para la operación mal cerrada reportada.
3. Corrección manual del ledger local: no elegido porque puede duplicar o deformar la contabilidad real.

## Decisiones de diseño

- El backend conservará `summary` para el desglose local y expondrá/seleccionará explícitamente el total oficial de Hyperliquid sin borrar el resumen local.
- El frontend resolverá una única serie oficial para cards, mini-gráficos y gráfico acumulado; si Hyperliquid no está disponible, mostrará fallback local claramente marcado.
- Las mini-gráficas serán SVG livianos y reutilizarán la misma serie ya cargada, sin una consulta nueva por card.
- El gráfico del Explorador se moverá en el layout, no se duplicará ni se cargará dos veces.
- Los cambios tendrán pruebas de modelo/UI para: selección de fuente oficial, fallback, compresión del resumen y orden del gráfico del explorador.

## Resultado esperado

El valor total visible debe coincidir con Hyperliquid para la ventana seleccionada, incluyendo pérdidas de operaciones que Pair Desk no pueda atribuir limpiamente a un par. Las diferencias locales deben quedar explicadas como reconciliación, no mezcladas con el total oficial.
