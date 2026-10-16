#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PIP_DISABLE_PIP_VERSION_CHECK=1
# Verifica siempre el SHA-256 de KLineCharts. Código 2 = integridad fallida: no se inicia.
if command -v python3 >/dev/null 2>&1; then
  set +e
  python3 install_klinechart.py
  KL_STATUS=$?
  set -e
  if [ "$KL_STATUS" -eq 2 ]; then
    echo "ERROR: KLineCharts no pasó la verificación de integridad. Abortando." >&2
    exit 2
  elif [ "$KL_STATUS" -ne 0 ]; then
    echo "AVISO: KLineCharts verificado no disponible; el gráfico React no se mostrará." >&2
  fi
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: falta Python 3. Instalá python3 y python3-venv desde el gestor de paquetes de Ubuntu." >&2; exit 1
fi
if [ ! -d .venv_frontend ]; then
  if ! python3 -m venv .venv_frontend; then
    echo "ERROR: no se pudo crear el entorno virtual. En Ubuntu instalá python3-venv." >&2; exit 1
  fi
fi
. .venv_frontend/bin/activate
python -m pip install -q -r requirements_frontend.txt
if [ -f react_frontend/package.json ]; then
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
    if [ "$MAJOR" -ge 20 ]; then
      echo "Preparando Aurora React (primera ejecución puede tardar)…"
      if [ ! -d react_frontend/node_modules ]; then
        echo "Instalando dependencias de React…"
        if [ -f react_frontend/package-lock.json ]; then
          (cd react_frontend && npm ci --no-audit --no-fund)
        else
          echo "No existe package-lock.json: npm install lo generará en esta primera ejecución."
          (cd react_frontend && npm install --no-audit --no-fund)
        fi
      elif [ ! -f react_frontend/package-lock.json ]; then
        echo "Generando package-lock.json para próximas instalaciones reproducibles…"
        (cd react_frontend && npm install --package-lock-only --no-audit --no-fund)
      fi
      NEED_BUILD=0
      [ ! -f react_dist/index.html ] && NEED_BUILD=1
      if [ "$NEED_BUILD" -eq 0 ] && find react_frontend/src react_frontend/index.html react_frontend/vite.config.ts react_frontend/package.json -type f -newer react_dist/index.html | grep -q .; then NEED_BUILD=1; fi
      if [ "$NEED_BUILD" -eq 0 ]; then
        echo "React sin cambios; reutilizando compilación existente."
      elif (cd react_frontend && npm run build); then
        echo "React compilado correctamente: http://127.0.0.1:8510/react"
      else
        echo "AVISO: React no se pudo compilar. Aurora clásica sigue disponible en /aurora." >&2
      fi
    else
      echo "AVISO: React requiere Node.js 20+. Detectado: $(node --version). Aurora clásica sigue disponible." >&2
    fi
  else
    echo "AVISO: Node.js/npm no encontrados. React requiere Node.js 20+ y npm." >&2
    echo "En Ubuntu podés instalarlos desde el gestor de paquetes o NodeSource; el launcher no modifica paquetes del sistema." >&2
  fi
fi
printf '\nAurora: http://127.0.0.1:8510/aurora\nReact (si compiló): http://127.0.0.1:8510/react\nVersión estable: http://127.0.0.1:8510/\n'
printf 'Las operaciones reales requieren habilitación y confirmación explícitas. Ctrl+C para detener.\n'
python -m uvicorn read_only_server:app --host 127.0.0.1 --port 8510
