# Aurora Beta 01 — Cambios y límites

- Se preserva el gráfico KLineCharts de Alpha 05, con TP/ADD, marcadores, media, zoom y desplazamiento.
- Paneles laterales redimensionables con mouse o teclado (pantallas >1250 px), y restablecimiento de diseño.
- Persistencia local de ancho de paneles, par seleccionado, orden de posiciones y período de PNL.
- PNL: selector Todo / 24 horas / 7 días / 30 días sobre datos históricos registrados. No interpola ni inventa datos.
- Lista de posiciones: más criterios de ordenamiento (flotante, realizado, funding, porcentaje, exposición, nombre).
- No se modifican las rutas de ejecución ni la contabilidad. El neto continúa como subtotal si falta funding.
- React + TypeScript sigue pendiente: el entorno no pudo acceder a registry.npmjs.org; no se presenta como compilado.
- Beta incremental, no versión final. Validar visualmente en Ubuntu antes de reemplazar cualquier instalación.
