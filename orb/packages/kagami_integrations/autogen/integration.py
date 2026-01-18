"""AutoGen Integration Implementation."""

from __future__ import annotations

import logging
from typing import Any

from kagami_integrations.base import BaseIntegration, IntegrationConfig

logger = logging.getLogger(__name__)


class AutoGenIntegration(BaseIntegration):
    """K os integration with AutoGen.

    Enables multi-agent conversations with K os capabilities.

    Example:
        ```python
        from kagami_integrations.autogen import AutoGenIntegration
        from kagami_integrations.base import IntegrationConfig
        import autogen  # noqa: F401 - availability check

        config = IntegrationConfig(
            name="autogen",
            kagami_url="http://localhost:8001",
            kagami_api_key="your-key",
        )

        integration = AutoGenIntegration(config)
        await integration.initialize()

        # Get K os as an AutoGen function
        kagami_func = await integration.as_tool()

        # Create AutoGen agents with K os
        assistant = autogen.AssistantAgent(
            name="assistant",
            llm_config={
                "functions": [kagami_func],
            },
        )

        user_proxy = autogen.UserProxyAgent(
            name="user_proxy",
            function_map={"kagami": kagami_func["function"]},
        )

        # Start conversation
        user_proxy.initiate_chat(
            assistant,
            message="Analyze our sales data and create a report",
        )
        ```
    """

    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self._function_def: dict[str, Any] | None = None
        self._bridge: Any = None

    async def _initialize_impl(self) -> None:
        """Initialize AutoGen integration."""
        try:
            # Verify AutoGen is installed
            import autogen  # noqa: F401 - availability check

            self.logger.info("AutoGen detected")
        except ImportError:
            self.logger.warning("AutoGen not installed. Install with: pip install pyautogen")
            raise

        # Initialize function definition and bridge
        from kagami_integrations.autogen.bridge import AutoGenBridge
        from kagami_integrations.autogen.tools import create_kagami_function

        self._function_def = create_kagami_function(
            kagami_url=self.config.kagami_url,
            api_key=self.config.kagami_api_key,
        )

        self._bridge = AutoGenBridge(
            kagami_url=self.config.kagami_url,
            api_key=self.config.kagami_api_key,
        )

        self.logger.info("AutoGen integration initialized")

    async def as_tool(self) -> dict[str, Any]:
        """Get K os as an AutoGen function definition.

        Returns:
            Function definition dict for AutoGen agents
        """
        if not self._initialized:
            await self.initialize()

        return self._function_def  # type: ignore

    async def from_tool(self, tool: Any) -> None:
        """Import an AutoGen function into K os.

        Args:
            tool: AutoGen function definition or callable
        """
        if not self._initialized:
            await self.initialize()

        await self._bridge.import_function(tool)

    async def _shutdown_impl(self) -> None:
        """Shutdown AutoGen integration."""
        self._function_def = None
        self._bridge = None
