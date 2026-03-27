# Build desde la raíz del repo: docker build -f backend/Dockerfile .
# El backend necesita backend/ + src/ para importar el pipeline.
# Dependencias con uv (pyproject.toml + uv.lock en la raíz).

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# uv: copiar proyecto y lockfile primero (mejor cache de capas)
COPY pyproject.toml uv.lock ./
COPY backend/ /app/backend/
COPY src/ /app/src/


RUN pip install --no-cache-dir uv \
    && uv sync --frozen --no-dev --extra backend

ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /app/backend
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

RUN chmod +x /app/backend/docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
