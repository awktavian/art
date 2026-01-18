"""Bridge for importing LangChain tools into Kagami."""

from __future__ import annotations

from kagami_integrations.base_bridge import BaseToolBridge


class LangChainBridge(BaseToolBridge):
    """Bridge for importing LangChain tools into Kagami.

    Allows Kagami agents to use tools from the LangChain ecosystem.

    Example:
        ```python
        import os
        from langchain.tools import DuckDuckGoSearchRun
        from kagami_integrations.langchain import LangChainBridge

        bridge = LangChainBridge(
            kagami_url="http://localhost:8001",
            api_key=os.environ.get("KAGAMI_API_KEY"),
        )

        # Import a LangChain tool
        search_tool = DuckDuckGoSearchRun()
        await bridge.import_tool(search_tool)

        # Now Kagami can use it via: "use duckduckgo_search to find..."
        ```
    """

    def __init__(
        self,
        kagami_url: str = "http://localhost:8001",
        api_key: str | None = None,
    ):
        """Initialize LangChain bridge.

        Args:
            kagami_url: Kagami API base URL
            api_key: API key for authentication
        """
        super().__init__(
            framework_name="langchain",
            kagami_url=kagami_url,
            api_key=api_key,
        )

    # All common methods inherited from BaseToolBridge
