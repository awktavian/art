"""LangChain Tools for K os.

REFACTORED (December 25, 2025):
===============================
Now uses unified executor from kagami_integrations.unified_executor.
Reduced from 267 lines to ~90 lines (thin adapter).
"""

from __future__ import annotations

import logging

from kagami_integrations.unified_executor import (
    ExecutorConfig,
    UnifiedKagamiExecutor,
    format_result_for_agent,
)

logger = logging.getLogger(__name__)


class ChronosTool:
    """LangChain tool for executing K os intents.

    Uses unified executor for all K os API calls.
    """

    name: str = "kagami"
    description: str = (
        "Execute complex multi-agent tasks with K os. "
        "Use this for workflows that require multiple steps, coordination, "
        "or safety guarantees. Supports natural language commands."
    )

    def __init__(
        self,
        kagami_url: str = "http://localhost:8001",
        api_key: str | None = None,
        auto_confirm: bool = False,
        timeout: float = 30.0,
    ):
        """Initialize K os tool."""
        self._executor = UnifiedKagamiExecutor(
            ExecutorConfig(
                kagami_url=kagami_url,
                api_key=api_key,
                auto_confirm=auto_confirm,
                timeout=timeout,
            )
        )
        self._kagami_url = kagami_url

    def _run(self, query: str) -> str:
        """Execute K os intent synchronously."""
        result = self._executor.execute(query)
        return format_result_for_agent(result, self._kagami_url)

    async def _arun(self, query: str) -> str:
        """Execute K os intent asynchronously."""
        result = await self._executor.execute_async(query)
        return format_result_for_agent(result, self._kagami_url)


class ChronosToolkit:
    """LangChain toolkit providing multiple K os tools.

    Provides specialized tools for different K os capabilities.
    """

    def __init__(
        self,
        kagami_url: str = "http://localhost:8001",
        api_key: str | None = None,
    ):
        """Initialize K os toolkit."""
        self.kagami_url = kagami_url
        self.api_key = api_key

    def get_tools(self) -> list[ChronosTool]:
        """Get all tools in the toolkit."""
        tools = []
        for name, desc in [
            ("kagami", "Execute general K os workflows."),
            ("kagami_files", "Search and manage files through K os."),
            ("kagami_analytics", "Analyze data and generate insights."),
            ("kagami_planner", "Create and manage plans and workflows."),
        ]:
            tool = ChronosTool(kagami_url=self.kagami_url, api_key=self.api_key)
            tool.name = name
            tool.description = desc
            tools.append(tool)
        return tools
