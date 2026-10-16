# Pairs Desk 2.0 — Aurora consolidada

## PNL: campos independientes

- `summary.unrealized`: flotante de pares abiertos, disponible aunque falten fills.
- `summary.realized`: realizado activo + archivado, `null` si los fills activos no son verificables.
- `summary.total`: neto con funding y comisiones, `null` si faltan componentes.
- `pair.pnl`: flotante. `pair.realized`: realizado. `pair.total_pnl`: neto verificable.
- La lista y el gráfico de cada par muestran el **flotante**, no la suma de realizado y no realizado.
- El historial del PNL conserva su base contable original, indicada debajo del gráfico.

## Seguridad

La vista `/aurora` es de solo lectura. La interfaz operativa estable `/` permanece intacta. No se modificaron fórmulas de contabilidad ni rutas de ejecución.

## Alcance

Esta entrega consolida la interfaz Aurora existente. **No constituye una migración React finalizada**: el frontend en producción sigue siendo HTML/CSS/JS. Los módulos Explorador, Laboratorio e Investigación siguen en fase preliminar.
