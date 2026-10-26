# Tareas pendientes

Estas tareas se mantienen alineadas con `docs/current/PLAN_CONSOLIDACION.md`. Marcar una tarea como hecha solo después de implementar y verificarla.

## Prioridad alta — seguridad y operación

- [ ] Validar en testnet el flujo React de `PairActions` antes de considerarlo operativo.
- [x] Completar cuenta regresiva, bloqueo al vencer y refresco de posiciones tras una orden. Verificado con pruebas locales; falta validación operativa en testnet.
- [x] Manejar respuestas no JSON en `request()`.

## Prioridad media — React

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

- [ ] Completar paridad de Cerrados, Cuenta, Eventos, Alertas y Gestión.
- [ ] Retirar interfaces antiguas solo después de verificar paridad.

## Regla de actualización

Si una tarea cambia rutas de trading, contabilidad o persistencia, actualizar primero `CURRENT_STATE.md`, `docs/ARCHITECTURE.md` y las pruebas relevantes.
