# Fase 3B — Salud estadística y alertas de escritorio

## Instalación y uso
Cerrá la versión anterior, extraé el ZIP y ejecutá iniciar_frontend.sh.
El iniciador instala statsmodels. Recargá el navegador con Ctrl+Shift+R.
Se conservan settings y el ledger en sus ubicaciones habituales.

- En Escritorio → Gestión aparece Salud estadística del par.
- En Alertas, pulsá Probar aviso para verificar las notificaciones de Ubuntu.
- Pulsá Activar alertas para iniciar el vigilante. Inicialmente está desactivado.
- La selección se conserva al reiniciar. Desactivar alertas detiene los avisos nuevos.

## Salud estadística
ADF sobre los últimos 250 cierres diarios disponibles del log-ratio, con un mínimo
de 60 observaciones. Excluye la vela diaria abierta y rechaza datos vencidos o con
huecos de más de cuatro días. Usa constante y selección de rezagos AIC.

Si p ≥ 0,05 muestra Reversión no confirmada: no equivale a demostrar que nunca revierte.
Si p < 0,05 muestra evidencia de estacionariedad, sin garantizar reversión futura.
El half-life AR(1) solo se informa con phi entre 0 y 1, límite superior aproximado
al 95% por debajo de 1 y duración menor que media ventana de observación.
Los días son aproximados; en series con fines de semana se considera el espaciado medio.
El cálculo antiguo de half-life también exige ahora evidencia de estacionariedad.

No se cambia el Z utilizado por TP/ADD ni se condicionan automáticamente las órdenes.
No se implementó Engle-Granger: este diagnóstico prueba el log-ratio de pesos fijos.
Referencia: https://www.statsmodels.org/stable/generated/statsmodels.tsa.stattools.adfuller.html

## Alertas
Vigilante de solo lectura en el servidor local. Consulta cada 60 segundos después
de terminar el barrido anterior; las velas diarias se cachean cinco minutos.
Funciona con la pestaña cerrada mientras el servidor y la computadora sigan encendidos.
No es un servicio del sistema ni una notificación a teléfono/Telegram.
Ejecutá una sola instancia del servidor para evitar duplicar vigilantes.

Condiciones:
- Distancia estimada a liquidación ≤ 10%; se restablece a ≥ 12%.
- Desbalance absoluto (L−S)/(L+S) ≥ 5%; se restablece a ≤ 4%.
- |Z| ≥ 2; se restablece a ≤ 1,7.
- Señal TP/ADD pendiente, patas ausentes o dirección inesperada.
- Dos lecturas fallidas consecutivas; señales sin datos se informan por separado.

Máximo un aviso por cuenta/condición cada 15 minutos, con estados persistentes.
Una condición activa puede generar un recordatorio tras esos 15 minutos.
La primera observación puede avisar sobre una condición ya existente.
Los avisos no envían órdenes, no cierran posiciones y no marcan escalones ejecutados.

Los avisos usan notify-send. Si falta libnotify-bin o no hay sesión de escritorio,
se conservan en la pestaña Alertas. Un retorno exitoso de notify-send indica envío
al sistema de notificaciones, no garantiza que el usuario lo haya visto.
El historial/configuración se guarda en ~/.local/share/crypto-pairs-desk/alerts.json
(últimos 200 avisos, 40 visibles). No guarda claves ni credenciales.
Activación y prueba están protegidas por origen local y CSRF.

## Validación y pendientes
97 pruebas Python y tres suites JavaScript aprobadas. Compilación Python y sintaxis
JavaScript verificadas. Notificaciones probadas con un emisor simulado; no se validó
la entrega en una sesión real de Ubuntu ni una cuenta real de Hyperliquid.
La revisión visual en navegador sigue pendiente por indisponibilidad de Chromium.
Conserva el gráfico PnL interactivo y el funding visible de entregas anteriores.
Siguen pendientes vela en vivo, mejoras de ejecución y las siguientes etapas analíticas.
