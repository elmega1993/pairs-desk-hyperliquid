## Fase 0 — Analytics v3 (2026-10-15)
- Caché compartida para niveles diarios, desacople del refresco de cartera y aclaración de Z-score deprecado.

# Pairs Desk 2.0 — Historial

## Auditoría visual y de monitoreo (2026-10-16)

- **Cola de atención:** sube al tope del escritorio y ordena por severidad. Un error o la ausencia de analítica ya **no** se muestra como "Sin pares que requieran acción": se informa "Analítica no disponible", "desactualizada" o "sin analítica" por par. `SIN_DATOS` deja de contarse como alerta. Los estados desconocidos se muestran como advertencia. Lógica pura en `src/attention.ts`.
- **Estado por par:** insignia de severidad y distancia a liquidación en *Mis posiciones*.
- **PNL total (gráfico):** color por signo con relleno, línea cero visible por defecto, huecos sin datos (la app solo registra mientras está abierta) y cortes en cada cambio de base bruta/neta, en lugar de unir puntos no comparables. Franja de estadísticas (actual, cambio, máx/mín, desde el máximo), chips de fuente y base, lectura fija bajo el gráfico (ya no tapa la curva), inspección con teclado (← → Inicio Fin Esc) y táctil. Lógica pura en `src/pnlModel.ts`.
- **Conciliación del PNL:** `PnlReconciliation` muestra realizado − comisiones + funding + flotante = neto y avisa si el neto verificado no coincide con sus componentes o con el último punto del gráfico (`src/reconcile.ts`). Se conserva `basis` y se usa `pnl_source`, que antes se descartaban.
- **Escala del PNL:** por defecto "Incluir cero" (clave nueva `pnlScaleV2`; la preferencia anterior se ignora).
- **Frescura:** indicador "Datos de hace N s" (ámbar > 60 s, rojo > 120 s o con la última lectura fallida).
- **Estado de órdenes siempre visible:** `TradeBadge` (Deshabilitadas / HABILITADAS con botón *Deshabilitar* / bloqueado / desconocido). Lee `/api/trade/status` al cargar, al volver a la pestaña y tras cambios en PairActions; no hace polling porque ese endpoint consulta el llavero.
- **KPI de margen usado** (cuenta core), con umbrales 40 % / 60 %.
- **Backend:** `states()` lee `snapshots.jsonl` una vez menos por llamada. Sin cambios en rutas de trading, ledger ni contabilidad.
- Pruebas nuevas: `tests/test_pnl_model.cjs`. Suite completa: 156 pruebas, incluidas las de navegador.
- **Huecos de registro (corrección):** los snapshots solo se guardaban mientras una pestaña consultaba `/api/state`; con la pestaña dormida o cerrada se perdían tramos. Nuevo registrador en segundo plano (`record_once`, cada 60 s, desactivable con `PAIRS_DESK_RECORDER=0`) que solo actúa si ningún navegador registró en los últimos 90 s; `states()` se serializa con un lock. El gráfico NO interpola los huecos: deja la línea cortada, marca el tramo con una franja fina al pie indica el tiempo total "Sin registro" y el umbral de hueco sube a 15 min. Los huecos ya existentes no se pueden recuperar.
- **Escala automática inteligente:** incluye el cero solo si la serie lo cruza o está cerca; si no, ajusta al rango (con base de $2.500 el cero aplastaba la variación). Clave nueva `pnlScaleV3`.
- **Fuente del gráfico de PNL (cambio de diseño):** la curva ahora usa por defecto el `portfolio` de Hyperliquid (`perpDay`/`perpWeek`/`perpMonth`/`perpAllTime`, una ventana por período, continuo y sin huecos). El registro local pasa a ser una opción ("Registro local (pares)") y el respaldo si Hyperliquid no devuelve datos (con aviso). El backend devuelve `hl_pnl` con las cuatro ventanas, reajustadas a 0 en su primer punto. Se eliminan los conectores punteados: los huecos del registro local se marcan con una franja fina al pie y el chip de tiempo sin registro. Clave nueva `pnlSourceV1`. Nota: esa curva es de toda la cuenta de perps, no solo de los pares, y no se concilia contra el neto.
- **Pendiente (no incluido):** desarme automático de órdenes por tiempo o tras ejecutar, y un flag de desarme independiente de `_LOCK` (requieren tocar `secure_trade_routes.py`); endpoint `/api/pnl-history` con downsampling; navegación móvil.


## Consolidación — Pulido visual de React

- **PNL:** el gráfico se dibuja en píxeles reales (`ResizeObserver`) en lugar de estirar un SVG de 1000×260; el texto ya no se deforma. Se corrigió además la regla heredada `.bottom svg{margin:15px 0}` que empujaba el SVG fuera de su contenedor y recortaba las etiquetas del eje X.
- **PNL:** marcas redondas en el eje Y ($0, $200, $400…, `src/ticks.ts`), línea cero rotulada y menos etiquetas en el eje X cuando el ancho es corto (formato `d/m` en móvil, sin superposiciones).
- **Exposición** deja de colorearse como ganancia o pérdida (color neutro); el verde y el rojo quedan solo para el signo del PNL.
- **Gráfico de velas:** tooltip en español, sin "Volume", con la misma tipografía de la interfaz; fuentes del eje y de las marcas de precio unificadas.
- **Radar de posiciones:** columnas numéricas alineadas a la derecha con cifras tabulares, color en Realizado, PNL % y Funding, y fila del par seleccionado resaltada (`aria-selected`).
- **"Ir a hoy"** pasa a la fila del pie del gráfico, junto al texto de ayuda.
- **Controles de orden** más legibles (10,5 px en escritorio; 12 px y 36 px de alto en pantallas táctiles).
- Nuevas pruebas: `tests/test_pnl_ticks.cjs` y `tests/test_visual_smoke.py` (navegador; se omite sin Playwright/Chromium o sin `react_dist`). Capturas de antes y después en `docs/visual/`.
- Sin cambios en backend ni en rutas de trading.

## Consolidación — Cambios rápidos de Fase 0

- `install_klinechart.py` verifica el SHA-256 fijado (coincide con `klinecharts@9.8.12` de npm). Archivo alterado: código 2 y los launchers abortan; archivo ausente: descarga solo si el hash coincide.
- `package-lock.json` generado; `npm ci` y `tsc`/`vite build` verificados con instalación limpia.
- `tests/test_react_sort_behavior.cjs` ya no usa una ruta absoluta de TypeScript.
- Nuevo `tests/test_js_suites.py` ejecuta las suites de Node desde `pytest`; nuevo `tests/test_klinecharts_integrity.py`.
- Repositorio git inicializado.
- Documentación unificada: `FASE_1_PARTE_2.md` fusionado en `docs/FASE_1_ESTADO.md`; plan, dependencias y README actualizados.
- Sin cambios en backend, rutas de trading ni código React.

## Consolidación — Base React (Fase 1)

- `main.tsx` dividido en `App.tsx`, `api.ts`, `format.ts`, `sort.ts`, `types.ts` y `components/`.
- `RatioChart.tsx`: KLineCharts como componente TypeScript, sin puente `window.AuroraTradingChart`; el zoom se conserva al refrescar.
- `PnlChart.tsx`: eje temporal, escala USD, línea cero y tooltip; datos solo de `/api/state`.
- Refresco automático cada 30 s con la pestaña visible.
- **`components/PairActions.tsx`: Agregar par y Operar par (órdenes reales) en React.** Mismo flujo que el estable (estado, CSRF, habilitar, ticket, confirmación). Sin cambios en el backend. **No validado en testnet.**

## Consolidación React — Corrección de navegación y ordenamiento

- Ordenamiento directo en **Mis posiciones** mediante botones Flotante, Realizado, PNL %, Exposición, Funding y Par; segunda pulsación invierte el sentido.
- El radar inferior comparte el mismo estado de ordenamiento.
- Eliminado `window.scrollTo` al seleccionar un par en el radar: la página conserva la posición.
- Desactivado scroll anchoring automático para evitar saltos al refrescar la lista.
- Selección por teclado en el radar, sin activar navegación inesperada.
- No se modifican rutas de trading, ledger, archivos de configuración ni algoritmos contables.
- No se agregan datos ficticios.

### Pendiente para consolidación completa

- Paridad de Cerrados, Cuenta, Eventos, Alertas y Gestión con la versión estable.
- Migración completa de KLineCharts a módulo TypeScript.
- Auditoría de snapshots, GET con efectos secundarios y reconciliación histórica del funding.
- Pruebas de navegador sobre Ubuntu.

## Analytics v3 · entrega parcial (2026-10-15)
- Núcleo estadístico puro y endpoints analíticos de solo lectura.
- Cola de atención, tabla de seguimiento y detalle analítico en React.
- Niveles descriptivos v3 y pruebas unitarias; no se activaron nuevas órdenes.
- Ver `ANALYTICS_V3.md` para tareas pendientes y limitaciones.

## Pares cerrados: gráfico y revinculación (2026-10-15)
- Gráfico KLineCharts para un par archivado, con intervalos e historial anterior.
- Acción de revinculación segura: reutiliza `/api/trade/pair-candidates` y `/api/trade/pairs/add` exclusivamente si las dos patas ya están abiertas y libres; no crea órdenes ni restaura una operación antigua.
- No se modifican rutas de ejecución, secretos ni settings desde consultas GET.
- Limitación: abrir desde cero una posición cerrada requiere un flujo de preview/confirmación específico, no implementado en esta entrega.

## Saneamiento S1 — Controles analíticos de ADD
- Validación de números finitos y fracción ADD antes de generar escenarios.
- Un ADD queda bloqueado si la distancia estimada a liquidación tras ampliar la exposición cae por debajo del umbral configurado.
- La liquidación no verificable y la correlación aún no calculada se identifican explícitamente como advertencias, no como verificaciones superadas.
- Sin cambios en rutas de órdenes, configuración, ledger ni lógica de ejecución.

## Saneamiento S1 — Entrega 2
- Archivado: reset de confirmaciones cuando el historial de fills está incompleto.
- Archivado: exigir token de snapshot distinto para confirmar un cierre en React.
- Pruebas de regresión de lecturas cacheadas y errores intermedios.

### S1 — Entrega 3: exclusión mutua del armado
- Validación `_ARMED` dentro de `_LOCK` en previsualización y ejecución para cerrar carrera con desarmado.
- Tests de regresión del guard bajo lock (`test_s1_trade_lock.py`).
