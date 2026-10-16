# Auditoría — primera intervención (12/10/2026)

## Implementado
- Se usa `spread_stats` de `pairs_desk.metrics` para el Z-score diario de la terminal, con la misma muestra final de 250 velas que solicita Streamlit (ventana dinámica `min(90, max(10, len/3))`). Se deja de usar Z(20) del log-ratio. **El Z permanece N/D cuando no está disponible**.
- Se mantiene el Z de gestión exclusivamente diario: los gráficos en otros intervalos no deben recalcular una señal de gestión incompatible.
- Los niveles TP/ADD de las velas HTML se dibujan desde `management_entry_ratio` guardado, no desde la entrada media móvil de la posición; TP3 por defecto se ajusta a 20%.
- Funding `sinceOpen` incompleto en cualquier pata da N/D, no cero. `total_pnl` activo se declara N/D si falta funding, además del historial de fills.
- El total neto de la terminal se declara N/D cuando hay pares archivados cuyo funding aún no está acreditado. Esto evita sobrestimar la precisión; el realizado y comisiones de cerrados siguen visibles.
- Consulta periódica de cuenta cada 30 s cuando la pestaña está visible. WebSocket de ratios sin cambios.
- Validación de Host en todos los endpoints mediante `TrustedHostMiddleware` (localhost / 127.0.0.1 / ::1).
- Se excluyeron `.venv_frontend` y `__pycache__` del ZIP distribuido. El lanzador regenera el entorno virtual cuando falta.

## Pendiente, deliberadamente no implementado
- Ledger persistente SQLite de fills y `userFunding`, con reconciliación histórica: no se puede asignar funding pasado a ciclos sin recuperar y verificar timestamps, incluyendo solapes de patas.
- Señales TP/ADD completas y sus marcadores en la terminal, y migración de Streamlit.
- Semáforo de estacionariedad/half-life y calibración de umbrales: no cambiar señales de trading real sin comparación sobre históricos.
- Auto-conciliación, `bulk_orders`, tickets de reparación, alertas push y stress tests.

## Seguridad
No se modificaron las rutas de firma, emisión/consumo de tickets, CSRF ni el bloqueo de trading ante incertidumbre. Ningún cambio emite órdenes por sí solo.
