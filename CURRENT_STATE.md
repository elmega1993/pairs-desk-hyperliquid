# Estado actual — cierre 2026-11-11

## Interfaz y cuenta

React es la interfaz principal en `/react`; `/` y `/aurora` siguen como fallback. El escritorio incluye cuenta/estrategia, gráficos de PNL y ratio, explorador, cerrados y asesor. Se consolidaron cards de costos, funding por activo sin duplicación, exposición, filtros y series oficiales frente a estimaciones históricas. Ver `docs/current/HISTORICAL_ACCOUNT.md` y `docs/ARCHITECTURE.md` para cobertura y límites. El acceso móvil por Tailscale es privado y de consulta; requiere validación final en Android.

## Desk

Se extendió el asesor existente con identidad editable, conversaciones persistentes, memoria estructurada SQLite, FTS5, procedencia/revisiones, recuperación acotada, administración y modos Chat/Analyze/Research. Codex App Server es el proveedor predeterminado mediante la sesión existente de ChatGPT; modelo comprobado `gpt-5.6-sol`. Ollama sigue disponible con `PAIRS_DESK_ADVISOR_PROVIDER=ollama`; GPU local comprobada. El panel requiere consentimiento para enviar contexto seleccionado a Codex. El modelo no recibe credenciales ni tiene herramientas de órdenes. No confundir corrección de cálculos con calidad garantizada de recomendaciones. Research sin proveedores externos no promete investigación web. Ver `docs/current/DESK_MEMORIA.md`.

## TWAP nativo

Integrado en el ticket actual para aumentar, reducir y cerrar: minutos/horas/días, de 5 minutos a 7 días, mínimo nativo de USD100 por pata. Dos ejecuciones independientes, cantidades redondeadas y wire firmado mediante SDK oficial. Reserva durable, bloqueo por activos compartidos, cancelación confirmada incluso con nuevas órdenes deshabilitadas, recuperación sin reenvíos y seguimiento WebSocket por cuenta/dex. El administrador muestra estado/progreso/fills y errores saneados. El exchange puede rechazar por cantidad máxima de TWAP activos: se observó ese motivo, pero no se codifica un máximo numérico sin contrato verificado.

El gráfico agrupa cada TWAP en un tramo temporal. La media actual usa entryPx de Hyperliquid; la evolución histórica incorpora fills TWAP cacheados, deduplicados y reconciliados, exclusivamente para esa curva. No modifica PNL ni ledger. MEDIA ACTUAL aparece en 0% por escala normalizada. Ver `docs/current/NATIVE_TWAP.md`.

## Verificación de cierre

- Python: **534 passed, 1 skipped**. Se actualizaron las pruebas obsoletas de call-stats (contabilización al completar la petición) y Z-score (indicador nativo, dominio completo y valores rolling).
- **21 suites JavaScript aprobadas** y build Vite aprobado. La compilación se genera localmente, no se versiona.
- TypeScript estricto aún tiene errores previos en PnlChart/PortfolioKpis/pnlModel; no confundir build Vite con typecheck completo.
- Se observaron aceptaciones nativas/fills iniciados por el usuario. Las pruebas del agente no enviaron órdenes, no cancelaron TWAP ni habilitaron trading. Cancelación contra exchange y fallos operativos extremos siguen sin validación integral en testnet.
- Los datos personales, exportaciones, SQLite, settings, credenciales y copias de entregas quedan fuera de Git. El snapshot histórico detallado previo al cierre se conserva en almacenamiento local privado.

## Retomar

Leer START_HERE.md, AGENTS.md, TASKS.md y las guías de Desk/TWAP. No reinstalar driver/GPU ni rehacer el asesor. No reintentar órdenes inciertas ni cancelar trabajos para probar. Consultar el estado actual al abrir; no asumir que el estado de la sesión anterior sigue vigente.
