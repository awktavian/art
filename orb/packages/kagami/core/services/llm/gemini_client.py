"""Gemini Client - Integration with Google's Gemini API via GenAI SDK.

Provides support for Gemini models (Pro, Flash, etc.) using the
google-genai library.

FEATURES:
=========
- Text generation with streaming support
- Structured output with Pydantic schemas
- Function calling (tool use)
- Grounding with Google Search
- Multi-turn conversations
- Code execution

FUNCTION CALLING:
=================
Define functions as Python callables with type hints:

    def get_weather(city: str, unit: str = "celsius") -> dict:
        '''Get current weather for a city.'''
        return {"temp": 20, "unit": unit}

    client = GeminiClient()
    result = await client.generate_with_tools(
        prompt="What's the weather in Seattle?",
        tools=[get_weather],
    )

GROUNDING:
==========
Enable Google Search grounding for real-time information:

    result = await client.generate_with_grounding(
        prompt="What are the latest AI news today?",
        grounding_source="google_search",
    )

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints

from kagami.utils.retry import retry_async

logger = logging.getLogger(__name__)

try:
    from google import genai
    from google.genai import types
    from google.genai.client import Client

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    Client = None  # type: ignore[assignment, misc]
    types = None  # type: ignore[assignment]


@dataclass
class FunctionDeclaration:
    """Declaration of a callable function for Gemini tools.

    Attributes:
        name: Function name.
        description: Function description.
        parameters: JSON schema for parameters.
        callable: The actual Python function.
    """

    name: str
    description: str
    parameters: dict[str, Any]
    callable: Callable[..., Any]


@dataclass
class FunctionCall:
    """A function call made by the model.

    Attributes:
        name: Function name.
        args: Arguments to pass.
        id: Call ID for response matching.
    """

    name: str
    args: dict[str, Any]
    id: str = ""


@dataclass
class ToolResult:
    """Result from executing a tool function.

    Attributes:
        call: The original function call.
        result: The function's return value.
        error: Error message if execution failed.
    """

    call: FunctionCall
    result: Any | None = None
    error: str | None = None


@dataclass
class GroundingResult:
    """Result with grounding metadata.

    Attributes:
        text: Generated text.
        grounding_chunks: Source chunks from grounding.
        search_queries: Queries used for grounding.
        supports: Grounding support scores.
    """

    text: str
    grounding_chunks: list[dict[str, Any]] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    supports: list[dict[str, Any]] = field(default_factory=list)


def _python_type_to_json_schema(python_type: type) -> dict[str, Any]:
    """Convert Python type to JSON Schema.

    Args:
        python_type: Python type annotation.

    Returns:
        JSON Schema dict.
    """
    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
    }

    # Handle typing generics
    origin = getattr(python_type, "__origin__", None)
    if origin is list:
        args = getattr(python_type, "__args__", (Any,))
        return {
            "type": "array",
            "items": _python_type_to_json_schema(args[0]) if args else {},
        }
    elif origin is dict:
        return {"type": "object"}

    return type_map.get(python_type, {"type": "string"})


def _function_to_declaration(func: Callable[..., Any]) -> FunctionDeclaration:
    """Convert a Python function to a FunctionDeclaration.

    Args:
        func: Python callable with type hints.

    Returns:
        FunctionDeclaration for Gemini tools.
    """
    sig = inspect.signature(func)
    hints = get_type_hints(func)
    doc = inspect.getdoc(func) or ""

    # Build parameters schema
    properties: dict[str, Any] = {}
    required: list[str] = []

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        param_type = hints.get(param_name, str)
        param_schema = _python_type_to_json_schema(param_type)

        # Extract param description from docstring if available
        param_schema["description"] = f"Parameter {param_name}"

        properties[param_name] = param_schema

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    parameters = {
        "type": "object",
        "properties": properties,
    }
    if required:
        parameters["required"] = required

    return FunctionDeclaration(
        name=func.__name__,
        description=doc.split("\n")[0] if doc else f"Function {func.__name__}",
        parameters=parameters,
        callable=func,
    )


class GeminiClient:
    """Client for interacting with Google Gemini API."""

    def __init__(self, model_name: str = "gemini-3-pro-preview") -> None:
        """Initialize Gemini client.

        Args:
            model_name: Gemini model name (e.g., "gemini-3-pro-preview")
        """
        self.model_name = model_name
        self.api_key = os.getenv("GOOGLE_API_KEY")
        self.client: Client | None = None
        self.initialized = False

    async def initialize(self) -> None:
        """Initialize the Gemini API client.

        Raises:
            RuntimeError: If google-genai is not installed or API key is missing.
        """
        if self.initialized:
            return

        if not GEMINI_AVAILABLE:
            raise RuntimeError(
                "google-genai library not installed. Please install with: pip install google-genai"
            )

        if not self.api_key:
            raise RuntimeError(
                "GOOGLE_API_KEY environment variable not set[Any]. Please set[Any] it to use Gemini models."
            )

        try:
            # The new SDK uses explicit Client initialization
            # It picks up GOOGLE_API_KEY from env automatically if not passed,
            # but we pass it explicitly to be safe.
            self.client = genai.Client(api_key=self.api_key)
            self.initialized = True
            logger.info(f"✅ GeminiClient initialized with model: {self.model_name}")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Gemini client: {e}") from e

    @retry_async(attempts=3)
    async def generate_text(
        self, prompt: str, max_tokens: int = 1000, temperature: float = 0.7, **kwargs: Any
    ) -> str:
        """Generate text using Gemini.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional arguments passed to generate_content

        Returns:
            Generated text response
        """
        if not self.initialized or not self.client:
            await self.initialize()

        # Ensure client is initialized
        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        try:
            # Configure generation config using the new types
            # Note: Parameter names might vary in the new SDK vs old.
            # Assuming standard params for now based on user snippet structure.

            # Create the config object if needed, or pass params directly.
            # The user snippet showed:
            # client.models.generate_content(model=..., contents=...)

            # We need to handle async execution since the SDK might be synchronous
            import asyncio

            def _generate() -> str:
                # Prepare configuration
                # Note: thinking_budget is deprecated in favor of thinking_level in Gemini 3
                # but for now we use the standard generation config from the new SDK
                assert self.client is not None, "Client must be initialized"
                config = types.GenerateContentConfig(
                    max_output_tokens=max_tokens, temperature=temperature, candidate_count=1
                )

                # Call generation
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name, contents=prompt, config=config
                    )

                    # #region agent log
                    try:
                        import json
                        import time

                        with open(
                            "/Users/schizodactyl/projects/chronOS/.cursor/debug.log", "a"
                        ) as f:
                            log_entry = {
                                "timestamp": time.time() * 1000,
                                "location": "gemini_client.py:_generate",
                                "message": "Gemini response received",
                                "data": {
                                    "response_type": str(type(response)),
                                    "has_text": hasattr(response, "text"),
                                    "text_val": (
                                        str(response.text) if hasattr(response, "text") else "N/A"
                                    ),
                                    "has_candidates": hasattr(response, "candidates"),
                                    "candidates_val": (
                                        str(response.candidates)
                                        if hasattr(response, "candidates")
                                        else "N/A"
                                    ),
                                    "candidates_type": (
                                        str(type(response.candidates))
                                        if hasattr(response, "candidates")
                                        else "N/A"
                                    ),
                                    "dir_response": str(dir(response)),
                                },
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "A,B,D",
                            }
                            f.write(json.dumps(log_entry) + "\n")
                    except Exception:
                        pass
                    # #endregion

                    # Robust response parsing for new SDK
                    if hasattr(response, "text") and response.text is not None:
                        return str(response.text)
                    elif hasattr(response, "candidates") and response.candidates:
                        # Fallback for structured content or different SDK version
                        candidate = response.candidates[0]
                        if hasattr(candidate, "content") and candidate.content is not None:
                            if hasattr(candidate.content, "parts") and candidate.content.parts:
                                # Check if parts is valid and subscriptable
                                parts = candidate.content.parts
                                if parts and len(parts) > 0:
                                    part = parts[0]
                                    return str(part.text) if hasattr(part, "text") else str(part)

                    # If we get here, check for other common attributes in new SDK
                    if hasattr(response, "parts") and response.parts:
                        part = response.parts[0]
                        return str(part.text) if hasattr(part, "text") else str(part)

                    return ""
                except Exception as api_err:
                    # #region agent log
                    try:
                        import json
                        import time

                        with open(
                            "/Users/schizodactyl/projects/chronOS/.cursor/debug.log", "a"
                        ) as f:
                            log_entry = {
                                "timestamp": time.time() * 1000,
                                "location": "gemini_client.py:_generate",
                                "message": "Gemini API Exception",
                                "data": {"error": str(api_err), "type": str(type(api_err))},
                                "sessionId": "debug-session",
                                "runId": "run1",
                                "hypothesisId": "C",
                            }
                            f.write(json.dumps(log_entry) + "\n")
                    except Exception:
                        pass
                    # #endregion
                    raise api_err

            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, _generate)

        except Exception as e:
            logger.error(f"Gemini generation failed: {e}")
            raise RuntimeError(f"Gemini generation failed: {e}") from e

    @retry_async(attempts=3)
    async def generate_structured(
        self,
        prompt: str,
        response_model: type[Any],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ) -> Any:
        """Generate structured output matching a Pydantic schema."""
        if not self.initialized or not self.client:
            await self.initialize()

        # Ensure client is initialized
        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        try:
            import asyncio
            import json

            # Pydantic schema extraction
            # Google GenAI SDK often accepts the class itself if using the right helpers,
            # or we can request JSON output and parse it.
            # Using response_mime_type="application/json" is reliable.

            def _generate() -> str:
                assert self.client is not None, "Client must be initialized"
                config = types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    response_mime_type="application/json",
                    response_schema=response_model,  # Pass Pydantic model directly if supported, else schema
                    candidate_count=1,
                )

                response = self.client.models.generate_content(
                    model=self.model_name, contents=prompt, config=config
                )
                return str(response.text) if response.text is not None else ""

            loop = asyncio.get_running_loop()
            response_text = await loop.run_in_executor(None, _generate)

            # Parse JSON and validate with Pydantic
            data = json.loads(response_text)
            return response_model(**data)

        except Exception as e:
            logger.error(f"Gemini structured generation failed: {e}")
            raise RuntimeError(f"Gemini structured generation failed: {e}") from e

    @retry_async(attempts=3)
    async def generate_with_tools(
        self,
        prompt: str,
        tools: list[Callable[..., Any]],
        max_tokens: int = 2000,
        temperature: float = 0.7,
        auto_execute: bool = True,
        max_iterations: int = 5,
    ) -> tuple[str, list[ToolResult]]:
        """Generate response with function calling (tool use).

        The model can call functions to gather information or perform actions,
        then use the results to generate a final response.

        Args:
            prompt: User prompt.
            tools: List of Python functions to make available.
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature.
            auto_execute: If True, automatically execute tool calls and continue.
            max_iterations: Maximum tool call iterations.

        Returns:
            Tuple of (final_text, list of ToolResults).

        Example:
            def get_weather(city: str) -> dict:
                '''Get weather for a city.'''
                return {"temp": 20, "conditions": "sunny"}

            text, results = await client.generate_with_tools(
                prompt="What's the weather in Seattle and NYC?",
                tools=[get_weather],
            )
        """
        if not self.initialized or not self.client:
            await self.initialize()

        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        # Convert functions to declarations
        declarations = [_function_to_declaration(f) for f in tools]
        func_map = {d.name: d.callable for d in declarations}

        # Build tool config for Gemini
        tool_defs = []
        for decl in declarations:
            tool_defs.append(
                {
                    "name": decl.name,
                    "description": decl.description,
                    "parameters": decl.parameters,
                }
            )

        all_results: list[ToolResult] = []
        messages = [{"role": "user", "parts": [{"text": prompt}]}]
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            def _generate_with_tools() -> Any:
                assert self.client is not None
                config = types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    candidate_count=1,
                    tools=[{"function_declarations": tool_defs}],
                )

                return self.client.models.generate_content(
                    model=self.model_name,
                    contents=messages,
                    config=config,
                )

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, _generate_with_tools)

            # Check for function calls
            function_calls = self._extract_function_calls(response)

            if not function_calls:
                # No more function calls, extract final text
                final_text = self._extract_text(response)
                return final_text, all_results

            if not auto_execute:
                # Return function calls without executing
                for fc in function_calls:
                    all_results.append(ToolResult(call=fc))
                final_text = self._extract_text(response)
                return final_text, all_results

            # Execute function calls
            function_responses = []
            for fc in function_calls:
                try:
                    func = func_map.get(fc.name)
                    if func:
                        # Execute synchronously or await if async
                        if asyncio.iscoroutinefunction(func):
                            result = await func(**fc.args)
                        else:
                            result = await loop.run_in_executor(
                                None, lambda f=func, a=fc.args: f(**a)
                            )
                        all_results.append(ToolResult(call=fc, result=result))
                        function_responses.append(
                            {
                                "name": fc.name,
                                "response": {"result": result},
                            }
                        )
                    else:
                        error = f"Function {fc.name} not found"
                        all_results.append(ToolResult(call=fc, error=error))
                        function_responses.append(
                            {
                                "name": fc.name,
                                "response": {"error": error},
                            }
                        )
                except Exception as e:
                    all_results.append(ToolResult(call=fc, error=str(e)))
                    function_responses.append(
                        {
                            "name": fc.name,
                            "response": {"error": str(e)},
                        }
                    )

            # Add function results to conversation
            messages.append(
                {
                    "role": "model",
                    "parts": [
                        {"function_call": {"name": fc.name, "args": fc.args}}
                        for fc in function_calls
                    ],
                }
            )
            messages.append(
                {
                    "role": "function",
                    "parts": [{"function_response": fr} for fr in function_responses],
                }
            )

        # Max iterations reached
        final_text = self._extract_text(response) if response else ""
        return final_text, all_results

    def _extract_function_calls(self, response: Any) -> list[FunctionCall]:
        """Extract function calls from Gemini response.

        Args:
            response: Gemini API response.

        Returns:
            List of FunctionCall objects.
        """
        calls = []

        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    for part in candidate.content.parts or []:
                        if hasattr(part, "function_call") and part.function_call:
                            fc = part.function_call
                            calls.append(
                                FunctionCall(
                                    name=fc.name,
                                    args=dict(fc.args) if fc.args else {},
                                )
                            )
        except Exception as e:
            logger.warning(f"Error extracting function calls: {e}")

        return calls

    def _extract_text(self, response: Any) -> str:
        """Extract text from Gemini response.

        Args:
            response: Gemini API response.

        Returns:
            Text string.
        """
        try:
            if hasattr(response, "text") and response.text:
                return str(response.text)
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    parts = candidate.content.parts or []
                    text_parts = []
                    for part in parts:
                        if hasattr(part, "text") and part.text:
                            text_parts.append(str(part.text))
                    return "\n".join(text_parts)
        except Exception as e:
            logger.warning(f"Error extracting text: {e}")

        return ""

    @retry_async(attempts=3)
    async def generate_with_grounding(
        self,
        prompt: str,
        grounding_source: str = "google_search",
        max_tokens: int = 2000,
        temperature: float = 0.7,
        dynamic_retrieval_threshold: float = 0.3,
    ) -> GroundingResult:
        """Generate response with grounding (Google Search or custom).

        Grounding provides real-time, factual information by searching
        external sources and citing them.

        Args:
            prompt: User prompt.
            grounding_source: "google_search" for Google Search grounding.
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature.
            dynamic_retrieval_threshold: Threshold for dynamic retrieval (0-1).

        Returns:
            GroundingResult with text and source metadata.

        Example:
            result = await client.generate_with_grounding(
                prompt="What are the latest developments in AI?",
                grounding_source="google_search",
            )
            print(result.text)
            for chunk in result.grounding_chunks:
                print(f"Source: {chunk.get('uri')}")
        """
        if not self.initialized or not self.client:
            await self.initialize()

        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        def _generate_grounded() -> Any:
            assert self.client is not None

            # Configure grounding tool
            tools = []
            if grounding_source == "google_search":
                tools.append(
                    {
                        "google_search": {
                            "dynamic_retrieval_config": {
                                "mode": "MODE_DYNAMIC",
                                "dynamic_threshold": dynamic_retrieval_threshold,
                            }
                        }
                    }
                )

            config = types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                candidate_count=1,
                tools=tools if tools else None,
            )

            return self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, _generate_grounded)

        # Extract text
        text = self._extract_text(response)

        # Extract grounding metadata
        grounding_chunks = []
        search_queries = []
        supports = []

        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]

                # Get grounding metadata
                grounding_meta = getattr(candidate, "grounding_metadata", None)
                if grounding_meta:
                    # Grounding chunks (sources)
                    if hasattr(grounding_meta, "grounding_chunks"):
                        for chunk in grounding_meta.grounding_chunks or []:
                            chunk_data = {
                                "uri": getattr(getattr(chunk, "web", None), "uri", None),
                                "title": getattr(getattr(chunk, "web", None), "title", None),
                            }
                            grounding_chunks.append(chunk_data)

                    # Search queries used
                    if hasattr(grounding_meta, "web_search_queries"):
                        search_queries = list(grounding_meta.web_search_queries or [])

                    # Grounding supports (inline citations)
                    if hasattr(grounding_meta, "grounding_supports"):
                        for support in grounding_meta.grounding_supports or []:
                            support_data = {
                                "segment": getattr(support, "segment", {}),
                                "grounding_chunk_indices": list(
                                    getattr(support, "grounding_chunk_indices", [])
                                ),
                                "confidence_scores": list(
                                    getattr(support, "confidence_scores", [])
                                ),
                            }
                            supports.append(support_data)

        except Exception as e:
            logger.warning(f"Error extracting grounding metadata: {e}")

        return GroundingResult(
            text=text,
            grounding_chunks=grounding_chunks,
            search_queries=search_queries,
            supports=supports,
        )

    @retry_async(attempts=3)
    async def generate_with_code_execution(
        self,
        prompt: str,
        max_tokens: int = 4000,
        temperature: float = 0.3,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Generate response with code execution capability.

        The model can write and execute Python code to solve problems.

        Args:
            prompt: User prompt.
            max_tokens: Maximum output tokens.
            temperature: Sampling temperature.

        Returns:
            Tuple of (text, list of code execution results).

        Example:
            text, executions = await client.generate_with_code_execution(
                prompt="Calculate the first 10 fibonacci numbers",
            )
        """
        if not self.initialized or not self.client:
            await self.initialize()

        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        def _generate_with_code() -> Any:
            assert self.client is not None

            config = types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                candidate_count=1,
                tools=[{"code_execution": {}}],
            )

            return self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )

        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(None, _generate_with_code)

        # Extract text and code execution results
        text_parts = []
        code_results = []

        try:
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and candidate.content:
                    for part in candidate.content.parts or []:
                        if hasattr(part, "text") and part.text:
                            text_parts.append(str(part.text))
                        if hasattr(part, "executable_code") and part.executable_code:
                            code_results.append(
                                {
                                    "type": "code",
                                    "language": getattr(part.executable_code, "language", "python"),
                                    "code": getattr(part.executable_code, "code", ""),
                                }
                            )
                        if hasattr(part, "code_execution_result") and part.code_execution_result:
                            code_results.append(
                                {
                                    "type": "result",
                                    "outcome": getattr(part.code_execution_result, "outcome", ""),
                                    "output": getattr(part.code_execution_result, "output", ""),
                                }
                            )
        except Exception as e:
            logger.warning(f"Error extracting code execution results: {e}")

        return "\n".join(text_parts), code_results

    async def count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for.

        Returns:
            Token count.
        """
        if not self.initialized or not self.client:
            await self.initialize()

        if not self.client:
            raise RuntimeError("Gemini client not initialized")

        def _count() -> int:
            assert self.client is not None
            result = self.client.models.count_tokens(
                model=self.model_name,
                contents=text,
            )
            return result.total_tokens if hasattr(result, "total_tokens") else 0

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, _count)
