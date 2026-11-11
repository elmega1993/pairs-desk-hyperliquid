# Asesor local de Pair Desk

Diseño derivado de la propuesta aceptada en conversación: chat integrado en React con Ollama local y qwen3.5:9b ya instalado. Asesor de lectura, respuesta progresiva, contexto reciente de cuenta/posiciones y consultas acotadas de estrategia, analytics, velas, cerrados y ledger. Evidencia de fuentes/fecha visible; hechos separados de hipótesis. Cálculos del backend, sin herramientas de órdenes ni acceso a secretos. Sin descargas ni cambios de driver antes del reinicio. Alertas autónomas quedan fuera de esta primera entrega; el contexto se renueva al consultar.

Arquitectura: servicio aislado `pairs_desk/local_advisor.py` con copia saneada en memoria de las lecturas normales del servidor, cliente HTTP a 127.0.0.1:11434, herramientas con lista permitida, límites de contexto/tiempo/concurrencia y rechazo de modelos cloud. Router `pairs_desk/advisor_routes.py` con validación de origen y entrada, streaming NDJSON. UI `Advisor.tsx` y cliente específico; conversación solo en memoria del navegador, conservada al cambiar vistas, con borrado. Backend integra observadores y proveedores de lectura, sin ejecutar states() adicional desde el modelo.

Decisiones: conservar copia de trabajo actual y cambios previos. Modelo inicial fijo configurable por entorno local, sin endpoints remotos. Datos de cuenta con más de 90 s se rechazan. Contexto de análisis conserva su propia fecha. Reglas de asesoramiento describen riesgos y escenarios sin prometer rentabilidad ni certeza. Una sola generación concurrente, con estado y errores recuperables.

- [x] Pruebas de saneamiento, cobertura/antigüedad, herramientas prohibidas, presupuesto, cloud/busy y errores de Ollama.
- [x] Servicio y router; registrar estado/analítica ya leídos y proveedores de velas/ledger.
- [x] Chat responsivo con streaming, fecha/fuentes, preguntas sugeridas, historial y errores; mantener vista montada.
- [x] Pruebas focalizadas, suite completa, compilación, prueba del modelo local y navegador; documentación de uso y reinicio.

## Verificación y decisiones de cierre

- Revisión independiente: sin hallazgos críticos de privacidad/transporte local. Corregido fallback del diario reconstruido vacío a muestras oficiales, con fecha de cálculo histórico separada. Retirado control Detener para no prometer cancelación remota inmediata con transporte síncrono. Las fuentes muestran fecha y hora de Buenos Aires.
- Ledger fijado a la cuenta del snapshot y abierto mode=ro. Pruebas de account switch, cobertura, proveedor fallido, datos faltantes, modelos cloud, herramientas prohibidas, streaming interrumpido y límites.
- Contexto inicial reducido a resumen y pares compactos; detalles por herramientas, costos paginados. Una consulta real en CPU con contexto extenso agotó el timeout inicial; tras reducir a resumen y contexto de 8192 tokens, consulta real desde navegador completó correctamente con PNL y fecha exacta de su snapshot.
- 17 nuevas pruebas Python pasan; prueba JS de streaming pasa (UTF-8 fragmentado, errores, truncación e historial acotado). Suite completa: 376 passed, 2 failed previos (test_call_stats_records_local_api_request_without_sensitive_fields y test_zscore_keeps_the_same_full_x_domain_as_ratio_bars), 1 skipped. Los cuatro diagnósticos TypeScript previos continúan en PnlChart.tsx (2), PortfolioKpis.tsx y pnlModel.ts; sin errores nuevos en los archivos del asesor. Vite compila.
- Chrome headless: tres sugerencias disponibles, consulta real completada sin error y con fuente; historial conservado al cambiar de vista; sin desbordamiento horizontal a 1660 y 390 px. Capturas privadas locales /tmp/pairdesk-advisor-*.png.
- Modelo probado en CPU. GPU/latencia tras reinicio quedan explícitamente pendientes. No se modificaron drivers, secretos, configuración de trading ni rutas de órdenes.

- Prueba real final de herramientas: consulta de funding pagado/cobrado completada con fuentes `cuenta y posiciones` y `strategy`, sin error, en 104 s en CPU. La primera prueba no solicitaba la herramienta pese a la instrucción; se reforzó la disponibilidad explícita de herramientas de lectura y la consulta obligatoria del desglose para cobros/pagos. Una prueba mínima de function calling del modelo también pasó. La calidad de consejos complejos y el rendimiento GPU siguen como evaluación posterior.
