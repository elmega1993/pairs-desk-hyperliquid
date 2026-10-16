# Pairs Desk 2.0 — plan de consolidación

## Principio
La versión React no debe perder funciones presentes en Aurora Beta 01. Conservar el backend, el ledger, el modo solo lectura y KLineCharts hasta que una alternativa demuestre paridad funcional.

## Entrega 04 — Radar (implementado)
- Clic en encabezados PAR, FLOTANTE, REALIZADO, PNL %, EXPOSICIÓN y FUNDING.
- Alternar descendente/ascendente con un segundo clic; flecha visible y aria-sort.
- Valores desconocidos N/D al final; desempate alfabético.
- Lista lateral y radar comparten el orden; persistencia local del criterio.
- Se eliminó el selector desplegable de ordenamiento.

## Pendiente: cierre del escritorio (no implementado en esta entrega)
1. Paridad visual exacta con Aurora Beta 01: tamaños, densidad, scroll interno y paneles ajustables.
2. Radar y gráfico PNL: interacciones y escalas; verificar tooltips, período y marcas de operaciones.
3. Etiquetas TP/ADD: evitar superposición sin modificar niveles reales; distinguir objetivos de órdenes activas.
4. Regresión automatizada React (npm build, interacción en navegador) y pruebas con Core/XYZ.
5. Contabilidad: conciliar funding histórico y PNL neto; conservar N/D ante datos incompletos.

## Criterio de salida de la fase de escritorio
No avanzar al explorador mientras exista regresión respecto a Aurora Beta 01. Validar por captura y por prueba de usuario en Ubuntu.
