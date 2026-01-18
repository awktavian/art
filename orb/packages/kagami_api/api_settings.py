"""Centralized API settings (Proxy).

Delegates to ``kagami.core.config.api_defaults`` to break the Core→API
dependency while keeping legacy import paths stable for API modules.
"""

from __future__ import annotations

from kagami.core.config import api_defaults as _defaults

# Re-export default values so existing imports keep working.
IDEMPOTENCY_CACHE_TTL_SECONDS = _defaults.IDEMPOTENCY_CACHE_TTL_SECONDS
IDEMPOTENCY_PERSIST_TTL_MINUTES = _defaults.IDEMPOTENCY_PERSIST_TTL_MINUTES
WS_IDEMPOTENCY_TTL_SECONDS = _defaults.WS_IDEMPOTENCY_TTL_SECONDS
RATE_LIMIT_AUTH_RPM = _defaults.RATE_LIMIT_AUTH_RPM
RATE_LIMIT_API_RPM = _defaults.RATE_LIMIT_API_RPM
RATE_LIMIT_PUBLIC_RPM = _defaults.RATE_LIMIT_PUBLIC_RPM
HTTP_CLIENT_TIMEOUT_SECONDS = _defaults.HTTP_CLIENT_TIMEOUT_SECONDS

__all__ = [
    "HTTP_CLIENT_TIMEOUT_SECONDS",
    "IDEMPOTENCY_CACHE_TTL_SECONDS",
    "IDEMPOTENCY_PERSIST_TTL_MINUTES",
    "RATE_LIMIT_API_RPM",
    "RATE_LIMIT_AUTH_RPM",
    "RATE_LIMIT_PUBLIC_RPM",
    "WS_IDEMPOTENCY_TTL_SECONDS",
]
