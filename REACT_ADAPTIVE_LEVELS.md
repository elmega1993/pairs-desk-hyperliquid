# React Adaptive Levels v1

- Endpoint de solo lectura `/api/adaptive-levels/{pair_id}`. Usa velas diarias y la referencia de gestión guardada.
- React consulta el endpoint al seleccionar cada par, y dibuja ADD1, ADD2, TP1 y TP2 calculados, sin porcentajes fijos de respaldo.
- Cuando no hay datos suficientes, muestra N/D y no dibuja objetivos automáticos.
- Se conservan settings, operaciones y reglas manuales existentes. Esta integración NO modifica la lógica de ejecución de órdenes ni otras vistas.
- La metodología es experimental: percentiles históricos de movimientos a 14 días, no probabilidades predictivas validadas.
- IMPORTANTE: React requiere compilar assets en el equipo destino con `iniciar_frontend.sh`. No se incluyó build precompilado: npm no pudo obtener dependencias en este entorno.
