"""Comprehensive tests for Unified Storage Router.

Tests routing to Weaviate, Redis, CockroachDB, and etcd.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami.core.services.storage_routing import (
    STORAGE_ROUTING,
    DataCategory,
    StorageBackend,
    StorageConfig,
    UnifiedStorageRouter,
    get_storage_router,
)


class TestDataCategory:
    """Test DataCategory enum."""

    def test_all_categories_exist(self):
        """Test that all expected categories exist."""
        assert hasattr(DataCategory, "VECTOR")
        assert hasattr(DataCategory, "CACHE")
        assert hasattr(DataCategory, "RELATIONAL")
        assert hasattr(DataCategory, "COORDINATION")
        assert hasattr(DataCategory, "PATTERN")
        assert hasattr(DataCategory, "RECEIPT")

    def test_category_values(self):
        """Test category values are strings."""
        assert isinstance(DataCategory.VECTOR.value, str)
        assert isinstance(DataCategory.CACHE.value, str)


class TestStorageBackend:
    """Test StorageBackend enum."""

    def test_all_backends_exist(self):
        """Test that all expected backends exist."""
        assert hasattr(StorageBackend, "WEAVIATE")
        assert hasattr(StorageBackend, "REDIS")
        assert hasattr(StorageBackend, "COCKROACHDB")
        assert hasattr(StorageBackend, "ETCD")
        assert hasattr(StorageBackend, "MEMORY")


class TestStorageRouting:
    """Test storage routing rules."""

    def test_routing_mapping(self):
        """Test that routing map contains all categories."""
        assert DataCategory.VECTOR in STORAGE_ROUTING
        assert DataCategory.PATTERN in STORAGE_ROUTING
        assert DataCategory.CACHE in STORAGE_ROUTING
        assert DataCategory.RELATIONAL in STORAGE_ROUTING
        assert DataCategory.COORDINATION in STORAGE_ROUTING

    def test_vector_routes_to_weaviate(self):
        """Test that vector data routes to Weaviate."""
        assert STORAGE_ROUTING[DataCategory.VECTOR] == StorageBackend.WEAVIATE

    def test_cache_routes_to_redis(self):
        """Test that cache data routes to Redis."""
        assert STORAGE_ROUTING[DataCategory.CACHE] == StorageBackend.REDIS

    def test_relational_routes_to_cockroach(self):
        """Test that relational data routes to CockroachDB."""
        assert STORAGE_ROUTING[DataCategory.RELATIONAL] == StorageBackend.COCKROACHDB

    def test_coordination_routes_to_etcd(self):
        """Test that coordination data routes to etcd."""
        assert STORAGE_ROUTING[DataCategory.COORDINATION] == StorageBackend.ETCD

    def test_pattern_routes_to_weaviate(self):
        """Test that pattern data routes to Weaviate."""
        assert STORAGE_ROUTING[DataCategory.PATTERN] == StorageBackend.WEAVIATE


class TestStorageConfig:
    """Test StorageConfig dataclass."""

    def test_default_config(self):
        """Test default storage configuration."""
        config = StorageConfig()

        assert config.weaviate_enabled
        assert config.redis_enabled
        assert config.cockroach_enabled
        assert config.etcd_enabled
        assert "redis://" in config.redis_url
        assert "postgresql://" in config.cockroach_url

    def test_custom_config(self):
        """Test custom storage configuration."""
        config = StorageConfig(
            weaviate_enabled=False,
            redis_url="redis://custom:6380",
            cockroach_url="postgresql://custom:26258/db",
        )

        assert not config.weaviate_enabled
        assert config.redis_url == "redis://custom:6380"
        assert config.cockroach_url == "postgresql://custom:26258/db"


class TestUnifiedStorageRouter:
    """Test UnifiedStorageRouter class."""

    def test_router_initialization(self):
        """Test router initializes correctly."""
        router = UnifiedStorageRouter()

        assert router.config is not None
        assert router._weaviate is None
        assert router._redis is None
        assert router._cockroach is None
        assert router._etcd is None

    def test_router_with_custom_config(self):
        """Test router with custom config."""
        config = StorageConfig(redis_url="redis://test:6379")
        router = UnifiedStorageRouter(config)

        assert router.config.redis_url == "redis://test:6379"

    def test_get_backend(self):
        """Test getting backend for data category."""
        router = UnifiedStorageRouter()

        assert router.get_backend(DataCategory.VECTOR) == StorageBackend.WEAVIATE
        assert router.get_backend(DataCategory.CACHE) == StorageBackend.REDIS
        assert router.get_backend(DataCategory.RELATIONAL) == StorageBackend.COCKROACHDB
        assert router.get_backend(DataCategory.COORDINATION) == StorageBackend.ETCD

    def test_get_backend_fallback(self):
        """Test that unknown categories fall back to Redis."""
        router = UnifiedStorageRouter()

        # Create a mock category that's not in routing
        class UnknownCategory:
            pass

        backend = router.get_backend(UnknownCategory())  # type: ignore
        assert backend == StorageBackend.REDIS

    @pytest.mark.asyncio
    async def test_get_weaviate_lazy_load(self):
        """Test lazy loading of Weaviate adapter."""
        router = UnifiedStorageRouter()

        with patch("kagami.core.services.storage_routing.get_weaviate_adapter") as mock_get:
            mock_adapter = MagicMock()
            mock_get.return_value = mock_adapter

            # First call loads
            adapter1 = router._get_weaviate()
            assert adapter1 is mock_adapter
            mock_get.assert_called_once()

            # Second call uses cached
            adapter2 = router._get_weaviate()
            assert adapter2 is mock_adapter
            assert mock_get.call_count == 1

    def test_get_weaviate_import_error(self):
        """Test Weaviate lazy load handles import error."""
        router = UnifiedStorageRouter()

        with patch(
            "kagami.core.services.storage_routing.get_weaviate_adapter", side_effect=ImportError
        ):
            adapter = router._get_weaviate()
            assert adapter is None

    def test_get_redis_lazy_load(self):
        """Test lazy loading of Redis client."""
        router = UnifiedStorageRouter()

        with patch("kagami.core.services.storage_routing.RedisClientFactory") as mock_factory:
            mock_client = MagicMock()
            mock_factory.get_client.return_value = mock_client

            client1 = router._get_redis()
            assert client1 is mock_client

            client2 = router._get_redis()
            assert client2 is mock_client
            assert mock_factory.get_client.call_count == 1

    def test_get_cockroach_lazy_load(self):
        """Test lazy loading of CockroachDB client."""
        router = UnifiedStorageRouter()

        with patch("kagami.core.services.storage_routing.CockroachDB") as mock_db:
            mock_instance = MagicMock()
            mock_db.return_value = mock_instance

            db1 = router._get_cockroach()
            assert db1 is mock_instance

    def test_get_etcd_lazy_load(self):
        """Test lazy loading of etcd client."""
        router = UnifiedStorageRouter()

        with patch("kagami.core.services.storage_routing.get_etcd_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client

            client1 = router._get_etcd()
            assert client1 is mock_client

    @pytest.mark.asyncio
    async def test_coerce_embedding_to_torch_with_tensor(self):
        """Test coercing torch tensor embedding."""
        router = UnifiedStorageRouter()

        with patch("kagami.core.services.storage_routing.torch") as mock_torch:
            mock_tensor = MagicMock()
            mock_torch.Tensor = type(mock_tensor)

            result = router._coerce_embedding_to_torch(mock_tensor)
            assert result is mock_tensor

    @pytest.mark.asyncio
    async def test_coerce_embedding_to_torch_with_numpy(self):
        """Test coercing numpy array embedding."""
        router = UnifiedStorageRouter()

        with patch("kagami.core.services.storage_routing.torch") as mock_torch:
            with patch("kagami.core.services.storage_routing.np") as mock_np:
                mock_array = MagicMock()
                mock_np.ndarray = type(mock_array)
                mock_tensor = MagicMock()
                mock_torch.from_numpy.return_value.float.return_value = mock_tensor

                result = router._coerce_embedding_to_torch(mock_array)
                mock_torch.from_numpy.assert_called_once()

    @pytest.mark.asyncio
    async def test_coerce_embedding_to_torch_with_list(self):
        """Test coercing list embedding."""
        router = UnifiedStorageRouter()

        with patch("kagami.core.services.storage_routing.torch") as mock_torch:
            mock_tensor = MagicMock()
            mock_torch.tensor.return_value = mock_tensor

            result = router._coerce_embedding_to_torch([1.0, 2.0, 3.0])
            mock_torch.tensor.assert_called_once()

    @pytest.mark.asyncio
    async def test_embed_text(self):
        """Test text embedding generation."""
        router = UnifiedStorageRouter()

        with patch("kagami.core.services.storage_routing.get_embedding_service") as mock_get:
            mock_service = MagicMock()
            mock_service.embedding_dim = 768
            mock_tensor = MagicMock()
            mock_service.embed_text.return_value = mock_tensor
            mock_get.return_value = mock_service

            result = router._embed_text("test text")

            assert result is mock_tensor
            mock_service.embed_text.assert_called_once_with(
                "test text",
                dimension=768,
                return_tensor=True,
            )

    @pytest.mark.asyncio
    async def test_embed_text_error_handling(self):
        """Test text embedding handles errors."""
        router = UnifiedStorageRouter()

        with patch(
            "kagami.core.services.storage_routing.get_embedding_service", side_effect=ImportError
        ):
            result = router._embed_text("test text")
            assert result is None

    @pytest.mark.asyncio
    async def test_store_vector(self):
        """Test storing vector data."""
        router = UnifiedStorageRouter()

        mock_weaviate = AsyncMock()
        mock_weaviate.store.return_value = "uuid-123"
        router._weaviate = mock_weaviate

        uuid = await router.store_vector(
            content="test content",
            embedding=None,
            metadata={"key": "value"},
        )

        assert uuid == "uuid-123"
        mock_weaviate.connect.assert_called_once()
        mock_weaviate.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_vector_no_weaviate(self):
        """Test storing vector when Weaviate unavailable."""
        router = UnifiedStorageRouter()
        router._weaviate = None

        with patch.object(router, "_get_weaviate", return_value=None):
            uuid = await router.store_vector(content="test", embedding=None)
            assert uuid is None

    @pytest.mark.asyncio
    async def test_search_semantic(self):
        """Test semantic search."""
        router = UnifiedStorageRouter()

        mock_weaviate = AsyncMock()
        mock_results = [{"content": "result 1"}, {"content": "result 2"}]
        mock_weaviate.search_similar.return_value = mock_results
        router._weaviate = mock_weaviate

        results = await router.search_semantic(
            query="test query",
            limit=10,
            colony_filter="nexus",
        )

        assert results == mock_results
        mock_weaviate.connect.assert_called_once()
        mock_weaviate.search_similar.assert_called()

    @pytest.mark.asyncio
    async def test_search_semantic_no_weaviate(self):
        """Test semantic search when Weaviate unavailable."""
        router = UnifiedStorageRouter()
        router._weaviate = None

        with patch.object(router, "_get_weaviate", return_value=None):
            results = await router.search_semantic(query="test")
            assert results == []

    @pytest.mark.asyncio
    async def test_store_pattern(self):
        """Test storing stigmergy pattern."""
        router = UnifiedStorageRouter()

        with patch("kagami.core.services.storage_routing.get_weaviate_pattern_store") as mock_get:
            mock_store = AsyncMock()
            mock_store.load_patterns.return_value = {}
            mock_store.save_pattern.return_value = True
            mock_get.return_value = mock_store

            success = await router.store_pattern(
                action="test_action",
                domain="test_domain",
                success=True,
                duration=1.5,
            )

            assert success
            mock_store.load_patterns.assert_called_once()
            mock_store.save_pattern.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_pattern_update_existing(self):
        """Test updating existing pattern."""
        router = UnifiedStorageRouter()

        with patch("kagami.core.services.storage_routing.get_weaviate_pattern_store") as mock_get:
            with patch("kagami.core.services.storage_routing.WeaviatePattern") as mock_pattern:
                mock_store = AsyncMock()

                # Create existing pattern
                existing = MagicMock()
                existing.success_count = 5
                existing.failure_count = 1
                existing.avg_duration = 1.0
                existing.access_count = 6

                mock_store.load_patterns.return_value = {("test_action", "test_domain"): existing}
                mock_store.save_pattern.return_value = True
                mock_get.return_value = mock_store

                success = await router.store_pattern(
                    action="test_action",
                    domain="test_domain",
                    success=True,
                    duration=2.0,
                )

                assert success
                assert existing.success_count == 6
                assert existing.access_count == 7

    @pytest.mark.asyncio
    async def test_store_pattern_error_handling(self):
        """Test pattern storage handles errors."""
        router = UnifiedStorageRouter()

        with patch(
            "kagami.core.services.storage_routing.get_weaviate_pattern_store",
            side_effect=ImportError,
        ):
            success = await router.store_pattern(
                action="test",
                domain="test",
                success=True,
            )
            assert not success

    @pytest.mark.asyncio
    async def test_cache_set(self):
        """Test setting cache value."""
        router = UnifiedStorageRouter()

        mock_redis = AsyncMock()
        router._redis = mock_redis

        success = await router.cache_set(
            key="test_key",
            value={"data": "value"},
            ttl=300,
        )

        assert success
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_set_no_redis(self):
        """Test cache set when Redis unavailable."""
        router = UnifiedStorageRouter()
        router._redis = None

        with patch.object(router, "_get_redis", return_value=None):
            success = await router.cache_set("key", "value")
            assert not success

    @pytest.mark.asyncio
    async def test_cache_get(self):
        """Test getting cache value."""
        router = UnifiedStorageRouter()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"data": "value"}'
        router._redis = mock_redis

        value = await router.cache_get("test_key")

        assert value == {"data": "value"}
        mock_redis.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_cache_get_no_value(self):
        """Test cache get with no value."""
        router = UnifiedStorageRouter()

        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        router._redis = mock_redis

        value = await router.cache_get("nonexistent")
        assert value is None

    @pytest.mark.asyncio
    async def test_cache_get_no_redis(self):
        """Test cache get when Redis unavailable."""
        router = UnifiedStorageRouter()
        router._redis = None

        with patch.object(router, "_get_redis", return_value=None):
            value = await router.cache_get("key")
            assert value is None

    @pytest.mark.asyncio
    async def test_store_receipt_to_weaviate(self):
        """Test storing receipt to Weaviate."""
        router = UnifiedStorageRouter()

        mock_weaviate = AsyncMock()
        mock_weaviate.store.return_value = "receipt-uuid"
        router._weaviate = mock_weaviate

        receipt = {
            "event_name": "test_event",
            "phase": "execution",
            "status": "success",
            "colony": "nexus",
            "correlation_id": "corr-123",
        }

        uuid = await router.store_receipt_to_weaviate(receipt)

        assert uuid == "receipt-uuid"
        mock_weaviate.connect.assert_called_once()
        mock_weaviate.store.assert_called_once()

        # Check that content was constructed
        call_args = mock_weaviate.store.call_args
        content = call_args[0][0]
        assert "action:test_event" in content
        assert "phase:execution" in content
        assert "status:success" in content

    @pytest.mark.asyncio
    async def test_store_receipt_with_error(self):
        """Test storing receipt with error information."""
        router = UnifiedStorageRouter()

        mock_weaviate = AsyncMock()
        mock_weaviate.store.return_value = "receipt-uuid"
        router._weaviate = mock_weaviate

        receipt = {
            "event_name": "test_event",
            "phase": "execution",
            "status": "error",
            "colony": "nexus",
            "error": "Something went wrong",
        }

        uuid = await router.store_receipt_to_weaviate(receipt)

        call_args = mock_weaviate.store.call_args
        content = call_args[0][0]
        assert "error:Something went wrong" in content

    def test_get_status(self):
        """Test getting storage status."""
        router = UnifiedStorageRouter()

        status = router.get_status()

        assert "weaviate" in status
        assert "redis" in status
        assert "cockroachdb" in status
        assert "etcd" in status
        assert "routing" in status

        assert status["weaviate"]["enabled"]
        assert not status["weaviate"]["connected"]  # Not loaded yet

    def test_get_status_with_loaded_backends(self):
        """Test status with loaded backends."""
        router = UnifiedStorageRouter()
        router._weaviate = MagicMock()
        router._redis = MagicMock()

        status = router.get_status()

        assert status["weaviate"]["connected"]
        assert status["redis"]["connected"]


class TestGlobalRouter:
    """Test global router singleton."""

    def test_get_storage_router_singleton(self):
        """Test that get_storage_router returns singleton."""
        router1 = get_storage_router()
        router2 = get_storage_router()

        assert router1 is router2

    def test_get_storage_router_returns_router(self):
        """Test that get_storage_router returns UnifiedStorageRouter."""
        router = get_storage_router()

        assert isinstance(router, UnifiedStorageRouter)


@pytest.mark.asyncio
async def test_storage_router_integration():
    """Integration test: routing to different backends."""
    router = UnifiedStorageRouter()

    # Test routing decisions
    assert router.get_backend(DataCategory.VECTOR) == StorageBackend.WEAVIATE
    assert router.get_backend(DataCategory.CACHE) == StorageBackend.REDIS
    assert router.get_backend(DataCategory.RELATIONAL) == StorageBackend.COCKROACHDB
    assert router.get_backend(DataCategory.COORDINATION) == StorageBackend.ETCD
    assert router.get_backend(DataCategory.PATTERN) == StorageBackend.WEAVIATE

    # Test status retrieval
    status = router.get_status()
    assert len(status) >= 5  # At least 4 backends + routing


@pytest.mark.asyncio
async def test_storage_router_cache_workflow():
    """Integration test: cache workflow."""
    router = UnifiedStorageRouter()

    mock_redis = AsyncMock()
    router._redis = mock_redis

    # Store value
    mock_redis.set.return_value = True
    success = await router.cache_set("key1", {"data": "test"}, ttl=60)
    assert success

    # Retrieve value
    mock_redis.get.return_value = '{"data": "test"}'
    value = await router.cache_get("key1")
    assert value == {"data": "test"}

    # Value not found
    mock_redis.get.return_value = None
    value = await router.cache_get("nonexistent")
    assert value is None
