# Detalle de cards de estrategia

Diseño aprobado en conversación: conservar cinco cards, costos legibles con comisiones y funding neto; detalle de cobros/pagos y activos; proyección long/short con tasas actuales y fecha; drawdown con fecha y recuperación pendiente; realizado/flotante; medias diarias ganadora/perdedora. Detalles nativos desplegables, sin dependencias nuevas.

Decisión: activos históricos en vez de asignación a pares (un activo puede pertenecer a varios pares). Sin inventar atribuciones. Cobertura incompleta → N/D, sin sumar parciales como totales. Importes de fees firmados para conservar rebates. PNL neto oficial intacto. Cards independientes del filtro del gráfico, desde inicio.

Ejecución en copia actual por contener cambios previos y fuentes nuevas sin commit de la app en uso. Sin commits ni cambios de ramas que incluyan trabajo ajeno.

- [x] Pruebas de ledger completo/incompleto, signos, rebates, activos, fechas, medias y proyección parcial.
- [x] Agregar agregación pura a strategy_snapshot y proyección por pata/par; fecha real de tasas cacheadas.
- [x] Ampliar tipos, métricas y cards; estilos responsivos y details accesibles.
- [x] Pruebas focalizadas, suite completa, build y revisión de interfaz; documentar limitaciones.

Revisión independiente: detectado doble conteo previo de funding proyectado con activos compartidos. Resuelto pasando posiciones únicas de la cuenta a la agregación; incluye activos fuera de pares, sin atribución inventada. Flotante también usa posiciones únicas. Dos pruebas de regresión añadidas y verificadas rojo/verde.

Verificación: 48 pruebas focalizadas Python y pruebas JS de métricas pasan. Build Vite pasa. Chrome headless: cinco cards, cuatro desplegables, datos de ledger disponibles y sin desbordamiento horizontal a 1660px y 390px; capturas locales en /tmp/pairdesk-cards-*.png. TypeScript conserva cuatro diagnósticos previos en PnlChart.tsx (2), PortfolioKpis.tsx y pnlModel.ts, observados antes de modificar la UI. Suite completa conserva fallos ajenos en test_call_stats_records_local_api_request_without_sensitive_fields y test_zscore_keeps_the_same_full_x_domain_as_ratio_bars (archivo ZScorePane eliminado previamente). Actualizada prueba estructural de estrategia que seguía esperando daily={strategy.daily} pese al selector diario existente.

Cierre: suite completa 358 passed, 2 failed (previos identificados arriba), 1 skipped; modelo PNL JS y métricas de estrategia JS pasan. Build final Vite correcto. Servidor local reiniciado con las fuentes actualizadas. Revisión independiente de la corrección: sin hallazgos importantes adicionales.
