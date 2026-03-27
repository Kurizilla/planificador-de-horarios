# Deployment — Story Map Pipeline

Guía mínima para desplegar backend + frontend en un entorno tipo producción. Para desarrollo local ver [setup.md](setup.md).

---

## 1. Variables de entorno

Usar `env.example` como base. En producción **obligatorio**:

| Variable | Dónde | Descripción |
|----------|--------|-------------|
| `DATABASE_URL` | Backend | PostgreSQL recomendado (no SQLite en prod). |
| `JWT_SECRET` | Backend | Valor secreto fuerte; no usar el default. |
| `STORAGE_ROOT` | Backend | Ruta absoluta donde se guardan proyectos/runs; debe existir y ser escribible. |
| `XAI_API_KEY` | Backend (pipeline) | Necesaria para Fase 1, Fase 2 y Fase 1.5. |
| `VITE_API_URL` | Frontend (build) | URL pública de la API (ej. `https://api.example.com/api/v1`). |

Opcional: `ACCESS_TOKEN_EXPIRE_MINUTES`, `XAI_MODEL`, `XAI_BASE_URL`, `CORS_ORIGINS` (si se implementa CORS configurable), `ALLOW_PUBLIC_REGISTRATION` (ver abajo).

### User management & security

- **JWT**: En producción **siempre** definir `JWT_SECRET` con un valor aleatorio fuerte (p. ej. `openssl rand -hex 32`). El backend registra un warning al arrancar si se usa el valor por defecto.
- **Registro público**: Por defecto cualquiera puede registrarse (`/api/v1/auth/register`). Para entornos cerrados (solo usuarios que tú creas), pon `ALLOW_PUBLIC_REGISTRATION=false`. Los usuarios se crean entonces con `backend/scripts/seed_user.py` o futuras herramientas de administración.
- **Whitelist**: Opcionalmente define `USER_WHITELIST` (emails separados por comas). Si está definido, solo esos emails pueden registrarse o ser creados por un admin; el seed script no está limitado por la whitelist.
- **Contraseñas**: El registro exige al menos 8 caracteres. Para políticas más estrictas (complejidad, longitud mayor) se puede extender la validación en `app/schemas/auth.py`.
- **Recomendaciones adicionales**: usar HTTPS, configurar CORS de forma restrictiva, y (opcional) añadir rate limiting en login/register para mitigar fuerza bruta.

---

## 2. Base de datos

- Usar **PostgreSQL** en producción.
- Crear la base y configurar `DATABASE_URL`.
- Aplicar migraciones (desde la raíz del repo, con el venv de uv):
  ```bash
  uv sync --extra backend
  cd backend && uv run alembic upgrade head
  ```
- Opcional: usuario inicial con `cd backend && uv run python scripts/seed_user.py`. Para crear el primer admin: `SEED_ADMIN_EMAIL=admin@example.com SEED_ADMIN_PASSWORD=... python scripts/seed_user.py` (ver `env.example`).

---

## 3. Backend (FastAPI)

- Instalar dependencias con **uv** (recomendado: venv o contenedor):
  ```bash
  uv sync --extra backend
  ```
  O con pip clásico ya no se usa; el proyecto usa `pyproject.toml` + `uv.lock` en la raíz.
- Exportar las variables de entorno (o usar `.env` con `python-dotenv`).
- En producción no usar `--reload`. Ejemplo con uvicorn y workers:
  ```bash
  uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
  ```
  (Ajustar `--workers` según carga; para más control considerar gunicorn + uvicorn workers.)
- El endpoint `/health` sirve para health checks del load balancer/contenedor.
- **CORS**: Si el frontend está en otro dominio, configurar `allow_origins` en `main.py` (actualmente fijo a localhost:5173/5174). Ideal: leer de `CORS_ORIGINS` en env.

---

## 4. Frontend (React + Vite)

- Build con la URL de la API de producción:
  ```bash
  cd frontend
  VITE_API_URL=https://api.example.com/api/v1 npm run build
  ```
- El resultado queda en `frontend/dist/`. Servir con un servidor estático (nginx, Apache, o el mismo host que la API con rutas estáticas). Configurar SPA fallback: todas las rutas no encontradas devuelven `index.html`.

---

## 5. Resumen de pasos

| Paso | Acción |
|------|--------|
| 1 | Configurar PostgreSQL y `DATABASE_URL`. |
| 2 | En `backend/`: `alembic upgrade head`. |
| 3 | Definir `JWT_SECRET`, `STORAGE_ROOT`, `XAI_API_KEY` (y opc. `CORS_ORIGINS`). |
| 4 | Arrancar backend (ej. `uvicorn main:app --host 0.0.0.0 --port 8000`). |
| 5 | Build frontend con `VITE_API_URL` apuntando a la API. |
| 6 | Servir `frontend/dist/` con nginx u otro; health check a `/health` del backend. |

---

## 6. Opcional: Docker

- Actualmente `docker-compose.yml` solo levanta PostgreSQL.
- Para despliegue con contenedores: añadir Dockerfile para backend (y opcionalmente para frontend) y servicios en docker-compose (backend, frontend, db). No incluido en este repo; se puede añadir en un siguiente paso.

---

## 7. Checklist pre-producción

- [ ] `JWT_SECRET` distinto del default y no commitado.
- [ ] `DATABASE_URL` apuntando a PostgreSQL.
- [ ] Migraciones aplicadas (`alembic upgrade head`).
- [ ] `STORAGE_ROOT` existe y es escribible.
- [ ] CORS permite el origen del frontend (o CORS configurable por env).
- [ ] Frontend construido con `VITE_API_URL` correcta.
- [ ] Health check configurado contra `/health`.
- [ ] Si no quieres registro público: `ALLOW_PUBLIC_REGISTRATION=false` y usuarios creados vía seed/script.

---

## 8. Cloud Build (GCP) — troubleshooting

Si `gcloud builds submit . --config=cloudbuild.yaml --region=...` falla con **NOT_FOUND: Requested entity was not found** justo después del upload del tarball:

El debug muestra que el 404 es en **POST .../locations/REGION/builds**: la “entidad no encontrada” es el **recurso regional** de Cloud Build (la ubicación en sí), no el proyecto.

1. **Habilitar Compute Engine API**  
   En proyectos recientes Cloud Build usa la cuenta de servicio por defecto de Compute Engine:
   ```bash
   gcloud services enable compute.googleapis.com --project=TU_PROJECT_ID
   ```

2. **Si el 404 persiste en varias regiones (p. ej. us-central1 y us-east1)**  
   Suele indicar restricción a nivel proyecto u organización:
   - **Probar desde la consola:** En GCP Console → **Cloud Build → Historial de compilaciones** (o **Triggers**), crear y ejecutar una compilación sencilla desde la UI. Si también falla, el problema es de configuración del proyecto/org, no del comando.
   - **Políticas de organización:** Un admin debe revisar **IAM y administración → Políticas de la organización** y comprobar si hay restricciones sobre Cloud Build (p. ej. `constraints/cloudbuild.*` o restricción de regiones).
   - **Propietario del proyecto:** Verificar en **APIs y servicios → API habilitadas** que **Cloud Build API** está habilitada y que no hay políticas que deshabiliten la API o las regiones de Cloud Build.

3. **Si los builds por trigger funcionan pero `gcloud builds submit` sigue dando NOT_FOUND**  
   En algunos proyectos solo las cuentas de servicio de Cloud Build pueden crear builds en la región; tu usuario puede no tener permiso para crear builds manualmente.
   - **Usar un trigger (recomendado):** Conectar el repo en **Cloud Build → Triggers** y crear un trigger que use `cloudbuild.yaml` en la rama que quieras (p. ej. `main` o `develop`). Región **us-east1**; sustituciones: `_REGION=us-east1`, `_REPOSITORY=storymap`, `_VITE_API_URL` = URL del backend cuando esté desplegado. Así no necesitas `gcloud builds submit` en tu máquina.
   - **Permisos:** Un admin puede dar a tu usuario el rol **Cloud Build Editor** (`roles/cloudbuild.builds.editor`) en el proyecto para poder crear builds con `gcloud builds submit`.
   - **Probar desde Cloud Shell:** Ejecutar `gcloud builds submit . --config=cloudbuild.yaml --region=us-east1` desde **Cloud Shell** en la consola del mismo proyecto; si ahí funciona, el problema es permisos o contexto de tu cuenta local.

4. **Ver el recurso exacto que falla**  
   Ejecutar con verbosidad; en la salida aparece la URL que devuelve 404 (p. ej. `.../locations/us-east1/builds`):
   ```bash
   gcloud builds submit . --config=cloudbuild.yaml --region=us-east1 --verbosity=debug
   ```

5. **Permisos del usuario**  
   El usuario debe tener al menos `roles/cloudbuild.builds.editor` y acceso al bucket de logs (p. ej. `roles/storage.objectViewer` en el bucket `*_cloudbuild` o rol de visor del proyecto).

---

## 9. Deploy a Cloud Run (GCP)

El [Makefile](../Makefile) incluye targets para desplegar backend y frontend en Cloud Run.

### Requisitos previos

1. **Cloud SQL (PostgreSQL)**  
   Instancia creada, base de datos `storymap`, usuario con contraseña. Anotar el **connection name** (ej. `proyecto:region:nombre-instancia`).

2. **Secret Manager**  
   Crear tres secretos (con el valor que corresponda):
   - `jwt-secret`: valor aleatorio fuerte (ej. `openssl rand -hex 32`).
   - `xai-api-key`: API key de xAI.
   - `database-url`: URL completa de PostgreSQL con socket Cloud SQL, ej.  
     `postgresql://usuario:contraseña@/storymap?host=/cloudsql/PROJECT_ID:REGION:INSTANCE_NAME`

3. **Bucket GCS**  
   Crear bucket para artefactos (ej. `storymap-artifacts-PROJECT_ID`). Dar a la cuenta de servicio de Cloud Run del backend el rol **Storage Object Admin** en ese bucket.

4. **Cuenta de servicio de Cloud Run**  
   Asegurar que la cuenta de servicio por defecto de Cloud Run (o la que use el servicio) tenga **Secret Manager Secret Accessor** sobre los tres secretos anteriores.

### Variables del Makefile (deploy)

Definir o exportar antes de `make deploy-backend` / `make deploy-frontend`:

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `CLOUD_SQL_INSTANCE` | Connection name de Cloud SQL | `proyecto:us-east1:storymap-db` |
| `BUCKET_NAME` | Nombre del bucket GCS para artefactos | `storymap-artifacts-proyecto` |
| `CORS_ORIGINS` | URL del frontend (para CORS del backend) | `https://storymap-frontend-xxx.run.app` |

Las demás (`PROJECT_ID`, `REGION`, `REPOSITORY`, nombres de servicios) tienen valores por defecto en el Makefile.

### Orden de deploy

1. **Backend**  
   ```bash
   make deploy-backend CLOUD_SQL_INSTANCE=proyecto:us-east1:TU_INSTANCIA BUCKET_NAME=storymap-artifacts-TU_PROYECTO
   ```  
   Anotar la URL del servicio (ej. `https://storymap-backend-xxx.run.app`).

2. **Frontend**  
   ```bash
   make deploy-frontend
   ```  
   Anotar la URL del frontend.

3. **CORS**  
   Si el backend se desplegó con un `CORS_ORIGINS` genérico, actualizar con la URL real del frontend y volver a desplegar el backend:
   ```bash
   make deploy-backend CORS_ORIGINS=https://storymap-frontend-XXX.run.app
   ```

Los secretos se inyectan como variables de entorno (`JWT_SECRET`, `XAI_API_KEY`, `DATABASE_URL`). El bucket GCS se monta en `/data` (Cloud Run Gen2 con volumen en beta: `gcloud beta run deploy`).

### Rutas de almacenamiento (mapeo local → Cloud Run)

En Cloud Run el backend tiene:

| Entorno   | `STORAGE_ROOT` | Montaje real                          |
|-----------|-----------------|----------------------------------------|
| Cloud Run | `/data`         | Volumen GCS (bucket `storymap-artifacts-*`) |
| Docker Compose (local) | `/data` | Volumen nombrado `backend_data`        |
| Local (uv) | `./data` (default) | Carpeta en el repo                 |

**Regla:** Todo archivo que el backend escriba o lea como “almacenamiento persistente” debe vivir bajo `STORAGE_ROOT`. Así en Cloud Run todo cae en `/data` (GCS) y en local en `./data` o el volumen según corresponda.

- **Implementación:** Usar siempre `get_storage()` ([`app.services.storage`](../backend/app/services/storage.py)) para guardar/leer artefactos, o `get_settings().storage_root` si se construye un path propio (p. ej. un subdirectorio).
- **Qué ya cumple:** Subida de Excel de proyecto, outputs de runs (Fase 1, 1.5, 2), logs, artefactos de feedback y descargas usan `get_storage()` → paths bajo `storage_root`.
- **Cualquier feature nueva que escriba archivos** (p. ej. export Phase 0, reportes, cachés) debe usar `storage_root` (por ejemplo `storage_root / "phase0_artifacts"`) y **no** rutas derivadas de `Path(__file__)` o de la raíz del repo, para que en Cloud Run queden en `/data` y persistan en GCS.

### Error: Permission 'iam.serviceaccounts.actAs' denied

Si el deploy falla con **Permission 'iam.serviceaccounts.actAs' denied on service account ...-compute@developer.gserviceaccount.com**, tu usuario no puede “actuar como” la cuenta de servicio por defecto de Compute Engine que usa Cloud Run.

**Solución:** Un admin del proyecto debe concederte el rol **Service Account User** sobre esa cuenta de servicio (o sobre el proyecto):

```bash
# Sobre la cuenta de servicio (reemplaza NUMBER por el número del proyecto)
gcloud iam service-accounts add-iam-policy-binding \
  NUMBER-compute@developer.gserviceaccount.com \
  --project=TU_PROJECT_ID \
  --member="user:TU_EMAIL@dominio" \
  --role="roles/iam.serviceAccountUser"
```

Luego vuelve a ejecutar `make deploy-backend`.

### Error: failed to start and listen on the port / Application exec likely failed

Si GCSFuse monta bien pero el contenedor no llega a escuchar en el puerto 8000:

1. **Revisar los logs completos** del revision en Cloud Run (Logs del revision). Busca un traceback de Python, un error de **alembic** (ej. "can't connect to database") o de **uvicorn**. Suele ser:
   - **DATABASE_URL** no disponible o incorrecta: el secret `database-url-storymap` debe existir y la cuenta de servicio debe tener **Secret Manager Secret Accessor**. La URL debe ser `postgresql://user:pass@/storymap?host=/cloudsql/PROJECT:REGION:INSTANCE`.
   - **Conexión a Cloud SQL**: la instancia debe estar en la misma región (o permitir la conexión desde Cloud Run) y el connection name en `--add-cloudsql-instances` debe coincidir con el de la URL.

2. **Arranque lento**: El Makefile usa `--no-cpu-throttling` para dar CPU completa durante el arranque (GCSFuse + migraciones + uvicorn). Si aún falla por timeout, en la consola de Cloud Run puedes aumentar el **startup probe** (hasta 240 s) en la revisión.    