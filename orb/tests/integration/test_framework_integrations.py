"""Integration tests for framework integrations (LangChain, CrewAI, AutoGen)."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from kagami_integrations.base import IntegrationConfig


class TestLangChainIntegration:
    """Test LangChain integration."""

    @pytest.mark.asyncio
    async def test_langchain_initialization(self):
        """Test initializing LangChain integration."""
        try:
            from kagami_integrations.langchain import LangChainIntegration

            config = IntegrationConfig(
                name="langchain",
                kagami_url="http://localhost:8001",
                kagami_api_key="test_key",
            )

            integration = LangChainIntegration(config)
            await integration.initialize()

            assert integration._initialized
            await integration.shutdown()
        except ImportError:
            pytest.skip("LangChain not installed")

    @pytest.mark.asyncio
    async def test_langchain_as_tool(self):
        """Test exporting K os as LangChain tool."""
        try:
            from kagami_integrations.langchain import LangChainIntegration

            config = IntegrationConfig(
                name="langchain",
                kagami_url="http://localhost:8001",
                kagami_api_key="test_key",
            )

            integration = LangChainIntegration(config)
            await integration.initialize()

            tool = await integration.as_tool()
            assert tool is not None

            await integration.shutdown()
        except ImportError:
            pytest.skip("LangChain not installed")


class TestCrewAIIntegration:
    """Test CrewAI integration."""

    @pytest.mark.asyncio
    async def test_crewai_initialization(self):
        """Test initializing CrewAI integration."""
        try:
            from kagami_integrations.crewai import CrewAIIntegration

            config = IntegrationConfig(
                name="crewai",
                kagami_url="http://localhost:8001",
                kagami_api_key="test_key",
            )

            integration = CrewAIIntegration(config)
            await integration.initialize()

            assert integration._initialized
            await integration.shutdown()
        except ImportError:
            pytest.skip("CrewAI not installed")

    @pytest.mark.asyncio
    async def test_crewai_as_tool(self):
        """Test exporting K os as CrewAI tool."""
        try:
            from kagami_integrations.crewai import CrewAIIntegration

            config = IntegrationConfig(
                name="crewai",
                kagami_url="http://localhost:8001",
                kagami_api_key="test_key",
            )

            integration = CrewAIIntegration(config)
            await integration.initialize()

            tool = await integration.as_tool()
            assert tool is not None

            await integration.shutdown()
        except ImportError:
            pytest.skip("CrewAI not installed")


class TestAutoGenIntegration:
    """Test AutoGen integration."""

    @pytest.mark.asyncio
    async def test_autogen_initialization(self):
        """Test initializing AutoGen integration."""
        try:
            from kagami_integrations.autogen import AutoGenIntegration

            config = IntegrationConfig(
                name="autogen",
                kagami_url="http://localhost:8001",
                kagami_api_key="test_key",
            )

            integration = AutoGenIntegration(config)
            await integration.initialize()

            assert integration._initialized
            await integration.shutdown()
        except ImportError:
            pytest.skip("AutoGen not installed")

    @pytest.mark.asyncio
    async def test_autogen_as_tool(self):
        """Test exporting K os as AutoGen function."""
        try:
            from kagami_integrations.autogen import AutoGenIntegration

            config = IntegrationConfig(
                name="autogen",
                kagami_url="http://localhost:8001",
                kagami_api_key="test_key",
            )

            integration = AutoGenIntegration(config)
            await integration.initialize()

            func_def = await integration.as_tool()
            assert isinstance(func_def, dict)
            assert "name" in func_def or "function" in func_def

            await integration.shutdown()
        except ImportError:
            pytest.skip("AutoGen not installed")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
