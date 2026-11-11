# Tareas pendientes

## Cierre 2026-11-11

- [x] Desk persistente, identidad, herramientas de lectura, consentimiento y proveedor Codex; mantener evaluación de calidad de análisis como trabajo continuo.
- [x] TWAP nativo aumentar/reducir/cerrar, unidades y rango nativo 7d, persistencia/seguimiento, diagnóstico, gráfico agrupado y evolución de media con fills nativos.
- [x] Suite Python completa y suites JS aprobadas; documentación consolidada.
- [ ] Validar cancelación TWAP y fallos extremos en testnet sin usar la cartera real.
- [ ] Resolver errores de TypeScript estricto pendientes y ampliar smoke visual de regresión.

Las notas de validación/fallos anteriores son históricas; CURRENT_STATE.md contiene el resultado vigente.


Estas tareas se mantienen alineadas con `docs/current/PLAN_CONSOLIDACION.md`. Marcar una tarea como hecha solo después de implementar y verificarla.

## Prioridad alta — seguridad y operación

- [ ] Validar en testnet el flujo React de `PairActions` antes de considerarlo operativo.
- [x] Completar cuenta regresiva, bloqueo al vencer y refresco de posiciones tras una orden. Verificado con pruebas locales; falta validación operativa en testnet.
- [x] Manejar respuestas no JSON en `request()`.

## Prioridad media — React

- [x] Ampliar cards de Cuenta / Estrategia con desglose contable, proyección por pata, fecha de drawdown y medias diarias; evitar doble conteo de posiciones compartidas.

- [ ] Migrar KLineCharts a una dependencia npm importada por TypeScript.
- [ ] Dividir `App.tsx` en hooks y componentes más pequeños.
- [x] Agregar pruebas de comportamiento para `PairActions` (contratos de expiración, bloqueo, refresco y errores HTTP).
- [ ] Resolver navegación y controles en pantallas móviles.
- [x] Mejorar lectura de PNL total, mini gráfico, escala acumulada y resumen compacto del par. Validado con build y pruebas focalizadas; falta ejecutar pytest en un entorno con pytest.
- [x] Mantener el gráfico del Explorador accesible junto a la selección en escritorio y móvil. Validado con build y prueba estructural; falta smoke visual con Chromium.
- [ ] Atenuar secciones sin contenido y mejorar indicadores que hoy dependen solo del color.

## Prioridad media — backend

- [ ] Separar lecturas de escrituras; `GET /api/state` todavía tiene efectos secundarios documentados.
- [ ] Revisar snapshots SQLite, esquemas Pydantic y configuración de host/puerto.
- [ ] Unificar dependencias entre `requirements.txt` y `requirements_frontend.txt`.

## Pendientes de producto

- [x] Integrar primera versión del chat Asesor IA local con Ollama, contexto fresco y herramientas de lectura.
- [x] Verificar aceleración GPU y latencia del Asesor IA tras reinicio: 100% GPU, PNL fría 52,98 s / caliente 3,19 s. Ver `docs/current/RETOMAR_ASESOR_GPU.md`.
- [x] Reforzar fidelidad de funding/posiciones: prelectura obligatoria por backend, conteos separados de pares/posiciones y evidencia compacta completa. Funding real contrastado a centavos; seguir evaluando análisis y calidad general.
- [x] Extender Desk con identidad versionada, persistencia de conversaciones, memoria por ámbito, revisiones/consolidación, recuperación contextual, herramientas permitidas y administración React. Ver `docs/current/DESK_MEMORIA.md`.
- [ ] Configurar un modelo local de embeddings si hace falta búsqueda semántica adicional; FTS5 funciona sin él. Research externo requiere proveedores explícitos.
- [ ] **Prioridad Desk:** validar criterio de análisis, no solo cifras/streaming. pair_review mejora la evidencia, pero Qwen sigue produciendo conclusiones no respaldadas; think=true fue probado sin mejora suficiente y no está activado. Revisar DESK_MEMORIA.md antes de ampliar a recomendaciones/alertas.

- [ ] Completar paridad de Cerrados, Eventos, Alertas y Gestión. Cuenta / Estrategia ya tiene una primera vista operativa; queda validar visualmente y ampliar paridad si hace falta.
- [ ] Retirar interfaces antiguas solo después de verificar paridad.

## Regla de actualización

Si una tarea cambia rutas de trading, contabilidad o persistencia, actualizar primero `CURRENT_STATE.md`, `docs/ARCHITECTURE.md` y las pruebas relevantes.
