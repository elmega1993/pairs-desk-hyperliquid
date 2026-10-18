# START HERE

## Lectura rápida

1. `AGENTS.md`: reglas de seguridad y trabajo.
2. `CURRENT_STATE.md`: estado comprobado de esta copia.
3. `TASKS.md`: pendientes priorizados.
4. `docs/ARCHITECTURE.md`: mapa de componentes y datos.
5. `docs/TESTING.md`: cómo validar cambios.
6. `README.md`: instalación, precauciones y explicación general.

## Mapa del proyecto

- `react_frontend/`: fuente de la interfaz principal React.
- `react_dist/`: compilación servida por el backend.
- `read_only_server.py`: API local y servidor FastAPI.
- `pairs_desk/`: dominio, mercado, ledger, métricas y almacenamiento.
- `secure_trade_routes.py`: rutas de trading real.
- `frontend/`: interfaz estable legacy.
- `aurora/`: interfaz legacy anterior.
- `tests/`: pruebas Python, JavaScript y navegador.
- `docs/current/`: estado y plan de consolidación.
- `docs/history/`: historial de entregas y decisiones anteriores.

## Arranque recomendado

Para desarrollo de la interfaz principal:

```bash
./iniciar_frontend.sh
```

Para una validación rápida:

```bash
pytest tests/
```

No asumir que la aplicación es de solo lectura: la UI React incluye acciones para agregar y operar pares.
