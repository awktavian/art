# Kagami SmartHome - Cloud Run Dockerfile
#
# Persistent smart home controller with always-on integrations.
# Build: gcloud builds submit --config=deploy/cloudrun/smarthome/cloudbuild.yaml
#
# Created: January 5, 2026

FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir \
    fastapi>=0.109.0 \
    uvicorn[standard]>=0.27.0 \
    aiohttp>=3.9.0 \
    httpx>=0.26.0 \
    pydantic>=2.5.0 \
    pydantic-settings>=2.1.0 \
    python-dotenv>=1.0.0 \
    structlog>=24.1.0 \
    numpy>=2.1

FROM python:3.12-slim AS runtime

RUN groupadd -r kagami && useradd -r -g kagami kagami

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY packages/kagami_smarthome/ ./packages/kagami_smarthome/
COPY packages/kagami/ ./packages/kagami/
COPY deploy/cloudrun/smarthome/main.py ./main.py

ENV PYTHONPATH="/app/packages:/app"
ENV PYTHONUNBUFFERED=1
ENV KAGAMI_ENVIRONMENT="production"
ENV PORT=8080

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

USER kagami

CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT} --workers 1
