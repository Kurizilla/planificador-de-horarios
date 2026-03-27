#!/bin/sh
# Comprueba conexión a la DB, aplica migraciones y arranca la app.
# Logs a stderr para que Cloud Run los muestre enseguida.
set -e

echo "[entrypoint] Inicio." >&2
if [ -z "${DATABASE_URL:-}" ]; then
  echo "[entrypoint] DATABASE_URL no definida." >&2
  exit 1
fi

echo "[entrypoint] Comprobando conexión a DB..." >&2
cd /app/backend && python scripts/check_db.py || exit 1

echo "[entrypoint] Aplicando migraciones..." >&2
alembic upgrade head

echo "[entrypoint] Ejecutando seed de usuarios..." >&2
python scripts/seed_user.py

echo "[entrypoint] Listo. Arrancando app." >&2
exec "$@"
