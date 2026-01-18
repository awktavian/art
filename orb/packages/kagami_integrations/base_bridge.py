"""Base bridge class for external tool integrations.

Provides common functionality for importing tools from external frameworks
(CrewAI, LangChain, etc.) into the Kagami ecosystem.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class BaseToolBridge:
    """Base class for external tool bridges.

    Consolidates common logic for importing tools from external frameworks
    into Kagami. Subclasses only need to specify the framework name.

    Created: December 2025 - Eliminates code clones between CrewAI/LangChain bridges
    """

    def __init__(
        self,
        framework_name: str,
        kagami_url: str = "http://localhost:8001",
        api_key: str | None = None,
    ):
        """Initialize tool bridge.

        Args:
            framework_name: Name of the external framework (e.g., "crewai", "langchain")
            kagami_url: Kagami API base URL
            api_key: API key for authentication
        """
        self.framework_name = framework_name
        self.kagami_url = kagami_url
        self.api_key = api_key
        self._imported_tools: dict[str, Any] = {}

    async def import_tool(self, tool: Any) -> None:
        """Import an external tool into Kagami.

        Args:
            tool: External tool instance (BaseTool-like interface expected)
        """
        try:
            # Extract tool metadata
            name = getattr(tool, "name", "unknown_tool")
            description = getattr(tool, "description", "No description")

            # Get tool schema if available
            schema = None
            if hasattr(tool, "args_schema"):
                schema = tool.args_schema

            logger.info(f"Importing {self.framework_name} tool: {name}")

            # Register with Kagami tools integration
            await self._register_with_kagami(
                name=name,
                description=description,
                tool=tool,
                schema=schema,
            )

            self._imported_tools[name] = tool
            logger.info(f"Successfully imported tool: {name}")

        except Exception as e:
            logger.error(f"Failed to import {self.framework_name} tool: {e}")
            raise

    async def _register_with_kagami(
        self,
        name: str,
        description: str,
        tool: Any,
        schema: Any,
    ) -> None:
        """Register tool with Kagami tools registry.

        Args:
            name: Tool name
            description: Tool description
            tool: External tool instance
            schema: Pydantic schema for tool arguments
        """
        try:
            import httpx

            # Convert schema to OpenAPI format
            parameters = {}
            if schema:
                try:
                    if hasattr(schema, "schema"):
                        parameters = schema.schema()
                    elif hasattr(schema, "model_json_schema"):
                        parameters = schema.model_json_schema()
                except Exception as e:
                    logger.warning(f"Failed to extract schema: {e}")

            # Register via Kagami API
            headers = {}
            if self.api_key:
                headers["x-api-key"] = self.api_key

            tool_def = {
                "name": name,
                "description": description,
                "category": self.framework_name,
                "parameters": parameters,
                "tags": [self.framework_name, "external"],
                "metadata": {
                    "source": self.framework_name,
                    "tool_type": type(tool).__name__,
                },
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.kagami_url}/api/tools/register",
                    json=tool_def,
                    headers=headers,
                )
                response.raise_for_status()

            logger.info(f"Registered tool with Kagami: {name}")

        except Exception as e:
            logger.warning(f"Failed to register with Kagami API: {e}")
            # Continue anyway - tool can still be used locally

    def get_imported_tools(self) -> dict[str, Any]:
        """Get all imported tools.

        Returns:
            Dictionary mapping tool names to tool instances
        """
        return self._imported_tools.copy()

    async def execute_tool(  # type: ignore[no-untyped-def]
        self,
        tool_name: str,
        **kwargs,
    ) -> Any:
        """Execute an imported tool by name.

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Tool arguments

        Returns:
            Tool execution result

        Raises:
            KeyError: If tool not found
        """
        if tool_name not in self._imported_tools:
            raise KeyError(f"Tool '{tool_name}' not imported")

        tool = self._imported_tools[tool_name]

        try:
            # Try async execution first
            if hasattr(tool, "arun"):
                return await tool.arun(**kwargs)
            # Fall back to sync execution (will block)
            elif hasattr(tool, "run"):
                return tool.run(**kwargs)
            # Try __call__ as last resort
            elif callable(tool):
                result = tool(**kwargs)
                # If result is awaitable, await it
                import asyncio

                if asyncio.iscoroutine(result):
                    return await result
                return result
            else:
                raise AttributeError(f"Tool '{tool_name}' has no run/arun/__call__ method")

        except Exception as e:
            logger.error(f"Failed to execute tool '{tool_name}': {e}")
            raise
