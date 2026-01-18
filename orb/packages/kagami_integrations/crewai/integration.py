"""CrewAI Integration Implementation."""

from __future__ import annotations

import logging
from typing import Any

from kagami_integrations.base import BaseIntegration, IntegrationConfig

logger = logging.getLogger(__name__)


class CrewAIIntegration(BaseIntegration):
    """K os integration with CrewAI.

    Enables coordination between K os agents and CrewAI crews.

    Example:
        ```python
        import os
        from kagami_integrations.crewai import CrewAIIntegration
        from kagami_integrations.base import IntegrationConfig
        from crewai import Agent, Task, Crew

        config = IntegrationConfig(
            name="crewai",
            kagami_url="http://localhost:8001",
            kagami_api_key=os.environ.get("KAGAMI_API_KEY"),
        )

        integration = CrewAIIntegration(config)
        await integration.initialize()

        # Create a crew with K os tool
        kagami_tool = await integration.as_tool()

        agent = Agent(
            role="Orchestrator",
            goal="Coordinate complex workflows",
            tools=[kagami_tool],
            backstory="Expert at multi-agent coordination",
        )

        task = Task(
            description="Analyze data and generate report",
            agent=agent,
        )

        crew = Crew(agents=[agent], tasks=[task])
        result = crew.kickoff()
        ```
    """

    def __init__(self, config: IntegrationConfig):
        super().__init__(config)
        self._tool: Any = None
        self._bridge: Any = None

    async def _initialize_impl(self) -> None:
        """Initialize CrewAI integration."""
        try:
            # Verify CrewAI is installed
            import crewai  # noqa: F401 - availability check

            self.logger.info("CrewAI detected")
        except ImportError:
            self.logger.warning("CrewAI not installed. Install with: pip install crewai")
            raise

        # Initialize tool and bridge
        from kagami_integrations.crewai.bridge import CrewBridge
        from kagami_integrations.crewai.tools import ChronosCrewTool

        self._tool = ChronosCrewTool(
            kagami_url=self.config.kagami_url,
            api_key=self.config.kagami_api_key,
        )

        self._bridge = CrewBridge(
            kagami_url=self.config.kagami_url,
            api_key=self.config.kagami_api_key,
        )

        self.logger.info("CrewAI integration initialized")

    async def as_tool(self) -> Any:
        """Get K os as a CrewAI tool.

        Returns:
            CrewAI BaseTool that executes K os intents
        """
        if not self._initialized:
            await self.initialize()

        return self._tool

    async def from_tool(self, tool: Any) -> None:
        """Import a CrewAI tool into K os.

        Args:
            tool: CrewAI BaseTool instance
        """
        if not self._initialized:
            await self.initialize()

        await self._bridge.import_tool(tool)

    async def _shutdown_impl(self) -> None:
        """Shutdown CrewAI integration."""
        self._tool = None
        self._bridge = None
