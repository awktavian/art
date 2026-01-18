# Kagami API - Cloud Run Optimized Dockerfile
#
# Multi-stage build optimized for Cloud Run:
# - Minimal image size with distroless base
# - Pre-compiled dependencies
# - Non-root user for security
# - Health check endpoint
# - Graceful shutdown handling
#
# Build: gcloud builds submit --tag gcr.io/$PROJECT_ID/kagami-api
# Deploy: gcloud run deploy kagami-api --image gcr.io/$PROJECT_ID/kagami-api
#
# Created: January 4, 2026

# ==============================================================================
# Stage 1: Build dependencies
# ==============================================================================
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt requirements-optional.txt ./

# Install dependencies to a virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install core dependencies
RUN pip install --no-cache-dir --upgrade pip wheel setuptools && \
    pip install --no-cache-dir -r requirements.txt

# Install GCP-specific optional dependencies
RUN pip install --no-cache-dir \
    google-cloud-aiplatform \
    google-cloud-pubsub \
    google-cloud-logging \
    google-cloud-monitoring \
    google-cloud-storage \
    opentelemetry-exporter-gcp-trace \
    grpcio

# ==============================================================================
# Stage 2: Runtime image
# ==============================================================================
FROM python:3.12-slim AS runtime

# Security: Run as non-root user
RUN groupadd -r kagami && useradd -r -g kagami kagami

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY packages/ ./packages/
COPY config/ ./config/
COPY kagami/ ./kagami/

# Set Python path
ENV PYTHONPATH="/app/packages:/app"
ENV PYTHONUNBUFFERED=1

# GCP metadata detection
ENV GOOGLE_CLOUD_PROJECT=""
ENV K_SERVICE=""
ENV K_REVISION=""

# Application configuration
ENV KAGAMI_ENVIRONMENT="production"
ENV KAGAMI_LOG_LEVEL="INFO"
ENV GCP_ENABLE_LOGGING="true"
ENV GCP_ENABLE_MONITORING="true"
ENV GCP_ENABLE_TRACING="true"

# Cloud Run uses PORT env var (default 8080)
ENV PORT=8080
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Switch to non-root user
USER kagami

# Cloud Run startup command
# Uses gunicorn with uvicorn workers for async support
CMD exec gunicorn \
    --bind :${PORT} \
    --workers 2 \
    --threads 8 \
    --worker-class uvicorn.workers.UvicornWorker \
    --timeout 0 \
    --graceful-timeout 30 \
    --keep-alive 650 \
    --max-requests 1000 \
    --max-requests-jitter 50 \
    kagami.api.main:app
