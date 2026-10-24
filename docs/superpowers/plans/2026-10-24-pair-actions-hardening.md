# Plan: endurecer PairActions

## Objetivo

Cerrar los pendientes operativos de la interfaz React sin cambiar las rutas de trading reales: mostrar el tiempo restante del ticket, impedir el envío vencido, refrescar posiciones después de una ejecución y conservar mensajes útiles cuando la API responde sin JSON.

## Alcance

- Agregar funciones puras para calcular segundos restantes y estado vencido.
- Registrar cuándo se recibió el ticket y actualizar el contador cada segundo.
- Deshabilitar el botón de envío y limpiar la confirmación cuando el ticket vence.
- Refrescar el par actual mediante `onAdded(pair.id)` después de una ejecución, incluso si el resultado requiere revisión.
- Parsear respuestas JSON, texto plano y cuerpos vacíos en `request()`.
- Cubrir estos comportamientos con pruebas Node/Python deterministas y verificar el build React.

## No alcance

- No modificar `secure_trade_routes.py`.
- No ejecutar órdenes reales ni probar contra mainnet/testnet.
- No migrar KLineCharts, dividir `App.tsx` ni resolver otros pendientes de producto.

## Decisiones

- El vencimiento se calcula desde la recepción del ticket más `expires_in_s`; el servidor sigue siendo la autoridad final.
- Un error HTTP incluye el cuerpo textual cuando existe, con fallback a `HTTP <status>`.
- El refresco posterior a `/api/trade/execute` es de lectura; se ejecuta también ante resultado incierto para actualizar el estado visible sin reintentar la orden.

## Verificación

- Prueba unitaria del helper de ticket.
- Prueba fuente de `PairActions` para contrato de contador, bloqueo, refresco y parser.
- Suite `pytest tests/`.
- `npm run build`.
