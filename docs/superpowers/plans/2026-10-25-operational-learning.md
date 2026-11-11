# Operational Learning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Construir un análisis retrospectivo reproducible que compare entradas, gestión/cierres y selección de pares usando los datos locales disponibles, sin tocar la ejecución de órdenes.

**Architecture:** Un módulo puro normalizará observaciones y calculará métricas; un cargador separado leerá settings y SQLite en modo solo lectura; un script local generará CSV y un resumen JSON/Markdown. La primera entrega quedará fuera de la UI para validar qué señales merecen integración posterior.

**Tech Stack:** Python 3.12, dataclasses/typing, sqlite3 en modo `ro`, pandas 2.3, pytest 8.4. No agregar dependencias.

**Spec:** `docs/superpowers/specs/2026-10-25-operational-learning-design.md`

## Global Constraints

- No modificar `secure_trade_routes.py` ni ejecutar órdenes.
- No exponer address, fills crudos, bases SQLite ni configuraciones personales en salidas compartidas.
- Clasificar cada observación como `verificada`, `parcial` o `no comparable`.
- No inferir MAE/MFE o efectos de ADD/TP cuando no existan velas/eventos suficientes.
- No proponer reglas con menos de 10 casos comparables; mostrar tamaño de muestra y casos contrarios.
- Mantener los cálculos puros y testeables, separados del acceso a datos.

## Review Focus

- Historial truncado o funding incompleto: la operación debe quedar `parcial`, nunca presentarse como resultado neto verificado. Test en Task 2.
- `settings.json` corrupto o con filas inválidas: el análisis debe fallar de forma explicable sin escribir ni reparar el archivo. Test en Task 1.
- SQLite ausente, bloqueada o sin una tabla: reportar fuente no disponible y continuar con las demás fuentes. Test en Task 1.
- Operaciones con patas desbalanceadas o timestamps inconsistentes: excluirlas de comparaciones que requieran neutralidad/duración y conservar el motivo. Test en Task 2.
- Muestra pequeña: resumen y reglas candidatas deben marcar `insufficient_sample`, no producir win-rate concluyente. Test en Task 3.

### Task 1: Lectura segura y snapshot analítico

**Files:**
- Create: `pairs_desk/learning_data.py`
- Test: `tests/test_learning_data.py`

**Interfaces:**
- Consumes: paths explícitos a settings, ledger, orders y market.
- Produces: `load_learning_snapshot(paths: DataPaths) -> LearningSnapshot` y lectores SQLite read-only que devuelven filas JSON normalizadas y advertencias.

- [ ] **Step 1: Write the failing tests**

  Cubrir `settings.json` válido, JSON inválido sin escritura, SQLite ausente y lectura de tablas con conteo estable.

- [ ] **Step 2: Run tests to verify they fail**

  Run: `pytest tests/test_learning_data.py -v`
  Expected: FAIL because the loader and result types do not exist.

- [ ] **Step 3: Implement the read-only loader**

  Definir `DataPaths`, `LearningSnapshot`, `SourceStatus` y `load_learning_snapshot`. Reutilizar `storage.load_settings`; abrir SQLite con URI `mode=ro`; nunca instanciar componentes que creen tablas ni llamar a endpoints externos. Separar `closed_pairs`, fills, funding, order attempts/events y metadatos de mercado; conservar errores por fuente.

- [ ] **Step 4: Run tests to verify they pass**

  Run: `pytest tests/test_learning_data.py -v`
  Expected: PASS.

- [ ] **Step 5: Commit**

  `git add pairs_desk/learning_data.py tests/test_learning_data.py && git commit -m "feat: add read-only learning data loader"`

### Task 2: Construcción y clasificación de observaciones

**Files:**
- Create: `pairs_desk/operation_learning.py`
- Test: `tests/test_operation_learning.py`

**Interfaces:**
- Consumes: `LearningSnapshot` de Task 1.
- Produces: `build_operation_rows(snapshot: LearningSnapshot) -> list[dict]`, con campos estables para operación, par, timestamps, ratio, PNL, funding, fees, eventos y `data_quality`/`quality_reasons`.

- [ ] **Step 1: Write the failing tests**

  Cubrir cierre verificado con PNL neto, cierre con fills incompletos, timestamps inválidos, funding ausente, duración y clasificación de fila.

- [ ] **Step 2: Run tests to verify they fail**

  Run: `pytest tests/test_operation_learning.py -v`
  Expected: FAIL because row construction is not implemented.

- [ ] **Step 3: Implement pure row construction**

  Usar `closed_pairs` como unidad principal; reconciliar fills, funding y eventos solo cuando las claves/ventanas temporales coincidan. Calcular duración en días, PNL neto cuando sea verificable, resultado ganador/perdedor solo para filas verificadas y dejar `None` en métricas no sustentadas. No estimar MAE/MFE ni efecto de gestión sin datos suficientes.

- [ ] **Step 4: Run tests to verify they pass**

  Run: `pytest tests/test_operation_learning.py -v`
  Expected: PASS.

- [ ] **Step 5: Commit**

  `git add pairs_desk/operation_learning.py tests/test_operation_learning.py && git commit -m "feat: classify operation learning rows"`

### Task 3: Métricas comparativas y reglas candidatas

**Files:**
- Create: `pairs_desk/learning_metrics.py`
- Test: `tests/test_learning_metrics.py`

**Interfaces:**
- Consumes: filas de Task 2.
- Produces: `summarize_learning(rows: list[dict], min_sample: int = 10) -> dict`, incluyendo bloques `entry`, `management`, `pair_context` y `candidate_rules`.

- [ ] **Step 1: Write the failing tests**

  Probar agregación por par, duración y resultado; exclusión de filas no comparables; `min_sample=10`; y regla candidata con condición, casos, tasa de éxito, PNL mediano/agregado y casos contrarios.

- [ ] **Step 2: Run tests to verify they fail**

  Run: `pytest tests/test_learning_metrics.py -v`
  Expected: FAIL because summary functions do not exist.

- [ ] **Step 3: Implement deterministic summaries**

  Comparar ganadoras/perdedoras por par, duración, ratio y variables disponibles. No crear umbrales por optimización automática en esta fase; las reglas serán descripciones de cortes observados y quedarán `insufficient_sample` si tienen menos de 10 casos.

- [ ] **Step 4: Run tests to verify they pass**

  Run: `pytest tests/test_learning_metrics.py -v`
  Expected: PASS.

- [ ] **Step 5: Commit**

  `git add pairs_desk/learning_metrics.py tests/test_learning_metrics.py && git commit -m "feat: summarize operational patterns"`

### Task 4: Informe local reproducible

**Files:**
- Create: `scripts/analyze_operations.py`
- Modify: `.gitignore` only if required for report output paths
- Test: `tests/test_analyze_operations.py`

**Interfaces:**
- Consumes: paths por defecto en `~/.config/crypto-pairs-desk` y `~/.local/share/crypto-pairs-desk`, sobrescribibles por CLI.
- Produces: CSV de filas analíticas y JSON/Markdown de resumen en un directorio de salida local indicado por `--output`; stdout solo muestra conteos y advertencias sin address ni fills crudos.

- [ ] **Step 1: Write the failing tests**

  Probar que el CLI acepta paths temporales, produce los tres archivos esperados y no incluye el campo `address` ni payloads crudos.

- [ ] **Step 2: Run tests to verify they fail**

  Run: `pytest tests/test_analyze_operations.py -v`
  Expected: FAIL because the CLI does not exist.

- [ ] **Step 3: Implement the CLI/report writer**

  Añadir `--settings`, `--ledger`, `--orders`, `--market`, `--output` y `--min-sample`. Serializar números JSON de forma estable, ordenar por `closed_at`, generar `operations.csv`, `summary.json` y `summary.md`; crear el directorio de salida con permisos de usuario y no modificar ninguna fuente.

- [ ] **Step 4: Run focused and full tests**

  Run: `pytest tests/test_analyze_operations.py tests/test_learning_data.py tests/test_operation_learning.py tests/test_learning_metrics.py -v`
  Expected: PASS.

- [ ] **Step 5: Run the report against local data**

  Run: `python scripts/analyze_operations.py --output /home/alan/.local/share/crypto-pairs-desk/analysis`
  Expected: report generated, with warnings for incomplete sources and no writes to settings or SQLite.

- [ ] **Step 6: Commit**

  `git add scripts/analyze_operations.py tests/test_analyze_operations.py .gitignore && git commit -m "feat: add reproducible operational analysis report"`

### Task 5: Verificación final y handoff

**Files:**
- Modify: `docs/current/FASE_1_ESTADO.md` or `docs/history/CHANGELOG.md` only if the repository convention requires recording the new analysis tool.

- [ ] **Step 1: Run the complete relevant suite**

  Run: `pytest tests/`
  Expected: existing tests and new learning tests pass; document any optional dependency omissions.

- [ ] **Step 2: Inspect the generated summary**

  Confirmar que el resumen distingue verificado/parcial/no comparable, que no recomienda reglas con muestra insuficiente y que las conclusiones incluyen limitaciones.

- [ ] **Step 3: Record the result**

  Actualizar documentación solo con conteos agregados, advertencias y cómo regenerar el informe; no guardar address, fills ni bases en el repositorio.

- [ ] **Step 4: Commit**

  `git add docs/current/FASE_1_ESTADO.md docs/history/CHANGELOG.md && git commit -m "docs: record operational learning analysis"`
