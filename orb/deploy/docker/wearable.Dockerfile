# K os Wearable-Optimized Deployment
# Stripped-down image for edge/wearable deployment
# Optimized for low-memory, low-compute environments

FROM python:3.11-slim

WORKDIR /app

# Install only essential dependencies
COPY requirements-minimal.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy only core wearable components
COPY kagami/core/wearable/ kagami/core/wearable/
COPY kagami/core/services/ kagami/core/services/
COPY kagami/api/routes/wearable.py kagami/api/routes/
COPY kagami/api/__init__.py kagami/api/
COPY kagami/api/security.py kagami/api/
COPY kagami/__init__.py kagami/

# NOTE: Embedding model is downloaded at runtime or pre-cached externally
# For edge deployment, use sentence-transformers/all-MiniLM-L6-v2 (22M params)
# or BAAI/bge-small-en-v1.5 (33M params) instead of large models

ENV PYTHONPATH=/app
ENV KAGAMI_WEARABLE_MODE=1
ENV KAGAMI_EDGE_LLM=qwen3:0.6b
ENV KAGAMI_EDGE_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

EXPOSE 8001

# Health check for wearable deployments
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8001/health || exit 1

CMD ["uvicorn", "kagami_api:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
