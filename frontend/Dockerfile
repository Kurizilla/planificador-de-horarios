# Build desde la raíz del repo: docker build -f frontend/Dockerfile .
# URL de la API en tiempo de build: --build-arg VITE_API_URL=...

FROM node:22-alpine AS builder

WORKDIR /app

# Context = repo root cuando se usa desde docker-compose
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci 2>/dev/null || npm install

COPY frontend/ .

# En local: VITE_API_URL apunta al backend (ej. http://localhost:8000/api/v1)
# En prod: la URL pública del backend (ej. https://api-xxx.run.app/api/v1)
ARG VITE_API_URL=http://localhost:8000/api/v1
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

# Servir con nginx (SPA fallback)
FROM nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
