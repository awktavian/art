"""KagamiOS API - Main Application Entry Point.

CREATED: December 14, 2025
UPDATED: December 18, 2025 - Fixed to use create_app_v2 with full route registration
PURPOSE: Production API server with full K OS functionality

This is the main entry point that imports the proper FastAPI application factory
which includes ALL routes:
- Authentication (JWT, API keys, RBAC)
- Intent Detection (LANG/2 parser, Forge operations)
- Colony Management (7 agents, Fano routing)
- LLM Services (multi-provider inference)
- World Model (RSSM, sessions, sync)
- Mind (receipts, thoughts, goals, dynamics)
- Compression (E8 quantization)
- Safety (CBF verification)
- Routing (Fano plane coordination)
- And 100+ other endpoints

DEPLOYMENT:
- Development: uvicorn kagami_api.main:app --reload
- Production: gunicorn -w 4 -k uvicorn.workers.UvicornWorker kagami_api.main:app

MONITORING:
- OpenAPI docs: /docs
- Prometheus metrics: /metrics
- Health check: /health
- Readiness: /health/ready

ENVIRONMENT VARIABLES:
- DATABASE_URL: PostgreSQL/CockroachDB connection (default: localhost:26257)
- SECRET_KEY: JWT signing key (required for auth)
- OPENAI_API_KEY: OpenAI provider key (optional)
- ANTHROPIC_API_KEY: Anthropic provider key (optional)
- ENVIRONMENT: production/development (default: development)
- LOG_LEVEL: DEBUG/INFO/WARNING/ERROR (default: INFO)

Reference: docs/BUSINESS_STRATEGY.md (Phase 2 API Launch)
"""

from __future__ import annotations

import logging
import os

# Import the proper factory that includes full route registration
from kagami_api.create_app_v2 import create_app_v2

logger = logging.getLogger(__name__)

# =============================================================================
# APPLICATION INSTANCE
# =============================================================================

# Create the application using the V2 factory with full route registration
# This includes ALL 100+ routes via register_all_routes()
app = create_app_v2(
    title="KagamiOS API",
    description=(
        "Production API for K OS - AI Life Companions\n\n"
        "**Features:**\n"
        "- 🔐 Authentication (JWT, API keys, RBAC)\n"
        "- 🧠 Intent Detection (LANG/2 parser)\n"
        "- 🤖 Colony Management (7 specialized agents)\n"
        "- 🌐 LLM Services (multi-provider inference)\n"
        "- 🌍 World Model (RSSM, active inference)\n"
        "- 📝 Receipt System (unified event tracking)\n"
        "- 🔒 Safety (CBF verification, h(x) >= 0)\n"
        "- 🗜️ Compression (E8 quantization)\n"
        "- 🧭 Routing (Fano plane coordination)\n\n"
        "**Authentication:** Bearer token or X-API-Key header required\n"
        "**Rate Limits:** Vary by tier (Free: 60/min, Pro: 600/min)\n\n"
        "Powered by exceptional Lie algebras and catastrophe theory."
    ),
    version="1.0.0",
)

# =============================================================================
# DEVELOPMENT SERVER
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    # Use centralized logging (lazy init via logging_setup.py)
    # NOTE: Removed logging.basicConfig() to avoid conflicting with centralized setup
    log_level = os.getenv("LOG_LEVEL", "INFO").lower()

    logger.info("KagamiOS API - Starting Development Server")
    logger.info("Server: http://localhost:8000 | Docs: /docs | Health: /health")

    # Start Uvicorn server
    uvicorn.run(
        "kagami_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=log_level,
    )
