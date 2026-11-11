# Diseño: card compacta de costos y descomposición

## Intención

Reutilizar la card `PNL REALIZADO` del dashboard para mostrar información operativa que no se repita con `PNL NO REALIZADO` ni `PNL TOTAL · HYPERLIQUID`.

## Diseño elegido

Renombrar la card como `COSTOS Y DESCOMPOSICIÓN` y reemplazar su valor grande y subtítulo por una grilla compacta 2×2:

- `FUNDING HISTÓRICO`: `summary.account_funding` cuando esté disponible.
- `COMISIONES HISTÓRICAS`: `summary.fees`.
- `PNL LONGS`: suma de `long_pnl` de las posiciones activas.
- `PNL SHORTS`: suma de `short_pnl` de las posiciones activas.

Los valores monetarios conservarán el color por signo. Los valores no verificables mostrarán `N/D`, siguiendo la convención existente. La card no tendrá gráfico, porque estas métricas no comparten una serie temporal homogénea y el espacio debe mantenerse compacto.

## Alcance

- Modificar el componente React de KPIs y sus estilos.
- Extender los tipos o datos derivados solo si TypeScript lo necesita.
- Mantener intactos `PNL NO REALIZADO`, `PNL TOTAL · HYPERLIQUID`, exposición y margen.
- Agregar pruebas estructurales/de comportamiento para confirmar etiquetas, valores y manejo de datos faltantes.

## Decisiones y límites

- `PNL Longs/Shorts` representa PNL flotante por lado de las posiciones abiertas; no se presentará como histórico realizado porque el backend actual no separa el realizado histórico por lado con certeza.
- `Funding histórico` usa el valor de cuenta ya reconciliado por el ledger, no la tasa vigente ni la estimación diaria.
- `Comisiones históricas` usa el total de comisiones verificadas que ya alimenta el resumen.
- No se agrega selector 24h/7d/30d en esta iteración.

## Criterio de éxito

La card ocupa el mismo lugar, mantiene una lectura clara en escritorio y móvil, muestra las cuatro métricas sin duplicar las otras cards y pasa el build/pruebas focalizadas del frontend.
