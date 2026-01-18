"""Tests for LangChain integration."""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio

pytestmark = pytest.mark.tier_integration
from unittest.mock import AsyncMock, Mock, patch
from kagami_integrations.base import IntegrationConfig
from kagami_integrations.langchain.bridge import LangChainBridge
from kagami_integrations.langchain.integration import LangChainIntegration
from kagami_integrations.langchain.tools import ChronosTool, ChronosToolkit


@pytest.fixture
def integration_config() -> Any:
    """Create integration config for testing."""
    return IntegrationConfig(
        name="langchain",
        kagami_url="http://test:8001",
        kagami_api_key="test-key",
    )


@pytest_asyncio.fixture
async def integration(integration_config):
    """Create LangChain integration."""
    # Mock langchain imports at module level, not as attribute
    with patch.dict("sys.modules", {"langchain": Mock(), "langchain.tools": Mock()}):
        integration = LangChainIntegration(integration_config)
        await integration.initialize()
        yield integration
        await integration.shutdown()


@pytest.mark.asyncio
class TestLangChainIntegration:
    """Test LangChain integration."""

    async def test_initialization(self, integration) -> None:
        """Test integration initializes successfully."""
        assert integration._initialized
        assert integration._toolkit is not None
        assert integration._bridge is not None

    async def test_as_tool(self, integration) -> None:
        """Test getting K os as a tool."""
        tool = await integration.as_tool()
        assert tool is not None
        assert hasattr(tool, "name")
        assert hasattr(tool, "description")
        assert hasattr(tool, "_run")

    async def test_as_toolkit(self, integration) -> None:
        """Test getting K os toolkit."""
        toolkit = await integration.as_toolkit()
        assert toolkit is not None
        tools = toolkit.get_tools()
        assert len(tools) > 0
        assert all(hasattr(t, "name") for t in tools)

    async def test_from_tool(self, integration) -> None:
        """Test importing LangChain tool."""
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test tool"
        # Should not raise
        await integration.from_tool(mock_tool)


class TestChronosTool:
    """Test K os LangChain tool."""

    def test_tool_attributes(self) -> None:
        """Test tool has required attributes."""
        tool = ChronosTool()
        assert tool.name == "kagami"
        assert len(tool.description) > 0
        assert hasattr(tool, "_run")
        assert hasattr(tool, "_arun")

    @pytest.mark.asyncio
    async def test_execute_intent_success(self) -> None:
        """Test successful intent execution."""
        tool = ChronosTool(kagami_url="http://test:8001")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "accepted",
            "response": "Task completed",
            "receipt": {"correlation_id": "test-123"},
        }
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            result = await tool._arun("test command")
            assert "SUCCESS" in result or "Accepted" in result
            assert "test-123" in result

    @pytest.mark.asyncio
    async def test_execute_intent_confirmation_required(self) -> None:
        """Test confirmation required response."""
        tool = ChronosTool(kagami_url="http://test:8001")
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "needs_confirmation",
            "summary": "High risk operation",
            "risk": "high",
            "confirmation": {"bullets": ["Item 1", "Item 2"]},
        }
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            result = await tool._arun("test command")
            assert "Confirmation Required" in result or "CONFIRMATION" in result
            assert "high" in result.lower()

    @pytest.mark.asyncio
    async def test_execute_intent_error(self) -> None:
        """Test error handling."""
        tool = ChronosTool(kagami_url="http://test:8001")
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Connection failed")
            )
            result = await tool._arun("test command")
            assert "Error" in result or "ERROR" in result


class TestChronosToolkit:
    """Test K os toolkit."""

    def test_toolkit_tools(self) -> None:
        """Test toolkit provides multiple tools."""
        toolkit = ChronosToolkit(kagami_url="http://test:8001")
        tools = toolkit.get_tools()
        assert len(tools) == 4  # general, files, analytics, planner
        names = [t.name for t in tools]
        assert "kagami" in names
        assert "kagami_files" in names
        assert "kagami_analytics" in names
        assert "kagami_planner" in names


@pytest.mark.asyncio
class TestLangChainBridge:
    """Test LangChain bridge."""

    async def test_import_tool(self) -> None:
        """Test importing a tool."""
        bridge = LangChainBridge(kagami_url="http://test:8001")
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test description"
        mock_response = Mock()
        mock_response.status_code = 200
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            await bridge.import_tool(mock_tool)
            imported = bridge.get_imported_tools()
            assert "test_tool" in imported

    async def test_execute_imported_tool(self) -> None:
        """Test executing an imported tool."""
        bridge = LangChainBridge(kagami_url="http://test:8001")
        # Mock tool with async _arun method
        mock_tool = Mock()
        mock_tool.name = "test_tool"
        mock_tool.description = "Test"
        mock_tool._arun = AsyncMock(return_value="result")
        bridge._imported_tools["test_tool"] = mock_tool
        result = await bridge.execute_tool("test_tool", arg="value")
        assert result == "result"
        mock_tool._arun.assert_called_once()
