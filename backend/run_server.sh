#!/usr/bin/env bash
# Arranca el backend con el Python del .venv del proyecto (donde está xai_sdk).
# Ejecutar desde backend/: ./run_server.sh

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="${REPO_ROOT}/.venv/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "No se encontró .venv. Creá uno con: cd $REPO_ROOT && uv sync --extra backend"
  exit 1
fi
cd "$(dirname "$0")"
# Usar SQLite si no tenés PostgreSQL (evita "role storymap does not exist")
export SQLITE=1
# --reload-dir .. hace que cambios en src/ (raíz del repo) también recarguen el servidor
exec "$VENV_PYTHON" -m uvicorn main:app --reload --reload-dir "$REPO_ROOT" --host 0.0.0.0 --port 8001
