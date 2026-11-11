# Arquitectura

## Capas

```text
React (`react_frontend/`)
        │ HTTP local
FastAPI (`read_only_server.py`)
        │
Dominio (`pairs_desk/`) ─── Trading (`secure_trade_routes.py`)
        │
Mercado / ledger / órdenes / snapshots
```

## Interfaz

`react_frontend/` es la interfaz principal. Vite compila el código a `react_dist/`. La aplicación contiene vistas de posiciones, PNL, gráficos de ratio, radar, explorador y acciones de pares. `frontend/` y `aurora/` son superficies legacy y no deben confundirse con la fuente React principal.

## API y dominio

El acceso móvil opcional usa Tailscale Serve como proxy HTTPS privado hacia localhost. `pairs_desk/mobile_access.py` permite solo el DNS exacto de la PC indicado en `remote_access.json`; no cambia el bind ni permite órdenes desde un origen remoto. Preparación y autenticación son explícitas mediante `configurar_movil.sh`. Ver `docs/current/ACCESO_ANDROID.md`.

`read_only_server.py` sirve la API local y el frontend compilado. `pairs_desk/` contiene ingestión y calidad de mercado, análisis de pares, ratios, niveles, métricas, ledger, almacenamiento y servicios auxiliares. Las rutas de ejecución real están aisladas en `secure_trade_routes.py`.

## Datos

El lector del diario reconstruido completa automáticamente las fechas posteriores al cálculo guardado con las últimas muestras oficiales de cada día de Buenos Aires, solo si coincide el ancla contable. Reemplaza el último día parcial congelado y conserva los cierres estimados completos anteriores. La primera variación enlaza con el cierre estimado previo; las siguientes usan cierres oficiales aproximados. Sin muestra del día o del anterior, el PNL es null. Esto es una combinación de fuentes identificadas en cada fila, sin descargar precios ni modificar la base histórica.

La serie oficial de portfolio es la base del PNL neto de estrategia: no se vuelven a deducir fees/funding de ella. El desglose bruto se calcula como neto - funding firmado + fees USDC de futuros, únicamente con cobertura completa. La conciliación histórica compara esa misma base neta contra realizado/flotante reconstruidos y flujos de costo/ingreso.

`historical_account.sqlite3` conserva evidencia privada y reconstrucciones, con separación entre eventos originales, observaciones oficiales y estimaciones. Importa CSV por hash y los concilia sin añadirlos otra vez al ledger. El proceso manual `scripts/build_account_history.py` obtiene precios y calcula cierres; el servidor solo conserva observaciones oficiales y eventos ya disponibles cada ~5 min si la base existe. Las estimaciones se leen en modo SQLite read-only y se exponen en un campo separado `strategy.reconstructed_daily`; la UI las etiqueta como estimadas y permite compararlas con las muestras oficiales. La curva principal usa observaciones oficiales. Ver `docs/current/HISTORICAL_ACCOUNT.md`.

El diario de estrategia combina `perpAllTime`, `perpMonth`, `perpWeek` y `perpDay` del mismo portfolio tras alinear sus bases: cada ventana está rebasada independientemente. El offset se obtiene en timestamps compartidos y se exige consistencia a un centavo; una ventana sin alineación verificable se omite. Emite cada fecha local desde el 23/09: si falta el punto del día o del anterior, su PNL es null. Las métricas excluyen esos días; los huecos no se interpolan ni se convierten en cero. Los cierres diarios son aproximados: se usa la última muestra disponible del día, no necesariamente medianoche.

- Mercado: catálogo, checkpoints y velas históricas.
- Ledger: fills y funding de la cuenta.
- Órdenes: bitácora de intentos de trading.
- Snapshots: historial local usado para series y estados.

La separación evita usar una serie de mercado como si fuera contabilidad o convertir un registro local incompleto en una fuente histórica continua.

## Dependencias especiales

El gráfico y el diario de estrategia usan la misma serie oficial alineada de todas las ventanas. `official_strategy_history.json`, junto a los snapshots existentes, conserva esas muestras oficiales con cuenta y base contable identificadas; se actualiza como máximo cada cinco minutos durante lecturas de estado. Los puntos actuales tienen prioridad sobre los guardados. Los snapshots del cálculo local de pares no se incorporan a esta curva por tener distinta base. Sin portfolio actual verificable no se dibuja una curva con datos guardados antiguos.

KLineCharts se sirve desde `pairs_desk/vendor/klinecharts.min.js` y se verifica mediante `pairs_desk/vendor/klinecharts.sha256`. El plan vigente contempla migrarlo a una dependencia npm.

## Límites importantes

No cambiar rutas de trading, ledger ni contabilidad durante trabajos puramente visuales. Si una modificación cruza esos límites, actualizar pruebas y documentación de estado antes de continuar.

## Desglose de cards de estrategia (2026-11-10)

`strategy_snapshot.cost_details` agrupa comisiones USDC de futuros y funding firmado desde el inicio por activo; expone cobrado/pagado por separado. Sin cobertura completa, conserva null en lugar de presentar sumas parciales. Los rebates mantienen signo. `funding_projection` usa las posiciones únicas de la cuenta, incluyendo activos fuera de pares. Sus totales long/short no duplican activos compartidos; el desglose por par se omite con explicación cuando no hay atribución verificable. `as_of_ms` proviene del cache de tasas. El flotante de estrategia también se suma por posición única. El PNL neto oficial conserva su cálculo y no vuelve a descontar flujos. Los desplegables son HTML nativo; filtros del gráfico no alteran las cards desde el inicio.

## Asesor local (2026-11-10)

`pairs_desk/local_advisor.py` mantiene una copia saneada en memoria de las lecturas normales de estado y analítica. Excluye direcciones, notas libres, tokens y configuración privada; las posiciones por activo se conservan por separado de los pares que pueden compartirlas. Cada consulta fija su snapshot y su cuenta interna. Una lectura de cuenta con más de 90 s se rechaza; la analítica conserva fecha propia y vence a los 180 s.

El cliente usa exclusivamente `127.0.0.1:11434`, sin proxies de entorno ni redirecciones, y comprueba que el modelo no sea cloud antes de transmitir contexto. Modelo inicial `qwen3.5:9b`, configurable con `PAIRS_DESK_ADVISOR_MODEL`. No descarga modelos. Las herramientas permitidas son posiciones, estrategia/costos/diario/historia, cerrados, indicadores del par, velas de pares conocidos y ledger paginado. El ledger se abre con SQLite `mode=ro`, con cuenta fijada al inicio y cobertura explícita; las velas reutilizan la consulta pública validada. El modelo no puede ejecutar código, consultar rutas arbitrarias ni operar.

`pairs_desk/advisor_routes.py` valida origen, tamaño, roles e historial. Transmite eventos NDJSON con texto, progreso, fuentes y fechas. Hay una generación concurrente, tres rondas máximas, hasta cuatro herramientas por ronda, límite de contexto y generación de unos cuatro minutos (más la comprobación inicial del modelo). Una pestaña desconectada puede dejar al modelo finalizando hasta el límite; la primera versión no promete cancelación remota. No registra prompts o respuestas en disco.

`Advisor.tsx` permanece montado al cambiar de vista, conserva conversaciones en el store privado de Desk y permite conversaciones independientes (la implementación inicial solo conservaba la pestaña). Cada consulta agrega contexto fresco del servidor; no recibe un snapshot suministrado por el navegador. Esta primera versión responde a consultas, sin análisis autónomo continuo ni alertas generadas por IA.

## Desk persistente (2026-11-10)

El Asesor existente se extiende mediante `pairs_desk/ai/`: MemoryStore (SQLite privado, migración, revisiones/FTS5/embeddings opcionales), ContextBuilder, adquisición explícita y DeskService. La identidad se carga de cinco archivos versionados. Se conserva `/api/advisor` y el streaming NDJSON; se agregan gestión de conversaciones/memorias/settings/import/export/backup, con ámbito derivado en servidor y cuenta fijada. React extiende el mismo Advisor con historial paginado, revisión de memorias y modos. No se alteran rutas de trading ni se agrega polling a Hyperliquid. Detalles de seguridad, recuperación, herramientas, borrado y limitaciones: `docs/current/DESK_MEMORIA.md`.

`ai/pair_analysis.py` calcula evidencia de un par abierto sin I/O: nominal neto, escenarios de PNL a cantidades constantes, carry y analítica cacheada con vigencia separada. La herramienta pair_review resuelve aliases inequívocos y preserva orientación. Esta capa verifica cálculo/evidencia, no la validez del texto generado por Qwen; ver límites de criterio en DESK_MEMORIA.md.

## TWAP nativo (2026-11-10)

El ticket existente delega twapOrder/twapCancel al SDK y registra dos patas independientes en orders.sqlite3. NativeTwapStore reserva activos atómicamente junto al journal inmediato; NativeTwapMonitor observa WebSocket por cuenta/dex sin claves ni reenvíos. El estado adjunta grupos temporales al gráfico y solo suprime marcas de fills con identidad exacta; contabilidad intacta. Diseño, recuperación y límites: `docs/current/NATIVE_TWAP.md` (desde raíz).

TWAP: el mínimo de USD 100 se valida por pata en preview y de nuevo tras redondeo/preflight actual, antes de todo POST. El diagnóstico del exchange usa códigos cerrados, sin respuestas crudas; errores desconocidos permanecen genéricos. Intentos rechazados sin IDs/fills no dibujan una operación.

TWAP: tamaños pasan por float_to_wire oficial antes de construir/firma de acción. No usar str(float) ni formato Decimal de float sin normalizar: los ceros finales cambian el hash msgpack. Acción firmada y enviada mantienen exactamente el wire a,b,s,r,m,t del protocolo.

TWAP admite hasta 10080 minutos (7 días) desde 2026-11-11, reemplazando el límite local anterior de 1440. Validación consistente en Pydantic, motor y React; el contrato persiste minutos enteros.

TWAP legs incorporan error_detail nullable mediante migración aditiva. Solo conserva string de error saneado (320 caracteres, sin credenciales/direcciones/HTML), separado del código categórico; React lo muestra como texto. No se persisten respuestas completas ni se reconstruyen motivos descartados.

Media del gráfico: entry_ratio conserva el cociente de entryPx de posiciones actuales. Solo entry_history mezcla fills generales y vista mínima de fills nativos persistidos (cuenta/activos, deduplicación coin/tid/side). El inicio requiere startPosition conocido; fills nativos sin él no implican apertura. Reconcilia cantidad/promedio con posiciones actuales antes de publicar curva. No modifica contabilidad ni agrega consultas Hyperliquid.

## Proveedor Codex y cierre vigente (2026-11-11)

DeskService conserva el mismo panel/API del asesor y permite proveedor `codex` (predeterminado) u `ollama`. `ai/codex_provider.py` adapta Codex App Server a streaming/eventos y contexto acotado; usa la sesión de ChatGPT configurada localmente. La UI exige consentimiento `allow_codex_context` antes de transmitir contexto seleccionado. Modelo comprobado `gpt-5.6-sol`; acceso a otros modelos depende de la cuenta. No se usan credenciales de trading en el contexto ni se entrega shell/órdenes al modelo. Las secciones de Qwen anteriores describen el proveedor alternativo y la evolución del sistema. Configuración/consentimiento y límites: docs/current/DESK_MEMORIA.md. Estado consolidado: CURRENT_STATE.md.
