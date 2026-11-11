# Desk: identidad, memoria y uso

Desk extiende el Asesor IA existente con qwen3.5:9b/Ollama. No agrega un chatbot paralelo. La cuenta y el trading siguen en sus servicios originales; Desk no tiene herramientas de órdenes. El modelo sigue corriendo localmente con GPU.

## Uso

En **Asesor IA**, elegí una conversación guardada o **Nueva conversación**. El historial persiste al recargar y reiniciar el backend; las conversaciones son independientes. Se cargan las últimas 30 entradas y hay un control para traer anteriores, con listas de conversaciones paginadas de 20.

Para enseñar una preferencia estable, podés decir `Prefiero pares con market caps similares.`. Para corregir una regla, `Te corrijo: no sumes nominales de pares con activos compartidos.`. Las frases explícitas reconocidas se guardan con el mensaje original como procedencia. No se convierte todo mensaje en recuerdo: posiciones declaradas como `Estoy long CRV y short GMX` permanecen como escenario atribuido en la conversación y su resumen, no como tenencias actuales de la cuenta.

**Memorias y preferencias** permite revisar/editar contenido, categoría, importancia, confianza y estado; aprobar propuestas pendientes, desactivar o eliminar, ver versiones y buscar/consolidar duplicados explícitamente. En cada respuesta, **Memorias utilizadas** explica cuáles se recuperaron y su origen. Las reglas personales y parámetros se editan en otra pestaña. No cambian las reglas principales ni habilitan herramientas.

**Datos y copias** exporta/importa JSON, crea copias privadas y borra el ámbito activo tras escribir DESK. El borrado de una conversación no borra los recuerdos adquiridos; borrar una memoria no elimina los mensajes originales o referencias históricas en conversaciones. Para quitar ambas cosas, eliminá las conversaciones correspondientes o borrá todos los datos de Desk del ámbito. Backups y JSON exportados son copias independientes y permanecen hasta que el usuario los retire. No se borran datos de trading.

## Persistencia, identidad y ámbitos

Base exclusiva: `~/.local/share/crypto-pairs-desk/desk/desk.sqlite3`; configurable mediante `PAIRS_DESK_AI_DATA_DIR`. Carpeta privada nueva 0700 y SQLite/WAL/SHM/backups 0600. No se modifica el ledger, credenciales ni settings de trading. SQLite usa WAL, foreign keys y secure_delete; `PRAGMA user_version=1` inicializa la primera migración e impide abrir versiones futuras incompatibles. Las migraciones futuras deben ser aditivas y respaldar antes de transformar datos.

El ámbito se deriva en el servidor del usuario del sistema y de la cuenta configurada, hasheados; la dirección no entra al prompt. La identidad y cuenta se capturan con una sola lectura y se fija la cuenta del snapshot. Direcciones Ethereum se comparan sin diferencias de mayúsculas. Si cambia la cuenta durante una consulta, se interrumpe su transmisión y se conserva como incompleta. No se aceptan user_id, scope ni account enviados por el navegador. Es una aplicación personal local con el mecanismo de acceso privado actual, no un sistema de login multiusuario: un despliegue multiusuario requiere autenticación real adicional. El aislamiento del store se prueba con dos ámbitos diferentes.

Memorias incluyen todos los campos del diseño: id/namespace/type/category/content/importance/confidence/source/source_id/created_at/updated_at/last_accessed_at/valid_until/status/supersedes_id/metadata. Historial, resúmenes, settings y revisiones viven en tablas separadas. Tipos persistentes: semantic, procedural, episodic, conversation y knowledge. Operational corresponde a los snapshots y herramientas actuales, no a otra copia permanente de precios.

## Recuperación y adquisición

FTS5 con filtro de palabras comunes, ranking por relevancia, importancia, actualidad y confianza. Se excluyen pendientes, desactivadas, sustituidas y vencidas. Correcciones/reglas vigentes y consultas explícitas de preferencias tienen recuperación acotada adicional. No se inyecta toda la base. Cada resultado explica el puntaje o el motivo de recuperación.

La adquisición es conservadora y determinista: reconoce preferencias, objetivos, reglas, correcciones y lecciones explícitas al principio de un mensaje del usuario. Las preferencias de temas conocidos (longitud de respuesta, market caps) y correcciones se versionan al cambiar; temas ambiguos quedan para revisión manual. No es un extractor universal de cualquier frase. `save_memory` del modelo solo crea propuestas pendientes con confianza 0,4; no puede aprobar sus propias inferencias. Se filtran credenciales reconocibles y cotizaciones efímeras. No hay adquisición automática desde resultados web/herramientas.

Duplicados exactos se deduplican normalizando texto. La similitud lexical/vectorial propone duplicados del mismo tipo/categoría/namespace, con guardas de polaridad; la consolidación exige elección explícita. Conserva originales sustituidos y su procedencia para evitar destruir preferencias opuestas por una similitud alta. Cambiar contenido deja revisión; eliminar retira la fila de FTS, vectores y revisiones. Importar valida todo de forma atómica, remapea IDs al ámbito activo y no acepta otro scope.

Embeddings son opcionales. No hay modelo de embeddings habilitado por defecto ni se descarga uno automáticamente. Si ya existe un modelo local compatible, configurar `PAIRS_DESK_EMBEDDING_MODEL` antes del arranque. `OllamaLocalEmbedder` usa solo loopback, sin proxies/redirecciones, y comprueba `/api/show` antes de enviar texto para bloquear modelos remotos/cloud. Si falla, FTS sigue disponible. La interfaz `LocalEmbedder` permite sustituir proveedor local. Cambiar modelo exige reindexar las memorias existentes para obtener vectores nuevos; no se aplica un vector de otra dimensión.

## Contexto, herramientas y modos

Identidad cargada al iniciar desde `pairs_desk/ai/identity/{system,trading_rules,response_style,memory_policy,tool_policy}.md`. Son archivos versionables/editables; reiniciar para recargarlos. El ContextBuilder separa identidad de datos recuperados, resumen extractivo atribuido, historial reciente y reglas personales. Los límites de memoria/historial son máximos: un presupuesto agregado reserva espacio para snapshots, herramientas y respuesta. Tokens se estiman conservadoramente por bytes; Ollama conserva num_ctx=8192 como límite duro. No hay promesa de tokenización exacta de Qwen.

Chat reduce herramientas a memoria/reglas cuando no requiere cartera; Analyze utiliza datos operativos y varias rondas; Research organiza análisis local e indica capas sin proveedor. Selección automática o manual. No hay proveedor web de noticias/fundamentales configurado: no se simula investigación externa.

El backend obliga a leer costos/posiciones ante intenciones identificadas, aunque Qwen omita el tool call. Se distinguen pair_count y holding_count. PNL/ratio/costos requieren snapshot reciente (cuenta 90 s, analítica 180 s). Las herramientas preservan null, fechas, cobertura y paginación. No se vuelve a consultar el universo de Hyperliquid por mensaje.

Registro de esquemas JSON tipados, argumentos extra rechazados, requeridos/tipos/rangos/enums validados:

| Herramienta | Fuente y alcance |
| --- | --- |
| positions / closed_pairs | Pares abiertos/cerrados y posiciones únicas del snapshot |
| strategy | Resumen oficial, costos/funding, diario o historia; paginado |
| account_exposure | Exposición por posiciones únicas, sin duplicar pares |
| pair_ratio | Ratio long/short y entrada de un par conocido |
| analytics | Indicadores calculados existentes, con vigencia propia |
| pair_candles | Chart/velas del ratio existente, consulta acotada |
| available_assets | Caché actual del catálogo; no dispara descarga, máximo 60 |
| ledger | Ledger existente en SQLite read-only y cuenta fijada |
| search_memories / save_memory / get_trading_rules | Store del ámbito; guardado del modelo pendiente |

Z-score y salud estadística se reutilizan de la analítica disponible. No se agregaron cálculos ficticios ni proveedores duplicados de correlación/cointegración. Una métrica o capa ausente debe identificarse como faltante. Nuevos proveedores requieren esquema y handler autorizados en código, respetando el mismo límite de resultados; no se aceptan URLs arbitrarias del modelo.

## API, seguridad y fallos

Se mantiene `/api/advisor/status` y `/chat`, incluyendo compatibilidad con history legacy (con persistencia se ignora el historial del cliente). Chat admite conversation_id y modo. Start/done informan conversación y modo; done incluye fuentes, memorias usadas y recuerdos guardados. La conversación se persiste antes de indicar done; truncadas/fallidas/desconectadas quedan incompletas y no se reinyectan como conclusiones.

Endpoints adicionales: conversations, conversations/{id}/messages, memories (CRUD), memories/{id}/revisions, /duplicates, /consolidate, settings, export, import, backup y data. Listas paginadas con límites. Mutaciones requieren mismo Origin y se conserva TrustedHostMiddleware. El middleware rechaza acceso cross-site, limita cuerpos antes de parsear (32 KB general, 2,1 MB import) y añade no-store. No registra prompts/respuestas en logs. Como antes, desconectarse no garantiza cancelar inmediatamente el cómputo en Ollama; finaliza dentro de los límites de generación. Una consulta concurrente, máximo tres rondas y cuatro herramientas por ronda.

## Validación

Pruebas: `tests/test_desk_memory.py`, `test_desk_context.py`, `test_desk_integration.py`; se conservan las anteriores `test_local_advisor.py` y `test_advisor_routes.py`. JS: test_advisor_api_behavior.cjs, test_desk_ui_behavior.cjs, test_desk_memory_evidence.cjs. Cubren persistencia/reinicio, contexto CRV long/GMX short→UNI, correcciones nuevas conversaciones, dedup/consolidación, contradicciones, scopes/cambio de cuenta/checksum, timeouts, bloqueo de órdenes, cuotas, privacidad, imports y UI.

Prueba real (base temporal separada de la memoria personal): Qwen recordó la preferencia por market caps similares tras recrear FastAPI; consulta nueva 1,62 s. Otro proceso Python recuperó y respondió con la misma memoria en 1,70 s. Ollama indicó 100% GPU. Smoke Chromium a 1440 px y 390 px, sin overflow horizontal ni excepciones JavaScript. El resultado de funding y la suite final se registran en CURRENT_STATE.md.

Resultado final de cartera real: 17 pares y peor PNL coinciden con el backend a centavos, con fuente positions, en 2,14 s. Se compactan tablas conservando todas las filas y valores. La muestra usó una etiqueta USDT no informada por la fuente; se reforzó la regla de conservar el símbolo $ sin inventar moneda. La calidad generativa (incluido estilo/unidades) sigue requiriendo evaluación, no se promete ausencia absoluta de alucinaciones.

Suite final: **445 passed, 2 failed previos, 1 skipped**. Fallos previos: `test_call_stats_records_local_api_request_without_sensitive_fields` y `test_zscore_keeps_the_same_full_x_domain_as_ratio_bars`. Los 84 tests focalizados del asesor/Desk pasan, al igual que las tres suites JS y Vite. Persisten cuatro diagnósticos TypeScript previos en PnlChart/PortfolioKpis/pnlModel; ninguno nuevo en Desk. Compilación Python y diff check correctos.

## Corrección de respuestas cortadas (2026-11-10)

La respuesta de XRP/LTC de las 16:52 alcanzó exactamente 700 tokens; el historial la guardó con truncated=true. Se duplicó el límite predeterminado a 1400, conservando configuraciones explícitas más bajas. Se acotó el estilo del análisis a 250–450 palabras y conclusión primero. El streaming/historial incluyen stop_reason; la UI distingue límite de extensión de interrupción de conexión. Sigue habiendo un límite finito: una respuesta que lo alcance se marca incompleta. Pruebas focalizadas:88; suite449 passed,2 fallos previos(call_stats,zscore alignment),1 skipped; build/JS correctos.

Validación real del arreglo: misma consulta `Analizá XRP / LTC: situación actual, riesgos y escenarios.` completada en 14,53 s, stop_reason=stop, truncated=false, 3749 caracteres y fuentes cuenta/positions/pair_ratio. La detección de símbolos de par ahora fuerza contexto operativo y lectura del ratio, para que esta validación use datos actuales. Conversación temporal eliminada; conversación original del usuario conservada.

## Análisis específico de pares y límite de criterio (2026-11-10)

La crítica de Alan: el asesor narraba el tablero, confundía variación de ratio con funding y margen de cuenta con liquidez. Se agregó `ai/pair_analysis.py` y herramienta `pair_review`: evidencia nombrada con unidades, hedge neto, shocks de ambas patas a ratio constante, alternativas de sensibilidad, carry actual y estadística ya cacheada con fecha propia. Ningún I/O de mercado nuevo en esta herramienta. El análisis nominal no equivale a hedge por beta ni a reversión confirmada. Activos compartidos se explicitan; no se atribuye funding exclusivo si existe solapamiento. Se admiten aliases con/sin prefijo y minúsculas solo cuando son inequívocos, preservando long/short; pares cerrados deben usar herramientas históricas.

Pedidos de analizar un par precargan esta evidencia en lugar de toda la tabla de cartera. El margen no se convierte en liquidez, los valores faltantes siguen null y la analítica vencida no se reutiliza. Se corrigieron por revisión independiente dos casos: consulta en minúsculas sin prelectura y par cerrado tratado como activo.

**Calidad generativa todavía no resuelta.** Dos pruebas con Qwen real mejoraron las cifras/unidades al alimentar el par en objeto nombrado, pero siguieron conteniendo conclusiones injustificadas: reversión pese a ADF inconcluso, fundamentos DeFi no verificados para estos instrumentos, plazo de salida arbitrario y pérdida temporal por mantener una tesis. No afirmar que esta capa ya sea un analista confiable. La muestra con contexto analítico fresco tardó 6,11 s y terminó completa; eso NO valida sus recomendaciones.

Prueba aislada con think=true, contexto 12288 y 4096 tokens: 47,75 s, 100% GPU, 3886 tokens, y persistieron errores de criterio. No se activó ese perfil en producción: el mayor costo no mostró mejora suficiente. Evidencia privada temporal en `/tmp/pairdesk-desk-live/pair-analysis.json`, `reasoning-evidence.json` y `reasoning-result.json`; estos archivos no son memoria personal. El siguiente trabajo debe validar afirmaciones/criterios de decisión y evaluar capacidad del modelo, no limitarse a sumar instrucciones de estilo.

## Codex con la cuenta de ChatGPT

Pair Desk usa Codex App Server por defecto y la sesión existente de ChatGPT. El modelo comprobado con esta cuenta es `gpt-5.6-sol`. El servicio rechazó `gpt-6.1-sol` durante la prueba de acceso. Para usar Ollama al iniciar el servidor, configurá `PAIRS_DESK_ADVISOR_PROVIDER=ollama`. `PAIRS_DESK_CODEX_MODEL` permite elegir otro modelo habilitado.

Antes de consultar, el panel permite autorizar el envío a OpenAI de la pregunta, el historial reciente, las memorias pertinentes y la evidencia operativa seleccionada. El backend rechaza solicitudes sin esa autorización antes de guardar la consulta. Codex usa una sesión efímera, una carpeta temporal y un perfil con comandos, conectores y búsqueda web deshabilitados. Pair Desk reúne la evidencia con sus herramientas locales. La respuesta se muestra al completar el turno.

Validación con cartera ficticia por la ruta de chat y base temporal. Sol respondió en 15,8 s, distinguió carry de reversión y calculó una pérdida incremental de $10 ante una suba común del 5% con ratio constante. El servidor local verificó el proveedor activo y respondió 403 a una consulta sin autorización. Suite: 462 pruebas pasan, una omitida y los dos fallos previos de call_stats y zscore_alignment.
