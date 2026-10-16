# Saneamiento organizativo — Fase 1

## Objetivo

Ordenar el repositorio de Pairs Desk sin modificar la lógica de negocio, las rutas de trading ni las rutas de ejecución. React queda definido como la interfaz principal; las interfaces existentes se conservan como fallback o legacy.

## Alcance aprobado

- Reorganizar documentación histórica y notas de entregas anteriores.
- Aclarar en `README.md` cuál es la interfaz principal y cuáles son las alternativas legacy.
- Mantener las rutas actuales de código para no romper imports, launchers ni endpoints.
- Mantener `pairs_desk/`, `read_only_server.py` y `secure_trade_routes.py` en sus ubicaciones actuales.
- No eliminar archivos ni alterar comportamiento funcional.

## Estructura objetivo de esta fase

```text
Pairs_Desk/
├── pairs_desk/              # lógica de negocio e integración Hyperliquid
├── react_frontend/          # interfaz principal; código fuente React
├── frontend/                # interfaz estable legacy/fallback
├── aurora/                  # interfaz legacy anterior
├── docs/
│   ├── current/             # documentación vigente y operativa
│   ├── history/             # changelogs, entregas y notas históricas
│   ├── visual/              # capturas de auditoría visual
│   └── superpowers/specs/   # especificaciones de trabajo
├── scripts/                 # utilidades y backtests
├── tests/
├── app.py                   # interfaz Streamlit legacy
├── read_only_server.py      # API y servidor principal
└── secure_trade_routes.py   # rutas de operaciones reales
```

Las carpetas `frontend/`, `aurora/` y el archivo `app.py` no se mueven en esta fase porque el servidor y los tests usan sus rutas actuales.

## Movimientos previstos

1. Clasificar los documentos de la raíz.
2. Mover a `docs/current/` solo la documentación vigente que describe instalación, arquitectura, dependencias y estado actual.
3. Mover a `docs/history/` changelogs, entregas S1, notas de versiones y documentos de auditorías cerradas.
4. Mantener `docs/visual/` sin cambios de ubicación.
5. Actualizar enlaces y referencias internas afectados por esos movimientos.
6. Actualizar `README.md` con:
   - React como interfaz principal.
   - comando de inicio recomendado.
   - ubicación de las interfaces legacy.
   - advertencia explícita sobre las rutas de trading real.
   - mapa breve de la estructura del repositorio.

## Límites de seguridad

- No tocar `.env`, configuraciones locales, bases de datos ni artefactos ignorados.
- No modificar `secure_trade_routes.py`.
- No modificar contratos HTTP, puertos, endpoints ni imports de runtime.
- No borrar archivos; los documentos dudosos se conservan en `docs/history/`.
- Después de cada movimiento, buscar referencias rotas con `rg`.

## Verificación

- `git status` limpio salvo los cambios intencionales.
- Todos los archivos documentales siguen versionados.
- No quedan enlaces a las rutas antiguas de documentación.
- Los launchers conservan sus rutas actuales.
- Ejecutar la suite Python/Node disponible; si falta una dependencia, documentarlo sin instalarla automáticamente.
- Verificar que el repositorio no incluya artefactos ignorados ni secretos.

## Fuera de alcance

- Reubicar el backend en `backend/`.
- Cambiar `pairs_desk/` a un layout `src/`.
- Fusionar o eliminar las interfaces legacy.
- Rediseñar la UI React.
- Cambiar la lógica de trading o validar operaciones reales.
