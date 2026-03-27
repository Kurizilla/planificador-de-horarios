# Setup — Story Map Pipeline (producto web)

Entorno local para desarrollar backend, frontend y base de datos. Para despliegue en producción ver [DEPLOYMENT.md](DEPLOYMENT.md).

## Requisitos

- Python 3.10+
- Node 18+
- Docker (opcional; para PostgreSQL)

## 1. Base de datos

### Opción A: PostgreSQL con Docker

```bash
# Desde la raíz del repo
docker compose up -d
```

Conexión: `postgresql://storymap:storymap@localhost:5432/storymap`

### Opción B: SQLite (solo desarrollo)

No hace falta levantar ningún servicio. La API usará un archivo SQLite si se setea `SQLITE=1` o `DATABASE_URL=sqlite:///./storymap.db`.

## 2. Variables de entorno

Crear en la raíz del repo (o en `backend/`) un archivo `.env` con:

```env
# Base de datos (elegir una)
# PostgreSQL (con docker compose up -d):
DATABASE_URL=postgresql://storymap:storymap@localhost:5432/storymap

# SQLite (desarrollo sin Docker):
# SQLITE=1
# DATABASE_URL=sqlite:///./storymap.db

# Opcional
STORAGE_ROOT=./data
```

Puedes copiar desde `env.example`: `cp env.example .env` y editar.

## 3. Backend (FastAPI)

```bash
# Desde la raíz del repo
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Para Fase 1 el backend importa src.pipeline; la raíz del repo debe ser el directorio padre de backend/.

# Aplicar migraciones (Alembic). Usar el venv activado y python -m alembic:
# Con SQLite:
SQLITE=1 python3 -m alembic upgrade head

# Con PostgreSQL (Docker):
python3 -m alembic upgrade head

# Levantar servidor
uvicorn main:app --reload
```

La API queda en `http://127.0.0.1:8000`. Probar: `GET http://127.0.0.1:8000/health` → `{"status":"ok"}`.

**Nota:** Ejecutá todo desde el directorio `backend/` con el venv activado (`source .venv/bin/activate`). Así `python3 -m alembic` y `uvicorn` usan los paquetes del venv.

## 4. Frontend (React + Vite)

```bash
# Desde la raíz del repo
cd frontend
npm install
npm run dev
```

La app queda en `http://127.0.0.1:5173`. Ruta inicial: "Hello" (MVP 0).

## 5. Resumen rápido

| Paso | Comando (desde raíz) |
|------|----------------------|
| DB | `docker compose up -d` (o usar SQLite con `SQLITE=1`) |
| Backend | `cd backend && .venv/bin/activate && pip install -r requirements.txt && alembic upgrade head && uvicorn main:app --reload` |
| Frontend | `cd frontend && npm install && npm run dev` |

## Estructura creada (MVP 0)

- `backend/` — FastAPI, `/health`, SQLAlchemy + Alembic, modelos User, Project, Run, Artifact
- `frontend/` — Vite + React + React Router, página "Hello" en `/`
- `docker-compose.yml` — PostgreSQL 15
- `docs/setup.md` — esta guía
