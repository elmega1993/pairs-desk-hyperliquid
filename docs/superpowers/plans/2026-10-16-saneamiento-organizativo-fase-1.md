# Saneamiento organizativo Fase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ordenar la documentación y aclarar la arquitectura pública del repositorio, dejando React como interfaz principal sin alterar runtime ni rutas de trading.

**Architecture:** Se conserva la estructura ejecutable actual: `pairs_desk/`, `react_frontend/`, `frontend/`, `aurora/` y los entrypoints de raíz. Solo se agrupa documentación en `docs/current/` y `docs/history/`, se actualizan referencias y se documenta la jerarquía de interfaces.

**Tech Stack:** Markdown, Git, Python/Node existentes para verificaciones; sin nuevas dependencias.

**Spec:** `docs/superpowers/specs/2026-10-16-saneamiento-organizativo-fase-1-design.md`

## Global Constraints

- No eliminar archivos ni alterar comportamiento funcional.
- No modificar `secure_trade_routes.py`.
- No modificar contratos HTTP, puertos ni imports de runtime.
- No tocar `.env`, configuraciones locales, bases de datos ni artefactos ignorados.
- React es la interfaz principal; `frontend/`, `aurora/` y `app.py` quedan como legacy/fallback.
- Después de cada movimiento, buscar referencias rotas con `rg`.

## Review Focus

- Enlaces Markdown que apunten a documentos movidos: deben resolver a la nueva ruta.
- Scripts y launchers que mencionen rutas de documentación: deben conservar su comportamiento.
- Documentos de entregas con referencias cruzadas: deben seguir siendo legibles desde `docs/history/`.
- Archivos ignorados (`react_dist/`, `node_modules/`, entornos virtuales y caches): no deben entrar en el commit.
- Código de trading y endpoints: no deben aparecer en el diff salvo documentación que los describa.

### Task 1: Clasificar la documentación

**Files:**
- Move: documentos Markdown seleccionados de la raíz a `docs/current/` o `docs/history/`
- Preserve: `docs/visual/`
- Modify: referencias Markdown afectadas por los movimientos

**Interfaces:**
- Consumes: inventario actual de Markdown y referencias encontrado con `rg`.
- Produces: clasificación estable de cada documento versionado, sin cambios de contenido funcional.

- [ ] **Step 1: Crear el inventario de documentos versionados**

  Ejecutar `git ls-files '*.md'` y clasificar cada archivo por función: documentación vigente, historial/entrega, especificación de trabajo o material visual.

- [ ] **Step 2: Crear las carpetas documentales aprobadas**

  Crear `docs/current/` y `docs/history/`. No crear carpetas adicionales para esta fase.

- [ ] **Step 3: Mover únicamente los documentos clasificados**

  Usar `git mv` para conservar el historial. Mantener los nombres de archivo salvo que exista una colisión real.

- [ ] **Step 4: Buscar referencias a las rutas antiguas**

  Ejecutar `rg -n 'README\.md|CHANGELOG\.md|SANEAMIENTO_|ADAPTIVE_|ANALYTICS_|CHART_PRO_|REACT_ADAPTIVE_|docs/' --glob '*.md' --glob '*.sh' --glob '*.py' .` y registrar cada enlace que necesite actualización.

- [ ] **Step 5: Commit de clasificación documental**

  ```bash
  git add docs README.md
  git commit -m "docs: organize project documentation"
  ```

### Task 2: Actualizar README y mapa de interfaces

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: nueva clasificación documental de Task 1.
- Produces: instrucciones de entrada reproducibles y mapa público de interfaces.

- [ ] **Step 1: Definir la documentación mínima del README**

  Mantener las instrucciones actuales de Ubuntu, pruebas y precauciones. Añadir secciones breves de arquitectura, interfaz principal, interfaces legacy y estructura del repositorio.

- [ ] **Step 2: Documentar el orden de uso de interfaces**

  Indicar `iniciar_frontend.sh` como launcher recomendado para React/API. Describir `frontend/` como estable legacy, `aurora/` como interfaz anterior y `app.py` como Streamlit legacy.

- [ ] **Step 3: Actualizar enlaces a documentación**

  Cambiar exclusivamente rutas afectadas por Task 1; no alterar comandos, puertos, endpoints ni nombres de runtime.

- [ ] **Step 4: Verificar el README**

  Ejecutar `rg -n 'React|legacy|iniciar_frontend|secure_trade_routes|docs/' README.md` y comprobar que la descripción coincide con la estructura real.

- [ ] **Step 5: Commit del README**

  ```bash
  git add README.md
  git commit -m "docs: define React as primary interface"
  ```

### Task 3: Verificar referencias y exclusiones

**Files:**
- Test/inspect: todos los archivos versionados y referencias documentales
- Do not modify: `pairs_desk/`, `read_only_server.py`, `secure_trade_routes.py`, launchers y frontends

**Interfaces:**
- Consumes: estructura y README de Tasks 1–2.
- Produces: evidencia de que el saneamiento no rompe rutas ni incluye artefactos locales.

- [ ] **Step 1: Buscar referencias documentales rotas**

  Ejecutar `rg -n 'docs/(?!superpowers)' --pcre2 .` y revisar manualmente cada resultado relacionado con archivos movidos.

- [ ] **Step 2: Verificar que no se movió código ejecutable**

  Ejecutar `git diff HEAD~2 --name-status` y confirmar que solo contiene documentación y README.

- [ ] **Step 3: Verificar exclusiones**

  Ejecutar `git status --short --ignored` y confirmar que `node_modules/`, entornos virtuales, caches y `react_dist/` siguen ignorados y no staged.

- [ ] **Step 4: Ejecutar verificaciones disponibles**

  Ejecutar `pytest -q` si existe pytest en el entorno. Si no está disponible, ejecutar al menos `npm run build` desde `react_frontend/` si existen Node/npm y documentar la limitación sin instalar dependencias automáticamente.

### Task 4: Revisión final y entrega

**Files:**
- Inspect: `git diff`, `README.md`, `docs/current/`, `docs/history/`
- Modify only if needed: enlaces documentales rotos detectados en Task 3

**Interfaces:**
- Consumes: commits y verificaciones de Tasks 1–3.
- Produces: árbol ordenado, working tree limpio y resumen de cambios.

- [ ] **Step 1: Revisar el diff completo**

  Ejecutar `git diff origin/main..HEAD --stat` y `git diff origin/main..HEAD --check`.

- [ ] **Step 2: Confirmar estado Git**

  Ejecutar `git status --short --branch`; no debe haber cambios no intencionales.

- [ ] **Step 3: Publicar la actualización**

  ```bash
  git push origin main
  ```

- [ ] **Step 4: Entregar resultado**

  Informar carpetas creadas, documentos movidos, verificaciones ejecutadas y cualquier test omitido por dependencias faltantes.
