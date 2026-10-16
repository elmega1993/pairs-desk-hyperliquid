# Roadmap de expansión — Pairs Desk 2.0

> **Documento reconstruido** a partir de las conversaciones del 13–14 de octubre de 2026. No es una copia literal del archivo original. Se recuperaron los módulos y el orden general; la numeración de las etapas posteriores a la Fase 1 es una organización propuesta para hacer el roadmap ejecutable.

## Objetivo

Convertir Pairs Desk en una plataforma integral para descubrir, investigar, simular, seguir y gestionar operaciones de pares long/short en **Hyperliquid, incluido XYZ**, sin perder la rapidez ni la seguridad del escritorio de operaciones.

## Estado actual — 2026-10-16

- React es la interfaz principal y FastAPI/Python es el backend operativo.
- El escritorio actual consulta posiciones, precios, velas, analítica básica, riesgo y cierres.
- Existe SQLite separado para ledger, diario de operaciones y configuraciones, además del catálogo de mercado de Fase 1A.
- Fase 1A ya dispone de almacén Parquet e ingesta histórica incremental compartida; Fase 1B agrega el contrato interno de ratios.
- Explorador, Laboratorio y Watchlist tienen presencia parcial o conceptual, pero aún no son módulos funcionales independientes.
- El backtesting disponible es básico y está limitado a niveles; no equivale todavía a un motor de validación walk-forward.
- React contiene rutas de operaciones reales. La ejecución debe seguir aislada del catálogo, la investigación, el simulador y el backtesting.

La siguiente entrega aprobada fue la **Fase 1A — Catálogo e históricos de mercado**. La implementación actual continúa con **Fase 1B — Contratos de ratios y calidad histórica**, especificada en `docs/superpowers/specs/2026-10-16-fase-1b-ratios-design.md`.

## Arquitectura acordada

- **Frontend:** React, con escritorio compacto y gráfico avanzado de velas.
- **Backend:** FastAPI/Python; módulos analíticos desacoplados de la ejecución.
- **SQLite:** catálogo de activos, pares, investigaciones, posiciones, watchlist y alertas.
- **Parquet:** series históricas de precios/ratios para análisis y backtesting.
- **Ingesta incremental:** actualizar solamente velas y datos nuevos; reutilizar caché y evitar consultas redundantes.
- **Seguridad:** mantener aislado el agente de ejecución y los controles existentes. Las herramientas de investigación y simulación no envían órdenes.

## Secuencia de desarrollo recuperada

### Fase 0 — Diagnóstico y auditoría

- Auditar estructura actual, endpoints, persistencia, rendimiento y consistencia de datos.
- Identificar funciones duplicadas y puntos donde una petición recalcula innecesariamente históricos.
- Fijar criterios de seguridad, integridad y pruebas antes de ampliar funcionalidades.

### Fase 1 — Base de datos, catálogo e históricos incrementales

- Catálogo de instrumentos disponibles en Hyperliquid core y XYZ.
- Identificadores consistentes para activos y pares.
- Persistencia SQLite para metadatos, configuraciones e investigaciones.
- Almacenamiento Parquet de velas históricas.
- Actualización incremental, control de huecos y calidad de datos.
- Caché compartida para escritorio, explorador, laboratorio y backtesting.

#### Fase 1A — Catálogo e históricos de mercado

Primera implementación aprobada. No agrega pantallas ni envía órdenes.

- Separar `market.sqlite3` de `ledger.sqlite3` y `orders.sqlite3`.
- Crear catálogo estable de instrumentos Core/XYZ y pares normalizados.
- Registrar checkpoints de ingesta por instrumento e intervalo.
- Guardar velas validadas en Parquet bajo `market-data/candles/`.
- Descargar solo ventanas nuevas y hacer merges idempotentes.
- Rechazar OHLC inválidos, duplicados, respuestas vacías y datos no finitos.
- Registrar huecos y distinguir datos completos de datos parciales.
- Mantener la ingesta fuera de `/api/state`, del refresco de React y de `secure_trade_routes.py`.

Fuera de esta subfase quedan los ratios históricos, el Scanner, la Watchlist, el Laboratorio visual y la automatización periódica.

#### Fase 1B — Contratos de ratios y calidad histórica

Implementación interna completada; todavía no agrega pantallas ni persistencia de ratios.

- Construir `price_ratio` y `log_ratio` a partir de las velas compartidas.
- Alinear timestamps exactamente y distinguir cobertura completa, parcial y vacía.
- Rechazar precios no positivos, no finitos, duplicados y series incompatibles.
- Exponer `build_pair_ratios(...)` para el futuro Laboratorio y Scanner.

#### Fase 1C — Ingesta operativa controlada

Implementación interna completada; la programación residente queda deliberadamente fuera del ciclo de renderizado.

- Ejecutar sincronizaciones manuales o desde un scheduler externo.
- Reutilizar checkpoints y solicitar solo ventanas nuevas o pendientes con solapamiento seguro.
- Medir duración, filas recibidas, filas nuevas, huecos, errores y cobertura.
- Procesar lotes secuencialmente y aislar el error de un instrumento.
- Reutilizar la caché compartida de Parquet después de validar la calidad de los datos.

### Fase 2 — Explorador de pares / Scanner

- Buscar y filtrar combinaciones de activos compatibles con Hyperliquid/XYZ.
- Examinar ratios y sus cambios recientes sin crear posiciones.
- Ordenar candidatos mediante métricas estadísticas y filtros configurables.
- Abrir un candidato directamente en el gráfico y enviarlo al Laboratorio o a la Watchlist.
- Evitar barridos costosos en cada refresco de la interfaz.

### Fase 3 — Laboratorio estadístico de ratios

- Investigar un par antes de operarlo.
- Analizar ratio histórico, tendencia, reversión a la media, Z-score y volatilidad.
- Examinar estacionariedad, correlación, half-life y estabilidad del régimen cuando los datos lo permitan.
- Comparar distintas ventanas temporales y registrar una tesis.
- Distinguir resultados descriptivos de señales predictivas; mostrar N/D cuando falten datos.

### Fase 4 — Watchlist independiente

- Tabla compacta de pares observados, separada de las posiciones abiertas.
- Mostrar ratio, cambio 24 h, Z-score, estado, alertas y notas.
- Guardar zona objetivo de entrada y acceder al gráfico avanzado con un clic.
- Reutilizar la fuente de precios y caché del escritorio.
- Carga diferida para no ralentizar la app; propuesta inicial de **20–30 ratios**.
- Persistencia en SQLite (o JSON durante una transición controlada).

### Fase 5 — Simulador y backtesting

- Simular entradas long/short y distintos tamaños por pata sin ejecutar órdenes.
- Estimar evolución del ratio, exposición, PnL, costes y escenarios de riesgo.
- Backtesting histórico con separación entre calibración y validación fuera de muestra.
- Comparar estrategias y registrar resultados reproducibles.

## Módulos adicionales previstos

Los siguientes componentes formaban parte del alcance conversado. Su posición exacta dentro del roadmap original no se pudo recuperar; conviene priorizarlos una vez estabilizada la base de datos y el Laboratorio.

| Módulo | Propósito |
|---|---|
| Radar de riesgo | Concentración, exposición por activo, correlaciones y alertas de cartera |
| Alertas | Avisos sobre ratios, zonas objetivo, riesgo y cambios relevantes |
| Diario de operaciones | Tesis, notas, eventos, entradas, ADD, TP y cierres |
| Monitor de tesis | Revisar si siguen vigentes las condiciones que justificaron una operación |
| Unlocks | Seguimiento de desbloqueos de tokens que afecten a pares observados |
| Heatmap | Vista compacta de movimientos relativos y oportunidades |
| Rebalanceo | Evaluar desviaciones de nominales y equilibrio entre patas |
| Investigador integrado / IA | Ayudar a estudiar candidatos y resumir evidencia, sin ejecutar operaciones automáticamente |

## Integración con el escritorio actual

- **Escritorio:** operaciones activas, PnL, gráfico de velas, control de posiciones y riesgo.
- **Cerrados:** historial, gráfico y posibilidad de estudiar una reapertura; preservar cada operación histórica.
- **Explorador:** descubrir candidatos.
- **Laboratorio:** investigar y validar una tesis.
- **Watchlist:** seguir candidatos antes de abrirlos.
- **Simulador / Backtesting:** evaluar hipótesis sin riesgo de ejecución.

## Principios de implementación

1. Entregar cada fase funcional y comprobable antes de avanzar.
2. No sacrificar la velocidad del escritorio: cálculos pesados fuera del refresco de posiciones.
3. Compartir datos históricos y métricas, en lugar de mantener cálculos paralelos contradictorios.
4. No fabricar históricos, precios, probabilidades ni resultados.
5. Mantener separación estricta entre análisis y ejecución de órdenes.
6. Probar backend, compilación React y regresiones antes de promover una entrega a la instalación operativa.
7. Separar siempre datos públicos de mercado, contabilidad de cuenta y ejecución de órdenes.

## Relación con los planes posteriores

- **PLAN_ANALITICA_PAIRS_DESK.md:** referencia histórica prevista para TP/ADD, seguimiento analítico, alertas y backtesting; debe revisarse antes de ejecutarse porque todavía no está presente en este repositorio.
- **Saneamiento S1–S4:** trabajo posterior de integridad, seguridad, rendimiento y validación.

Estos dos planes complementan el roadmap de expansión; **no lo reemplazan**.

## Estado de recuperación

**Confirmado por conversaciones previas:** módulos previstos; arquitectura SQLite + Parquet; ingesta incremental; orden general diagnóstico → base de datos → explorador → laboratorio → backtesting/IA; diseño de Watchlist compacta e independiente.

**Reconstruido para facilitar la ejecución:** numeración y agrupación exacta de las fases 2–5, dependencias detalladas y algunos criterios de aceptación. No se afirma que coincidan literalmente con el documento original.
