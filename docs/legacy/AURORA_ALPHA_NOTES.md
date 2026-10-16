# Pairs Desk 2.0 — Aurora Alpha 0.1

- `/aurora` muestra una interfaz visual paralela de solo lectura con datos de `/api/state` y `/api/chart/{pair_id}`.
- `/` conserva la interfaz estable. El código de órdenes y sus rutas no se modificaron.
- El prototipo HTML/CSS/JS es funcional sin descargar dependencias de internet.
- `aurora-react/` contiene el inicio de migración React/TypeScript/Vite, **todavía no compilado ni listo para reemplazar el prototipo**: el entorno de construcción no tenía acceso a npm.
- Esta Alpha no incluye aún gráficos de velas completos, explorador, laboratorio ni controles de ejecución. El gráfico del ratio es una línea basada en cierres verificables.
- Inicio habitual: `./iniciar_frontend.sh`, abrir `http://127.0.0.1:8510/aurora`.
- Pendiente: comprobar el resultado en Ubuntu con la cuenta real, completar React, verificar gráficos y mejorar el layout antes de migrar la UI.
