"""AutoGen Tools/Functions for K os.

REFACTORED (December 25, 2025):
===============================
Now uses unified executor from kagami_integrations.unified_executor.
Reduced from 230 lines to ~80 lines (thin adapter).
"""

from __future__ import annotations

import logging
from typing import Any

from kagami_integrations.unified_executor import (
    ExecutorConfig,
    UnifiedKagamiExecutor,
    format_result_for_agent,
)

logger = logging.getLogger(__name__)


def execute_kagami_command(
    command: str,
    kagami_url: str = "http://localhost:8001",
    api_key: str | None = None,
    auto_confirm: bool = False,
) -> str:
    """Execute a K os command.

    This function is used by AutoGen agents to execute K os intents.
    """
    executor = UnifiedKagamiExecutor(
        ExecutorConfig(
            kagami_url=kagami_url,
            api_key=api_key,
            auto_confirm=auto_confirm,
        )
    )
    result = executor.execute(command)
    return format_result_for_agent(result, kagami_url)


def create_kagami_function(
    kagami_url: str = "http://localhost:8001",
    api_key: str | None = None,
) -> dict[str, Any]:
    """Create an AutoGen function definition for K os."""
    return {
        "name": "kagami",
        "description": (
            "Execute complex multi-agent workflows through K os. "
            "Use this for tasks requiring multiple steps, coordination, "
            "safety checks, or detailed tracking."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Natural language command or LANG/2 intent",
                },
            },
            "required": ["command"],
        },
        "function": lambda command: execute_kagami_command(
            command,
            kagami_url=kagami_url,
            api_key=api_key,
        ),
    }


class ChronosAutoGenTool:
    """Wrapper class for K os AutoGen function."""

    def __init__(
        self,
        kagami_url: str = "http://localhost:8001",
        api_key: str | None = None,
        auto_confirm: bool = False,
    ):
        """Initialize K os AutoGen tool."""
        self._executor = UnifiedKagamiExecutor(
            ExecutorConfig(
                kagami_url=kagami_url,
                api_key=api_key,
                auto_confirm=auto_confirm,
            )
        )
        self._kagami_url = kagami_url
        self._api_key = api_key

    def execute(self, command: str) -> str:
        """Execute a K os command."""
        result = self._executor.execute(command)
        return format_result_for_agent(result, self._kagami_url)

    def get_function_def(self) -> dict[str, Any]:
        """Get AutoGen function definition."""
        return create_kagami_function(
            kagami_url=self._kagami_url,
            api_key=self._api_key,
        )
