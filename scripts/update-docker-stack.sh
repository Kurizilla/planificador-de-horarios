#!/usr/bin/env bash
# Actualiza todo el stack Docker (backend + frontend) sin caché y reinicia.
# Uso: ./scripts/update-docker-stack.sh   o   bash scripts/update-docker-stack.sh
set -e

cd "$(dirname "$0")/.."
echo "→ Reconstruyendo backend (sin caché)..."
docker compose build --no-cache backend

echo "→ Reconstruyendo frontend (sin caché)..."
docker compose build --no-cache frontend

echo "→ Levantando servicios..."
docker compose up -d

echo "→ Aplicando migraciones (por si acaso)..."
docker compose exec backend alembic upgrade head 2>/dev/null || true

echo "✓ Listo. Frontend: http://localhost:3000  — Backend: http://localhost:8001"
echo "  Refrescá el navegador con Cmd+Shift+R (Mac) o Ctrl+Shift+R (Windows/Linux)."
