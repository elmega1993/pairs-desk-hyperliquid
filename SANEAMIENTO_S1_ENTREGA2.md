# Saneamiento S1 — Entrega 2

## Archivado de pares cerrados

- `frontend_archive.archive_frontend`: una lectura incompleta de fills invalida confirmaciones pendientes para esa cuenta.
- Se agregó `snapshot_token` opcional: dos observaciones de un mismo payload no pueden completar la doble confirmación, aunque transcurra el intervalo mínimo.
- `read_only_server.states()` pasa un token generado tras obtener los datos de las consultas de Hyperliquid. Cada llamada a `states()` efectúa lecturas nuevas de `clearinghouseState`.
- Se agregaron pruebas de respuesta repetida y de recuperación tras un historial incompleto.

## Límites y pendientes

- El token del servidor distingue llamadas, no valida criptográficamente el origen de cada respuesta; no reemplaza la validación de integridad de fills.
- El GET `/api/state` sigue archivando y escribiendo snapshots: deuda de arquitectura existente.
- Falta auditoría completa de rutas de ejecución, concurrencia de settings y pruebas integradas de React.
- No se modificaron rutas de trading ni datos del usuario.
