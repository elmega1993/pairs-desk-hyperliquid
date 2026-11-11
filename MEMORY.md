# Memoria curada del proyecto

Actualizada: 2026-11-11. Estado operativo y pruebas: CURRENT_STATE.md.

- Extender Pair Desk existente; React en /react, conservar trading y contabilidad.
- Desk: identidad versionada y memoria persistente independiente del modelo. Codex App Server usa la sesión de ChatGPT y consentimiento explícito para contexto; Ollama/GPU queda como alternativa. No herramientas financieras de ejecución en el asesor.
- TWAP elegido: nativo de Hyperliquid; dos patas independientes. Unidades minutos/horas/días, 5min–7d. No imponer límites locales menores sin motivo. Mínimo nativo USD100 por pata.
- Firmar wire normalizado con float_to_wire oficial antes de sign_l1_action. Nunca str(float) con .0.
- Persistir intención e IDs antes/después del envío, nunca reenviar estados inciertos. Cancelar conserva fills. Bloquear activos compartidos con órdenes pendientes; no probar con órdenes reales sin autorización explícita.
- Diagnóstico: preservar únicamente el mensaje de error saneado, acotado y sin credenciales/direcciones. No descartar automáticamente errores desconocidos ni atribuir una causa que no quedó registrada. Se observó rechazo por máximo de TWAP activos; no hardcodear un número por inferencia.
- Media actual del ratio = entryPx long / entryPx short. En escala relativa vale 0%. Evolución histórica debe incorporar fills nativos observados, deduplicar y reconciliar; no usar esa fusión para alterar contabilidad.
- Contexto específico: docs/current/DESK_MEMORIA.md, NATIVE_TWAP.md, HISTORICAL_ACCOUNT.md. Exportaciones, settings, bases, secretos, copias de UI y notas históricas personales quedan locales, fuera de Git.
