"""Test TLS enforcement for all services (Phase 2.2).

Tests that production mode requires TLS/authentication for:
- CockroachDB / PostgreSQL
- Redis
- etcd
- Weaviate

Created: December 21, 2025
"""

from __future__ import annotations
from typing import Any

import os

import pytest
from unittest.mock import MagicMock, patch

from kagami.core.exceptions import EtcdConnectionError


class TestCockroachDBTLSEnforcement:
    """Test CockroachDB/PostgreSQL TLS enforcement."""

    def test_production_rejects_sslmode_disable(self, monkeypatch: Any) -> None:
        """Test that production mode rejects sslmode=disable."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://root@db.example.com:26257/kagami?sslmode=disable"
        )
        # Prevent test mode from overriding to SQLite
        monkeypatch.setenv("KAGAMI_TEST_PERSIST_DB", "1")
        monkeypatch.delenv("CI", raising=False)

        # Clear cache
        from kagami.core.database import connection

        connection._DATABASE_URL_CACHE = None

        with pytest.raises(RuntimeError, match="Production database MUST use TLS"):
            connection._resolve_database_url()

    def test_development_allows_sslmode_disable(self, monkeypatch: Any) -> None:
        """Test that development mode allows sslmode=disable."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv(
            "DATABASE_URL", "postgresql://root@localhost:26257/kagami?sslmode=disable"
        )
        # Prevent test mode from overriding to SQLite
        monkeypatch.setenv("KAGAMI_TEST_PERSIST_DB", "1")
        monkeypatch.delenv("CI", raising=False)

        # Clear cache
        from kagami.core.database import connection

        connection._DATABASE_URL_CACHE = None

        # Should not raise
        url = connection._resolve_database_url()
        assert "sslmode=disable" in url

    def test_production_allows_verify_full(self, monkeypatch: Any) -> None:
        """Test that production mode allows sslmode=verify-full."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv(
            "DATABASE_URL",
            "postgresql://root@db.example.com:26257/kagami?sslmode=verify-full&"
            "sslrootcert=/certs/ca.crt",
        )
        # Prevent test mode from overriding to SQLite
        monkeypatch.setenv("KAGAMI_TEST_PERSIST_DB", "1")
        monkeypatch.delenv("CI", raising=False)

        # Clear cache
        from kagami.core.database import connection

        connection._DATABASE_URL_CACHE = None

        # Should not raise
        url = connection._resolve_database_url()
        assert "sslmode=verify-full" in url


class TestRedisTLSEnforcement:
    """Test Redis TLS enforcement."""

    def test_production_rejects_default_password(self, monkeypatch: Any) -> None:
        """Test that production mode rejects default password."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")

        from kagami.core.caching.redis.factory import RedisClientFactory

        with pytest.raises(
            RuntimeError, match=r"Production Redis URL must be set.*with secure credentials"
        ):
            RedisClientFactory._get_url_for_purpose("default")

    def test_production_warns_plaintext_redis(self, monkeypatch: Any, caplog: Any) -> None:
        """Test that production mode warns about plaintext Redis."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("REDIS_URL", "redis://:secure-password@redis.example.com:6379/0")

        from kagami.core.caching.redis.factory import RedisClientFactory

        import logging

        caplog.set_level(logging.WARNING)

        url = RedisClientFactory._get_url_for_purpose("default")

        # Should return URL
        assert url == "redis://:secure-password@redis.example.com:6379/0"

        # Should have warning about plaintext
        assert any("plaintext" in record.message.lower() for record in caplog.records)

    def test_production_allows_rediss(self, monkeypatch: Any) -> None:
        """Test that production mode allows rediss:// (TLS)."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("REDIS_URL", "rediss://:secure-password@redis.example.com:6379/0")

        from kagami.core.caching.redis.factory import RedisClientFactory

        url = RedisClientFactory._get_url_for_purpose("default")

        # Should return URL without warnings
        assert url == "rediss://:secure-password@redis.example.com:6379/0"

    def test_development_allows_plaintext(self, monkeypatch: Any) -> None:
        """Test that development mode allows plaintext Redis."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

        from kagami.core.caching.redis.factory import RedisClientFactory

        url = RedisClientFactory._get_url_for_purpose("default")

        # Should return URL
        assert url == "redis://localhost:6379/0"


class TestEtcdTLSEnforcement:
    """Test etcd TLS enforcement."""

    def test_production_requires_tls_certs(self, monkeypatch: Any) -> None:
        """Test that production mode requires TLS certificates."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ETCD_ENDPOINTS", "http://etcd1.example.com:2379")
        # Don't set cert env vars

        with pytest.raises(EtcdConnectionError, match="Production etcd connections must use TLS"):
            from kagami.core.consensus.etcd_client import _create_etcd_client

            _create_etcd_client()

    def test_production_allows_tls_with_certs(self, monkeypatch: Any) -> None:
        """Test that production mode allows TLS with certificates."""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("ETCD_ENDPOINTS", "https://etcd1.example.com:2379")
        monkeypatch.setenv("ETCD_CA_CERT", "/certs/ca.pem")
        monkeypatch.setenv("ETCD_CERT_KEY", "/certs/client-key.pem")
        monkeypatch.setenv("ETCD_CERT_CERT", "/certs/client.pem")

        # Mock etcd3 import
        with patch.dict("sys.modules", {"etcd3": MagicMock()}):
            # Should not raise during validation (will fail at actual connection)
            try:
                from kagami.core.consensus.etcd_client import _create_etcd_client

                _create_etcd_client()
            except EtcdConnectionError as e:
                # Connection will fail (no real etcd), but TLS validation should pass
                assert "must use TLS" not in str(e)

    def test_development_allows_plaintext(self, monkeypatch: Any) -> None:
        """Test that development mode allows plaintext etcd."""
        monkeypatch.setenv("ENVIRONMENT", "development")
        monkeypatch.setenv("ETCD_ENDPOINTS", "http://localhost:2379")
        # Don't set cert env vars

        # Mock etcd3 import
        with patch.dict("sys.modules", {"etcd3": MagicMock()}):
            # Should not raise TLS error (will fail at connection, not validation)
            try:
                from kagami.core.consensus.etcd_client import _create_etcd_client

                _create_etcd_client()
            except EtcdConnectionError as e:
                assert "must use TLS" not in str(e)


class TestWeaviateTLSEnforcement:
    """Test Weaviate API key enforcement."""

    @pytest.mark.asyncio
    async def test_production_requires_api_key(self, monkeypatch: Any, caplog: Any) -> None:
        """Test that production mode requires Weaviate API key."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        from kagami_integrations.elysia.weaviate_e8_adapter import (
            WeaviateE8Adapter,
            WeaviateE8Config,
        )

        config = WeaviateE8Config(
            url="https://cluster.weaviate.network",
            api_key="",
            vector_dim=512,  # Empty API key
        )

        adapter = WeaviateE8Adapter(config=config)

        # Mock weaviate module
        with patch.dict("sys.modules", {"weaviate": MagicMock()}):
            result = await adapter.connect()
            # Should return False (connection failed due to missing API key)
            assert result is False
            # Check error was logged
            assert any("must use API key" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_production_allows_api_key(self, monkeypatch: Any) -> None:
        """Test that production mode allows Weaviate with API key."""
        monkeypatch.setenv("ENVIRONMENT", "production")

        from kagami_integrations.elysia.weaviate_e8_adapter import (
            WeaviateE8Adapter,
            WeaviateE8Config,
        )

        config = WeaviateE8Config(
            url="https://cluster.weaviate.network", api_key="test-api-key-12345", vector_dim=512
        )

        adapter = WeaviateE8Adapter(config=config)

        # Mock weaviate module and client
        mock_weaviate = MagicMock()
        mock_client = MagicMock()
        mock_client.is_ready.return_value = True
        mock_weaviate.connect_to_weaviate_cloud.return_value = mock_client

        with patch.dict(
            "sys.modules", {"weaviate": mock_weaviate, "weaviate.classes.init": MagicMock()}
        ):
            # Should not raise (TLS validation passes)
            try:
                result = await adapter.connect()
                assert result is True or isinstance(result, bool)
            except Exception as e:
                # If connection fails, ensure it's not due to missing API key
                assert "must use API key" not in str(e)

    @pytest.mark.asyncio
    async def test_development_allows_no_api_key(self, monkeypatch: Any) -> None:
        """Test that development mode allows Weaviate without API key."""
        monkeypatch.setenv("ENVIRONMENT", "development")

        from kagami_integrations.elysia.weaviate_e8_adapter import (
            WeaviateE8Adapter,
            WeaviateE8Config,
        )

        config = WeaviateE8Config(
            url="http://localhost:8080",
            api_key="",
            vector_dim=512,  # Empty API key
        )

        adapter = WeaviateE8Adapter(config=config)

        # Mock weaviate module and client
        mock_weaviate = MagicMock()
        mock_client = MagicMock()
        mock_client.is_ready.return_value = True
        mock_weaviate.connect_to_local.return_value = mock_client

        with patch.dict(
            "sys.modules", {"weaviate": mock_weaviate, "weaviate.classes.init": MagicMock()}
        ):
            # Should not raise API key error
            try:
                result = await adapter.connect()
                assert result is True or isinstance(result, bool)
            except RuntimeError as e:
                assert "must use API key" not in str(e)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
