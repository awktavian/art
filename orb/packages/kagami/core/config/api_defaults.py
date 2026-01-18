"""Centralized API settings (env-backed).

Moved from kagami_api.api_settings to kagami.core.config.api_defaults to break Core->API cycle.
"""

from __future__ import annotations

from kagami.core.config import get_int_config

# Idempotency
IDEMPOTENCY_CACHE_TTL_SECONDS: int = get_int_config("KAGAMI_IDEMPOTENCY_CACHE_TTL", 300)
IDEMPOTENCY_PERSIST_TTL_MINUTES: int = get_int_config("KAGAMI_IDEMPOTENCY_PERSIST_TTL_MINUTES", 10)

# WebSocket/session idempotency
WS_IDEMPOTENCY_TTL_SECONDS: int = get_int_config("KAGAMI_WS_IDEMPOTENCY_TTL_SECONDS", 300)

# Rate limiting defaults (requests per minute)
RATE_LIMIT_AUTH_RPM: int = get_int_config("RATE_LIMIT_AUTH_RPM", 10)
RATE_LIMIT_API_RPM: int = get_int_config("RATE_LIMIT_API_RPM", 100)
RATE_LIMIT_PUBLIC_RPM: int = get_int_config("RATE_LIMIT_PUBLIC_RPM", 200)

# HTTP client timeouts (seconds)
HTTP_CLIENT_TIMEOUT_SECONDS: int = get_int_config("HTTP_CLIENT_TIMEOUT_SECONDS", 10)
