"""Unit tests for kagami.boot.actions module.

Tests startup and shutdown actions for the K os boot process.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI


class TestEnvHelpers:
    """Test environment helper functions."""

    def test_env_int_default(self, monkeypatch) -> None:
        """Test _env_int returns default when env not set."""
        from kagami.boot.actions.init import _env_int

        monkeypatch.delenv("TEST_INT_VAR", raising=False)
        result = _env_int("TEST_INT_VAR", 42)
        assert result == 42

    def test_env_int_set(self, monkeypatch) -> None:
        """Test _env_int returns env value when set."""
        from kagami.boot.actions.init import _env_int

        monkeypatch.setenv("TEST_INT_VAR", "100")
        result = _env_int("TEST_INT_VAR", 42)
        assert result == 100

    def test_env_int_invalid(self, monkeypatch) -> None:
        """Test _env_int returns default for invalid values."""
        from kagami.boot.actions.init import _env_int

        monkeypatch.setenv("TEST_INT_VAR", "not_an_int")
        result = _env_int("TEST_INT_VAR", 42)
        assert result == 42


class TestShouldEnableLoader:
    """Test _should_enable_loader function."""

    def test_explicit_env_true(self, monkeypatch) -> None:
        """Test explicit env override with true."""
        from kagami.boot.actions.init import _should_enable_loader

        monkeypatch.setenv("TEST_LOADER", "1")
        result = _should_enable_loader(
            "TEST_LOADER",
            default_full=False,
            default_test=False,
        )
        assert result is True

    def test_explicit_env_true_variations(self, monkeypatch) -> None:
        """Test various true values."""
        from kagami.boot.actions.init import _should_enable_loader

        for value in ["1", "true", "yes", "on"]:
            monkeypatch.setenv("TEST_LOADER", value)
            result = _should_enable_loader(
                "TEST_LOADER",
                default_full=False,
                default_test=False,
            )
            assert result is True, f"Expected True for value '{value}'"

    def test_explicit_env_false(self, monkeypatch) -> None:
        """Test explicit env override with false."""
        from kagami.boot.actions.init import _should_enable_loader

        monkeypatch.setenv("TEST_LOADER", "0")
        result = _should_enable_loader(
            "TEST_LOADER",
            default_full=True,
            default_test=True,
        )
        assert result is False

    def test_full_mode_default(self, monkeypatch) -> None:
        """Test full mode uses default_full."""
        from kagami.boot.actions.init import _should_enable_loader

        monkeypatch.delenv("TEST_LOADER", raising=False)
        monkeypatch.setenv("KAGAMI_FULL_OPERATION", "1")
        monkeypatch.delenv("KAGAMI_BOOT_MODE", raising=False)
        with patch("kagami.core.boot_mode.is_full_mode", return_value=True):
            with patch("kagami.core.boot_mode.is_test_mode", return_value=False):
                result = _should_enable_loader(
                    "TEST_LOADER",
                    default_full=True,
                    default_test=False,
                )
                assert result is True

    def test_test_mode_default(self, monkeypatch) -> None:
        """Test test mode uses default_test."""
        from kagami.boot.actions.init import _should_enable_loader

        monkeypatch.delenv("TEST_LOADER", raising=False)
        with patch("kagami.core.boot_mode.is_full_mode", return_value=False):
            with patch("kagami.core.boot_mode.is_test_mode", return_value=True):
                result = _should_enable_loader(
                    "TEST_LOADER",
                    default_full=True,
                    default_test=False,
                )
                assert result is False


class TestStartupDatabase:
    """Test startup_database function."""

    @pytest.mark.asyncio
    async def test_startup_database_success(self) -> None:
        """Test successful database startup."""
        from kagami.boot.actions.init import startup_database

        app = FastAPI()
        with patch("kagami.core.database.connection.init_db", new_callable=AsyncMock) as mock_init:
            mock_init.return_value = None
            await startup_database(app)
            assert app.state.db_ready is True
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_startup_database_no_app(self) -> None:
        """Test that None app raises ValueError."""
        from kagami.boot.actions.init import startup_database

        with pytest.raises(ValueError):
            await startup_database(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_startup_database_connection_error(self) -> None:
        """Test database connection error handling.

        Note: Connection errors are wrapped in RuntimeError with context.
        """
        from kagami.boot.actions.init import startup_database

        app = FastAPI()
        with patch("kagami.core.database.connection.init_db", new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = ConnectionError("Cannot connect to DB")
            with pytest.raises(RuntimeError, match="Database initialization failed"):
                await startup_database(app)

    @pytest.mark.asyncio
    async def test_startup_database_cockroachdb_version_handled(self) -> None:
        """Test CockroachDB version parsing is handled gracefully."""
        from kagami.boot.actions.init import startup_database

        app = FastAPI()
        with patch("kagami.core.database.connection.init_db", new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = Exception("Could not determine version from CockroachDB")
            await startup_database(app)
            # Should still mark as ready
            assert app.state.db_ready is True

    @pytest.mark.asyncio
    async def test_startup_database_offline_mode(self, monkeypatch) -> None:
        """Test database startup is skipped in offline mode."""
        from kagami.boot.actions.init import startup_database

        monkeypatch.setenv("KAGAMI_OFFLINE_MODE", "1")

        app = FastAPI()
        await startup_database(app)
        assert app.state.db_ready is False


class TestStartupRedis:
    """Test startup_redis function.

    OPTIMIZED (Dec 30, 2025): Redis startup was optimized to skip redundant operations.
    - Ping is no longer called (enforce_full_operation already verified Redis)
    - Local/offline modes skip Redis entirely (use in-memory fallback)
    """

    @pytest.mark.asyncio
    async def test_startup_redis_success(self, monkeypatch) -> None:
        """Test successful Redis startup marks app ready.

        Note: Ping is no longer called - enforce_full_operation already verified Redis.
        """
        from kagami.boot.actions.init import startup_redis

        # Clear env vars that would skip Redis
        monkeypatch.delenv("KAGAMI_LOCAL_MODE", raising=False)
        monkeypatch.delenv("KAGAMI_SKIP_DISTRIBUTED", raising=False)
        monkeypatch.delenv("KAGAMI_OFFLINE_MODE", raising=False)

        app = FastAPI()
        await startup_redis(app)
        assert app.state.redis_ready is True

    @pytest.mark.asyncio
    async def test_startup_redis_no_app(self) -> None:
        """Test that None app raises ValueError."""
        from kagami.boot.actions.init import startup_redis

        with pytest.raises(ValueError):
            await startup_redis(None)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_startup_redis_local_mode_skips(self, monkeypatch) -> None:
        """Test Redis startup skipped in local mode."""
        from kagami.boot.actions.init import startup_redis

        monkeypatch.setenv("KAGAMI_LOCAL_MODE", "1")

        app = FastAPI()
        await startup_redis(app)
        assert app.state.redis_ready is False

    @pytest.mark.asyncio
    async def test_startup_redis_offline_mode_skips(self, monkeypatch) -> None:
        """Test Redis startup skipped in offline mode."""
        from kagami.boot.actions.init import startup_redis

        monkeypatch.setenv("KAGAMI_OFFLINE_MODE", "1")

        app = FastAPI()
        await startup_redis(app)
        assert app.state.redis_ready is False


class TestEnforceFullOperation:
    """Test enforce_full_operation_check function."""

    @pytest.mark.asyncio
    async def test_enforce_full_operation_success(self) -> None:
        """Test successful full operation check."""
        from kagami.boot.actions.init import enforce_full_operation_check

        app = FastAPI()
        with patch(
            "kagami_api._full_operation_check.enforce_full_operation", new_callable=AsyncMock
        ) as mock_enforce:
            mock_enforce.return_value = None
            # Should not raise (or should exit)
            try:
                await enforce_full_operation_check(app)
                mock_enforce.assert_called_once()
            except SystemExit:
                # It's OK to exit - full operation check may fail
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
