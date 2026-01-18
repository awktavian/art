"""Unified K os Command Executor.

CONSOLIDATION (December 25, 2025):
==================================
This module consolidates the duplicate HTTP execution logic that was
previously scattered across:
- kagami/integrations/crewai/tools.py
- kagami/integrations/langchain/tools.py
- kagami/integrations/autogen/tools.py

All three frameworks now use this single executor for K os API calls.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExecutorConfig:
    """Configuration for K os command executor."""

    kagami_url: str = "http://localhost:8001"
    api_key: str | None = None
    auto_confirm: bool = False
    timeout: float = 30.0


@dataclass
class ExecutionResult:
    """Result from K os command execution."""

    success: bool
    status: str
    correlation_id: str | None
    output: str
    raw_response: dict[str, Any] | None = None
    error: str | None = None


class UnifiedKagamiExecutor:
    """Unified executor for K os commands.

    Consolidates HTTP logic used by all integration frameworks.

    Example:
        executor = UnifiedKagamiExecutor(
            config=ExecutorConfig(
                kagami_url="http://localhost:8001",
                api_key="your-api-key",
            )
        )
        result = await executor.execute_async("analyze sales data")
        print(result.output)
    """

    def __init__(self, config: ExecutorConfig | None = None) -> None:
        self.config = config or ExecutorConfig()

    def execute(self, command: str) -> ExecutionResult:
        """Execute K os command synchronously.

        Args:
            command: Natural language command or LANG/2 intent

        Returns:
            ExecutionResult with status and output
        """
        try:
            return asyncio.run(self.execute_async(command))
        except RuntimeError:
            # Already in async context
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self.execute_async(command))

    async def execute_async(self, command: str) -> ExecutionResult:
        """Execute K os command asynchronously.

        Args:
            command: Natural language command or LANG/2 intent

        Returns:
            ExecutionResult with status and output
        """
        try:
            import httpx
        except ImportError:
            return ExecutionResult(
                success=False,
                status="error",
                correlation_id=None,
                output="Error: httpx not installed. Run: pip install httpx",
                error="missing_dependency",
            )

        headers = {}
        if self.config.api_key:
            headers["x-api-key"] = self.config.api_key

        body = {
            "lang": command,
            "confirm": self.config.auto_confirm,
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    f"{self.config.kagami_url}/api/command/execute",
                    json=body,
                    headers=headers,
                )

                # Rate limit handling
                if response.status_code == 429:
                    return ExecutionResult(
                        success=False,
                        status="rate_limited",
                        correlation_id=None,
                        output="Rate limit exceeded. Please try again later.",
                        error="rate_limit",
                    )

                response.raise_for_status()
                result = response.json()

                return self._process_response(result)

        except httpx.TimeoutException:
            return ExecutionResult(
                success=False,
                status="timeout",
                correlation_id=None,
                output=f"Request timed out after {self.config.timeout}s",
                error="timeout",
            )
        except httpx.HTTPStatusError as e:
            return ExecutionResult(
                success=False,
                status="http_error",
                correlation_id=None,
                output=f"HTTP error: {e.response.status_code}",
                error=str(e),
            )
        except Exception as e:
            logger.error(f"K os command execution failed: {e}")
            return ExecutionResult(
                success=False,
                status="error",
                correlation_id=None,
                output=f"Error: {e}",
                error=str(e),
            )

    def _process_response(self, result: dict[str, Any]) -> ExecutionResult:
        """Process K os API response into ExecutionResult."""
        status = result.get("status", "unknown")
        correlation_id = result.get("receipt", {}).get("correlation_id")

        # Handle confirmation required
        if status == "needs_confirmation":
            summary = result.get("summary", "")
            risk = result.get("risk", "unknown")
            bullets = result.get("confirmation", {}).get("bullets", [])
            confirmation_text = "\n".join(f"  - {bullet}" for bullet in bullets)

            output = (
                f"CONFIRMATION REQUIRED\n"
                f"Risk Level: {risk.upper()}\n\n"
                f"{summary}\n\n"
                f"Details:\n{confirmation_text}\n\n"
                f"Set auto_confirm=True or manually approve to proceed."
            )
            return ExecutionResult(
                success=False,
                status="needs_confirmation",
                correlation_id=correlation_id,
                output=output,
                raw_response=result,
            )

        # Handle blocked operations
        if status == "blocked":
            reason = result.get("reason", "unknown")
            detail = result.get("detail", "")
            return ExecutionResult(
                success=False,
                status="blocked",
                correlation_id=correlation_id,
                output=f"BLOCKED: {reason}\n{detail}",
                raw_response=result,
                error=reason,
            )

        # Handle errors
        if status == "error":
            error = result.get("error", "unknown error")
            return ExecutionResult(
                success=False,
                status="error",
                correlation_id=correlation_id,
                output=f"Error: {error}",
                raw_response=result,
                error=error,
            )

        # Success - format response
        response_data = result.get("response") or result.get("result", {})
        output = self._format_response_data(response_data)

        return ExecutionResult(
            success=True,
            status=status,
            correlation_id=correlation_id,
            output=output,
            raw_response=result,
        )

    def _format_response_data(self, data: Any) -> str:
        """Format response data for output."""
        if isinstance(data, str):
            return data

        if isinstance(data, dict):
            parts = []
            for key in ["summary", "message", "result", "data", "output"]:
                if key in data:
                    value = data[key]
                    if isinstance(value, str | int | float | bool):
                        parts.append(f"{key.title()}: {value}")
                    elif isinstance(value, list) and len(value) <= 5:
                        parts.append(f"{key.title()}: {', '.join(str(v) for v in value)}")
            return "\n".join(parts) if parts else str(data)

        return str(data)


def format_result_for_agent(result: ExecutionResult, kagami_url: str = "") -> str:
    """Format ExecutionResult for agent consumption.

    Provides consistent formatting across all integration frameworks.

    Args:
        result: ExecutionResult from executor
        kagami_url: Base URL for receipt link

    Returns:
        Formatted string for agent output
    """
    if result.success:
        lines = [
            "SUCCESS",
            f"Status: {result.status}",
        ]
        if result.correlation_id:
            lines.append(f"Correlation ID: {result.correlation_id}")
        lines.append("")
        lines.append(result.output)
        if kagami_url:
            lines.append("")
            lines.append(f"[Receipt: {kagami_url}/metrics]")
        return "\n".join(lines)

    # Error cases with appropriate symbols
    if result.status == "needs_confirmation":
        return f"WARNING: {result.output}"
    if result.status == "blocked":
        return f"BLOCKED: {result.output}"
    if result.status == "rate_limited":
        return f"RATE LIMITED: {result.output}"

    return f"ERROR: {result.output}"


# Singleton executor for shared use
_default_executor: UnifiedKagamiExecutor | None = None


def get_executor(config: ExecutorConfig | None = None) -> UnifiedKagamiExecutor:
    """Get or create the default executor.

    Args:
        config: Optional config to use. If None, uses default config.

    Returns:
        UnifiedKagamiExecutor instance
    """
    global _default_executor
    if _default_executor is None or config is not None:
        _default_executor = UnifiedKagamiExecutor(config)
    return _default_executor


__all__ = [
    "ExecutionResult",
    "ExecutorConfig",
    "UnifiedKagamiExecutor",
    "format_result_for_agent",
    "get_executor",
]
