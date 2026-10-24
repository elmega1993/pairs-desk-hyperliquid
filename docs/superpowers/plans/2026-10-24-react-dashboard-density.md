# Plan: densidad visual del dashboard React

## Objetivo

Reducir ruido visual en el escritorio principal sin perder información operativa: `Mis posiciones` queda enfocada en par, PNL y cambios de ratio; el detalle permanece en `Resumen del par`.

## Cambios

- Compactar cada posición a nombre, PNL y ratios 1h/24h.
- Agrupar búsqueda y ordenamiento en un único desplegable.
- Reemplazar el encabezado grande por una barra compacta de estado, actualización y acciones.
- Mostrar `Radar de posiciones` y `Pares cerrados` en columnas en escritorio y apilados en pantallas angostas.

## Restricciones

- No cambiar cálculos ni endpoints.
- No eliminar datos del panel `Resumen del par`.
- Mantener accesibilidad de controles y responsive móvil.
