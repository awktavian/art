"""Test embedding generation consolidation.

Verifies that all embedding generation in the codebase delegates to
the canonical EmbeddingService, ensuring consistency and eliminating
duplicate embedding implementations.

Phase 3 of Receipt Pipeline Optimization (Dec 2025).
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import os
from unittest.mock import MagicMock, patch

import numpy as np
import torch


@pytest.fixture(autouse=True)
def _test_mode():
    """Force test mode for all tests."""
    os.environ["KAGAMI_TEST_MODE"] = "1"
    os.environ["KAGAMI_TEST_FAST_EMBEDDINGS"] = "1"


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService for delegation testing."""
    with patch("kagami.core.services.embedding_service.get_embedding_service") as mock_get:
        mock_svc = MagicMock()

        # Mock can return either numpy or torch depending on return_tensor parameter
        def embed_text_mock(text: Any, dimension: Any = 512, return_tensor: Any = False) -> Any:
            vec = np.random.rand(dimension).astype(np.float32)
            if return_tensor:
                return torch.from_numpy(vec)
            return vec

        mock_svc.embed_text = MagicMock(side_effect=embed_text_mock)
        mock_svc.embedding_dim = 512
        mock_get.return_value = mock_svc
        yield mock_svc


class TestEmbeddingConsolidation:
    """Test that all embedding generation delegates to EmbeddingService."""

    def test_embedding_service_is_canonical(self) -> Any:
        """Test that EmbeddingService works as the canonical implementation."""
        from kagami.core.services.embedding_service import get_embedding_service

        svc = get_embedding_service()
        vec = svc.embed_text("test query", dimension=512)

        assert vec is not None
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (512,)
        assert vec.dtype == np.float32

    def test_storage_routing_delegates_to_embedding_service(self, mock_embedding_service) -> None:
        """Test that storage_routing._embed_text delegates to EmbeddingService."""
        from kagami.core.services.storage_routing import UnifiedStorageRouter

        router = UnifiedStorageRouter()
        result = router._embed_text("test query")

        # Verify delegation occurred (storage_routing passes return_tensor=True)
        mock_embedding_service.embed_text.assert_called_once_with(
            "test query", dimension=mock_embedding_service.embedding_dim, return_tensor=True
        )

        # Verify result is converted to torch.Tensor
        assert result is not None
        assert isinstance(result, torch.Tensor)

    def test_weaviate_adapter_delegates_to_embedding_service(self, mock_embedding_service) -> None:
        """Test that weaviate_e8_adapter._try_embed_text delegates to EmbeddingService."""
        from kagami_integrations.elysia.weaviate_e8_adapter import (
            WeaviateE8Adapter,
            WeaviateE8Config,
        )

        config = WeaviateE8Config(url="http://localhost:8080", api_key="test", vector_dim=512)
        adapter = WeaviateE8Adapter(config)

        result = adapter._try_embed_text("test query")

        # Verify delegation occurred
        mock_embedding_service.embed_text.assert_called_once_with("test query", dimension=512)

        # Verify result is converted to torch.Tensor
        assert result is not None
        assert isinstance(result, torch.Tensor)
        assert result.shape == (512,)

    def test_no_duplicate_embedding_implementations(self) -> None:
        """Test that we don't have duplicate embedding implementations.

        This test verifies that the old duplicate implementations (OpenAI, Cohere, etc.)
        have been removed and all code delegates to EmbeddingService.
        """
        import inspect

        from kagami.core.services.storage_routing import UnifiedStorageRouter
        from kagami_integrations.elysia.weaviate_e8_adapter import WeaviateE8Adapter

        # Get source code for _embed_text methods
        storage_source = inspect.getsource(UnifiedStorageRouter._embed_text)
        weaviate_source = inspect.getsource(WeaviateE8Adapter._try_embed_text)

        # Verify they delegate to EmbeddingService
        assert "get_embedding_service" in storage_source, (
            "storage_routing._embed_text should delegate to EmbeddingService"
        )
        assert "get_embedding_service" in weaviate_source, (
            "weaviate_e8_adapter._try_embed_text should delegate to EmbeddingService"
        )

        # Verify no direct API calls (old duplicate implementations)
        forbidden_patterns = ["OpenAI", "Cohere", "openai.embeddings", "cohere.embed"]
        for pattern in forbidden_patterns:
            assert pattern not in storage_source, (
                f"storage_routing._embed_text should not directly call {pattern}"
            )
            assert pattern not in weaviate_source, (
                f"weaviate_e8_adapter._try_embed_text should not directly call {pattern}"
            )

    @pytest.mark.asyncio
    async def test_end_to_end_embedding_consistency(self) -> None:
        """Test that all embedding paths produce consistent results."""
        from kagami.core.services.embedding_service import get_embedding_service
        from kagami.core.services.storage_routing import UnifiedStorageRouter
        from kagami_integrations.elysia.weaviate_e8_adapter import (
            WeaviateE8Adapter,
            WeaviateE8Config,
        )

        test_text = "test query for consistency"

        # Get embeddings from all sources
        svc = get_embedding_service()
        vec_service = svc.embed_text(test_text, dimension=512)

        router = UnifiedStorageRouter()
        vec_storage = router._embed_text(test_text)

        config = WeaviateE8Config(url="http://localhost:8080", api_key="test", vector_dim=512)
        adapter = WeaviateE8Adapter(config)
        vec_weaviate = adapter._try_embed_text(test_text)

        # All should produce embeddings (not None)
        assert vec_service is not None
        assert vec_storage is not None
        assert vec_weaviate is not None

        # Convert to numpy for comparison
        if isinstance(vec_storage, torch.Tensor):
            vec_storage_np = vec_storage.cpu().numpy()
        else:
            vec_storage_np = vec_storage

        if isinstance(vec_weaviate, torch.Tensor):
            vec_weaviate_np = vec_weaviate.cpu().numpy()
        else:
            vec_weaviate_np = vec_weaviate

        # All should have same dimension
        assert vec_service.shape == (512,)
        assert vec_storage_np.shape == (512,)
        assert vec_weaviate_np.shape == (512,)

        # All should be normalized (approximately unit norm)
        assert 0.9 < np.linalg.norm(vec_service) < 1.1
        assert 0.9 < np.linalg.norm(vec_storage_np) < 1.1
        assert 0.9 < np.linalg.norm(vec_weaviate_np) < 1.1

        # All should be identical (same underlying service, deterministic hash in test mode)
        np.testing.assert_allclose(vec_service, vec_storage_np, rtol=1e-5, atol=1e-7)
        np.testing.assert_allclose(vec_service, vec_weaviate_np, rtol=1e-5, atol=1e-7)


class TestEmbeddingServiceFeatures:
    """Test that EmbeddingService supports all required features."""

    def test_configurable_dimension(self) -> None:
        """Test that EmbeddingService supports configurable dimensions."""
        from kagami.core.services.embedding_service import get_embedding_service

        svc = get_embedding_service()

        # Test various dimensions (E8 levels)
        for dim in [14, 52, 78, 133, 248, 512]:
            vec = svc.embed_text("test", dimension=dim)
            assert vec.shape == (dim,), f"Failed for dimension {dim}"

    def test_caching(self) -> None:
        """Test that EmbeddingService caches embeddings."""
        from kagami.core.services.embedding_service import get_embedding_service

        svc = get_embedding_service()

        # Clear cache
        svc._cache.clear()

        # First call - cache miss
        vec1 = svc.embed_text("test query", dimension=512)
        stats1 = svc._cache.stats()

        # Second call - cache hit
        vec2 = svc.embed_text("test query", dimension=512)
        stats2 = svc._cache.stats()

        # Verify caching worked
        assert stats2["hits"] > stats1["hits"], "Cache should have more hits after second call"
        np.testing.assert_array_equal(vec1, vec2, err_msg="Cached embedding should match")

    def test_error_handling(self) -> None:
        """Test that EmbeddingService handles errors gracefully."""
        from kagami.core.services.embedding_service import get_embedding_service

        svc = get_embedding_service()

        # Empty string should still work (fallback to hash)
        vec_empty = svc.embed_text("", dimension=512)
        assert vec_empty is not None
        assert vec_empty.shape == (512,)

        # Long text should work
        vec_long = svc.embed_text("test " * 1000, dimension=512)
        assert vec_long is not None
        assert vec_long.shape == (512,)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
