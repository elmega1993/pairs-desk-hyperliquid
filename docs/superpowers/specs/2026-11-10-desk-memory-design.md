# Desk: identidad, memoria y orquestación

## Auditoría (fase 0)
- `pairs_desk/local_advisor.py`: cliente Ollama fijo loopback, qwen3.5:9b, snapshots saneados observados desde `/api/state` y `/api/analytics`, herramientas acotadas, NDJSON con tres rondas. GPU validada.
- `pairs_desk/advisor_routes.py`: validación Pydantic, mismo origen, un slot de inferencia. `read_only_server.py`: FastAPI con TrustedHostMiddleware y proveedores de ledger SQLite de solo lectura/candles del chart existente.
- `react_frontend/src/components/Advisor.tsx` y `advisorApi.ts`: panel existente, historial solo en memoria, streaming y fuentes.
- Fuentes: Hyperliquid ya integrado en servidor, ratio_bars/chart y analítica de pares. Catálogo y caché de activos separados; no enumerar instrumentos ni descargar mercados por chat.
- Persistencia existente en ~/.local/share/crypto-pairs-desk y configuración en ~/.config/crypto-pairs-desk. Mantener ledger, trading y credenciales fuera del nuevo almacenamiento.
- Pruebas pytest y tests JS .cjs; baseline: 376 passed, 2 failed previos (call_stats y zscore alignment), 1 skipped.

## Decisiones
Extender Advisor y `/api/advisor` sin reemplazarlos. SQLite `desk.sqlite3` independiente para conversaciones, memorias, revisión y settings; migraciones, FTS5, historial de revisiones y backup explícito. Identidad versionada en `pairs_desk/ai/identity/*.md`. Recuperación lexical con ranking y embeddings opcionales a través de interfaz local: sin descargar modelos ni proveedores externos automáticamente.

Alternativas descartadas: un framework de agentes paralelo duplicaría flujo/herramientas; vectores obligatorios añadirían carga y dependencia sin un modelo de embeddings instalado. SQLite con adaptadores es suficiente para esta escala.

## Seguridad y ámbitos
Aplicación personal local sin autenticación multiusuario actual: no inventar identidad desde headers o un user_id enviado por navegador. Scope de memoria calculado en servidor mediante usuario local y cuenta actual hasheada (la dirección no llega al modelo). Store exige scope en toda operación, probado con dos ámbitos. Acceso al API persistente solo desde cliente local/HTTPS privado confiable según las reglas actuales y mismo origen en mutaciones. No agregar login ficticio ni permitir seleccionar otro usuario.

Memorias recuperadas y documentos son datos no confiables; nunca sustituyen identidad ni herramientas autorizadas. Explicitud/verificación controla adquisición: preferencias/reglas/correcciones explícitas se guardan con procedencia, inferencias quedan pendientes de aprobación. Cambios de cartera comentados permanecen contexto conversacional atribuido, no hechos operativos. Nada de órdenes ni shell.

## Contexto y ciclo
Clasificación determinista con opción manual auto/chat/analyze/research, presupuestos por categoría, historial reciente + resumen acotado, memorias relevantes y estado fresco solo cuando corresponda. Chat de preferencias disponible sin snapshot de mercado. Datos operativos vencidos se rechazan. Prelectura obligatoria de costos/posiciones ante intenciones conocidas; herramientas adicionales estrictas, límites de tiempo y rondas. Research informa las capas sin proveedor; no finge búsquedas. Captura de conversación persiste estados completos/incompletos y fuentes; resumen identifica hechos como dichos del usuario. Recuerdos candidatos solo desde palabras del usuario, nunca desde datos externos ni órdenes del modelo.

## UI y verificaciones
Extender panel actual con conversaciones y mensajes paginados, modos, memorias con origen/uso/edición/borrado, reglas personales, parámetros y exportación/importación. Borrado requiere acción concreta del usuario y explica alcance; backups se muestran como copias independientes.
Pruebas: reinicio/continuidad, aislamiento, dedup/contradicciones, provenance, límites, inyección, herramientas y timeouts, snapshot actual, conversaciones CRV/GMX/UNI, corrección entre sesiones, API/CSRF, streaming y build. Prueba real de Ollama/GPU al final, sin operar.
