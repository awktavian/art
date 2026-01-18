"""LLM Observer - Metrics and telemetry for LLM service.

Extracted from service.py to reduce god module complexity.
Centrality goal: <0.001
"""

import logging
import time
from typing import Any

from kagami_observability.metrics import REGISTRY
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)


# Define metrics
try:
    LLM_REQUESTS = Counter(
        "kagami_llm_requests_total",
        "Total LLM requests",
        ["app", "task_type", "provider", "model", "cache"],
        registry=REGISTRY,
    )
    LLM_DURATION = Histogram(
        "kagami_llm_request_duration_seconds",
        "LLM request duration",
        ["app", "task_type", "provider", "model", "cache"],
        registry=REGISTRY,
    )
    LLM_INPUT_CHARS = Counter(
        "kagami_llm_input_chars_total",
        "Total input characters sent to LLM",
        ["app", "task_type", "provider", "model", "cache"],
        registry=REGISTRY,
    )
    LLM_OUTPUT_CHARS = Counter(
        "kagami_llm_output_chars_total",
        "Total output characters produced by LLM",
        ["app", "task_type", "provider", "model", "cache"],
        registry=REGISTRY,
    )
except ValueError:
    # Metrics already registered - reuse them
    collectors = list(REGISTRY._names_to_collectors.values())
    LLM_REQUESTS = next(  # type: ignore[assignment]
        (c for c in collectors if hasattr(c, "_name") and c._name == "kagami_llm_requests_total"),
        None,
    )
    LLM_DURATION = next(  # type: ignore[assignment]
        (
            c
            for c in collectors
            if hasattr(c, "_name") and c._name == "kagami_llm_request_duration_seconds"
        ),
        None,
    )
    LLM_INPUT_CHARS = next(  # type: ignore[assignment]
        (
            c
            for c in collectors
            if hasattr(c, "_name") and c._name == "kagami_llm_input_chars_total"
        ),
        None,
    )
    LLM_OUTPUT_CHARS = next(  # type: ignore[assignment]
        (
            c
            for c in collectors
            if hasattr(c, "_name") and c._name == "kagami_llm_output_chars_total"
        ),
        None,
    )

try:
    LLM_TOKENS_TOTAL = Counter(
        "kagami_llm_tokens_total",
        "Total input/output tokens accounted",
        ["type", "provider", "model"],
        registry=REGISTRY,
    )
    LLM_COST_USD = Counter(
        "kagami_llm_cost_usd_total",
        "Total approximate cost in USD (best-effort)",
        ["provider", "model"],
        registry=REGISTRY,
    )
except Exception:
    LLM_TOKENS_TOTAL = None  # type: ignore[assignment]
    LLM_COST_USD = None  # type: ignore[assignment]

LLM_THINKING_PRESENT = Counter(
    "kagami_llm_thinking_present_total",
    "Number of LLM responses that included hidden thinking content",
    ["app", "task_type", "provider", "model"],
    registry=REGISTRY,
)

LLM_TOOL_CALLS = Counter(
    "kagami_llm_tool_calls_total",
    "Total number of tool calls returned by LLM responses",
    ["app", "task_type", "provider", "model"],
    registry=REGISTRY,
)

LLM_VALIDATION_ERRORS = Counter(
    "kagami_llm_validation_errors_total",
    "LLM output validation failures",
    ["app", "task_type", "reason"],
    registry=REGISTRY,
)


class LLMObserver:
    """Observes and tracks LLM requests, responses, and performance."""

    def __init__(self) -> None:
        """Initialize LLM observer."""
        self._request_start_times: dict[str, float] = {}

    def start_request(
        self,
        request_id: str,
        app_name: str,
        task_type: Any,
        provider: str,
        model: str,
        prompt_length: int,
        cache_status: str = "miss",
    ) -> None:
        """Record the start of an LLM request.

        Args:
            request_id: Unique request identifier
            app_name: Application name
            task_type: Task type enum
            provider: Provider name (local, api, etc.)
            model: Model name
            prompt_length: Length of input prompt in characters
            cache_status: "hit" or "miss"
        """
        self._request_start_times[request_id] = time.time()

        # Record input metrics
        task_name = getattr(task_type, "name", str(task_type))
        LLM_REQUESTS.labels(app_name, task_name, provider, model, cache_status).inc()
        LLM_INPUT_CHARS.labels(app_name, task_name, provider, model, cache_status).inc(
            prompt_length
        )

    def end_request(
        self,
        request_id: str,
        app_name: str,
        task_type: Any,
        provider: str,
        model: str,
        response_length: int,
        cache_status: str = "miss",
        had_thinking: bool = False,
        tool_call_count: int = 0,
    ) -> None:
        """Record the end of an LLM request.

        Args:
            request_id: Unique request identifier
            app_name: Application name
            task_type: Task type enum
            provider: Provider name
            model: Model name
            response_length: Length of response in characters
            cache_status: "hit" or "miss"
            had_thinking: Whether response included thinking tokens
            tool_call_count: Number of tool calls in response
        """
        # Calculate duration
        start_time = self._request_start_times.pop(request_id, None)
        if start_time:
            duration = time.time() - start_time
            task_name = getattr(task_type, "name", str(task_type))
            LLM_DURATION.labels(app_name, task_name, provider, model, cache_status).observe(
                duration
            )

            # Record output metrics
            LLM_OUTPUT_CHARS.labels(app_name, task_name, provider, model, cache_status).inc(
                response_length
            )

            # Record thinking presence
            if had_thinking:
                LLM_THINKING_PRESENT.labels(app_name, task_name, provider, model).inc()

            # Record tool calls
            if tool_call_count > 0:
                LLM_TOOL_CALLS.labels(app_name, task_name, provider, model).inc(tool_call_count)

    def record_validation_error(
        self,
        app_name: str,
        task_type: Any,
        reason: str,
    ) -> None:
        """Record a validation error.

        Args:
            app_name: Application name
            task_type: Task type enum
            reason: Error reason (empty, invalid_json, etc.)
        """
        task_name = getattr(task_type, "name", str(task_type))
        LLM_VALIDATION_ERRORS.labels(app_name, task_name, reason).inc()

    def record_tokens(
        self,
        token_type: str,
        provider: str,
        model: str,
        count: int,
    ) -> None:
        """Record token usage.

        Args:
            token_type: "input" or "output"
            provider: Provider name
            model: Model name
            count: Number of tokens
        """
        if LLM_TOKENS_TOTAL:
            LLM_TOKENS_TOTAL.labels(token_type, provider, model).inc(count)

    def record_cost(
        self,
        provider: str,
        model: str,
        cost_usd: float,
    ) -> None:
        """Record estimated cost.

        Args:
            provider: Provider name
            model: Model name
            cost_usd: Cost in USD
        """
        if LLM_COST_USD:
            LLM_COST_USD.labels(provider, model).inc(cost_usd)


# Global observer instance
_observer: LLMObserver | None = None


def get_observer() -> LLMObserver:
    """Get or create the global LLM observer instance."""
    global _observer
    if _observer is None:
        _observer = LLMObserver()
    return _observer
