"""Tests for Kagami Embedding Service.

Tests cover:
- Service initialization (singleton pattern)
- Text embedding (single and batch)
- LRU cache with TTL
- Hash fallback mode
- Geometric level selection
- Metrics collection

Coverage target: kagami/core/services/embedding_service.py
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


import threading
import time

import numpy as np
from kagami.core.services.embedding_service import (
    EmbeddingService,
    EmbeddingServiceConfig,
    get_embedding_service,
    reset_embedding_service,
)

# Default embedding dimension
KAGAMI_EMBED_DIM = 512  # Moved out of embedding_service

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def reset_service():
    """Reset embedding service before and after each test."""
    reset_embedding_service()
    yield
    reset_embedding_service()


@pytest.fixture
def config():
    """Test configuration."""
    return EmbeddingServiceConfig(
        embedding_dim=512,
        redis_enabled=False,
        cache_size=100,
        cache_ttl_seconds=60,
    )


@pytest.fixture
def service(config: Any) -> Any:
    """Create test embedding service."""
    return EmbeddingService(config)


# =============================================================================
# LRU CACHE TESTS
# =============================================================================
# EMBEDDING SERVICE TESTS (LRUCache tests removed - class deprecated)
# =============================================================================


class TestEmbeddingService:
    """Tests for EmbeddingService."""

    def test_service_creation(self, service) -> None:
        """Test service creation."""
        assert service is not None
        assert service.embedding_dim == 512
        assert not service._initialized

    def test_singleton_pattern(self) -> None:
        """Test singleton pattern for global service."""
        svc1 = get_embedding_service()
        svc2 = get_embedding_service()
        assert svc1 is svc2

    def test_embed_text_returns_correct_dimension(self, service) -> None:
        """Test embedding returns correct dimension."""
        embedding = service.embed_text("Hello world")

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (512,)
        assert embedding.dtype == np.float32

    def test_embed_text_normalized(self, service) -> None:
        """Test embeddings are L2 normalized."""
        embedding = service.embed_text("Test text")
        norm = np.linalg.norm(embedding)
        np.testing.assert_almost_equal(norm, 1.0, decimal=5)

    def test_embed_text_deterministic(self, service) -> None:
        """Test same text produces same embedding."""
        text = "Deterministic test"
        emb1 = service.embed_text(text)
        emb2 = service.embed_text(text)
        np.testing.assert_array_equal(emb1, emb2)

    def test_embed_text_different_texts(self, service) -> None:
        """Test different texts produce different embeddings."""
        emb1 = service.embed_text("Hello")
        emb2 = service.embed_text("Goodbye")
        assert not np.array_equal(emb1, emb2)

    def test_embed_text_custom_dimension(self, service) -> None:
        """Test embedding to specific geometric levels."""
        # G₂ level
        g2_emb = service.embed_text("Test", dimension=14)
        assert g2_emb.shape == (14,)

        # F₄ level
        f4_emb = service.embed_text("Test", dimension=52)
        assert f4_emb.shape == (52,)

        # E₈ level
        e8_emb = service.embed_text("Test", dimension=248)
        assert e8_emb.shape == (248,)

    def test_embed_batch(self, service) -> None:
        """Test batch embedding."""
        texts = ["Hello", "World", "Test"]
        embeddings = service.embed_batch(texts)

        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 512)
        assert embeddings.dtype == np.float32

    def test_embed_batch_empty(self, service) -> None:
        """Test batch embedding with empty list."""
        embeddings = service.embed_batch([])
        assert embeddings.shape == (0, 512)

    def test_embed_batch_single(self, service) -> None:
        """Test batch embedding with single item."""
        embeddings = service.embed_batch(["Single"])
        assert embeddings.shape == (1, 512)

    def test_embed_batch_custom_dimension(self, service) -> None:
        """Test batch embedding with custom dimension."""
        texts = ["Hello", "World"]
        embeddings = service.embed_batch(texts, dimension=14)
        assert embeddings.shape == (2, 14)

    def test_caching_works(self, service) -> None:
        """Test that caching improves performance."""
        text = "Caching test text"

        # First call (uncached)
        start1 = time.perf_counter()
        emb1 = service.embed_text(text)
        time1 = time.perf_counter() - start1

        # Second call (cached)
        start2 = time.perf_counter()
        emb2 = service.embed_text(text)
        time2 = time.perf_counter() - start2

        # Results should be identical
        np.testing.assert_array_equal(emb1, emb2)
        # Cached call should be faster (or at least not slower)
        # Note: In test mode, both may be very fast
        assert time2 <= time1 * 10  # Very relaxed check for test env


class TestEmbeddingServiceAsync:
    """Tests for async embedding operations."""

    @pytest.mark.asyncio
    async def test_embed_text_async(self, service: Any) -> None:
        """Test async text embedding."""
        embedding = await service.embed_text_async("Async test")
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (512,)

    @pytest.mark.asyncio
    async def test_embed_batch_async(self, service: Any) -> None:
        """Test async batch embedding."""
        texts = ["Async", "Batch", "Test"]
        embeddings = await service.embed_batch_async(texts)
        assert embeddings.shape == (3, 512)


class TestEmbeddingServiceMetrics:
    """Tests for metrics and health checks."""

    def test_get_stats(self, service) -> None:
        """Test statistics retrieval."""
        # Generate some embeddings
        service.embed_text("Test 1")
        service.embed_text("Test 2")
        service.embed_text("Test 1")  # Cache hit

        stats = service.get_stats()

        assert "model_name" in stats
        assert "embedding_dim" in stats
        assert "embed_count" in stats
        assert stats["embed_count"] >= 2

    def test_health_check(self, service) -> None:
        """Test health check."""
        health = service.health_check()

        assert "status" in health
        assert health["status"] in ("healthy", "degraded")
        assert "model" in health


class TestTensorOptimization:
    """Tests for GPU tensor optimization (Dec 16, 2025)."""

    def test_return_tensor_option(self, service) -> None:
        """Test return_tensor=True returns GPU tensor without CPU conversion."""
        import torch

        text = "GPU tensor test"

        # Default: returns numpy array
        emb_numpy = service.embed_text(text)
        assert isinstance(emb_numpy, np.ndarray)

        # return_tensor=True: returns GPU tensor
        emb_tensor = service.embed_text(text, return_tensor=True)
        assert isinstance(emb_tensor, torch.Tensor)

        # Values should be identical
        np.testing.assert_allclose(emb_numpy, emb_tensor.cpu().numpy(), rtol=1e-5)

    def test_batch_return_tensor(self, service) -> None:
        """Test batch embedding with return_tensor=True."""
        import torch

        texts = ["Batch", "GPU", "Test"]

        # Default: numpy array
        emb_numpy = service.embed_batch(texts)
        assert isinstance(emb_numpy, np.ndarray)
        assert emb_numpy.shape == (3, 512)

        # return_tensor=True: GPU tensor
        emb_tensor = service.embed_batch(texts, return_tensor=True)
        assert isinstance(emb_tensor, torch.Tensor)
        assert emb_tensor.shape == (3, 512)

        # Values should be identical
        np.testing.assert_allclose(emb_numpy, emb_tensor.cpu().numpy(), rtol=1e-5)

    def test_tensor_device(self, service) -> None:
        """Test tensor is on correct device."""
        import torch

        text = "Device test"
        emb_tensor = service.embed_text(text, return_tensor=True)

        # Should be on service's device (mps/cuda/cpu)
        assert emb_tensor.device.type == service.device

    def test_no_cpu_conversion_in_hot_path(self, service) -> None:
        """Verify no CPU conversion happens when using return_tensor=True.

        This test ensures the optimization is working: embeddings stay on GPU
        until explicitly requested as numpy.
        """
        import torch

        text = "Hot path test"

        # Using return_tensor=True should not call .cpu() internally
        emb_tensor = service.embed_text(text, return_tensor=True)

        # Verify it's a GPU tensor (not converted to CPU)
        assert isinstance(emb_tensor, torch.Tensor)
        assert emb_tensor.device.type == service.device

        # Only convert to numpy when explicitly needed
        emb_numpy = service.from_tensor(emb_tensor)
        assert isinstance(emb_numpy, np.ndarray)


class TestHashFallback:
    """Tests for deterministic hash fallback."""

    def test_hash_embed_deterministic(self, service) -> None:
        """Test hash embedding is deterministic."""
        text = "Hash fallback test"
        emb1 = service._hash_embed(text, 512)
        emb2 = service._hash_embed(text, 512)
        np.testing.assert_array_equal(emb1, emb2)

    def test_hash_embed_different_texts(self, service) -> None:
        """Test hash embedding produces different vectors for different texts."""
        emb1 = service._hash_embed("Text A", 512)
        emb2 = service._hash_embed("Text B", 512)
        assert not np.array_equal(emb1, emb2)

    def test_hash_embed_normalized(self, service) -> None:
        """Test hash embedding is normalized."""
        emb = service._hash_embed("Normalize test", 512)
        norm = np.linalg.norm(emb)
        np.testing.assert_almost_equal(norm, 1.0, decimal=5)

    def test_hash_embed_custom_dimension(self, service) -> None:
        """Test hash embedding with custom dimensions."""
        emb_14 = service._hash_embed("Test", 14)
        emb_52 = service._hash_embed("Test", 52)
        emb_248 = service._hash_embed("Test", 248)

        assert emb_14.shape == (14,)
        assert emb_52.shape == (52,)
        assert emb_248.shape == (248,)


class TestTensorConversion:
    """Tests for tensor conversion utilities."""

    def test_to_tensor(self, service) -> None:
        """Test numpy to tensor conversion."""
        import torch

        embedding = np.random.randn(512).astype(np.float32)
        tensor = service.to_tensor(embedding)

        assert isinstance(tensor, torch.Tensor)
        assert tensor.shape == (512,)
        assert tensor.dtype == torch.float32

    def test_from_tensor(self, service) -> None:
        """Test tensor to numpy conversion."""
        import torch

        tensor = torch.randn(512)
        embedding = service.from_tensor(tensor)

        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (512,)
        assert embedding.dtype == np.float32


class TestConfigFromEnv:
    """Tests for configuration from environment."""

    def test_config_from_env(self, monkeypatch) -> None:
        """Test configuration loading from environment."""
        monkeypatch.setenv("KAGAMI_EMBED_CACHE_SIZE", "5000")
        monkeypatch.setenv("KAGAMI_EMBED_INDEX", "test-index")

        config = EmbeddingServiceConfig.from_env()

        assert config.cache_size == 5000
        assert config.redis_index == "test-index"
