# Fase 3A — Gráfico interactivo de PnL y señales informativas

## Uso
Cerrá la app anterior, extraé este ZIP y ejecutá iniciar_frontend.sh.
Recargá el navegador con Ctrl+Shift+R para cargar los nuevos scripts.
La configuración y el ledger conservan sus ubicaciones habituales.

En Cuenta, el gráfico permite elegir 1/7/30/90 días o Todo, contados desde el último
registro disponible. Detalle permite todos los puntos, 1 hora, 4 horas o 1 día.
Cada intervalo conserva el último dato real: no se interpolan registros ausentes.
El cursor muestra fecha, hora y PnL del punto más cercano. También se puede recorrer
con las flechas del teclado enfocando el gráfico. Se muestran fechas en el eje inferior.
La selección se conserva durante los refrescos automáticos de la página.

Se quitó el recorte de 800 puntos del historial local. Todo muestra los registros que
existen en el archivo; no recupera datos no registrados. Se etiqueta la fuente local/HL.
Los snapshots nuevos identifican neto o abierto+realizado. Se interrumpe la línea cuando
cambia esa base para no presentar una diferencia contable como un movimiento de mercado.
Los registros antiguos se etiquetan como anteriores porque no guardaban esa distinción.

Gestión consulta TP/ADD en el backend usando management_signals y Z diario compartidos.
Respeta los escalones guardados como ejecutados y la referencia congelada. Si no existe
una referencia válida, muestra N/D. Informa condiciones y hora de cálculo. Las señales
se actualizan al abrir Gestión o con el refresco de cuenta; no se disparan con cada tick.
No se envían órdenes ni se marcan escalones automáticamente.

Se conservan los cambios de funding visible de fase 2.1.

## Validación y pendientes
86 pruebas Python y 3 suites JavaScript aprobadas. Compilación Python y sintaxis JS
verificadas. No se completó validación visual en navegador: la descarga de Chromium falló.
Sin consultas a una cuenta real ni envío de órdenes.
Siguen pendientes salud estadística/ADF, alertas push y vela alimentada en vivo.
