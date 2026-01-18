"""Bridge for importing CrewAI tools into Kagami."""

from __future__ import annotations

from kagami_integrations.base_bridge import BaseToolBridge


class CrewBridge(BaseToolBridge):
    """Bridge for importing CrewAI tools into Kagami.

    Allows Kagami agents to use tools from CrewAI crews.

    Example:
        ```python
        import os
        from crewai_tools import SerperDevTool
        from kagami_integrations.crewai import CrewBridge

        bridge = CrewBridge(
            kagami_url="http://localhost:8001",
            api_key=os.environ.get("KAGAMI_API_KEY"),
        )

        # Import a CrewAI tool
        search_tool = SerperDevTool()
        await bridge.import_tool(search_tool)

        # Now Kagami can use it
        ```
    """

    def __init__(
        self,
        kagami_url: str = "http://localhost:8001",
        api_key: str | None = None,
    ):
        """Initialize CrewAI bridge.

        Args:
            kagami_url: Kagami API base URL
            api_key: API key for authentication
        """
        super().__init__(
            framework_name="crewai",
            kagami_url=kagami_url,
            api_key=api_key,
        )

    # All common methods inherited from BaseToolBridge
