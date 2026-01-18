"""Tests for base integration framework."""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, Mock, patch

from kagami_integrations.base import (
    BaseIntegration,
    IntegrationConfig,
    IntegrationResult,
)

pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.asyncio,
]


class MockIntegration(BaseIntegration):
    """Mock integration for testing."""

    async def _initialize_impl(self) -> None:
        pass

    async def as_tool(self) -> dict[str, str]:
        return {"name": "mock_tool"}

    async def from_tool(self, tool) -> None:
        pass


class TestIntegrationConfig:
    """Test integration configuration."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = IntegrationConfig(name="test")
        assert config.name == "test"
        assert config.kagami_url == "http://localhost:8001"
        assert config.timeout_seconds == 30.0
        assert config.max_retries == 3
        assert config.enable_receipts is True

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = IntegrationConfig(
            name="test",
            kagami_url="http://custom:9000",
            timeout_seconds=60.0,
            enable_receipts=False,
        )
        assert config.kagami_url == "http://custom:9000"
        assert config.timeout_seconds == 60.0
        assert config.enable_receipts is False


class TestIntegrationResult:
    """Test integration result."""

    def test_success_result(self) -> None:
        """Test successful result."""
        result = IntegrationResult(
            status="accepted",
            response="Success",
            correlation_id="test-123",
        )
        assert result.status == "accepted"
        assert result.response == "Success"
        assert result.correlation_id == "test-123"
        assert result.error is None

    def test_error_result(self) -> None:
        """Test error result."""
        result = IntegrationResult(
            status="error",
            response=None,
            error="Something went wrong",
        )
        assert result.status == "error"
        assert result.error == "Something went wrong"


class TestBaseIntegration:
    """Test base integration class."""

    @pytest_asyncio.fixture
    def config(self) -> IntegrationConfig:
        """Create test config."""
        return IntegrationConfig(name="test")

    async def test_initialization(self, config) -> None:
        """Test integration initialization."""
        integration = MockIntegration(config)
        assert not integration._initialized

        await integration.initialize()
        assert integration._initialized

    async def test_double_initialization(self, config) -> None:
        """Test double initialization is safe."""
        integration = MockIntegration(config)
        await integration.initialize()
        await integration.initialize()  # Should not raise
        assert integration._initialized

    async def test_execute_intent_success(self, config) -> None:
        """Test successful intent execution."""
        integration = MockIntegration(config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "accepted",
            "response": "Success",
            "receipt": {"correlation_id": "test-123"},
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_response.raise_for_status = Mock()

            result = await integration.execute_intent("test command")

            assert result.status == "accepted"
            assert result.response == "Success"
            assert result.correlation_id == "test-123"

    async def test_execute_intent_rate_limit(self, config) -> None:
        """Test rate limit handling."""
        integration = MockIntegration(config)

        mock_response = Mock()
        mock_response.status_code = 429

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await integration.execute_intent("test command")

            assert result.status == "error"
            assert "rate_limit" in result.error.lower()  # type: ignore[union-attr]

    async def test_execute_intent_error(self, config) -> None:
        """Test error handling."""
        integration = MockIntegration(config)

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Connection failed")
            )

            result = await integration.execute_intent("test command")

            assert result.status == "error"
            assert result.error is not None

    async def test_get_available_actions(self, config) -> None:
        """Test getting available actions."""
        integration = MockIntegration(config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "action1", "description": "First action"},
            {"name": "action2", "description": "Second action"},
        ]

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            mock_response.raise_for_status = Mock()

            actions = await integration.get_available_actions()

            assert len(actions) == 2
            assert actions[0]["name"] == "action1"

    async def test_shutdown(self, config) -> None:
        """Test shutdown."""
        integration = MockIntegration(config)
        await integration.initialize()
        assert integration._initialized

        await integration.shutdown()
        assert not integration._initialized
