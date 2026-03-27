# Schedule Planner — build y push de imágenes
# Mantenemos dos flujos hasta tener permisos/trigger: local (build+push) y Cloud Build (submit).
#
# Uso:
#   make build-push          # build local + push a Artifact Registry (no usa gcloud builds submit)
#   make cloud-build         # gcloud builds submit (requiere permisos o trigger)
#   make docker-auth         # configurar Docker para Artifact Registry (una vez)

# --- Variables (override con make VAR=valor o .env) ---
PROJECT_ID    ?= g-tele-educacion-dev-prj-d18a
REGION        ?= us-east1
REPOSITORY    ?= scheduler
VITE_API_URL  ?= https://scheduler-backend-518959659589.us-east1.run.app/api/v1

# Deploy Cloud Run (definir antes de make deploy-backend / deploy-frontend)
CLOUD_SQL_INSTANCE ?= $(PROJECT_ID):$(REGION):supervisor-ia
BUCKET_NAME        ?= scheduler-artifacts-$(PROJECT_ID)
BACKEND_SERVICE    ?= scheduler-backend
FRONTEND_SERVICE   ?= scheduler-frontend
# CORS: URL del frontend en Cloud Run (ej. https://scheduler-frontend-xxx.run.app)
CORS_ORIGINS       ?= https://scheduler-frontend-518959659589.us-east1.run.app
# Cuenta de servicio que ejecuta Cloud Run (evita actAs sobre la cuenta por defecto de Compute)
SERVICE_ACCOUNT    ?= educacion-svc-dev@$(PROJECT_ID).iam.gserviceaccount.com

# Imagen base en Artifact Registry
REGISTRY      := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPOSITORY)
TAG           := $(shell git rev-parse --short HEAD 2>/dev/null || echo "local")

BACKEND_IMAGE  := $(REGISTRY)/backend:$(TAG)
BACKEND_LATEST := $(REGISTRY)/backend:latest
FRONTEND_IMAGE := $(REGISTRY)/frontend:$(TAG)
FRONTEND_LATEST:= $(REGISTRY)/frontend:latest

.PHONY: help docker-auth build-backend build-frontend build push-backend push-frontend push build-push cloud-build deploy-backend deploy-frontend deploy deploy-dev seed-admin

.DEFAULT_GOAL := help

help:
	@echo "Schedule Planner — build y deploy"
	@echo ""
	@echo "  make docker-auth       — Configura Docker para Artifact Registry (ejecutar una vez)"
	@echo "  make build-push       — Build local + push a Artifact Registry"
	@echo "  make build / push     — Solo build o solo push"
	@echo "  make cloud-build     — gcloud builds submit (cuando tengas permisos o trigger)"
	@echo ""
	@echo "  make deploy-backend  — Despliega backend a Cloud Run (Cloud SQL, Secret Manager, GCS)"
	@echo "  make deploy-frontend — Despliega frontend a Cloud Run"
	@echo "  make deploy          — Despliega backend y luego frontend"
	@echo "  make deploy-dev      — Build + push + deploy de backend y frontend (orden completo para dev)"
	@echo "  make seed-admin      — Crea el primer usuario admin (ADMIN_EMAIL, ADMIN_PASSWORD, ADMIN_NAME)"
	@echo ""
	@echo "Variables build: PROJECT_ID REGION REPOSITORY VITE_API_URL"
	@echo "Variables deploy: CLOUD_SQL_INSTANCE BUCKET_NAME CORS_ORIGINS (ver Makefile)"
	@echo "Primera vez: make docker-auth && make build-push"

# Configurar Docker para poder hacer push a Artifact Registry (solo una vez)
docker-auth:
	gcloud auth configure-docker $(REGION)-docker.pkg.dev --quiet

# --- Build local (no usa Cloud Build) ---
# --platform linux/amd64: Cloud Run es amd64; evita "exec format error" si construyes en Mac M1/M2 (ARM).
build-backend:
	docker build --platform linux/amd64 -f backend/Dockerfile \
	  -t $(BACKEND_IMAGE) -t $(BACKEND_LATEST) .

build-frontend:
	@echo "Building frontend with VITE_API_URL=$(VITE_API_URL)"
	docker build --platform linux/amd64 -f frontend/Dockerfile \
	  --build-arg VITE_API_URL=$(VITE_API_URL) \
	  -t $(FRONTEND_IMAGE) -t $(FRONTEND_LATEST) .

build: build-backend build-frontend

# --- Push a Artifact Registry ---
push-backend: build-backend
	docker push $(BACKEND_IMAGE)
	docker push $(BACKEND_LATEST)

push-frontend: build-frontend
	docker push $(FRONTEND_IMAGE)
	docker push $(FRONTEND_LATEST)

push: push-backend push-frontend

# Build + push en un solo paso (flujo recomendado sin admin)
# Antes la primera vez: make docker-auth
build-push: build push

# --- Cloud Build (build + push + deploy a Cloud Run; requiere permisos o trigger) ---
# Sustituciones opcionales: _VITE_API_URL, _CORS_ORIGINS (tras el primer deploy, usar URLs reales).
cloud-build:
	gcloud builds submit . --config=cloudbuild.yaml --region=$(REGION) \
	  --substitutions=_REGION=$(REGION),_REPOSITORY=$(REPOSITORY),_VITE_API_URL=$(VITE_API_URL),_CORS_ORIGINS=$(CORS_ORIGINS)

# --- Deploy a Cloud Run ---
# Requisitos: Cloud SQL creado (connection name = CLOUD_SQL_INSTANCE, ej. proyecto:region:nombre-instancia),
#   Secret Manager: jwt-secret, xai-api-key, database-url (URL completa postgresql://...?host=/cloudsql/...),
#   bucket GCS creado (BUCKET_NAME). Cuenta de servicio de Cloud Run con Secret Manager Secret Accessor y Storage Object Admin en el bucket.
# Reconstruye y sube la imagen antes de desplegar (así el deploy siempre lleva los últimos cambios).
# Orden: make deploy-backend → anotar URL backend → make deploy-frontend → actualizar CORS_ORIGINS y redeploy backend si hace falta.
# Volúmenes GCS están en beta; usamos gcloud beta run deploy para el backend.
deploy-backend: push-backend
	gcloud beta run deploy $(BACKEND_SERVICE) \
	  --project $(PROJECT_ID) \
	  --image $(BACKEND_LATEST) \
	  --region $(REGION) \
	  --port 8000 \
	  --service-account $(SERVICE_ACCOUNT) \
	  --no-cpu-throttling \
	  --set-secrets "JWT_SECRET=jwt-secret-scheduler:latest,XAI_API_KEY=xai-api-key:latest,DATABASE_URL=database-url-scheduler:1" \
	  --set-env-vars "STORAGE_ROOT=/data,CORS_ORIGINS=$(CORS_ORIGINS)" \
	  --memory 2Gi --cpu 2 --timeout 3600 \
	  --add-volume name=storage,type=cloud-storage,bucket=$(BUCKET_NAME) \
	  --add-volume-mount volume=storage,mount-path=/data \
	  --allow-unauthenticated

# Reconstruye y sube la imagen antes de desplegar (así el deploy siempre lleva los últimos cambios del front).
deploy-frontend: push-frontend
	gcloud run deploy $(FRONTEND_SERVICE) \
	  --project $(PROJECT_ID) \
	  --image $(FRONTEND_LATEST) \
	  --region $(REGION) \
	  --port 80 \
	  --service-account $(SERVICE_ACCOUNT) \
	  --allow-unauthenticated

# Backend primero; luego frontend. Después de deploy-backend, actualiza CORS_ORIGINS con la URL del frontend.
deploy: deploy-backend deploy-frontend

# Flujo completo para entorno dev: build + push de ambos, luego deploy backend → frontend.
# Usa VITE_API_URL y CORS_ORIGINS del Makefile (o .env). Primera vez: make docker-auth
deploy-dev: build-push deploy-backend deploy-frontend

# --- Seed admin user (one-time setup) ---
# Uso: make seed-admin ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='SecurePass123' ADMIN_NAME='Admin User'
ADMIN_EMAIL ?=
ADMIN_PASSWORD ?=
ADMIN_NAME ?= Admin

seed-admin:
	@if [ -z "$(ADMIN_EMAIL)" ] || [ -z "$(ADMIN_PASSWORD)" ]; then \
	  echo "Error: ADMIN_EMAIL y ADMIN_PASSWORD son obligatorios."; \
	  echo "Uso: make seed-admin ADMIN_EMAIL=admin@example.com ADMIN_PASSWORD='SecurePass123' [ADMIN_NAME='Admin']"; \
	  exit 1; \
	fi
	@echo "Creando usuario admin con Cloud Run Job..."
	gcloud run jobs create seed-admin-user \
	  --image $(BACKEND_LATEST) \
	  --region $(REGION) \
	  --service-account $(SERVICE_ACCOUNT) \
	  --set-cloudsql-instances $(CLOUD_SQL_INSTANCE) \
	  --set-secrets "DATABASE_URL=database-url-scheduler:1" \
	  --set-env-vars "SEED_ADMIN_EMAIL=$(ADMIN_EMAIL),SEED_ADMIN_PASSWORD=$(ADMIN_PASSWORD),SEED_ADMIN_NAME=$(ADMIN_NAME)" \
	  --execute-now \
	  --wait \
	  --command "python" \
	  --args "scripts/seed_user.py" \
	  --tasks 1 \
	  --max-retries 0
	@echo ""
	@echo "✅ Usuario admin creado:"
	@echo "   Email: $(ADMIN_EMAIL)"
	@echo "   Nombre: $(ADMIN_NAME)"
	@echo ""
	@echo "Limpiando job..."
	@gcloud run jobs delete seed-admin-user --region $(REGION) --quiet || true
