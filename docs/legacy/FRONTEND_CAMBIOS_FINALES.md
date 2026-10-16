# Pairs Desk — Refactor de interfaz

Versión construida sobre Fases 0–1, conservando backend y rutas de órdenes.

Incluye: avisos visibles y descartables; aviso persistente al armar trading; formato de moneda en-US también en PnL; cifras tabulares; sidebar de dos líneas y colores LONG/SHORT con banda de riesgo; métricas Z/neutralidad/liquidación por umbral; botones de temporalidad accesibles; avisos de mechas estimadas; ajuste del espaciado del panel Operar; cuenta como ecuación de PnL; cabeceras de historial; orden de cerrados por fecha; presentación compacta de alertas; mejor adaptación de tamaños y accesibilidad. Se mantienen mejoras previas de caché, Z diario, actualización incremental y preservación de ticket.

Seguridad: no se cambió secure_trade_routes.py, ni las llamadas POST de ejecución. No se enviaron órdenes reales. Si falta un dato verificable se muestra N/D.

Validación realizada: PYTHONPATH=. pytest -q tests/ (99 passed), node tests/test_pnl_chart.cjs, node tests/test_live_ratios.cjs, node tests/test_live_fallback.cjs, node --check main.js y pnl-chart.js.

**Pendiente de verificación manual:** funcionamiento visual con cuenta real y navegación, zoom, estado WS, 30 segundos de refresco y gráfico de cerrados en la instalación del usuario. La vista del ticket sigue integrada al panel para evitar cambiar comportamiento de órdenes sin pruebas de extremo a extremo. El autocalce del eje del gráfico y el tooltip especializado de KLineCharts no se han cambiado en esta entrega.

Preferencias del usuario: formatos en-US; KPIs solamente en Escritorio; margin_pct confirmado como porcentaje de margen usado respecto a equity Core.
