# Levantar entorno de desarrollo

## Opción 1: Todo con Docker

```bash
# Desde la raíz del proyecto
docker compose up -d

# Crear usuario admin (una vez)
docker compose exec backend python scripts/seed_user.py
```

- **Frontend:** http://localhost:3000  
- **Backend API / Docs:** http://localhost:8000 y http://localhost:8000/docs  

**Credenciales (tras el seed):**
- **Email:** `admin@example.com`
- **Contraseña:** `secure-password`

---

## Opción 2: DB en Docker, backend y frontend en local (recomendado para dev)

### 1. Base de datos

```bash
# Solo el servicio db
docker compose up -d db
```

### 2. Backend

```bash
# Desde la raíz del proyecto
cp env.example .env
# Opcional: editar .env y dejar DATABASE_URL=postgresql://scheduler:scheduler@localhost:5432/scheduler

uv sync --extra backend
cd backend
export DATABASE_URL=postgresql://scheduler:scheduler@localhost:5432/scheduler
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python scripts/seed_user.py   # crea admin@example.com / secure-password
../.venv/bin/python -m uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

Backend: http://localhost:8001 — Docs: http://localhost:8001/docs

### 3. Frontend (otra terminal)

```bash
cd frontend
npm install
npm run dev
```

Frontend: http://localhost:5173 (Vite usa por defecto la API en http://localhost:8001/api/v1)

### Credenciales

- **Email:** `admin@example.com`  
- **Contraseña:** `secure-password`  

(Si no ejecutaste el seed, podés registrarte en http://localhost:5173/register si `ALLOW_PUBLIC_REGISTRATION` está en true.)

### Verificar

1. Entrá a http://localhost:5173 (o 3000 si usás todo Docker).
2. Iniciá sesión con `admin@example.com` / `secure-password`.
