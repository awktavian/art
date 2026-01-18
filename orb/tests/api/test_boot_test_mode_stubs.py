"""Test mode stubs for expensive initialization.

Validates that etcd and HAL can be skipped in test mode,
reducing test startup time by 2-3 seconds per app instantiation.

Test Plan:
1. Verify etcd startup is skipped in test mode
2. Verify HAL startup is skipped in test mode
3. Verify stubs satisfy health check requirements
4. Verify normal mode still works (KAGAMI_*_TEST_ENABLED=1)
"""

from __future__ import annotations


import pytest
import os
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kagami.boot.actions.init import startup_etcd
from kagami.boot.actions.registration import startup_hal
from kagami.core.boot_mode import is_test_mode
from kagami_hal.types import HALStatus, Platform


@pytest.fixture
def app() -> FastAPI:
    """Create a test FastAPI app."""
    app = FastAPI()
    app.state.redis_ready = True
    return app


class TestETCDTestModeStub:
    """Test etcd startup skipping in test mode."""

    @pytest.mark.asyncio
    async def test_etcd_skipped_in_test_mode(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify etcd is skipped in test mode unless explicitly enabled."""
        # Ensure test mode is active
        monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
        assert is_test_mode(), "KAGAMI_TEST_MODE should enable test mode"

        # Clear explicit enable flag
        monkeypatch.delenv("KAGAMI_ETCD_TEST_ENABLED", raising=False)
        monkeypatch.delenv("KAGAMI_OFFLINE_MODE", raising=False)

        # Call startup
        await startup_etcd(app)

        # Verify app state
        assert app.state.etcd_pool is None, "etcd_pool should be None"
        assert app.state.etcd_ready is True, "etcd_ready should be True (mocked)"

    @pytest.mark.asyncio
    async def test_etcd_enabled_with_flag(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify etcd init proceeds when KAGAMI_ETCD_TEST_ENABLED=1."""
        monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
        monkeypatch.setenv("KAGAMI_ETCD_TEST_ENABLED", "1")
        monkeypatch.delenv("KAGAMI_OFFLINE_MODE", raising=False)

        # Mock the actual etcd client pool to avoid real connection
        mock_pool = MagicMock()

        with patch("kagami.core.consensus.etcd_client.get_etcd_client_pool") as mock_get:
            mock_get.return_value = mock_pool

            await startup_etcd(app)

        # Verify real init proceeded
        assert app.state.etcd_pool is mock_pool, "Should use real pool when flag is set"
        assert app.state.etcd_ready is True

    @pytest.mark.asyncio
    async def test_etcd_skipped_offline_mode(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify etcd is skipped in offline mode regardless of test mode."""
        monkeypatch.setenv("KAGAMI_OFFLINE_MODE", "1")
        monkeypatch.delenv("KAGAMI_TEST_MODE", raising=False)

        await startup_etcd(app)

        assert app.state.etcd_pool is None
        assert app.state.etcd_ready is False


class TestHALTestModeStub:
    """Test HAL startup skipping in test mode."""

    @pytest.mark.asyncio
    async def test_hal_skipped_in_test_mode(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify HAL is skipped in test mode, stub is created."""
        monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
        monkeypatch.delenv("KAGAMI_HAL_TEST_ENABLED", raising=False)
        assert is_test_mode()

        await startup_hal(app)

        # Verify stub is created
        assert app.state.hal_manager is not None, "HAL stub should be created"

        # Verify stub has required interface
        assert hasattr(app.state.hal_manager, "get_status"), "Stub must have get_status method"

        # Verify stub returns correct status
        status = app.state.hal_manager.get_status()
        assert isinstance(status, HALStatus), "get_status must return HALStatus"
        assert status.platform == Platform.UNKNOWN
        assert status.mock_mode is True

    @pytest.mark.asyncio
    async def test_hal_stub_satisfies_health_checks(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify HAL stub can be used in health check endpoints."""
        monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
        monkeypatch.delenv("KAGAMI_HAL_TEST_ENABLED", raising=False)

        await startup_hal(app)

        # Simulate what health check endpoints do
        hal_manager = app.state.hal_manager
        status = hal_manager.get_status()

        # These should not raise
        assert status.platform.value in (
            "unknown",
            "linux",
            "darwin",
            "windows",
            "android",
            "ios",
            "watchos",
            "wearos",
            "embedded",
            "wasm",
            "agui",
        )
        assert isinstance(status.mock_mode, bool)
        assert isinstance(status.display_available, bool)
        assert isinstance(status.audio_available, bool)

    @pytest.mark.asyncio
    async def test_hal_enabled_with_flag(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify HAL init proceeds when KAGAMI_HAL_TEST_ENABLED=1."""
        monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
        monkeypatch.setenv("KAGAMI_HAL_TEST_ENABLED", "1")

        # Mock the HAL manager
        mock_hal = MagicMock()
        mock_status = HALStatus(
            platform=Platform.MACOS,
            display_available=True,
            audio_available=True,
            input_available=True,
            sensors_available=False,
            power_available=True,
            mock_mode=False,
            adapters_initialized=5,
            adapters_failed=0,
        )
        mock_hal.get_status.return_value = mock_status

        with patch("kagami.core.hal.manager.get_hal_manager") as mock_get:
            mock_get.return_value = mock_hal
            await startup_hal(app)

        # Verify real init proceeded
        assert app.state.hal_manager is mock_hal

    @pytest.mark.asyncio
    async def test_hal_stub_all_fields_match_dataclass(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify HAL stub returns all required HALStatus fields."""
        monkeypatch.setenv("KAGAMI_TEST_MODE", "1")

        await startup_hal(app)

        status = app.state.hal_manager.get_status()

        # Verify all dataclass fields are present
        required_fields = {
            "platform",
            "display_available",
            "audio_available",
            "input_available",
            "sensors_available",
            "power_available",
            "mock_mode",
        }

        for field in required_fields:
            assert hasattr(status, field), f"Status missing field: {field}"


class TestBootTimeImprovement:
    """Verify test mode stubs reduce startup overhead."""

    @pytest.mark.asyncio
    async def test_etcd_stub_returns_immediately(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify etcd stub doesn't perform network operations."""
        import time

        monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
        monkeypatch.delenv("KAGAMI_ETCD_TEST_ENABLED", raising=False)

        start = time.perf_counter()
        await startup_etcd(app)
        elapsed = time.perf_counter() - start

        # Stub should be near-instant (< 50ms, accounting for CI overhead)
        assert elapsed < 0.05, f"etcd stub took too long: {elapsed:.3f}s"
        assert app.state.etcd_ready is True

    @pytest.mark.asyncio
    async def test_hal_stub_returns_immediately(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify HAL stub doesn't perform hardware detection."""
        import time

        monkeypatch.setenv("KAGAMI_TEST_MODE", "1")
        monkeypatch.delenv("KAGAMI_HAL_TEST_ENABLED", raising=False)

        start = time.perf_counter()
        await startup_hal(app)
        elapsed = time.perf_counter() - start

        # Stub should be near-instant (< 50ms, accounting for CI overhead)
        assert elapsed < 0.05, f"HAL stub took too long: {elapsed:.3f}s"
        assert app.state.hal_manager is not None


class TestFullModeUnaffected:
    """Verify full mode behavior is unaffected by test stubs.

    Note: These tests verify the logic paths, but pytest always sets PYTEST_CURRENT_TEST,
    forcing is_test_mode() to return True. So we mock is_test_mode() at source to simulate full mode.
    """

    @pytest.mark.asyncio
    async def test_full_mode_etcd_not_skipped(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify etcd is NOT skipped when is_test_mode() returns False."""
        # Mock is_test_mode to return False (simulating full mode) - patch at source
        with patch("kagami.core.boot_mode.is_test_mode", return_value=False):
            # Mock etcd client
            mock_pool = MagicMock()

            with patch("kagami.core.consensus.etcd_client.get_etcd_client_pool") as mock_get:
                mock_get.return_value = mock_pool

                await startup_etcd(app)

            # Verify real init was attempted (not skipped)
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_full_mode_hal_not_skipped(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify HAL is NOT skipped when is_test_mode() returns False."""
        # Mock is_test_mode to return False (simulating full mode) - patch at source
        with patch("kagami.core.boot_mode.is_test_mode", return_value=False):
            mock_hal = MagicMock()
            status = HALStatus(
                platform=Platform.LINUX,
                display_available=True,
                audio_available=True,
                input_available=True,
                sensors_available=False,
                power_available=True,
                mock_mode=False,
                adapters_initialized=5,
                adapters_failed=0,
            )
            mock_hal.get_status.return_value = status

            with patch("kagami.core.hal.manager.get_hal_manager") as mock_get:
                mock_get.return_value = mock_hal
                await startup_hal(app)

            # Verify real init was attempted (not skipped)
            mock_get.assert_called_once()
