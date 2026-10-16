# Pairs Desk 2.0 — PNL y pares cerrados

## Cambios
- Nueva sección **Pares cerrados** al final del escritorio, con acceso desde la barra lateral, búsqueda, ordenamiento por encabezados, apertura, cierre, realizado, funding, comisiones y PNL total.
- Radar de posiciones: nueva columna **TOTAL** ordenable por `total_pnl` del backend. Los importes no verificables siguen en **N/D**.
- Lista lateral: nuevo criterio de ordenamiento **Total**.
- Evolución del PNL: **autoescala vertical** por defecto (sin forzar cero), modo opcional **Desde cero**, variación visible del período y tooltip existente. Persistencia local de la preferencia de escala.
- No se cambiaron rutas de trading, configuración, ledger ni datos financieros.

## Precauciones
- `total_pnl` de un par o de cerrados puede ser N/D cuando falta funding histórico u otro componente; no se calcula artificialmente.
- El historial de PNL existente puede mezclar snapshots de base `gross` y `net`; no es necesariamente un neto verificado. La autoescala solo cambia la representación visual.
- El archivo `package-lock.json` está incluido. La compilación Vite debe ejecutarse en Ubuntu con npm; el contenedor no tiene cacheada la dependencia vite.

## Pruebas
- 123 tests Python aprobados, 10 omitidos.
- Transpilación TypeScript sin errores sintácticos en componentes modificados.
- Prueba visual y build de Vite pendientes en Ubuntu.
