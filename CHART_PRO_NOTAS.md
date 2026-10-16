# Chart Pro — Entrega integrada (2026-10-14)

## Incluido
- Velas japonesas del ratio conservadas, con entrada/media, objetivos TP/ADD y marcadores.
- Reparación del intervalo 5m en `ratio_bars` y botón 1w.
- Endpoint histórico con `before` (timestamp ms) y `limit` (50–1200), botón de carga de velas anteriores.
- Z-score móvil de 60 cierres en panel independiente, bandas ±1/±2.
- Barra experimental de dibujos KLineCharts: tendencia, rayo, horizontal, vertical, Fibonacci, rectángulo, canal y etiqueta.
- Indicadores KLineCharts MA/EMA/BOLL/RSI/MACD con botones de activación y preferencia de selección local.
- Modo gráfico expandido y nota sobre mechas sintéticas.

## Limitaciones y pruebas pendientes
- Las herramientas de dibujo y los indicadores dependen de las firmas exactas de KLineCharts 9.8.12 y requieren validación visual en Ubuntu; no se certifica que todos funcionen.
- La persistencia de dibujos, la edición de parámetros y la paginación automática al desplazar no están implementadas. La carga histórica es manual.
- Al cambiar de intervalo/par se reconstruye el gráfico; el zoom puede restablecerse. La actualización de barras de un mismo par usa la instancia existente.
- Las mechas son cotas sintéticas y no extremos sincronizados. No utilizar indicadores de volumen ni basados en máximos/mínimos como señales precisas.
- Se ejecutaron pruebas Python. No se compiló React en este contenedor por ausencia de caché npm; `iniciar_frontend.sh` compila en Ubuntu.
- No se modificaron rutas de trading ni lógica de órdenes.
