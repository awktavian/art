"""Forge events management."""

import logging
import time
from typing import Any

from kagami.forge.schema import CharacterRequest

logger = logging.getLogger(__name__)


class EventManager:
    """Manages tracing and event recording for Forge."""

    def __init__(self) -> None:
        self._execution_trace: list[dict[str, Any]] = []

    def record_trace_event(
        self,
        component: str,
        status: str,
        request: CharacterRequest | None = None,
        *,
        duration_ms: float | None = None,
        error: str | None = None,
        **extra: Any,
    ) -> None:
        event: dict[str, Any] = {"component": component, "status": status, "timestamp": time.time()}
        if request is not None:
            req_id = getattr(request, "request_id", None)
            if req_id:
                event["request_id"] = str(req_id)
            concept = getattr(request, "concept", None)
            if concept:
                event["concept"] = str(concept)
        if duration_ms is not None:
            event["duration_ms"] = round(duration_ms, 3)
        if error:
            event["error"] = str(error)[:500]
        for key, value in extra.items():
            if value is None:
                continue
            event[key] = value
        self._execution_trace.append(event)

    def build_trace_attrs(
        self, component: str, request: CharacterRequest | None, extra: dict[str, Any] | None
    ) -> dict[str, Any]:
        attrs: dict[str, Any] = {"forge.component": component}
        if request is not None:
            req_id = getattr(request, "request_id", None)
            if req_id:
                attrs["forge.request_id"] = str(req_id)
            concept = getattr(request, "concept", None)
            if concept:
                attrs["forge.concept"] = str(concept)
            try:
                quality = getattr(request, "quality_level", None)
                if quality is not None:
                    attrs["forge.quality_level"] = str(quality)
            except (AttributeError, TypeError) as e:
                logger.debug(f"Could not get quality_level from request: {e}")
        for key, value in (extra or {}).items():
            if value is None:
                continue
            attrs[f"forge.{key}"] = value
        return attrs
