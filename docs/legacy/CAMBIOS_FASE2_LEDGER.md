# Fase 2 — Ledger persistente de fills y funding

Continuación de Pairs_Desk_Auditoria_Fase1.zip. Se conservan sus cambios.

## Cómo usar esta versión

Cerrá la aplicación anterior, extraé este ZIP y abrí `iniciar_frontend.sh` como antes.
No hace falta copiar settings: se conserva el archivo habitual de configuración.
La primera lectura descarga el historial disponible; puede tardar más que una actualización normal.
El ledger se sincroniza mientras alguna interfaz consulta la cuenta. No hay vigilante en segundo plano.

La base se crea en `~/.local/share/crypto-pairs-desk/ledger.sqlite3`, fuera de la carpeta
extraída. Conservá una copia de esa base junto con `~/.config/crypto-pairs-desk/settings.json`
con la app cerrada. Cambiar de ZIP o reiniciar no borra el historial. Las cuentas se mantienen separadas.

## Cambios

- SQLite transaccional, registros originales y deduplicación por tid + moneda/lado/orden.
- Funding deduplicado por hash + timestamp + moneda, con signo original `delta.usdc`.
- Paginación con solapamiento en el último milisegundo: no salta eventos empatados.
- Sincronización incremental con checkpoint persistente y control de continuidad de fills.
- Fallos de API o eventos conflictivos no avanzan checkpoints ni sustituyen registros anteriores.
- Integración en la terminal HTML y Streamlit. Funding activo calculado desde el ledger;
  se muestra N/D si no se verifica la apertura de ambas patas o si su cobertura supera 60 s de antigüedad.
- Cerrados: reconstrucción individual de las dos patas y contraste de realizado/fees antes
  de incorporar funding. Se persiste la conciliación en settings sin alterar realizado ni fees.
- Historial y CSV: `total_pnl` = realizado − fees + funding. Cuando falta evidencia, N/D/celda vacía.
  `net_realized` queda como campo legado de realizado menos fees; las vistas usan `total_pnl`.
- El acumulado incorpora funding de activos y cerrados. Se informa la hora de cobertura del funding.
- Sin cambios en firma, órdenes, Agent, tickets, CSRF o conciliación de ejecución.

## Límites explícitos

- Guardar datos a partir de ahora no reconstruye movimientos que la API ya no devuelve.
- Si el primer barrido alcanza 10.000 fills, falta el punto de continuidad en una actualización,
  o un milisegundo satura una página, los fills quedan parciales; no se afirma que estén completos.
  Resolver un hueco antiguo requiere una futura importación/conciliación; esta versión no la automatiza.
- Cada barrido está limitado a 40 páginas. Un historial que supere ese límite seguirá como parcial.
- Un funding que coincide exactamente con la apertura/cierre de una pata se deja sin atribuir
  (N/D), porque su orden relativo no puede determinarse sólo con timestamps.
- Los archivos históricos que no coincidan con los ciclos reconstruidos mantienen su realizado,
  pero no reciben un funding estimado ni un neto ficticio.
- El PnL agregado corresponde a los pares registrados, no necesariamente a toda la cuenta:
  operaciones sueltas, otros pares o diferencias de período pueden impedir igualdad con Hyperliquid.
- No se ejecutó una sesión de cuenta real ni se enviaron órdenes. Validación con datos simulados.
- Siguen pendientes las señales completas TP/ADD en HTML, estacionariedad, alertas push,
  reparación de patas y las demás etapas de la auditoría.

Referencia del contrato API consultado:
https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint
https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api/info-endpoint/perpetuals

## Verificación de entrega

83 pruebas Python aprobadas, dos suites JavaScript de precios en vivo aprobadas,
compilación Python y sintaxis JavaScript verificadas.

## Corrección de visualización 2.1

Funding verificado muestra el subtotal conocido, con desglose activos/cerrados y cantidad de pares pendientes. El neto completo permanece N/D cuando falta cobertura. 84 pruebas Python aprobadas.
