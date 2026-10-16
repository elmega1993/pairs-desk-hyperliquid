# Ratios en vivo — corrección de conexión

Se corrigió la política Content-Security-Policy del servidor: connect-src ahora permite exclusivamente el WebSocket público wss://api.hyperliquid.xyz además del propio servidor. La versión anterior lo bloqueaba en el navegador.

Si la conexión no entrega precios, se consultan precios de marca públicos desde el servidor local cada 5 segundos. El encabezado distingue «Ratio en vivo» de «Ratio automático · respaldo 5 s». Si faltan ambas fuentes, no se muestran datos viejos como si fueran en vivo. Los detalles de error se pueden ver al dejar el cursor sobre el indicador.

Para instalar: cerrar el servidor anterior, reemplazar los archivos de código de la app por los del ZIP, iniciar con iniciar.sh y recargar con Ctrl+Shift+R. Es necesario reiniciar el servidor, porque la corrección principal cambia un encabezado HTTP. Se conservan los archivos de configuración e historial en las carpetas de usuario.

Ratio y variación desde la entrada se actualizan automáticamente. PnL, funding, Z-score y velas siguen con Actualizar. Los ticks no reinician el formulario de órdenes.

Validación: recepción WebSocket real de ZK/STRK y xyz:ORCL/xyz:XYZ100; consulta HTTP real de esos cuatro símbolos; pruebas de reconexión, datos vencidos, error HTTP, respaldo, fuentes consistentes y permiso CSP. No se accedió a la cuenta del usuario ni se enviaron órdenes.
