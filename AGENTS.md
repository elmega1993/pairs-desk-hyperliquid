# AGENTS.md — Reglas de trabajo de Pairs Desk

## Alcance

Este repositorio contiene una aplicación local para analizar posiciones y ratios de Hyperliquid. React es la interfaz principal; `/` y `/aurora` son interfaces legacy.

## Reglas de seguridad

- Tratar el proyecto como una aplicación con capacidad de trading real.
- No ejecutar órdenes ni habilitar trading sin una instrucción explícita y una revisión previa de la ruta involucrada.
- No exponer secretos, bases SQLite, configuraciones personales ni respuestas de la API.
- No modificar `secure_trade_routes.py` durante tareas de saneamiento o documentación salvo que Alan lo pida expresamente.
- Antes de una modificación destructiva o de datos, confirmar el alcance y conservar una alternativa recuperable.

## Flujo de trabajo

- Leer `START_HERE.md`, `CURRENT_STATE.md` y `TASKS.md` antes de cambios relevantes.
- Mantener los cambios acotados y actualizar la documentación cuando una decisión afecte el funcionamiento futuro.
- Preferir pruebas deterministas y de solo lectura.
- No inventar datos de mercado ni asumir que una pantalla está validada para operar.

## Comandos principales

```bash
./iniciar_frontend.sh
pytest tests/
(cd react_frontend && npm ci && npm run build)
```

Las pruebas de navegador requieren Playwright/Chromium. Las pruebas que dependen de Node o dependencias ausentes pueden omitirse según la configuración de la suite.

## Zonas sensibles

- `secure_trade_routes.py`: ejecución de órdenes reales.
- `read_only_server.py`: API local y servidor FastAPI; revisar efectos secundarios en endpoints de lectura.
- `pairs_desk/`: lógica de negocio, almacenamiento, ledger, métricas e integración con Hyperliquid.
- `react_frontend/`: interfaz principal.
- `frontend/`, `aurora/`: interfaces legacy/fallback.
