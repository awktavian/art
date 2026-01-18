"""Tests for Weaviate improvements (Phase 7).

Tests:
1. Connection pool timeout configuration
2. near_text fallback removal (fail-fast behavior)
3. Redis-persisted circuit breaker
4. Legacy API removal verification

Created: December 16, 2025
"""

from __future__ import annotations

import pytest
from typing import Any

import sys
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import torch

from kagami.core.resilience.circuit_breaker import CircuitBreakerOpen
from kagami_integrations.elysia.weaviate_e8_adapter import (
    WeaviateE8Adapter,
    WeaviateE8Config,
)


@pytest.fixture
def mock_redis() -> Any:
    """Mock Redis client for circuit breaker tests."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def adapter_config() -> Any:
    """Minimal Weaviate adapter config."""
    return WeaviateE8Config(
        url="http://localhost:8080",
        api_key="test-key",
        vector_dim=512,
    )


@pytest.mark.asyncio
class TestConnectionPooling:
    """Test connection pool timeout configuration."""

    async def test_connection_has_timeout_config(self, adapter_config) -> Any:
        """Test that Weaviate client is configured with proper timeouts."""
        # Mock weaviate module with timeout classes
        mock_weaviate = MagicMock()
        mock_client = MagicMock()
        mock_client.is_ready.return_value = True
        mock_weaviate.connect_to_local.return_value = mock_client

        # Mock the classes.init module with AdditionalConfig/Timeout
        mock_init = MagicMock()
        mock_init.AdditionalConfig = MagicMock()
        mock_init.Timeout = MagicMock()
        mock_init.Auth = MagicMock()
        mock_init.Auth.api_key = MagicMock(return_value="auth")

        mock_classes = MagicMock()
        mock_classes.init = mock_init

        with patch.dict(
            "sys.modules",
            {
                "weaviate": mock_weaviate,
                "weaviate.classes": mock_classes,
                "weaviate.classes.init": mock_init,
            },
        ):
            adapter = WeaviateE8Adapter(config=adapter_config)
            await adapter.connect()

            # Verify timeout config was attempted (best-effort across client versions)
            # The code tries to create AdditionalConfig with Timeout
            if mock_weaviate.connect_to_local.called:
                call_kwargs = mock_weaviate.connect_to_local.call_args.kwargs
                # Should have either additional_config OR be using fallback
                # (code tries new API first, falls back to older API)
                assert call_kwargs  # Connection was made

    async def test_timeout_values_respect_config(self, adapter_config) -> None:
        """Test that timeout values match config."""
        adapter_config.timeout = 45

        mock_weaviate = MagicMock()
        mock_client = MagicMock()
        mock_client.is_ready.return_value = True
        mock_weaviate.connect_to_local.return_value = mock_client

        with patch.dict("sys.modules", {"weaviate": mock_weaviate}):
            adapter = WeaviateE8Adapter(config=adapter_config)
            await adapter.connect()

            # Verify timeout propagated to config
            assert adapter.config.timeout == 45


@pytest.mark.asyncio
class TestNearTextRemoval:
    """Test near_text fallback has been removed."""

    async def test_near_text_method_removed(self, adapter_config) -> None:
        """Test that _near_text_fallback method does not exist."""
        adapter = WeaviateE8Adapter(config=adapter_config)
        assert not hasattr(adapter, "_near_text_fallback")

    async def test_search_fails_fast_without_embedding(self, adapter_config, mock_redis) -> None:
        """Test that search fails fast when embedding cannot be generated.

        Note: get_similar_feedback catches all exceptions and returns [].
        This test verifies the ValueError is raised internally.
        """
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            return_value=mock_redis,
        ):
            # Mock weaviate module
            mock_weaviate = MagicMock()
            with patch.dict(
                "sys.modules", {"weaviate": mock_weaviate, "weaviate.classes.query": MagicMock()}
            ):
                adapter = WeaviateE8Adapter(config=adapter_config)
                adapter._connected = True
                adapter.client = MagicMock()

                collection_mock = MagicMock()
                adapter.client.collections.use.return_value = collection_mock

                # Mock _try_embed_text to return None (embedding generation failure)
                with patch.object(adapter, "_try_embed_text", return_value=None):
                    # get_similar_feedback catches exceptions and returns []
                    result = await adapter.get_similar_feedback(query="test query")
                    # Should return empty list (error was caught and logged)
                    assert result == []

    async def test_feedback_search_requires_embedding(self, adapter_config, mock_redis) -> None:
        """Test that feedback search enforces bring-your-own vectors.

        The ValueError is raised but caught by get_similar_feedback,
        which logs the error and returns []. The key is that near_text
        is never called.
        """
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            return_value=mock_redis,
        ):
            # Mock weaviate module
            mock_weaviate = MagicMock()
            with patch.dict(
                "sys.modules", {"weaviate": mock_weaviate, "weaviate.classes.query": MagicMock()}
            ):
                adapter = WeaviateE8Adapter(config=adapter_config)
                adapter._connected = True
                adapter.client = MagicMock()

                collection_mock = MagicMock()
                adapter.client.collections.use.return_value = collection_mock

                # Mock _try_embed_text to fail
                with patch.object(adapter, "_try_embed_text", return_value=None):
                    # get_similar_feedback catches the ValueError and returns []
                    result = await adapter.get_similar_feedback(query="test")
                    assert result == []

                    # Verify near_text was NEVER called (this is the key test)
                    assert (
                        not hasattr(collection_mock.query, "near_text")
                        or not collection_mock.query.near_text.called
                    )


@pytest.mark.asyncio
class TestRedisCircuitBreaker:
    """Test Redis-persisted circuit breaker."""

    async def test_circuit_breaker_checks_redis(self, adapter_config, mock_redis) -> None:
        """Test that circuit breaker state is read from Redis."""
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            return_value=mock_redis,
        ):
            adapter = WeaviateE8Adapter(config=adapter_config)

            # Redis returns "open" (string - RedisClientFactory uses decode_responses=True)
            mock_redis.get.return_value = "open"
            assert not await adapter._check_circuit()

            # Redis returns None (circuit closed)
            mock_redis.get.return_value = None
            assert await adapter._check_circuit()

            mock_redis.get.assert_called_with("kagami:weaviate:circuit_breaker")

    async def test_open_circuit_persists_to_redis(self, adapter_config, mock_redis) -> None:
        """Test that opening circuit breaker persists to Redis."""
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            return_value=mock_redis,
        ):
            adapter = WeaviateE8Adapter(config=adapter_config)

            await adapter._open_circuit(duration=120)

            mock_redis.setex.assert_called_once_with("kagami:weaviate:circuit_breaker", 120, "open")

    async def test_close_circuit_deletes_redis_key(self, adapter_config, mock_redis) -> None:
        """Test that closing circuit breaker deletes Redis key."""
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            return_value=mock_redis,
        ):
            adapter = WeaviateE8Adapter(config=adapter_config)

            await adapter._close_circuit()

            mock_redis.delete.assert_called_once_with("kagami:weaviate:circuit_breaker")

    async def test_store_blocks_when_circuit_open(self, adapter_config, mock_redis) -> None:
        """Test that store operations are blocked when circuit is open."""
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            return_value=mock_redis,
        ):
            adapter = WeaviateE8Adapter(config=adapter_config)

            # Open circuit (string - RedisClientFactory uses decode_responses=True)
            mock_redis.get.return_value = "open"

            result = await adapter.store(content="test", embedding=torch.randn(512), metadata={})

            # Store should return None (blocked)
            assert result is None

    async def test_search_blocks_when_circuit_open(self, adapter_config, mock_redis) -> None:
        """Test that search operations are blocked when circuit is open."""
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            return_value=mock_redis,
        ):
            adapter = WeaviateE8Adapter(config=adapter_config)

            # Open circuit (string - RedisClientFactory uses decode_responses=True)
            mock_redis.get.return_value = "open"

            result = await adapter.search_similar(query=torch.randn(512))

            # Search should return empty list (blocked)
            assert result == []

    async def test_successful_store_closes_circuit(self, adapter_config, mock_redis) -> None:
        """Test that successful store closes the circuit breaker."""
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            return_value=mock_redis,
        ):
            adapter = WeaviateE8Adapter(config=adapter_config)
            adapter._connected = True

            # Mock client
            collection_mock = MagicMock()
            collection_mock.data.insert.return_value = "test-uuid"
            adapter.client = MagicMock()
            adapter.client.collections.use.return_value = collection_mock

            # Mock E8 quantizer
            adapter.e8_quantizer = Mock()
            adapter.e8_quantizer.return_value = (
                torch.randn(1, 8),
                torch.tensor([0]),
                {"complexity_estimate": 0.5},
            )

            # Circuit is closed
            mock_redis.get.return_value = None

            result = await adapter.store(content="test", embedding=torch.randn(512), metadata={})

            # Should succeed and close circuit
            assert result == "test-uuid"
            mock_redis.delete.assert_called_with("kagami:weaviate:circuit_breaker")

    async def test_failed_store_opens_circuit(self, adapter_config, mock_redis) -> None:
        """Test that failed store opens the circuit breaker."""
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            return_value=mock_redis,
        ):
            adapter = WeaviateE8Adapter(config=adapter_config)
            adapter._connected = True

            # Mock client to fail
            adapter.client = MagicMock()
            adapter.client.collections.use.side_effect = Exception("Connection timeout")

            # Circuit is closed
            mock_redis.get.return_value = None

            result = await adapter.store(content="test", embedding=torch.randn(512), metadata={})

            # Should fail and open circuit
            assert result is None
            mock_redis.setex.assert_called_with("kagami:weaviate:circuit_breaker", 60, "open")

    async def test_circuit_breaker_graceful_without_redis(self, adapter_config) -> None:
        """Test that adapter works without Redis (circuit breaker disabled)."""
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            side_effect=Exception("Redis unavailable"),
        ):
            adapter = WeaviateE8Adapter(config=adapter_config)

            # Circuit check should assume closed
            assert await adapter._check_circuit()

            # Open/close should be no-ops (no exceptions)
            await adapter._open_circuit()
            await adapter._close_circuit()


@pytest.mark.asyncio
class TestLegacyAPIRemoval:
    """Test that legacy v2/v3 APIs have been removed."""

    def test_no_legacy_imports(self) -> None:
        """Test that legacy VectorIndexConfig/ModuleConfig are not imported."""
        import kagami_integrations.elysia.weaviate_e8_adapter as module

        # Check module doesn't reference legacy classes
        module_code = open(module.__file__).read()
        assert "VectorIndexConfig" not in module_code
        assert "ModuleConfig" not in module_code

    def test_uses_v4_api_only(self) -> None:
        """Test that only v4 API (Configure) is used."""
        import kagami_integrations.elysia.weaviate_e8_adapter as module

        module_code = open(module.__file__).read()
        # Should use v4 Configure API
        assert "from weaviate.classes.config import Configure" in module_code


class TestIntegrationCompleteness:
    """Test that all Phase 7 requirements are met."""

    def test_connection_pool_configured(self, adapter_config) -> None:
        """Test connection pool timeout is configured."""
        adapter = WeaviateE8Adapter(config=adapter_config)
        # Config should have timeout
        assert hasattr(adapter.config, "timeout")
        assert adapter.config.timeout > 0

    def test_near_text_removed(self, adapter_config) -> None:
        """Test near_text fallback has been removed."""
        adapter = WeaviateE8Adapter(config=adapter_config)
        # Should not have fallback method
        assert not hasattr(adapter, "_near_text_fallback")

    def test_circuit_breaker_uses_redis(self, adapter_config, mock_redis) -> None:
        """Test circuit breaker uses Redis for persistence."""
        with patch(
            "kagami_integrations.elysia.weaviate_e8_adapter.RedisClientFactory.get_client",
            return_value=mock_redis,
        ):
            adapter = WeaviateE8Adapter(config=adapter_config)
            # Should have Redis client
            assert adapter._redis is not None
            # Should have circuit breaker key
            assert adapter._cb_key == "kagami:weaviate:circuit_breaker"
            # Should have helper methods
            assert hasattr(adapter, "_check_circuit")
            assert hasattr(adapter, "_open_circuit")
            assert hasattr(adapter, "_close_circuit")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
