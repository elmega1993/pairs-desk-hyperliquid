# Desk / Asesor IA local

La implementación existente fue extendida con identidad, memoria y conversaciones persistentes. Guía vigente: [DESK_MEMORIA.md](DESK_MEMORIA.md). Abrí **Asesor IA** para usar Desk y **Memorias y preferencias** para revisar recuerdos, reglas y parámetros. El modelo sigue local con GPU y sin herramientas de órdenes.

La guía anterior se conserva a continuación como historial de la primera versión; sus referencias a conversación solo en pestaña y GPU pendiente ya no describen el sistema actual.

# Asesor IA local

Para continuar después del reinicio: [RETOMAR_ASESOR_GPU.md](RETOMAR_ASESOR_GPU.md).

Abrí Pair Desk → **Asesor IA**. Usá una pregunta sugerida o consultá posiciones, costos, funding o escenarios de un par. La respuesta se muestra a medida que el modelo genera texto, con fecha y fuentes consultadas. El contexto se toma de las lecturas de cuenta que la app actualiza normalmente; si está antiguo, usá Actualizar y reintentá.

Requisitos: Ollama iniciado en esta PC y modelo local `qwen3.5:9b` instalado. Ya estaban disponibles al implementar. No se requieren claves de API ni una suscripción de inferencia. En el encabezado se informa CPU, GPU, ejecución mixta o sin cargar. La primera consulta tarda más por carga del modelo. GPU validada el 2026-11-10 tras reinicio: Ollama informa 100% GPU, contexto 8192. No se modifica el controlador desde la app.

La IA tiene acceso de lectura por herramientas a posiciones únicas y pares abiertos, resumen oficial de estrategia, funding/fees por activo, diario estimado u oficial, historia oficial, cerrados, indicadores calculados del par, velas de ratio y ledger histórico disponible. Cobertura incompleta y datos faltantes deben interpretarse como tales. No tiene acceso a claves, órdenes, archivos arbitrarios ni navegación. No se presupone acceso a noticias o precios externos a Pair Desk. Las respuestas son interpretaciones; cada conclusión debe contrastarse con datos, vigencia y escenarios.

La conversación vive en la pestaña: cambiar de vista la conserva, Nueva conversación o recargar la borra. Durante una consulta se espera al modelo; cerrar/recargar puede dejarlo terminando durante el tiempo acotado de generación. Si otra consulta está en curso, esperá. Si Ollama no responde o falta memoria, se muestra un error recuperable. Las respuestas truncadas/interrumpidas se marcan y no se incorporan como conclusiones al siguiente contexto.

Prueba local antes de reinicio: Ollama respondió una consulta mínima (aprox. 9 s incluyendo carga), con ejecución CPU. También completó una consulta real de PNL y fecha desde el chat. La velocidad con RTX 5070 queda pendiente de comprobar después del reinicio.

Validación completa del desglose: una consulta real llamó la herramienta de costos y respondió con ambas fuentes, en 104 s usando CPU. Antes de reiniciar, consultas con herramientas pueden tardar del orden de minutos; no extrapolar ese tiempo a la GPU.

Validación GPU posterior al reinicio (2026-11-10): PNL frío 52,98 s / caliente 3,19 s; pico observado 7.059 MiB de VRAM y 100% GPU. PNL contrastado con snapshot. Las consultas de funding y posiciones detectaron problemas de fidelidad: omitió herramientas explícitas, inventó desglose y confundió posiciones con pares. Su corrección sigue pendiente; ver RETOMAR_ASESOR_GPU.md para evidencia y continuación.
