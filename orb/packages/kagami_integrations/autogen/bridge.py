"""Bridge for importing AutoGen functions into K os."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class AutoGenBridge:
    """Bridge for importing AutoGen functions into K os.

    Allows K os agents to use functions from AutoGen.

    Example:
        ```python
        from kagami_integrations.autogen import AutoGenBridge

        bridge = AutoGenBridge(
            kagami_url="http://localhost:8001",
            api_key="your-key",
        )

        # Define an AutoGen function
        def search_web(query: str) -> str:
            '''Search the web for information.'''
            # Implementation...
            return results

        # Import it into K os
        await bridge.import_function({
            "name": "search_web",
            "description": "Search the web",
            "function": search_web,
        })
        ```
    """

    def __init__(
        self,
        kagami_url: str = "http://localhost:8001",
        api_key: str | None = None,
    ):
        """Initialize AutoGen bridge.

        Args:
            kagami_url: K os API base URL
            api_key: API key for authentication
        """
        self.kagami_url = kagami_url
        self.api_key = api_key
        self._imported_functions: dict[str, Callable] = {}

    async def import_function(self, function_def: dict[str, Any] | Callable) -> None:
        """Import an AutoGen function into K os.

        Args:
            function_def: AutoGen function definition dict or callable
        """
        try:
            # Extract function metadata
            if isinstance(function_def, dict):
                name = function_def.get("name", "unknown_function")
                description = function_def.get("description", "No description")
                func = function_def.get("function")
                parameters = function_def.get("parameters", {})
            else:
                # Assume it's a callable
                name = getattr(function_def, "__name__", "unknown_function")
                description = getattr(function_def, "__doc__", "No description") or "No description"
                func = function_def
                parameters = {}

            if not callable(func):
                raise ValueError(f"Function is not callable: {name}")

            logger.info(f"Importing AutoGen function: {name}")

            # Register with K os tools integration
            await self._register_with_kagami(
                name=name,
                description=description,
                func=func,
                parameters=parameters,
            )

            self._imported_functions[name] = func
            logger.info(f"Successfully imported function: {name}")

        except Exception as e:
            logger.error(f"Failed to import AutoGen function: {e}")
            raise

    async def _register_with_kagami(
        self,
        name: str,
        description: str,
        func: Callable,
        parameters: dict[str, Any],
    ) -> None:
        """Register function with K os tools registry.

        Args:
            name: Function name
            description: Function description
            func: Callable function
            parameters: OpenAPI-style parameters schema
        """
        try:
            import httpx

            # Register via K os API
            headers = {}
            if self.api_key:
                headers["x-api-key"] = self.api_key

            tool_def = {
                "name": name,
                "description": description,
                "category": "autogen",
                "parameters": parameters,
                "tags": ["autogen", "external"],
                "metadata": {
                    "source": "autogen",
                    "function_name": name,
                },
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.kagami_url}/api/tools/register",
                    json=tool_def,
                    headers=headers,
                )
                response.raise_for_status()

            logger.info(f"Registered function with K os: {name}")

        except Exception as e:
            logger.warning(f"Failed to register with K os API: {e}")
            # Continue anyway - function can still be used locally

    def get_imported_functions(self) -> dict[str, Callable]:
        """Get all imported functions.

        Returns:
            Dictionary mapping function names to callables
        """
        return self._imported_functions.copy()

    def execute_function(  # type: ignore[no-untyped-def]
        self,
        function_name: str,
        *args: Any,
        **kwargs,
    ) -> Any:
        """Execute an imported AutoGen function.

        Args:
            function_name: Name of the function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function execution result
        """
        if function_name not in self._imported_functions:
            raise ValueError(f"Function not imported: {function_name}")

        func = self._imported_functions[function_name]
        return func(*args, **kwargs)
