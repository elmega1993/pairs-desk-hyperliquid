# Adaptive Levels v1 — experimental

- Se sustituye la señal TP/ADD fija en el escritorio Streamlit por percentiles empíricos de cambios logarítmicos del ratio a 14 días, calculados por par con velas diarias.
- TP1/TP2: percentiles 75/90; ADD1/ADD2: percentiles 25/10. Los percentiles describen movimientos pasados, no probabilidad de alcanzar el objetivo.
- Diagnóstico heurístico de régimen: rango/tendencia/inestable. Si hay pocos datos, volatilidad nula o distribución no apta, se muestra N/D sin fallback a porcentajes fijos.
- Se muestran niveles en el panel de gestión y en el gráfico KLine. No se ejecutan órdenes automáticamente.
- Las reglas manuales se preservan en settings para compatibilidad pero no controlan las señales automáticas.

## Limitaciones conocidas
- Modelo preliminar sin backtesting walk-forward, sin calibración de probabilidades ni cointegración; NO asumir que un ADD es una oportunidad segura.
- La vista React/Aurora y cualquier otro consumidor independiente de niveles no se han migrado a este motor.
- TP3 antiguo no se calcula automáticamente; no se modifica el estado histórico de escalones ya ejecutados.
- No se calcula todavía PnL USD esperado por nivel. El horizonte de 14 días es un supuesto inicial que debe validarse por activo.
