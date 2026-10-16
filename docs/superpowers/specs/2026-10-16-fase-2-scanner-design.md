# Fase 2 — Explorador de pares / Scanner

## Objetivo

Agregar un explorador de solo lectura que use el catálogo y los datos Parquet de mercado para mostrar candidatos de pares sin crear posiciones ni ejecutar órdenes.

## Backend

El módulo `pairs_desk.market_scanner` expondrá un servicio inyectable que:

- lee pares activos del catálogo;
- obtiene las dos series del intervalo solicitado desde `MarketDataStore`;
- calcula ratios mediante `build_pair_ratios`;
- devuelve ratio actual, variación aproximada de 24 horas, cobertura, estado y filas coincidentes;
- filtra por búsqueda, mercado y límite sin barrer datos fuera del límite.

El endpoint de solo lectura será:

```text
GET /api/scanner?interval=1h&search=&venue=&limit=50
```

No se conectará a Hyperliquid en la petición: si no hay Parquet, el candidato mostrará `no_data` y una explicación.

## Frontend

La vista React `Explorador` reemplazará el placeholder actual y mostrará:

- filtros de búsqueda, intervalo y mercado;
- tabla ordenable visualmente por ratio, variación y cobertura;
- estado de datos y cantidad de observaciones;
- panel de detalle del candidato seleccionado;
- aviso explícito de que el módulo es analítico y no envía órdenes.

El escritorio operativo seguirá sin cambios. La vista no agregará botones de trading ni llamará rutas protegidas.

## No incluido

- Z-score, estacionariedad, half-life o señales.
- Persistencia de watchlist.
- Ejecución de órdenes.
- Descarga de datos dentro de `/api/scanner`.
- Rediseño del escritorio.
