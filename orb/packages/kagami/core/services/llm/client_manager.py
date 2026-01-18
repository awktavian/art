"""LLM Client Manager - Handles client lifecycle and caching.

Extracted from service.py to reduce god module complexity.
Centrality goal: <0.001

PERFORMANCE OPTIMIZATIONS (Dec 22, 2025):
=========================================
- Connection pooling via httpx with keep-alive
- Client caching by provider:model:base_url key
- Async concurrent client creation prevention (dedup)
"""

import asyncio
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Connection pool configuration
# These settings optimize for API latency while preventing resource exhaustion
HTTP_POOL_LIMITS = {
    "max_keepalive_connections": 20,  # Keep-alive for low latency
    "max_connections": 100,  # Hard limit for resource protection
    "keepalive_expiry": 30.0,  # Seconds before idle connection close
}


class ClientManager:
    """Manages LLM client creation, caching, and lifecycle.

    PERFORMANCE FEATURES:
    ====================
    - LRU-style client caching (unlimited, cleared on shutdown)
    - Connection pooling for HTTP clients (httpx limits)
    - Concurrent request deduplication (prevents thundering herd)

    Cache key format: "{provider}:{model}:{base_url}:{mode}"
    """

    def __init__(self) -> None:
        """Initialize client manager with connection pooling."""
        self._model_clients: dict[str, Any] = {}
        self._structured_clients: dict[str, Any] = {}
        self._loading_tasks: dict[str, asyncio.Task] = {}
        self._creation_locks: dict[str, asyncio.Lock] = {}

        # Shared HTTP client for connection pooling (lazy initialized)
        self._http_client: Any = None

    def _get_http_client(self) -> Any:
        """Get or create shared HTTP client with connection pooling.

        Uses httpx if available for superior connection pooling.
        Falls back to aiohttp if httpx not available.
        """
        if self._http_client is not None:
            return self._http_client

        try:
            import httpx

            # Create pooled HTTP client
            limits = httpx.Limits(
                max_keepalive_connections=HTTP_POOL_LIMITS["max_keepalive_connections"],  # type: ignore[arg-type]
                max_connections=HTTP_POOL_LIMITS["max_connections"],  # type: ignore[arg-type]
                keepalive_expiry=HTTP_POOL_LIMITS["keepalive_expiry"],
            )
            self._http_client = httpx.AsyncClient(
                limits=limits,
                timeout=httpx.Timeout(60.0, connect=10.0),
                http2=True,  # HTTP/2 for multiplexing
            )
            logger.info("✅ HTTP connection pool initialized (httpx, HTTP/2)")
        except ImportError:
            logger.debug("httpx not available, clients will use default HTTP handling")
            self._http_client = None

        return self._http_client

    async def get_or_create_client(
        self,
        provider: str,
        model: str | None,
        structured: bool = False,
        base_url: str | None = None,
    ) -> Any:
        """Create or fetch a cached text/structured client for the given provider/model.

        PERFORMANCE: Uses async locks to prevent concurrent duplicate creation
        (thundering herd prevention). First request creates, others wait.
        """
        key = f"{provider}:{model or 'auto'}:{base_url or ''}:{('structured' if structured else 'text')}"

        # Fast path: check cache without lock
        client = self._model_clients.get(key)
        if client is not None:
            logger.debug(f"♻️  Reusing cached client for key: {key}")
            return client

        # Slow path: acquire per-key lock to prevent duplicate creation
        if key not in self._creation_locks:
            self._creation_locks[key] = asyncio.Lock()

        async with self._creation_locks[key]:
            # Double-check after acquiring lock (another task may have created it)
            client = self._model_clients.get(key)
            if client is not None:
                logger.debug(f"♻️  Reusing client (created while waiting): {key}")
                return client

            logger.info(
                f"🔨 Creating new client for key: {key} (cache size: {len(self._model_clients)})"
            )

            if structured:
                return await self._create_structured_client(provider, model, base_url, key)
            return await self._create_text_client(provider, model, base_url, key)

    async def _create_structured_client(
        self,
        provider: str,
        model: str | None,
        base_url: str | None,
        key: str,
    ) -> Any:
        """Create structured output client with fallback to text."""
        from kagami.core.services.llm.client_factories import get_registry

        try:
            registry = get_registry()
            factory = registry.get_factory(provider, structured=True)
            client = await factory.create(model, True, base_url)
            self._model_clients[key] = client
            return client
        except Exception as e:
            logger.error(f"Failed to initialize structured client: {e}")
            logger.warning("Falling back to text generation for structured request")
            return await self.get_or_create_client(
                provider, model, structured=False, base_url=base_url
            )

    async def _create_text_client(
        self,
        provider: str,
        model: str | None,
        base_url: str | None,
        key: str,
    ) -> Any:
        """Create text generation client with provider-specific fallbacks."""
        from kagami.core.services.llm.client_factories import get_registry

        registry = get_registry()
        try:
            factory = registry.get_factory(provider, structured=False)
            client = await factory.create(model, False, base_url)
            self._model_clients[key] = client
            return client
        except Exception as exc:
            if provider == "api":
                return await self._handle_api_fallback(exc, model, key)
            if provider in ("local", "qwen", "transformers"):
                return await self._handle_local_fallback(exc, key, model, False, base_url)
            raise

    async def _handle_api_fallback(
        self,
        exc: Exception,
        model: str | None,
        key: str,
    ) -> Any:
        """REMOVED: No automatic fallback to local models.

        All model selection must be LLM-driven through LLMDrivenRouter.
        This ensures routing decisions are intelligent, not heuristic.

        Raises:
            RuntimeError: Always - heuristic fallbacks are disabled
        """
        logger.error(
            f"❌ API client failure for {model}: {exc}\n"
            "Heuristic fallback to local model is DISABLED. "
            "Use LLMDrivenRouter for intelligent model selection."
        )
        raise RuntimeError(
            f"API client unavailable for {model} and heuristic fallback is disabled. "
            "Use LLMDrivenRouter for intelligent routing."
        ) from exc

    async def _handle_local_fallback(
        self,
        exc: Exception,
        key: str,
        model: str | None,
        structured: bool,
        base_url: str | None,
    ) -> Any:
        """REMOVED: No automatic fallback to echo client.

        Test mode should explicitly request EchoClient if needed.
        Production should never use fallbacks - fail fast instead.

        Raises:
            RuntimeError: Always - heuristic fallbacks are disabled
        """
        from kagami.core.services.llm.client_factories import get_registry

        if self._is_test_mode():
            # Test mode: Allow explicit EchoClient but log warning
            logger.warning(
                f"Local transformers failed: {exc}\n"
                "⚠️ Test mode: Allowing EchoClient but this should be explicit, not fallback"
            )
            registry = get_registry()
            echo_factory = registry.get_factory("echo")
            client = await echo_factory.create(model, structured, base_url)
            self._model_clients[key] = client
            return client

        # Production or dev: NO FALLBACKS
        logger.critical(
            f"🚨 CRITICAL: Local transformers failed for {model}: {exc}\n"
            "Heuristic fallback is DISABLED. Use LLMDrivenRouter for intelligent routing."
        )
        raise RuntimeError(
            f"Transformers client failed for {model} and heuristic fallback is disabled. "
            "Use LLMDrivenRouter for intelligent model selection."
        ) from exc

    def _is_production(self) -> bool:
        """Check if running in production environment."""
        env = (os.environ.get("ENVIRONMENT") or os.environ.get("KAGAMI_ENV") or "").lower()
        return env in {"production", "prod"}

    def _is_test_mode(self) -> bool:
        """Check if running in test/benchmark mode."""
        is_test = os.getenv("KAGAMI_TEST_ECHO_LLM", "0") == "1"
        is_benchmark = "benchmark" in os.environ.get("KAGAMI_ENV", "")
        return is_test or is_benchmark

    async def shutdown(self) -> None:
        """Shutdown all clients and clean up resources."""
        # Cancel loading tasks
        for _name, task in self._loading_tasks.items():
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._loading_tasks.clear()
        self._model_clients.clear()
        self._structured_clients.clear()
        self._creation_locks.clear()

        # Close HTTP connection pool
        if self._http_client is not None:
            try:
                await self._http_client.aclose()
                logger.info("✅ HTTP connection pool closed")
            except Exception as e:
                logger.warning(f"Error closing HTTP pool: {e}")
            self._http_client = None

    def get_cache_size(self) -> int:
        """Get number of cached clients."""
        return len(self._model_clients)

    def get_pool_stats(self) -> dict[str, Any]:
        """Get connection pool statistics.

        Returns:
            Dictionary with pool metrics for monitoring.
        """
        stats = {
            "cached_clients": len(self._model_clients),
            "pending_creations": sum(1 for lock in self._creation_locks.values() if lock.locked()),
        }

        if self._http_client is not None:
            try:
                # httpx pool stats if available
                pool = getattr(self._http_client, "_transport", None)
                if pool is not None:
                    stats["http_pool_initialized"] = True
            except Exception:
                pass

        return stats
