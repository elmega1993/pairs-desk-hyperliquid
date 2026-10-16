# Pairs Desk — Terminal HTML independiente

## Inicio
1. Descomprimí el ZIP en una carpeta nueva (no borres la anterior).
2. Doble clic en `iniciar_frontend.sh` y elegí **Ejecutar** (o terminal si Ubuntu lo requiere).
3. Abrí http://127.0.0.1:8510 en tu navegador.

El script instala dependencias en `.venv_frontend` la primera vez. Lee los pares y la dirección pública desde `~/.config/crypto-pairs-desk/settings.json` y conserva la bitácora SQLite en `~/.local/share/crypto-pairs-desk/orders.sqlite3`. **No copia la clave privada en el navegador ni en archivos JSON.** La clave Agent se consulta únicamente del llavero de Ubuntu.

## Funciones
- Vista compacta con lista lateral de pares, gráfico central del ratio y panel de operar/gestión/notas/eventos.
- Precio del ratio (long / short), variación, PnL abierto, funding acumulado, neutralidad, tamaño, distancia de liquidación por pata.
- Fills y PnL realizado/comisiones recuperados desde Hyperliquid. Si la paginación o el ciclo de una pata no son verificables, la cifra aparece N/D.
- Z-score del log-ratio de los **últimos 20 cierres de la temporalidad seleccionada**; no necesariamente coincide con el filtro de gestión diario de la versión anterior.
- Línea de entrada, niveles TP/ADD y marcadores de apertura, ADD y CIERRE sobre KLineChart (si se instala su JS local), pestañas Cuenta y Cerrados y notas existentes.
- Acciones reales **Aumentar, Reducir, Cerrar** con Agent, previsualización del ticket y confirmación explícita. Rebalanceo no incluido.

## Seguridad de órdenes
- **Las órdenes reales arrancan DESHABILITADAS en cada inicio del servidor.** En la pestaña Operar se debe habilitar mainnet, aceptar la advertencia y generar una vista previa.
- Antes de habilitar se verifica el Agent con `userRole.data.user` para la cuenta principal. Si no hay Agent en el llavero, la operativa queda bloqueada: guardalo primero desde la versión Streamlit anterior.
- El servidor corre solo en 127.0.0.1:8510 y los POST exigen token antifalsificación y un Origin local, además de confirmación de cada ticket; ticket de un uso y 40 segundos.
- El envío usa el motor previo: manda primero una pata `xyz` si existe, ajusta proporcionalmente la segunda al fill confirmado de la primera, y registra intentos/OID en SQLite.
- **Las patas NO son atómicas.** Si alguna falla o queda incierta se bloquean nuevas órdenes hasta que verifiques Hyperliquid y concilies manualmente desde la aplicación estable. No hay reversión automática.
- **No hubo pruebas de ejecución REAL desde este entorno.** Se corrieron pruebas automatizadas simuladas, no sustituyen testnet ni una primera operación real con el mínimo monto permitido.

## Dependencia de KLineChart
KLineChart 9.8.12 no pudo descargarse dentro del entorno de compilación. Al ejecutar `iniciar_frontend.sh`, el instalador intenta obtenerlo y guardarlo de forma local en `pairs_desk/vendor/klinecharts.min.js` (sin usar CDN en el navegador). Si no puede descargarlo, se mostrará el gráfico SVG de respaldo, que también utiliza velas de datos reales.

## Limitaciones contables
- Hyperliquid limita su historial de fills; operaciones más antiguas que los últimos 10.000 fills pueden no estar disponibles. Los datos no verificables no se presentan como definitivos.
- Los extremos de las velas del ratio se construyen a partir de extremos por pata, sin garantizar simultaneidad intravela.
- La distancia a liquidación por pata no equivale al riesgo de margen cruzado total de la cuenta.
- El PnL acumulado mostrado corresponde a los pares rastreados y solo se calcula si la atribución de los fills disponibles es verificable.
- Las reglas y notas son de lectura: todavía se editan desde `iniciar.sh`.

**Importante:** mantené una copia de la instalación anterior hasta comprobar el nuevo frontend. No pegues la clave privada de tu wallet principal en ninguna interfaz.
