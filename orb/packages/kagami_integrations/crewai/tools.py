"""CrewAI Tools for K os.

REFACTORED (December 25, 2025):
===============================
Now uses unified executor from kagami_integrations.unified_executor.
Reduced from 195 lines to ~60 lines (thin adapter).
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from kagami_integrations.unified_executor import (
    ExecutorConfig,
    UnifiedKagamiExecutor,
    format_result_for_agent,
)

logger = logging.getLogger(__name__)


class ChronosInput(BaseModel):
    """Input schema for K os tool."""

    command: str = Field(
        ...,
        description="Natural language command or LANG/2 intent to execute via K os",
    )


class ChronosCrewTool:
    """CrewAI tool for executing K os intents.

    Uses unified executor for all K os API calls.
    """

    name: str = "kagami"
    description: str = (
        "Execute complex multi-agent workflows through K os. "
        "Use this for tasks requiring multiple steps, coordination, "
        "safety checks, or when you need detailed receipts and tracking. "
        "Supports natural language commands."
    )
    args_schema: type[BaseModel] = ChronosInput

    def __init__(
        self,
        kagami_url: str = "http://localhost:8001",
        api_key: str | None = None,
        auto_confirm: bool = False,
        timeout: float = 30.0,
    ):
        """Initialize K os CrewAI tool."""
        self._executor = UnifiedKagamiExecutor(
            ExecutorConfig(
                kagami_url=kagami_url,
                api_key=api_key,
                auto_confirm=auto_confirm,
                timeout=timeout,
            )
        )
        self._kagami_url = kagami_url

    def _run(self, command: str) -> str:
        """Execute K os intent synchronously."""
        result = self._executor.execute(command)
        return format_result_for_agent(result, self._kagami_url)

    async def _arun(self, command: str) -> str:
        """Execute K os intent asynchronously."""
        result = await self._executor.execute_async(command)
        return format_result_for_agent(result, self._kagami_url)
