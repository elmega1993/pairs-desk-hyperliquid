# Pairs Desk 2.0 — Aurora Alpha 03

## Cambios
- Escritorio Aurora más denso y con identidad violeta/azul, sin cambiar la interfaz estable.
- Navegación lateral a secciones de la misma vista (Explorador, Laboratorio, Investigación, Actividad), no páginas nuevas; botones de desplazamiento, no funciones terminadas.
- Búsqueda y ordenamiento de posiciones por PNL, nominal o nombre.
- Favoritos locales del navegador, sin sincronización con el backend.
- Radar de posiciones abiertas, con selección rápida del par. No es un scanner de oportunidades de todo Hyperliquid.
- Intervalos de velas 5m, 15m, 1h, 4h y 1d.
- Estadísticas derivadas de velas verificables: Z-score del backend cuando exista, rango de las últimas 60 velas y fecha de la última vela.
- Avisos cuando faltan fills, funding u otros datos verificables.
- PNL neto y funding siguen mostrando N/D cuando la fuente no permite verificarlos. No se fabrican cifras.
- Interfaz Aurora de solo lectura; ejecución sigue en la interfaz estable.

## Estado React
El código fuente React/TypeScript sigue en `aurora-react/`, pero no está compilado ni se sirve desde `/aurora`. El entorno no pudo acceder a registry.npmjs.org. No se presenta esta entrega como migración React completa.

## Prueba en Ubuntu
Extraer en una carpeta nueva, ejecutar `iniciar_frontend.sh`, abrir http://127.0.0.1:8510/aurora. Comparar posiciones y cifras con la interfaz estable en `/`.
