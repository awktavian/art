"""
K os Tools Integration

Manages tool registration, discovery, and execution for K os.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ChronosToolsIntegration:
    """Manages tool integration for K os."""

    def __init__(self) -> None:
        self.tools_registry: dict[str, dict[str, Any]] = {}
        self.initialized: bool = False
        self.composio_bridge: Any | None = None  # Will be set[Any] by lifespan
        self.qwen_bridge: Any | None = None

    async def initialize(self) -> None:
        """Initializes the tools integration."""
        if self.initialized:
            return

        # Register basic built-in tools
        await self._register_builtin_tools()

        # Initialize Qwen Tool Bridge to unify tool execution and schemas (optional)
        try:
            import os as _os

            if (_os.getenv("DISABLE_QWEN_TOOL_BRIDGE") or "0").lower() in (
                "1",
                "true",
                "yes",
                "on",
            ):
                raise RuntimeError("disabled_by_env")

            from kagami.core.services.qwen_tool_bridge import (
                qwen_tool_bridge,
            )

            self.qwen_bridge = qwen_tool_bridge
            if hasattr(self.qwen_bridge, "initialize"):
                await self.qwen_bridge.initialize()
            logger.info("Qwen Tool Bridge initialized for tool execution")
        except Exception as e:
            # Optional integration: log at info to avoid noisy warnings in deployments
            logger.info(f"Qwen Tool Bridge unavailable (optional): {e}")
            self.qwen_bridge = None

        # Log Composio bridge status
        if (
            self.composio_bridge
            and hasattr(self.composio_bridge, "initialized")
            and self.composio_bridge.initialized
        ):
            logger.info("Composio bridge available for external tool integration")
        else:
            logger.info("No Composio bridge available - external tools disabled")

        self.initialized = True
        logger.info("K os Tools Integration Initialized")

    async def _register_builtin_tools(self) -> None:
        """Register basic built-in tools."""
        builtin_tools = [
            {
                "id": "plan_creator",
                "name": "Plan Creator",
                "description": "Create and manage project plans",
                "category": "planning",
                "parameters": {
                    "name": {"type": "string", "required": True},
                    "description": {"type": "string", "required": False},
                    "target_date": {"type": "string", "required": False},
                },
                "tags": ["planning", "productivity"],
                "version": "1.0.0",
                "async_capable": True,
                "timeout": 10.0,
            },
            {
                "id": "task_generator",
                "name": "Task Generator",
                "description": "Generate task suggestions for plans",
                "category": "planning",
                "parameters": {
                    "plan_id": {"type": "string", "required": True},
                    "plan_type": {"type": "string", "required": False},
                },
                "tags": ["planning", "ai", "automation"],
                "version": "1.0.0",
                "async_capable": True,
                "timeout": 15.0,
            },
            {
                "id": "grep",
                "name": "Grep Code Search",
                "description": "Search code files for exact patterns using grep",
                "category": "code_analysis",
                "parameters": {
                    "pattern": {"type": "string", "required": True},
                    "path": {"type": "string", "required": False},
                },
                "tags": ["code", "search", "analysis"],
                "version": "1.0.0",
                "async_capable": True,
                "timeout": 5.0,
            },
            {
                "id": "web_search",
                "name": "Web Search",
                "description": "Search the web (DuckDuckGo HTML fallback)",
                "category": "web",
                "parameters": {
                    "query": {"type": "string", "required": True},
                    "max_results": {"type": "string", "required": False},
                    "timeout": {"type": "string", "required": False},
                },
                "tags": ["web", "search"],
                "version": "1.0.0",
                "async_capable": True,
                "timeout": 15.0,
            },
        ]

        for tool in builtin_tools:
            self.tools_registry[str(tool.get("id", ""))] = tool

        logger.info(f"Registered {len(builtin_tools)} built-in tools")

    def _is_tool_enabled(self, name: str | None, definition: dict[str, Any] | None = None) -> bool:
        """Determine if a tool should be exposed.

        We hide external-only tools (e.g., composio-backed) when no composio bridge
        is initialized to avoid presenting non-functional options.
        """
        if not name:
            return False
        # If definition provided, check requirements
        if isinstance(definition, dict):
            reqs = definition.get("requirements") or {}
            if reqs.get("external_only", False):
                return bool(
                    self.composio_bridge
                    and hasattr(self.composio_bridge, "initialized")
                    and self.composio_bridge.initialized
                )
        # When using Qwen bridge schemas, we cannot inspect requirements; allow all
        # and rely on executor/bridge to surface clear errors if invoked.
        if self.qwen_bridge is not None:
            if name in {"web_search", "file_operations"}:
                return bool(
                    self.composio_bridge
                    and hasattr(self.composio_bridge, "initialized")
                    and self.composio_bridge.initialized
                )
        return True

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Returns a list[Any] of available tools."""
        if not self.initialized:
            await self.initialize()

        tools = list(self.tools_registry.values())

        # Add tools from Qwen bridge if available
        try:
            if self.qwen_bridge is not None:
                schemas = self.qwen_bridge.tool_registry.get_all_tool_schemas()
                for schema in schemas:
                    fn = schema.get("function", {})
                    # Filter out external-only tools if Composio is unavailable
                    name = fn.get("name")
                    if not self._is_tool_enabled(name):
                        continue
                    tools.append(
                        {
                            "id": name,
                            "name": name,
                            "description": fn.get("description", ""),
                            "category": "tool",
                            "parameters": fn.get("parameters", {}),
                            "tags": ["tool"],
                            "version": "1.0.0",
                            "async_capable": True,
                            "timeout": 30.0,
                            "metadata": {"schema": schema},
                        }
                    )
        except Exception as e:
            logger.debug(f"Failed to enumerate tools from Qwen bridge: {e}")

        return tools

    async def register_tool(
        self,
        name: str,
        description: str,
        function_definition: dict[str, Any],
        parameters: dict[str, Any] | None = None,
        category: str = "general",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Register a new tool."""
        if not self.initialized:
            await self.initialize()

        tool_id = name.lower().replace(" ", "_")
        tool = {
            "id": tool_id,
            "name": name,
            "description": description,
            "category": category,
            "parameters": parameters or {},
            "tags": tags or [],
            "version": "1.0.0",
            "async_capable": True,
            "timeout": 30.0,
            "function_definition": function_definition,
        }

        self.tools_registry[tool_id] = tool
        logger.info(f"Registered tool: {name}")
        return tool

    async def search_tools(
        self,
        query: str | None = None,
        tags: list[str] | None = None,
        category: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Search for tools based on criteria."""
        tools = await self.get_available_tools()

        if not any([query, tags, category]):
            return tools[:limit]

        filtered_tools = []
        for tool in tools:
            match = True

            if query:
                query_lower = query.lower()
                if not (
                    query_lower in tool["name"].lower()
                    or query_lower in tool["description"].lower()
                ):
                    match = False

            if tags and match:
                tool_tags = [tag.lower() for tag in tool.get("tags", [])]
                search_tags = [tag.lower() for tag in tags]
                if not any(tag in tool_tags for tag in search_tags):
                    match = False

            if category and match:
                if tool.get("category", "").lower() != category.lower():
                    match = False

            if match:
                filtered_tools.append(tool)

        return filtered_tools[:limit]

    async def execute_tool(
        self,
        tool_name: str,
        parameters: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a tool with given parameters."""
        if not self.initialized:
            await self.initialize()

        # Prefer Qwen bridge executor if available
        if self.qwen_bridge is not None:
            try:
                exec_result = await self.qwen_bridge.execute_tool_directly(
                    tool_name, parameters or {}
                )
                return {
                    "success": bool(exec_result.success),
                    "result": exec_result.result,
                    "execution_time": exec_result.execution_time,
                    "error": exec_result.error,
                    "metadata": exec_result.metadata,
                }
            except Exception as e:
                logger.error(f"Qwen bridge execution failed: {e}")

        # Fallback to built-in tools execution
        # Find built-in tool by name
        tool = None
        for t in self.tools_registry.values():
            if t["name"].lower() == tool_name.lower() or t["id"] == tool_name:
                tool = t
                break

        if tool is None:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found",
                "execution_time": 0,
            }

        try:
            result = await self._execute_builtin_tool(tool, parameters or {}, context or {})
            return {
                "success": True,
                "result": result,
                "execution_time": 0.1,
                "metadata": {"tool_id": tool["id"]},
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {"success": False, "error": str(e), "execution_time": 0}

    async def _execute_builtin_tool(
        self, tool: dict[str, Any], parameters: dict[str, Any], context: dict[str, Any]
    ) -> Any:
        """Execute a built-in tool."""
        tool_id = tool["id"]

        if tool_id == "plan_creator":
            return {
                "message": "Plan creation tool executed",
                "plan_name": parameters.get("name", "Untitled Plan"),
                "description": parameters.get("description", ""),
                "target_date": parameters.get("target_date"),
            }
        elif tool_id == "task_generator":
            return {
                "message": "Task generation tool executed",
                "plan_id": parameters.get("plan_id"),
                "generated_tasks": [
                    "Define project scope",
                    "Create timeline",
                    "Identify resources",
                ],
            }
        elif tool_id == "grep":
            # Implement grep for agents (simple file-based search)
            import os
            import subprocess

            pattern = parameters.get("pattern", "")
            path = parameters.get("path", "kagami/")

            if not pattern:
                return {"error": "Pattern required"}

            try:
                # Use grep command for code search
                result = subprocess.run(
                    ["grep", "-r", "-n", pattern, path],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd=os.getcwd(),
                )

                output = result.stdout if result.stdout else result.stderr

                return {
                    "success": result.returncode == 0,
                    "matches": output,
                    "pattern": pattern,
                    "path": path,
                }
            except Exception as e:
                return {"error": str(e), "success": False}
        elif tool_id == "web_search":
            try:
                from kagami.tools.web.search import web_search as _web_search
            except Exception as e:
                return {"success": False, "error": f"Web search unavailable: {e}"}

            try:
                query = parameters.get("query", "")
                if not query:
                    return {"success": False, "error": "query required"}
                max_results = int(parameters.get("max_results", 5))
                timeout = float(parameters.get("timeout", 10.0))
                results = await _web_search(query=query, max_results=max_results, timeout=timeout)
                return {"success": True, "results": results}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {"message": f"Tool {tool['name']} executed successfully"}


# Singleton instance
_tools_integration: ChronosToolsIntegration | None = None


def get_kagami_tools_integration() -> ChronosToolsIntegration:
    """Returns a singleton instance of the ChronosToolsIntegration."""
    global _tools_integration
    if _tools_integration is None:
        _tools_integration = ChronosToolsIntegration()
    return _tools_integration
