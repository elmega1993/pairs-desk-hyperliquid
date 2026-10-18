# Memoria curada del repositorio

- React es la interfaz principal; las interfaces legacy siguen disponibles como fallback.
- Las rutas de trading reales están separadas en `secure_trade_routes.py`. Las tareas visuales y de saneamiento deben evitar modificar ese archivo.
- La fuente por defecto del gráfico de PNL usa datos de portfolio de Hyperliquid; el registro local de pares es una opción y puede tener huecos.
- El archivo local de KLineCharts está protegido por SHA-256 y el launcher aborta si la integridad no coincide.
- Los datos de mercado, ledger y órdenes se almacenan por separado. No mezclar sus bases ni compartirlas en reportes.
- Las decisiones históricas y limitaciones deben registrarse en `docs/history/` o `docs/current/`, no solo en una conversación.
