# Retomar después del reinicio: GPU del Asesor IA

## Continuación vigente: Desk persistente

La extensión de personalidad/memoria/orquestación está integrada. Leer `DESK_MEMORIA.md`; GPU continúa validada. Se forzó la lectura de costos/posiciones desde backend y funding real volvió a coincidir a centavos (1,59 s). La evaluación de calidad general sigue vigente. Los problemas y pendientes que siguen describen los puntos históricos de GPU previos a esta extensión.

## Resultado después del reinicio — 2026-11-10

**GPU validada.** `nvidia-smi` reconoce RTX 5070, driver 595.99.02 y 12.227 MiB. Ollama detecta CUDA/compute 12.0, carga qwen3.5:9b en **100% GPU**, contexto 8192; `/api/advisor/status` devuelve `processor: GPU`. Muestreo durante consultas: pico 7.059 MiB de VRAM y 100% utilización GPU. No hizo falta reinstalar, reiniciar servicios ni modificar código/configuración. Pair Desk ya estaba activo desde la copia correcta; `/react` y API responden 200.

Validación por HTTP local a `/api/advisor/chat`, con estado fresco y el mismo flujo que consume React (sin nueva prueba visual):

- PNL frío: 52,98 s, incluyendo carga e inicialización; terminó sin truncar. Log de Ollama: generación ~41 tokens/s.
- Misma pregunta PNL con modelo cargado: 3,19 s, primer token 0,90 s; PNL concuerda a centavos con el snapshot correspondiente. La respuesta añadió interpretaciones no solicitadas que todavía requieren evaluación.
- Funding: 2,35 s, primer token 0,86 s. **Falló la fidelidad:** omitió `strategy` pese al pedido explícito; dio un desglose cobrado/pagado distinto al backend. La fuente final solo fue `cuenta y posiciones`. No contar esta consulta como validación contable.
- Posiciones: 3,70 s, primer token 0,86 s. Omitió `positions`, confundió 34 posiciones con 17 pares; identificó correctamente el par con peor PNL. No considerar validado su análisis de riesgo.
- Pruebas focalizadas: 17 Python pasan; suite JS de streaming pasa. No se alteró código ni se repitió build. No se ejecutaron órdenes.

**Próximo foco:** corregir uso verificable de herramientas, conteos y fidelidad del asesor. GPU resuelta no implica calidad de respuestas resuelta. Evidencia privada temporal en `/tmp/pairdesk-gpu-check/`; no depender de esos archivos para retomar.

Lo que sigue conserva el punto de continuación y evidencia anteriores al reinicio como historial.

Fecha del punto de continuación: 2026-11-10. Alan pidió dejar todo documentado antes de reiniciar la PC tras instalar el controlador NVIDIA. Próxima tarea: comprobar aceleración GPU y medir latencia; la integración del chat ya está hecha.

## Proyecto correcto

Esta copia activa de Pair Desk está en:

```text
/home/alan/Descargas/Pairs_Desk_Saneamiento_con_cierres/Pairs_Desk_Saneamiento_S1_Entrega4_auditoria_visual (2)/Pairs_Desk_FINAL
```

No confundir con `/home/alan/Documentos/arbitraje` ni con los ZIP/backups del directorio de descargas. Leer AGENTS.md, CURRENT_STATE.md, TASKS.md y este archivo. Hay numerosos cambios previos y fuentes sin commit: conservarlos; no resetear, limpiar ni incluir todo en un commit.

## Estado comprobado antes del reinicio

- PC: i7-12700F, 32 GB de RAM, RTX 5070 de 12 GB (GPU indicada por Alan).
- Kernel activo: `7.0.0-42-generic`.
- `modinfo -F version nvidia`: `595.99.02` instalado.
- `lsmod` no muestra `nvidia` ni `nouveau`; no hay `/proc/driver/nvidia/version`.
- `nvidia-smi` falla al comunicarse con el controlador. No afirmar todavía que el reinicio resolvió el problema.
- Ollama 0.33.3, servicio systemd `enabled` y `active`. Modelo local `qwen3.5:9b` descargado. `ollama ps` verificó `100% CPU`, contexto 8192.
- API del modelo: `http://127.0.0.1:11434`. Pair Desk: `http://127.0.0.1:8510/react`, nueva sección **Asesor IA**.
- El servidor de Pair Desk se inició manualmente; ese proceso no sobrevive al reinicio. Ollama sí está habilitado como servicio. No se agregó un servicio de inicio para Pair Desk.

## Implementación terminada

- Backend: `pairs_desk/local_advisor.py` y `pairs_desk/advisor_routes.py`; observadores de estado/analítica y proveedores de lectura en `read_only_server.py`.
- React: `components/Advisor.tsx`, `advisorApi.ts`, navegación en App.tsx y estilos al final de style.css.
- Modelo fijo inicial `qwen3.5:9b`, configurable por entorno `PAIRS_DESK_ADVISOR_MODEL`; endpoint de Ollama fijo en loopback, sin proxies ni redirecciones; modelos cloud bloqueados.
- Herramientas: posiciones, estrategia/costos/diario/historia, cerrados, indicadores, velas de pares conocidos y ledger paginado en SQLite `mode=ro` con cuenta fijada por consulta.
- Sin herramientas de órdenes, claves, shell, archivos arbitrarios o navegación. No tocar `secure_trade_routes.py` para esta tarea.
- Snapshot de cuenta máximo 90 s; analítica máximo 180 s. Una generación concurrente, hasta tres rondas, contexto 8192, máximo 700 tokens de respuesta por ronda; límite de generación aproximado 4 min más comprobación inicial del modelo.
- Conversación solo en memoria de la pestaña. No hay cancelación remota inmediata prometida ni alertas autónomas en esta primera versión.
- Ver también `ASESOR_LOCAL.md` y `../superpowers/plans/2026-11-10-local-advisor.md`.

## Secuencia después del reinicio

1. Ejecutar `nvidia-smi`. Debe reconocer la RTX 5070 y la memoria. Si falla, diagnosticar antes de reinstalar o cambiar drivers: kernel, módulos cargados, versión del módulo, Secure Boot si corresponde y errores NVIDIA del arranque. No dar por hecho que hay que reinstalar.
2. Revisar `systemctl is-active ollama` y `ollama list`. No descargar otra vez los modelos existentes. `ollama ps` vacío antes de la primera consulta es normal.
3. Iniciar la copia correcta de Pair Desk mediante `./iniciar_frontend.sh` desde el directorio indicado arriba. Ya tiene dependencias y React compilado. Comprobar `/react` y `/api/advisor/status`.
4. Abrir **Asesor IA**, esperar datos frescos y hacer una consulta breve de PNL. Comprobar **durante o justo después de la generación** `ollama ps` y `nvidia-smi`: GPU/VRAM realmente utilizadas, sin conformarse con que el controlador esté instalado. El modelo se descarga de memoria tras unos 5 min inactivo.
5. Si NVIDIA funciona pero Ollama sigue en CPU, revisar diagnóstico del servicio y detección de GPU. Antes de descargar un modelo de memoria o reiniciar Ollama, comprobar que no haya consultas activas ni otras cargas que se vayan a interrumpir. No forzar CPU ni modificar opciones de CUDA sin evidencia.
6. Repetir la consulta real de costos que pasó antes del reinicio: «Usá strategy con section costs y limit 3. Necesito los montos de funding cobrado y pagado desde el inicio. Después respondé brevemente». Verificar fuente `strategy`, cifras contra el backend, fechas y tiempo total. También probar una pregunta natural de posiciones/riesgo; todavía falta evaluar ampliamente la calidad de consejos.
7. Registrar GPU/VRAM, latencia con carga fría y caliente, fuentes usadas y limitaciones. Actualizar CURRENT_STATE.md/TASKS.md. Solo marcar GPU validada cuando haya evidencia de inferencia usando la placa.

## Evidencia y límites de la validación anterior

- Modelo mínimo: respuesta real correcta en CPU, aproximadamente 9 s incluyendo carga.
- Consulta real desde navegador: PNL neto y fecha correctos, respuesta completa con fuente; historial conservado al cambiar de vista; escritorio 1660 px y móvil 390 px sin desbordamiento.
- Consulta real de funding: completada en CPU en **104 s**, fuentes `cuenta y posiciones` y `strategy`, sin error. No extrapolar esta latencia a GPU.
- El primer contexto extenso agotaba el timeout en CPU: se redujo a resumen compacto, detalles por herramientas y costos paginados. Inicialmente el modelo podía omitir una herramienta solicitada; se reforzaron las instrucciones explícitas de lectura y la prueba real final sí la llamó. Seguir evaluando fidelidad, no asumir fiabilidad perfecta.
- 17 nuevas pruebas Python y test JS de streaming pasan. Build Vite correcto; compilación Python y `git diff --check` correctos.
- Suite completa: **376 passed, 2 failed previos, 1 skipped**. Fallos previos: `test_call_stats_records_local_api_request_without_sensitive_fields` y `test_zscore_keeps_the_same_full_x_domain_as_ratio_bars`.
- Cuatro diagnósticos TypeScript previos: PnlChart.tsx (2), PortfolioKpis.tsx y pnlModel.ts. No hubo diagnósticos nuevos en los archivos del asesor.
- Capturas y logs de pruebas estaban en `/tmp/pairdesk-advisor-*`; son temporales y pueden desaparecer al reiniciar. No dependen de ellos los fuentes ni esta documentación.

Pruebas focalizadas si se modifica el asesor:

```bash
.venv_frontend/bin/python -m pytest tests/test_local_advisor.py tests/test_advisor_routes.py -q
node tests/test_advisor_api_behavior.cjs
npm --prefix react_frontend run build
```

No ejecutar órdenes reales ni alterar credenciales/configuración personal para validar GPU o chat.
