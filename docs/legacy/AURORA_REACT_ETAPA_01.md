# Aurora React — etapa 01

Ejecutar `./iniciar_frontend.sh`. Instala dependencias Python en `.venv_frontend` y, si hay Node.js 20+ y npm, instala dependencias React y compila el frontend. React disponible en `/react`; Aurora original en `/aurora`.

**Alcance real:** React implementa el contenedor superior y preferencias de vista, pero el escritorio actual se integra temporalmente mediante iframe local a `/aurora`. No se ha migrado todavía el gráfico ni la lógica del escritorio a componentes React. La aplicación es de solo lectura y conserva KLineCharts.

**Requisitos previos del sistema:** Python 3 con módulo venv; Node.js 20+ y npm para React. El script no usa sudo ni instala paquetes globales automáticamente, por seguridad. Si npm falla, el escritorio Aurora anterior continúa disponible. Requiere conexión a npm en la primera instalación.
