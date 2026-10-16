#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "No se encontró Python 3 instalado."
  echo "Instalalo y volvé a ejecutar este archivo."
  read -r -p "Presioná Enter para cerrar..."
  exit 1
fi

# Entorno virtual local para no tocar el Python del sistema.
if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate

# Instala/actualiza dependencias solo cuando cambia requirements.txt.
REQ_HASH_FILE=".venv/.requirements.sha256"
REQ_HASH="$(sha256sum requirements.txt | awk '{print $1}')"
OLD_HASH="$(cat "$REQ_HASH_FILE" 2>/dev/null || true)"

if [ "$REQ_HASH" != "$OLD_HASH" ]; then
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  printf '%s' "$REQ_HASH" > "$REQ_HASH_FILE"
fi

# Intenta obtener KLineChart una sola vez y lo aloja localmente.
# Si falla la red, el gráfico existente sigue funcionando.
set +e
python install_klinechart.py
KL_STATUS=$?
set -e
if [ "$KL_STATUS" -eq 2 ]; then
  echo "ERROR: KLineChart no pasó la verificación de integridad. Abortando." >&2
  exit 2
fi

# Abre la app solo en esta PC.
exec streamlit run app.py \
  --server.address 127.0.0.1 \
  --server.headless false \
  --browser.gatherUsageStats false
