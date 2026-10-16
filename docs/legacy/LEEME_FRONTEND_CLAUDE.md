# Pairs Desk — Terminal HTML (fase de integración)

## Inicio
Descomprimir en carpeta nueva y ejecutar `iniciar_frontend.sh` con doble clic (modo ejecutar). Abrir http://127.0.0.1:8510.

Se conserva **KLineChart** cuando el archivo local está instalado; el instalador al inicio intenta obtenerlo si falta. No se carga JavaScript desde CDN dentro del navegador. El gráfico SVG disponible como respaldo muestra velas del ratio derivadas de velas reales.

## Funciones de esta versión
- Layout HTML/CSS independiente de Streamlit, lista lateral de pares y gráfico de ratio.
- PNL abierto, nocional, neutralidad, funding acumulado y distancia de liquidación por pata cuando la API dispone de datos.
- Consulta de fills con paginación y contraste; PNL realizado, comisiones y PNL acumulado **solo cuando el historial de fills del ciclo está verificado**.
- Indicador Z-score aproximado de **log-ratio de los últimos 20 cierres** de la temporalidad visualizada; no equivale necesariamente al indicador diario de reglas del programa anterior.
- Eventos ADD/CIERRE reconstruidos desde fills cuando están disponibles, notas y umbrales TP/ADD de configuración, historial de cierres archivados y resumen de cuenta.

## Limitaciones relevantes
- **El frontend incluye operaciones reales (Aumentar/Reducir/Cerrar), pero arranca DESHABILITADO.** Para usarlo, el Agent debe estar guardado previamente en el llavero de Ubuntu desde la aplicación estable. En el panel Operar debés habilitar mainnet, aceptar la advertencia, previsualizar y confirmar el ticket. El servidor valida que el Agent pertenezca a la cuenta pública; nunca envía la clave privada al navegador.
- SQLite registra cada intento antes del envío. Un parcial o resultado incierto bloquea nuevas órdenes hasta una reconciliación manual en la aplicación estable.
- La ejecución de ambas patas NO es atómica. No hay garantía de ejecución simétrica ni botón automático de deshacer.
- **El envío de órdenes REALES no se pudo probar desde este entorno.** Recomendamos empezar con testnet o una reducción mínima y verificar las dos patas antes de confiarle tamaños importantes.
- En cuentas con más de 10.000 fills o con límites de la API, el PNL realizado aparece N/D en lugar de atribuir un historial incompleto.
- La distancia a liquidación por pata no sustituye un cálculo de riesgo de margen cruzado de cuenta. No sumamos equity de CORE y XYZ sin reconciliar su modelo.
- Los máximos/mínimos de las velas de ratio son combinaciones de extremos de cada pata, no movimientos simultáneos garantizados.
- La pantalla y las pruebas de Python/JS se verifican localmente, pero no se valida la conexión en vivo con tu cuenta ni el comportamiento en tu navegador.

Para mantener la cuenta segura, no pegues ni transmitas la clave privada del Agent en este frontend.
