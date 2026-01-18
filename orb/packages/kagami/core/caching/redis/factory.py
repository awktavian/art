"""Unified Redis client factory for K os.

Per CODE_DUPLICATION_REPORT.md (2025-10-04):
Consolidates 4+ different Redis client creation patterns.

HARDENED (Dec 22, 2025): No fake Redis fallbacks. Real Redis is MANDATORY.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Literal

logger = logging.getLogger(__name__)
redis = None
redis_async = None


def _ensure_redis() -> None:
    """Ensure redis module is imported."""
    global redis, redis_async
    if redis is None:
        try:
            import redis as _redis
            import redis.asyncio as _redis_async

            redis = _redis
            redis_async = _redis_async
        except ImportError:
            logger.error("redis package not installed. Install with: pip install redis")
            raise


class RedisClientFactory:
    """Factory for Redis clients with different configurations.

    Provides unified interface for all Redis access in K os:
    - Default: General-purpose Redis (decode_responses=True)
    - LLM cache: Binary storage (decode_responses=False)
    - Vector store: Redis Stack with modules
    - Sessions: Short-lived data

    All clients use connection pooling and health checks.
    Thread-safe client creation prevents connection pool exhaustion.
    """

    _clients: dict[str, Any] = {}
    _lock = threading.Lock()

    @classmethod
    def get_client(
        cls,
        purpose: Literal["default", "llm_cache", "vector_store", "sessions"] = "default",
        async_mode: bool = False,
        decode_responses: bool = True,
        **kwargs: Any,
    ) -> Any:
        """Get or create Redis client for specific purpose.

        HARDENED (Dec 22, 2025): Real Redis is MANDATORY. No fake fallbacks.

        Thread-safe client creation prevents race conditions and connection pool exhaustion.

        Args:
            purpose: Client purpose (affects URL and config)
            async_mode: Return async client
            decode_responses: Decode bytes to strings
            **kwargs: Additional redis.from_url() arguments

        Returns:
            Redis client instance

        Raises:
            RuntimeError: If Redis connection fails (no fallback)

        Examples:
            >>> # General use
            >>> redis = RedisClientFactory.get_client('default')
            >>> redis.set('key', 'value')

            >>> # LLM cache (bytes, not strings)
            >>> llm_redis = RedisClientFactory.get_client('llm_cache', decode_responses=False)
            >>> llm_redis.set(b'key', b'value')

            >>> # Async vector store
            >>> vector_redis = await RedisClientFactory.get_client('vector_store', async_mode=True)
            >>> await vector_redis.ping()
        """
        _ensure_redis()
        if purpose == "llm_cache":
            decode_responses = False
        elif purpose in ("default", "sessions"):
            decode_responses = True
        key = f"{purpose}:{async_mode}:{decode_responses}"
        if key in cls._clients:
            return cls._clients[key]
        with cls._lock:
            if key in cls._clients:
                return cls._clients[key]

            url = cls._get_url_for_purpose(purpose)
            # OPTIMIZATION: Increased max_connections for better concurrency (Dec 2025)
            client_config = {
                "decode_responses": decode_responses,
                "socket_keepalive": True,
                "socket_connect_timeout": 5,
                "socket_timeout": 10,
                "max_connections": 200,  # Increased from 100 (Dec 20, 2025)
                **kwargs,
            }

            # Assert after _ensure_redis() guarantees these are not None
            assert redis is not None and redis_async is not None
            if async_mode:
                client = redis_async.from_url(url, **client_config)
            else:
                client = redis.from_url(url, **client_config)
            if not async_mode:
                client.ping()
                logger.info(
                    f"Redis client connected: {purpose} ({('async' if async_mode else 'sync')})"
                )
            cls._clients[key] = client
            return client

    @staticmethod
    def _get_url_for_purpose(purpose: str) -> str:
        """Get Redis URL for specific purpose.

        Checks purpose-specific env vars first, falls back to REDIS_URL.

        Args:
            purpose: Client purpose

        Returns:
            Redis URL string

        Raises:
            RuntimeError: If production mode with insecure password
        """
        url_map = {
            "llm_cache": ["LLM_REDIS_URL", "REDIS_URL"],
            "vector_store": ["REDIS_OM_URL", "REDIS_STACK_URL", "REDIS_URL"],
            "sessions": ["SESSION_REDIS_URL", "REDIS_URL"],
            "default": ["REDIS_URL"],
        }
        for env_var in url_map.get(purpose, ["REDIS_URL"]):
            url = os.getenv(env_var)
            if url:
                # SECURITY CHECK (Dec 21, 2025): Prevent production deployment with insecure Redis
                environment = os.getenv("ENVIRONMENT", "development").lower()
                if environment == "production":
                    # Check for default/weak passwords
                    if not url or "changeme" in url.lower() or url == "redis://127.0.0.1:6379/0":
                        raise RuntimeError(
                            "Production Redis URL must be set with secure credentials. "
                            f"Found insecure URL in {env_var}. "
                            f"Set proper REDIS_URL with authentication (redis://:password@host:port/db or rediss://...)"
                        )

                    # Check for TLS usage (warn if plaintext)
                    if url.startswith("redis://") and not url.startswith("redis://localhost"):
                        logger.warning(
                            "Production Redis connection uses plaintext (redis://). "
                            "Strongly recommend using TLS (rediss://) for production. "
                            "Set REDIS_URL=rediss://:password@host:6379/0"
                        )
                        # Don't fail hard - some deployments use VPN/trusted networks
                        # But log warning for security audit
                return url
        return "redis://127.0.0.1:6379/0"

    @classmethod
    async def aclose_all(cls) -> None:
        """Asynchronously close all cached Redis clients."""
        for key, client in list(cls._clients.items()):
            try:
                if hasattr(client, "aclose") and callable(client.aclose):
                    try:
                        await client.aclose()
                    except RuntimeError as exc:
                        if "Event loop is closed" in str(exc):
                            logger.debug(
                                "Skipping Redis client close for %s: event loop already closed", key
                            )
                        else:
                            logger.warning(f"Error closing async Redis client {key}: {exc}")
                elif hasattr(client, "close"):
                    client.close()
                logger.debug(f"Closed Redis client: {key}")
            except Exception as e:
                logger.warning(f"Error closing Redis client {key}: {e}")
        cls._clients.clear()

    @classmethod
    def close_all(cls) -> None:
        """Close all cached Redis clients.

        This helper is safe to call from synchronous teardown contexts. When
        running inside an active asyncio loop, prefer ``await
        RedisClientFactory.aclose_all()`` instead.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(cls.aclose_all())
            return
        if loop.is_running():
            raise RuntimeError(
                "RedisClientFactory.close_all() cannot run inside an active event loop; await RedisClientFactory.aclose_all() instead."
            )
        loop.run_until_complete(cls.aclose_all())

    @classmethod
    def get_pool_stats(cls) -> dict[str, dict[str, Any]]:
        """Get connection pool statistics for all clients.

        Returns:
            Dict mapping client keys to pool stats
        """
        stats = {}
        for key, client in cls._clients.items():
            try:
                if hasattr(client, "connection_pool"):
                    pool = client.connection_pool

                    def _safe_len(obj: Any) -> int:
                        if obj is None:
                            return 0
                        if isinstance(obj, int | float):
                            return int(obj)
                        try:
                            return len(obj)
                        except TypeError:
                            return 0

                    stats[key] = {
                        "max_connections": getattr(pool, "max_connections", None),
                        "created_connections": _safe_len(getattr(pool, "_created_connections", [])),
                        "available_connections": _safe_len(
                            getattr(pool, "_available_connections", [])
                        ),
                        "in_use_connections": _safe_len(
                            getattr(pool, "_in_use_connections", set())
                        ),
                    }
            except Exception as e:
                stats[key] = {"error": str(e)}
        return stats


import atexit


def _safe_close_all() -> None:
    try:
        RedisClientFactory.close_all()
    except Exception:
        pass


atexit.register(_safe_close_all)
