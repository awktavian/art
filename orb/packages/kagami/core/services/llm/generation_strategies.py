"""Simplified LLM generate implementation.

Extracts retry/structured/repair logic from the 558-line god method
into focused strategy classes.

HOT PATH OPTIMIZATIONS:
- Parallel batch generation via asyncio.gather()
- Cache hit tracking integration
- Memory-aware token shaping
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import os
from enum import Enum
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# Module-level cache for TaskType to avoid repeated dynamic imports (HOT PATH OPTIMIZATION)
_cached_task_type: Any = None
_task_type_loaded = False


def _get_default_task_type() -> Any:
    """Get default TaskType.CONVERSATION, caching after first load."""
    global _cached_task_type, _task_type_loaded
    if not _task_type_loaded:
        try:
            import importlib

            svc_mod = importlib.import_module("kagami.core.services.llm.service")
            TaskType = getattr(svc_mod, "TaskType", None)
            if TaskType is not None:
                _cached_task_type = TaskType.CONVERSATION
        except (ImportError, AttributeError):
            pass
        _task_type_loaded = True
    return _cached_task_type


@runtime_checkable
class LLMClientProtocol(Protocol):
    """Protocol for LLM clients."""

    model: Any

    async def initialize(self) -> None: ...
    async def generate_text(self, prompt: str, max_tokens: int, temperature: float) -> str: ...


class GenerationStrategy(Enum):
    """Strategy for LLM generation."""

    STANDARD = "standard"
    STRUCTURED = "structured"
    GRAMMAR_CONSTRAINED = "grammar_constrained"
    JSON_REPAIR = "json_repair"


async def generate_parallel(
    service: Any,
    prompts: list[str],
    app_name: str,
    task_type: Any = None,
    max_tokens: int = 1000,
    temperature: float = 0.7,
    max_concurrent: int | None = None,
) -> list[str]:
    """HOT PATH OPTIMIZATION: Generate multiple responses in parallel using asyncio.gather().

    This is more efficient than sequential generation when making multiple
    independent LLM calls.

    Args:
        service: KagamiOSLLMService instance
        prompts: List of prompts to generate responses for
        app_name: Requesting app name
        task_type: Task type for routing
        max_tokens: Maximum tokens to generate per response
        temperature: Sampling temperature
        max_concurrent: Maximum concurrent requests (default: 8 from env)

    Returns:
        List of generated responses in the same order as prompts

    Example:
        results = await generate_parallel(
            service,
            ["Prompt 1", "Prompt 2", "Prompt 3"],
            app_name="my_app",
        )
    """
    if not prompts:
        return []

    # Get max concurrent from env or use default
    if max_concurrent is None:
        max_concurrent = int(os.getenv("KAGAMI_LLM_MAX_CONCURRENT", "8"))

    semaphore = asyncio.Semaphore(max_concurrent)

    async def bounded_generate(prompt: str) -> str:
        async with semaphore:
            result = await generate_v2(
                service,
                prompt,
                app_name,
                task_type,
                max_tokens,
                temperature,
                structured_output=None,
                routing_hints=None,
            )
            return str(result) if result else ""

    # Use asyncio.gather for parallel execution
    tasks = [bounded_generate(prompt) for prompt in prompts]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to empty strings and log
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"Parallel generation failed for prompt {i}: {result}")
            processed_results.append("")
        else:
            processed_results.append(result)

    return processed_results


async def generate_v2(
    service: Any,
    prompt: str,
    app_name: str,
    task_type: Any = None,
    max_tokens: int = 1000,
    temperature: float = 0.7,
    structured_output: type[T] | None = None,
    routing_hints: dict[str, Any] | None = None,
) -> str | T:
    """Simplified generate method that delegates to strategy classes.

    Args:
        service: KagamiOSLLMService instance
        prompt: Input prompt
        app_name: Requesting app name
        task_type: Task type for routing
        max_tokens: Maximum tokens to generate
        temperature: Sampling temperature
        structured_output: Optional Pydantic model for structured generation
        routing_hints: Optional routing hints

    Returns:
        Generated text or structured output
    """
    hints = routing_hints or {}

    # Default task type if not provided (uses cached value - HOT PATH OPTIMIZATION)
    if task_type is None:
        task_type = _get_default_task_type()

    # 1. Enhance prompt with context
    enhanced_prompt = await _enhance_prompt(service, prompt, app_name, hints)

    # 2. Choose generation strategy
    if structured_output is not None:
        strategy = GenerationStrategy.STRUCTURED
    elif hints.get("grammar"):
        strategy = GenerationStrategy.GRAMMAR_CONSTRAINED
    else:
        strategy = GenerationStrategy.STANDARD

    # 3. Generate with retries
    max_retries = 3
    last_error = None
    start_time = None
    result = None

    for attempt in range(max_retries):
        try:
            import time

            start_time = time.time()

            if strategy == GenerationStrategy.STRUCTURED:
                result = await _generate_structured(
                    service,
                    enhanced_prompt,
                    structured_output,  # type: ignore[arg-type]
                    max_tokens,
                    temperature,
                    hints,
                )
            elif strategy == GenerationStrategy.GRAMMAR_CONSTRAINED:
                result = await _generate_with_grammar(  # type: ignore[assignment]
                    service, enhanced_prompt, hints["grammar"], max_tokens, temperature
                )
            else:  # STANDARD
                result = await _generate_standard(  # type: ignore[assignment]
                    service, enhanced_prompt, app_name, task_type, max_tokens, temperature, hints
                )

            # PROMPT TRACE CAPTURE (10/10 Debugging)
            try:
                generation_time_ms = (time.time() - start_time) * 1000 if start_time else 0.0

                # Get correlation_id from hints if available
                correlation_id = hints.get("correlation_id") or f"llm_{int(time.time() * 1000)}"

                # Capture prompt trace for debugging
                from kagami.core.debugging.unified_debugging_system import (
                    get_unified_debugging_system,
                )

                debug_sys = get_unified_debugging_system()

                # Estimate tokens (simplified)
                prompt_tokens = len(enhanced_prompt.split()) * 1.3  # rough estimate
                response_str = str(result) if result else ""
                response_tokens = len(response_str.split()) * 1.3

                debug_sys.capture_prompt(
                    correlation_id=correlation_id,
                    model=hints.get("model", "qwen3-coder:14b"),
                    prompt=enhanced_prompt[:5000],  # Truncate for storage
                    prompt_tokens=int(prompt_tokens),
                    response=response_str[:5000],
                    response_tokens=int(response_tokens),
                    temperature=temperature,
                    max_tokens=max_tokens,
                    generation_time_ms=generation_time_ms,
                    finish_reason="completed",
                )
            except (ImportError, AttributeError, RuntimeError) as e:
                # Don't fail generation if capture fails
                logger.debug(f"Prompt capture failed: {e}")
                # Non-critical - debugging trace is optional enhancement

            return result  # type: ignore[return-value]

        except ValueError:
            raise
        except Exception as e:
            last_error = e
            logger.warning(f"Generation attempt {attempt + 1} failed: {e}")

            # Try JSON repair on last attempt if structured output was requested
            if attempt == max_retries - 1 and structured_output is not None:
                try:
                    return await _try_json_repair(service, enhanced_prompt, structured_output)
                except (ValueError, RuntimeError) as e:
                    logger.debug(f"JSON repair failed: {e}")
                    # Expected when JSON is too malformed for repair

            if attempt < max_retries - 1:
                # Exponential backoff
                import asyncio

                await asyncio.sleep(2**attempt)

    # All retries failed
    raise RuntimeError(
        f"LLM generation failed after {max_retries} attempts: {last_error}"
    ) from None


async def _enhance_prompt(
    service: Any,
    prompt: str,
    app_name: str,
    hints: dict[str, Any],
) -> str:
    """Enhance prompt with personality and context."""
    # Add personality prelude
    try:
        from kagami.core.rules_loader import build_prompt_prelude

        prelude = build_prompt_prelude(app_name)
        enhanced = f"{prelude}\n\n{prompt}"
    except (ImportError, AttributeError) as e:
        logger.debug(f"Rules prelude not available: {e}")
        enhanced = prompt
        # Optional enhancement - rules prelude adds personality but isn't required

    # Merge memory context if available
    try:
        enhanced = await service._merge_memory_context(enhanced, hints)
    except (AttributeError, RuntimeError) as e:
        logger.debug(f"Memory context merge failed: {e}")
        # Non-critical - memory context enhances quality but isn't required

    return enhanced


async def _generate_structured(
    service: Any,
    prompt: str,
    response_model: type[T],
    max_tokens: int,
    temperature: float,
    hints: dict[str, Any],
) -> T:
    """Generate structured output using configured provider (default: anthropic)."""
    provider = hints.get("provider") or os.getenv("KAGAMI_LLM_PROVIDER", "anthropic")
    model = hints.get("model")

    # Use service to get/create client (handles caching and lazy loading)
    # Note: structured=True hint tells service to prepare for structured output if needed
    get_client_fn = getattr(service, "_get_or_load_client", None)
    client: Any = None
    if callable(get_client_fn):
        maybe_client = get_client_fn(provider, model, structured=True)
        client = await maybe_client if inspect.isawaitable(maybe_client) else maybe_client
    else:
        # Fallback if service doesn't have the method (shouldn't happen in K os)
        from kagami.core.services.llm.structured_client import get_structured_client

        client = get_structured_client()
        await client.initialize()

    if hasattr(client, "generate_structured"):
        result = await client.generate_structured(
            prompt=prompt,
            response_model=response_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return result  # type: ignore[no-any-return]

    # Fallback: direct outlines usage if client is generic but we have local model ref
    # This path is mostly legacy/safety for non-updated clients
    from kagami.core.services.llm.structured_client import get_structured_client

    client = get_structured_client()
    await client.initialize()

    return await client.generate_structured(
        prompt=prompt,
        response_model=response_model,
        max_tokens=max_tokens,
        temperature=temperature,
    )


async def _generate_with_grammar(
    service: Any,
    prompt: str,
    grammar: str,
    max_tokens: int,
    temperature: float,
) -> str:
    """Generate with grammar constraints using outlines."""
    import outlines  # type: ignore[import-untyped]
    import outlines.generate  # type: ignore[import-untyped]

    # Create model wrapper
    from kagami.core.services.llm.structured_client import (
        create_structured_client,  # type: ignore[attr-defined]
    )

    client: Any = create_structured_client()
    await client.initialize()

    model_wrapper = outlines.models.Transformers(model=client.model, tokenizer=client.tokenizer)

    # Generate with grammar
    generator = outlines.generate.cfg(model_wrapper, grammar)
    result = generator(prompt)

    return result  # type: ignore[no-any-return]


async def _generate_standard(
    service: Any,
    prompt: str,
    app_name: str,
    task_type: Any,
    max_tokens: int,
    temperature: float,
    hints: dict[str, Any],
) -> str:
    """Standard text generation using transformers."""
    raw_text: str | None = None

    # Prefer service-provided model selector when available (enables tests/mocks).
    select_model = getattr(service, "_select_model", None)
    if callable(select_model):
        try:
            hints = hints or {}
            args: list[Any] = [task_type, len(prompt), hints, None]
            if not inspect.ismethod(select_model):
                args.insert(0, service)

            sig = inspect.signature(select_model)
            args = args[: len(sig.parameters)]

            maybe_model = select_model(*args)
            model_client: Any = (
                await maybe_model if inspect.isawaitable(maybe_model) else maybe_model
            )

            if model_client is None:
                logger.debug(
                    f"Model selector returned None for task_type={task_type}, models may still be loading"
                )

            if model_client is not None:
                # Check if client has internal model loaded (handles lazy loading)
                if hasattr(model_client, "model") and model_client.model is None:
                    # Model exists but not loaded yet - try to trigger load
                    logger.debug("Client model not loaded yet, attempting lazy initialization")
                    if hasattr(model_client, "initialize") and callable(model_client.initialize):
                        init_result = model_client.initialize()
                        if inspect.isawaitable(init_result):
                            await init_result

                if hasattr(model_client, "reason_async") and callable(model_client.reason_async):
                    maybe = model_client.reason_async(prompt)
                    result = await maybe if inspect.isawaitable(maybe) else maybe
                    raw_text = str(result) if result is not None else None
                elif hasattr(model_client, "generate_text") and callable(
                    model_client.generate_text
                ):
                    maybe = model_client.generate_text(
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    result = await maybe if inspect.isawaitable(maybe) else maybe
                    raw_text = str(result) if result is not None else None
                elif hasattr(model_client, "generate") and callable(model_client.generate):
                    maybe = model_client.generate(
                        prompt=prompt,
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    result = await maybe if inspect.isawaitable(maybe) else maybe
                    raw_text = str(result) if result is not None else None
        except (AttributeError, RuntimeError, ValueError) as exc:
            logger.debug(f"Model selection fallback: {exc}")
            # Expected when model selector unavailable or client method missing

    if raw_text is None:
        # Use canonical model resolution from types.py
        from kagami.core.services.llm.types import get_default_model, is_test_mode

        if is_test_mode():
            raw_text = prompt
        else:
            model_name = get_default_model()

            client: Any = None
            get_cached_client = getattr(service, "_get_or_create_client", None)
            if callable(get_cached_client):
                try:
                    maybe_client = get_cached_client(
                        "transformers",
                        model_name,
                        structured=False,
                    )
                    client = (
                        await maybe_client if inspect.isawaitable(maybe_client) else maybe_client
                    )
                except (AttributeError, RuntimeError) as exc:
                    logger.warning(
                        "LLM service client cache unavailable, instantiating new transformers client: %s",
                        exc,
                    )
                    # Expected when service doesn't support client caching

            if client is None:
                from kagami.core.services.llm.llm_providers import create_transformers_client

                logger.info(f"Creating transformers client for model: {model_name}")
                client = create_transformers_client(model_name)
                await client.initialize()
                logger.info(f"Transformers client initialized: {client is not None}")

            if client is None:
                raise RuntimeError(f"Failed to create client for model {model_name}")

            logger.debug(f"Calling client.generate_text with client={type(client)}")
            raw_text = await client.generate_text(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )

    if raw_text is not None and not isinstance(raw_text, str):
        raw_text = str(raw_text)

    # Apply filtering
    from kagami.core.services.llm.llm_filtering import LLMFiltering

    filtering = LLMFiltering()

    sanitized = filtering.sanitize_output(raw_text)  # type: ignore[arg-type]
    validated = filtering.validate_text_output(sanitized, app_name, task_type, hints.get("format"))

    return validated


async def _try_json_repair(
    service: Any,
    prompt: str,
    response_model: type[T],
) -> T:
    """Attempt to repair malformed JSON using JSON repair library.

    Uses canonical model resolution from types.py.
    """
    from kagami.core.services.llm.llm_providers import create_transformers_client
    from kagami.core.services.llm.types import get_coder_model

    model_name = get_coder_model()  # Use coder model for JSON repair
    client = create_transformers_client(model_name)
    await client.initialize()

    raw_text = await client.generate_text(prompt=prompt, max_tokens=1000, temperature=0.2)

    # Try to extract and repair JSON
    import json
    import re

    # Find JSON-like content
    json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(0)

        # Try parsing
        try:
            data = json.loads(json_str)
            return response_model(**data)
        except json.JSONDecodeError:
            # Try json_repair if available
            try:
                from json_repair import repair_json

                repaired = repair_json(json_str)
                data = json.loads(repaired)
                return response_model(**data)
            except (ImportError, json.JSONDecodeError):
                pass

    raise ValueError("JSON repair failed - could not extract valid structured output") from None
