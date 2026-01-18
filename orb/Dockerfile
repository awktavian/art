# Kagami Base Dockerfile
#
# Multi-stage build for optimal image size
#
# Usage:
#   docker build -t kagami:latest .
#   docker run -p 8000:8000 kagami:latest

FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements-frozen.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY packages/ packages/
COPY config/ config/

# Production stage
FROM python:3.11-slim

WORKDIR /app

# Copy from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /app /app

# Set Python path
ENV PYTHONPATH=/app/packages

# Create non-root user
RUN useradd -m kagami && chown -R kagami:kagami /app
USER kagami

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/vitals/probes/live')" || exit 1

# Expose API port
EXPOSE 8000

# Default command
CMD ["python", "-m", "uvicorn", "kagami_api:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
