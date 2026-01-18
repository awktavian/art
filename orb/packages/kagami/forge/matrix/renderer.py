"""Forge renderer state management."""

import logging
import time
from typing import Any

from kagami_observability.trace import trace_span

from kagami.forge.schema import CharacterRequest

FORGE_STAGE_DURATION_MS: Any = None
try:
    from kagami_observability.metrics import (
        FORGE_STAGE_DURATION_MS as _FORGE_STAGE_DURATION_MS,
    )

    FORGE_STAGE_DURATION_MS = _FORGE_STAGE_DURATION_MS
except Exception:
    pass

logger = logging.getLogger(__name__)


class ForgeStageContext:
    """Context manager that records Forge stage events and emits trace spans."""

    def __init__(
        self,
        matrix: Any,
        component: str,
        request: CharacterRequest | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self._matrix = matrix
        self._component = component
        self._request = request
        self._extra = extra or {}
        self._attrs = matrix._build_trace_attrs(component, request, self._extra)
        self._span = trace_span(f"forge.{component}", self._attrs)
        self._start = 0.0

    def __enter__(self) -> Any:
        self._start = time.perf_counter()
        self._matrix._record_trace_event(self._component, "start", self._request, **self._extra)
        return self._span.__enter__()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        duration_ms = (time.perf_counter() - self._start) * 1000.0
        status = "success" if exc is None else "error"
        error_text = None if exc is None else str(exc)
        self._matrix._record_trace_event(
            self._component,
            status,
            self._request,
            duration_ms=duration_ms,
            error=error_text,
            **self._extra,
        )
        try:
            if FORGE_STAGE_DURATION_MS is not None:
                FORGE_STAGE_DURATION_MS.labels(self._component, status).observe(
                    max(0.0, duration_ms)
                )
        except Exception:
            pass
        result: bool = self._span.__exit__(exc_type, exc, tb)
        return result

    async def __aenter__(self) -> Any:
        return self.__enter__()

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> bool:
        return self.__exit__(exc_type, exc, tb)
