# Plan de consolidación

**Referencia congelada:** React Etapa 04.

## Fase 0 — Higiene
- [x] Archivar documentación histórica sin borrarla
- [x] Retirar prototipo `aurora-react/`
- [x] `.gitignore`
- [x] Fijar SHA-256 de KLineCharts y **verificarlo** al iniciar (`install_klinechart.py`; código 2 aborta el arranque)
- [x] Evitar compilaciones npm innecesarias
- [x] `package-lock.json` generado; el launcher usa `npm ci`
- [x] Repositorio git local inicializado
- [x] Tests de Node ejecutables desde `pytest` (sin rutas absolutas)
- [ ] Unificar dependencias SDK tras análisis de compatibilidad (`requirements.txt` vs `requirements_frontend.txt`)
- [ ] Detección de cambios del build por hash en lugar de fecha de modificación

## Fase 1 — Base React
- [x] Separar API, formato, orden y tipos de `main.tsx`
- [x] Gráfico KLineCharts como componente TypeScript (`RatioChart.tsx`), sin `window.AuroraTradingChart`
- [x] Refresco cada 30 s con pestaña visible, sin destruir el zoom
- [x] PNL con ejes, línea cero y tooltip (`PnlChart.tsx`)
- [ ] KLineCharts como dependencia npm importada (hoy se carga como `<script>` desde `/vendor`)
- [ ] Dividir `App.tsx` (17 `useState`) en hooks y componentes
- [x] Verificar visualmente el PNL y corregir deformación, recorte de etiquetas y marcas del eje
- [x] Pruebas de navegador para el PNL, la exposición y el radar (`tests/test_visual_smoke.py`)
- [ ] Pruebas de comportamiento para `PairActions`

## Fase 1b — Operar en React (añadido, pendiente de validar)
`components/PairActions.tsx` ofrece **Agregar par** y **Operar par** (órdenes reales) con los mismos controles del frontend estable. El backend no cambió.
- [ ] Validar el flujo completo en testnet o con una operación `reduce-only` mínima
- [ ] Cuenta regresiva del ticket (40 s) y bloqueo del botón al vencer
- [ ] Refrescar posiciones tras ejecutar una orden
- [ ] Manejar respuestas de error que no sean JSON en `request()`
- [x] Auto-reconciliar intentos sin envío cuando las posiciones permanecen sin cambios; conservar bloqueo para fills o desbalances.

## Fase 1c — Visual pendiente
- [x] Indicador de estado de trading siempre visible (`TradeBadge`). Pendiente: cuenta regresiva y desarme automático (requiere backend)
- [x] Indicador de frescura de datos (ámbar > 60 s, rojo > 120 s)
- [ ] Navegación en móvil (la barra lateral desaparece) y ocultar controles de paneles en pantallas angostas
- [ ] Atenuar las secciones sin contenido (Explorador, Laboratorio, Investigación, Actividad)
- [ ] Prefijo "+" o flechas para no depender solo del color

## Fase 2 — Backend
Separar lectura de escrituras (hoy `GET /api/state` escribe `settings.json`), snapshots SQLite, configuración única de host/puerto (hoy `8510` fijo en `_request_ok`), `lifespan`, esquemas Pydantic.

## Fase 3 — Paridad
Cerrados, Cuenta, Eventos, Alertas, Gestión.

## Fase 4 — Retiro
Eliminar interfaces antiguas solo con paridad verificada.

**Seguridad:** las rutas de trading solo se modifican para controles explícitos de seguridad y conciliación; no se agregan envíos automáticos de órdenes.
