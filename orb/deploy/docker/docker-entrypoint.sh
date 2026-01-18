#!/usr/bin/env sh
set -e

# Production-safe entrypoint for K os API container
# Honors ENV vars: HOST, PORT, GUNICORN_WORKERS, LOG_LEVEL, TIMEOUT, GRACEFUL_TIMEOUT

: "${HOST:=0.0.0.0}"
: "${PORT:=8001}"
: "${GUNICORN_WORKERS:=12}"
: "${LOG_LEVEL:=info}"
: "${TIMEOUT:=120}"
: "${GRACEFUL_TIMEOUT:=30}"

mkdir -p /app/logs || true
echo "[entrypoint] Building K os Control assets (served at /control) if present..."
if [ -d "/app/kagami/web/dist" ]; then
  echo "[entrypoint] Web assets detected: /app/kagami/web/dist"
else
  echo "[entrypoint] WARNING: Web assets not found. Ensure Dockerfile web-builder stage ran."
fi

echo "[entrypoint] Starting gunicorn kagami_api:create_app --factory on ${HOST}:${PORT} (workers=${GUNICORN_WORKERS})"

exec gunicorn 'kagami_api:create_app()' \
  --workers "${GUNICORN_WORKERS}" \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind "${HOST}:${PORT}" \
  --keep-alive 30 \
  --timeout "${TIMEOUT}" \
  --graceful-timeout "${GRACEFUL_TIMEOUT}" \
  --log-level "${LOG_LEVEL}" \
  --access-logfile - \
  --error-logfile -
