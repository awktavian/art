"""LangChain Integration Implementation."""

from __future__ import annotations

import logging
from typing import Any

from kagami_integrations.base import BaseIntegration, IntegrationConfig

logger = logging.getLogger(__name__)


class LangChainIntegration(BaseIntegration):
    """K os integration with LangChain.

    Provides bidirectional integration:
    - Export K os as LangChain tools
    - Import LangChain tools into K os

    Example:
        ```python
        import os
        from kagami_integrations.langchain import LangChainIntegration
        from kagami_integrations.base import IntegrationConfig

        config = IntegrationConfig(
            name="langchain",
            kagami_url="http://localhost:8001",
            kagami_api_key=os.environ.get("KAGAMI_API_KEY"),
        )

        integration = LangChainIntegration(config)
        await integration.initialize()

        # Use K os as a LangChain tool
        kagami_tool = await integration.as_tool()

        # Or import LangChain tools into K os
        from langchain.tools import DuckDuckGoSearchRun
        search_tool = DuckDuckGoSearchRun()
        await integration.from_tool(search_tool)
        ```
    """

    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self._toolkit: Any = None
        self._bridge: Any = None

    async def _initialize_impl(self) -> None:
        """Initialize LangChain integration."""
        try:
            # Verify LangChain is installed
            import langchain  # noqa: F401 - availability check

            self.logger.info("LangChain detected")
        except ImportError:
            self.logger.warning("LangChain not installed. Install with: pip install langchain")
            raise

        # Initialize toolkit and bridge
        from kagami_integrations.langchain.bridge import LangChainBridge
        from kagami_integrations.langchain.tools import ChronosToolkit

        self._toolkit = ChronosToolkit(
            kagami_url=self.config.kagami_url,
            api_key=self.config.kagami_api_key,
        )

        self._bridge = LangChainBridge(
            kagami_url=self.config.kagami_url,
            api_key=self.config.kagami_api_key,
        )

        self.logger.info("LangChain integration initialized")

    async def as_tool(self) -> Any:
        """Get K os as a LangChain tool.

        Returns:
            LangChain Tool that executes K os intents
        """
        if not self._initialized:
            await self.initialize()

        from kagami_integrations.langchain.tools import ChronosTool

        return ChronosTool(
            kagami_url=self.config.kagami_url,
            api_key=self.config.kagami_api_key,
        )

    async def as_toolkit(self) -> Any:
        """Get K os as a LangChain toolkit.

        Returns:
            LangChain BaseToolkit with multiple K os tools
        """
        if not self._initialized:
            await self.initialize()

        return self._toolkit

    async def from_tool(self, tool: Any) -> None:
        """Import a LangChain tool into K os.

        Args:
            tool: LangChain Tool or BaseTool instance
        """
        if not self._initialized:
            await self.initialize()

        await self._bridge.import_tool(tool)

    async def _shutdown_impl(self) -> None:
        """Shutdown LangChain integration."""
        self._toolkit = None
        self._bridge = None
