# Fase 1B — Contratos de ratios y calidad histórica

## Objetivo

Crear una capa analítica interna que construya ratios reproducibles a partir de las velas validadas de las dos patas de un par. El resultado será reutilizable por el futuro Scanner, Laboratorio y backtesting, sin duplicar reglas de alineación ni calidad.

## Alcance

La fase calculará ratios en memoria a partir de `pandas.DataFrame` con el esquema canónico de velas de Fase 1A. No agregará pantallas, endpoints, tareas periódicas ni persistencia de ratios en Parquet.

## Contrato propuesto

El módulo `pairs_desk.market_ratios` expondrá:

```python
build_pair_ratios(
    long_candles: pd.DataFrame,
    short_candles: pd.DataFrame,
    *,
    pair_id: str,
) -> RatioResult
```

`RatioResult` contendrá:

```text
pair_id, frame, matched_rows, missing_long, missing_short, status, error
```

El `frame` tendrá como mínimo:

```text
timestamp_ms, long_close, short_close, price_ratio, log_ratio
```

## Reglas de cálculo

- La unión será temporal exacta por `timestamp_ms`; no se interpolarán precios.
- Solo se incluirán timestamps presentes en ambas patas.
- `price_ratio = long_close / short_close`.
- `log_ratio = log(long_close) - log(short_close)`.
- Los precios deben ser finitos y estrictamente positivos.
- Las entradas deben corresponder a una única serie por instrumento e intervalo.
- Las entradas se validarán antes de calcular; una entrada inválida no produce ratios parciales silenciosos.

## Calidad y disponibilidad

- `complete`: ambas patas tienen la misma cobertura temporal y no quedan timestamps sin pareja.
- `partial`: existe intersección válida, pero una o ambas patas tienen timestamps sin correspondencia.
- `empty`: no hay timestamps compartidos.
- `error`: el contrato de entrada o los valores no son válidos.

`missing_long` y `missing_short` identificarán timestamps que existen solamente en la otra pata. Los consumidores podrán distinguir ausencia de datos de un ratio matemáticamente inválido.

## Aislamiento

- No se importará `secure_trade_routes.py`.
- No se modificará `/api/state`.
- No se ejecutará durante el refresco de React.
- No se realizarán llamadas de red ni órdenes.

## Verificación

- Ratio de precio y log-ratio correctos.
- Alineación exacta sin interpolación.
- Detección de datos parciales y ausencia total de intersección.
- Rechazo de precios cero, negativos, no finitos y entradas incompatibles.
- La suite existente y el build de React continúan pasando.

## Fuera de alcance

- Persistencia de ratios.
- Z-score, hedge ratio, estacionariedad, half-life o señales.
- Scanner, Watchlist y Laboratorio visual.
- Automatización periódica.
