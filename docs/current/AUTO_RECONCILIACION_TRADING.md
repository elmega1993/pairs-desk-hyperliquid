# Auto-reconciliación de operaciones inciertas

## Objetivo

Evitar que una ejecución interrumpida bloquee indefinidamente el trading cuando se puede demostrar que ninguna orden llegó al exchange.

## Regla automática

Al consultar `GET /api/trade/status`, el backend revisa los intentos `uncertain` y solo los marca como `reconciled` cuando se cumplen todas estas condiciones:

- La bitácora contiene únicamente el evento `intent`.
- No existe ningún evento `before_send`, `filled` o error posterior al envío.
- Las cantidades actuales de las dos patas coinciden con las cantidades originales, dentro de una tolerancia del 0,1 %.

La verificación consulta las posiciones actuales de Hyperliquid Core e HIP-3. No envía órdenes ni modifica posiciones.

## Casos que siguen bloqueados

Un intento permanece pendiente si hubo un envío, un fill parcial, un error con respuesta incierta o un cambio de tamaño en cualquiera de las patas. Esos casos requieren verificar Hyperliquid antes de reconciliar manualmente.

## Implementación

- Regla pura de bitácora: `pairs_desk/trade_journal.py`.
- Consulta de posiciones y activación desde `secure_trade_routes.py`.
- Regresiones: `tests/test_trade_journal.py`.
