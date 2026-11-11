# TWAP nativo de Hyperliquid

## Uso

En Operar par, elegir Aumentar, Reducir o Cerrar y TWAP nativo. Duración en minutos, horas o días; valores decimales se convierten a minutos enteros sin redondeo silencioso. Rango vigente: 5 minutos–7 días (10080 minutos); predeterminado 30 minutos. Mínimo USD100 por pata. Ticket previo y confirmación explícita; reducir/cerrar son reduce-only. Cada pata es una orden independiente y puede ejecutarse parcialmente.

El botón TWAP abre el administrador incluso sin un par seleccionado o con nuevas órdenes deshabilitadas. Muestra IDs, cantidades observadas, progreso, frescura, fills paginados y cancelación confirmada. Cancelar solo detiene ejecución futura, no revierte fills. Hyperliquid continúa ejecutando aunque se cierre Pair Desk. Intervalos desde 30s y máximo slippage 3% propios del exchange; no aplica el slider de ejecución inmediata.

El exchange puede rechazar por máximo de TWAP activos. Ese motivo fue observado; cada par consume dos TWAP. No se impone un máximo numérico local deducido de una sola cuenta ni se cancelan otros trabajos automáticamente.

## Persistencia y seguridad

`pairs_desk/native_twap.py` agrega tablas e índices a orders.sqlite3 y reserva activos atómicamente por cuenta. Convive con el journal inmediato; ninguna ruta debe eludir el bloqueo de activos compartidos. Valida posiciones de ambas patas, mínimos y tamaños tras redondeo, y prepara firmas antes del primer POST. Usa float_to_wire y sign_l1_action del SDK: ceros finales y orden msgpack importan. No hay planificador local ni reenvío de resultados inciertos.

Se persisten intención e IDs por pata. Fallo de la segunda solicita cancelar la primera conocida. La intención de cancelación se serializa contra el envío pendiente; un ACK tardío no reemplaza un terminal verificado. Recuperación por ID o firma inequívoca de activo, dirección, tamaño, minutos, aleatorización, reduceOnly, cuenta y timestamp. Tiempo transcurrido no confirma ejecución completa. Reiniciar no reemite órdenes.

`native_twap_monitor.py` observa WebSocket público: twapStates (Core/XYZ), userTwapHistory y userTwapSliceFills. Reconecta con snapshots y deduplica fills. Frescura por dex: Core actualizado no oculta XYZ desactualizado.

Tickets/rutas conservan origen, CSRF, confirmación, cuenta, signer y bloqueo existentes. Endpoints GET /api/trade/twaps, GET /api/trade/twaps/{id}/fills y POST /api/trade/twaps/{id}/cancel. Cancelar se permite sin habilitar nuevas órdenes, manteniendo las demás comprobaciones.

Errores se clasifican y guardan con un detalle saneado opcional (máximo 320 caracteres), sin respuestas crudas, firmas, direcciones o credenciales. Migración aditiva nullable error_detail. Errores desconocidos conservan su mensaje útil saneado; los motivos descartados por versiones previas no se reconstruyen ni se inventan. React los muestra como texto.

## Gráfico y media

Un tramo por grupo, con avance por pata; escalas grandes pueden colapsarlo en una marca. Se ocultan marcas ADD/RED únicamente cuando coinciden exactamente con fills nativos identificados. Un rechazo sin IDs/fills no dibuja una ejecución. No cambia la contabilidad.

entry_ratio conserva el cociente entryPx long/short actual de Hyperliquid. MEDIA ACTUAL · 0% indica escala normalizada respecto de esa media. La evolución entry_history combina fills generales y la vista mínima nativa persistida solo para el gráfico, sin consultas adicionales al exchange ni cambios de PNL/fees/funding/ledger. Deduplica coin/tid/side, conserva el registro general y exige inicio verificable, cantidades reconciliadas y promedios coherentes con posiciones actuales (tolerancia relativa de redondeo 1e-4). Ausencia de startPosition en un fill nativo no equivale a una nueva apertura. Con cobertura insuficiente no inventa curva.

## Verificación y pendientes

Pruebas deterministas con SQLite temporal y transporte simulado: envíos, rechazo, timeouts, recuperación, cancelación concurrente, aislamiento, migraciones, duración, errores, reconciliación de medias y contabilidad intacta. Suites JS de ticket, administrador, modelo y gráfico; build Vite y smoke sintético desktop/móvil. Resultados globales vigentes en CURRENT_STATE.md.

El usuario inició órdenes nativas aceptadas y se observaron fills. El agente no envió/canceló órdenes para verificar. Falta aceptación integral de cancelación y fallos extremos contra testnet. Las dos patas no son atómicas; cobertura del historial público puede ser limitada. No inferir ausencia de ejecución por ausencia de fills observados.

Referencias: [acciones](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/exchange-endpoint), [firma](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/signing), [WebSocket](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/websocket/subscriptions), [ampliación oficial a 7 días](https://t.me/s/hyperliquid_announcements/578).
