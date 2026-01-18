# Kagami Agent Runtime — Live Markdown Agents
#
# Provides REST, WebSocket, Voice, and Video endpoints for agents
# deployed to api.awkronos.com
#
# Build: docker build -f deploy/cloudrun/agents/Dockerfile -t kagami-agents .
# Run: docker run -p 8000:8000 kagami-agents
#
# Created: January 7, 2026

FROM python:3.12-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt requirements-frozen.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# Production image
FROM python:3.12-slim

WORKDIR /app

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy wheels and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Copy application code
COPY packages/ ./packages/
COPY apps/agents/ ./apps/agents/

# Copy agent source files
COPY apps/agents/_agents/ ./agents/

# Environment
ENV PYTHONPATH=/app/packages \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    KAGAMI_ENVIRONMENT=production

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "kagami_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
