# Saneamiento S1 — Primera entrega

## Implementado
- Validación robusta de entradas numéricas en `pairs_desk/levels_v3.py`.
- Bloqueo de ADD cuando la estimación de distancia a liquidación después de ampliar la exposición queda por debajo de `LIQ_AFTER_ADD_MIN` (25%).
- Advertencias explícitas cuando no hay distancia de liquidación verificable o correlación de patas; **no se interpretan como controles superados**.
- Cuatro pruebas de regresión en `tests/test_sanitation_s1.py`.

## Validación
- `PYTHONPATH=. pytest -q tests/`: 141 passed, 10 skipped.
- Compilación React no ejecutada en esta entrega (no hay cambios frontend).

## Pendiente para completar S1
- Auditar rutas de ejecución y tickets, integridad de settings, estados inciertos y archivado de posiciones.
- Evaluar snapshots GET y reconciliación de cierres.
- Probar integración en entorno local antes de usar en operaciones reales.

## Advertencia
Los niveles v3 son descriptivos y aún no están calibrados. El cálculo de liquidación posterior a ADD es una aproximación; una advertencia de 'no verificado' no equivale a seguridad.

## Entrega 3 — Exclusión mutua de armado y ejecución

- `preview()` y `execute()` comprueban `_ARMED` **dentro** de `_LOCK`.
  Antes lo comprobaban fuera, dejando una ventana de carrera frente a `/arm`.
- Se mantiene el consumo único del ticket, el journal previo al envío y el bloqueo
  por intentos pendientes. No se cambió la semántica de órdenes ni el SDK.
- Se añadieron pruebas estructurales para evitar regresiones en la posición del guard.
- Pendiente: pruebas concurrentes de extremo a extremo y compilación del frontend.
