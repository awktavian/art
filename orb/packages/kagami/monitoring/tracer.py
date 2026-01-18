"""Distributed Tracing System.

Comprehensive distributed tracing for smart home services:
- Request correlation across services
- Span tracking with timing and metadata
- Trace aggregation and analysis
- Performance bottleneck identification
- Service dependency mapping
- OpenTelemetry-compatible format

Enables end-to-end observability across all smart home operations.

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import contextvars
import functools
import json
import logging
import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable, Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# Context variables for trace propagation
_trace_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "trace_context", default={}
)


class SpanKind(str, Enum):
    """OpenTelemetry span kinds."""

    INTERNAL = "internal"  # Internal operation
    SERVER = "server"  # Server handling request
    CLIENT = "client"  # Client making request
    PRODUCER = "producer"  # Message producer
    CONSUMER = "consumer"  # Message consumer


class SpanStatus(str, Enum):
    """Span completion status."""

    OK = "ok"  # Successful completion
    ERROR = "error"  # Completed with error
    TIMEOUT = "timeout"  # Timed out
    CANCELLED = "cancelled"  # Cancelled/aborted


@dataclass
class SpanEvent:
    """Event within a span."""

    name: str
    timestamp: float
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    """Distributed tracing span."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    operation_name: str
    start_time: float
    end_time: float | None = None
    duration_ms: float | None = None
    kind: SpanKind = SpanKind.INTERNAL
    status: SpanStatus = SpanStatus.OK
    service_name: str = "kagami"
    resource: dict[str, Any] = field(default_factory=dict)
    tags: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    error_message: str | None = None
    stack_trace: str | None = None


@dataclass
class Trace:
    """Complete distributed trace."""

    trace_id: str
    spans: list[Span] = field(default_factory=list)
    start_time: float | None = None
    end_time: float | None = None
    duration_ms: float | None = None
    service_count: int = 0
    span_count: int = 0
    error_count: int = 0


class DistributedTracer:
    """Distributed tracing system for smart home services.

    Features:
    - Automatic trace ID generation and propagation
    - Span creation and management
    - Service dependency mapping
    - Performance bottleneck identification
    - Trace sampling and storage
    - OpenTelemetry compatibility
    """

    def __init__(self, service_name: str = "kagami", max_traces: int = 10000):
        self.service_name = service_name
        self.max_traces = max_traces

        # Trace storage
        self._traces: dict[str, Trace] = {}
        self._active_spans: dict[str, Span] = {}
        self._recent_traces: deque[str] = deque(maxlen=max_traces)

        # Sampling configuration
        self._sample_rate = 1.0  # Sample 100% by default
        self._force_sample_operations = set()

        # Thread-local storage for span stack
        self._local = threading.local()

        # Performance analysis
        self._operation_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "total_duration": 0.0,
                "min_duration": float("inf"),
                "max_duration": 0.0,
                "error_count": 0,
                "recent_durations": deque(maxlen=100),
            }
        )

        # Service dependency graph
        self._service_dependencies: dict[str, set[str]] = defaultdict(set)

        # Lock for thread safety
        self._lock = threading.Lock()

    def _get_span_stack(self) -> list[Span]:
        """Get thread-local span stack."""
        if not hasattr(self._local, "span_stack"):
            self._local.span_stack = []
        return self._local.span_stack

    def start_trace(self, operation_name: str, trace_id: str | None = None) -> str:
        """Start a new distributed trace."""
        if trace_id is None:
            trace_id = self._generate_trace_id()

        # Check sampling
        if not self._should_sample(operation_name, trace_id):
            return trace_id

        with self._lock:
            if trace_id not in self._traces:
                self._traces[trace_id] = Trace(trace_id=trace_id, start_time=time.time())
                self._recent_traces.append(trace_id)

        # Set trace context
        _trace_context.set({"trace_id": trace_id})

        return trace_id

    def start_span(
        self,
        operation_name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        parent_span_id: str | None = None,
        tags: dict[str, Any] | None = None,
    ) -> Span:
        """Start a new span."""
        # Get or create trace
        trace_context = _trace_context.get({})
        trace_id = trace_context.get("trace_id")

        if not trace_id:
            trace_id = self.start_trace(operation_name)

        # Generate span ID
        span_id = self._generate_span_id()

        # Determine parent span
        if parent_span_id is None:
            span_stack = self._get_span_stack()
            if span_stack:
                parent_span_id = span_stack[-1].span_id

        # Create span
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            start_time=time.time(),
            kind=kind,
            service_name=self.service_name,
            tags=tags or {},
        )

        # Add to active spans
        with self._lock:
            self._active_spans[span_id] = span

            # Add to trace
            if trace_id in self._traces:
                self._traces[trace_id].spans.append(span)

        # Add to span stack
        self._get_span_stack().append(span)

        return span

    def finish_span(
        self, span: Span, status: SpanStatus = SpanStatus.OK, error_message: str | None = None
    ) -> None:
        """Finish a span."""
        span.end_time = time.time()
        span.duration_ms = (span.end_time - span.start_time) * 1000
        span.status = status
        span.error_message = error_message

        # Remove from active spans
        with self._lock:
            if span.span_id in self._active_spans:
                del self._active_spans[span.span_id]

            # Update operation statistics
            self._update_operation_stats(span)

            # Update service dependencies
            if span.parent_span_id:
                parent_span = self._find_span(span.parent_span_id)
                if parent_span and parent_span.service_name != span.service_name:
                    self._service_dependencies[parent_span.service_name].add(span.service_name)

        # Remove from span stack
        span_stack = self._get_span_stack()
        if span_stack and span_stack[-1].span_id == span.span_id:
            span_stack.pop()

        # Check if trace is complete
        self._check_trace_completion(span.trace_id)

    def _find_span(self, span_id: str) -> Span | None:
        """Find span by ID across all traces."""
        if span_id in self._active_spans:
            return self._active_spans[span_id]

        # Search in completed traces
        for trace in self._traces.values():
            for span in trace.spans:
                if span.span_id == span_id:
                    return span

        return None

    def _check_trace_completion(self, trace_id: str) -> None:
        """Check if trace is complete and finalize it."""
        with self._lock:
            if trace_id not in self._traces:
                return

            trace = self._traces[trace_id]

            # Check if all spans are finished
            active_spans_in_trace = [
                span for span in self._active_spans.values() if span.trace_id == trace_id
            ]

            if not active_spans_in_trace and trace.spans:
                # Trace is complete
                trace.end_time = max(span.end_time or 0 for span in trace.spans)
                trace.duration_ms = (trace.end_time - trace.start_time) * 1000
                trace.span_count = len(trace.spans)
                trace.service_count = len({span.service_name for span in trace.spans})
                trace.error_count = sum(
                    1 for span in trace.spans if span.status == SpanStatus.ERROR
                )

    @contextmanager
    def trace_operation(
        self,
        operation_name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        tags: dict[str, Any] | None = None,
    ) -> Generator[Span, None, None]:
        """Context manager for tracing operations."""
        span = self.start_span(operation_name, kind=kind, tags=tags)
        try:
            yield span
        except Exception as e:
            span.error_message = str(e)
            span.status = SpanStatus.ERROR
            raise
        finally:
            self.finish_span(span)

    def trace(
        self,
        operation_name: str | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        tags: dict[str, Any] | None = None,
    ):
        """Decorator for tracing functions."""

        def decorator(func: Callable) -> Callable:
            name = operation_name or f"{func.__module__}.{func.__name__}"

            if asyncio.iscoroutinefunction(func):

                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    with self.trace_operation(name, kind=kind, tags=tags) as span:
                        # Add function metadata
                        span.tags.update(
                            {
                                "function": func.__name__,
                                "module": func.__module__,
                                "args_count": len(args),
                                "kwargs_count": len(kwargs),
                            }
                        )
                        return await func(*args, **kwargs)

                return async_wrapper
            else:

                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    with self.trace_operation(name, kind=kind, tags=tags) as span:
                        # Add function metadata
                        span.tags.update(
                            {
                                "function": func.__name__,
                                "module": func.__module__,
                                "args_count": len(args),
                                "kwargs_count": len(kwargs),
                            }
                        )
                        return func(*args, **kwargs)

                return sync_wrapper

        return decorator

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        """Add event to current span."""
        span_stack = self._get_span_stack()
        if span_stack:
            current_span = span_stack[-1]
            event = SpanEvent(name=name, timestamp=time.time(), attributes=attributes or {})
            current_span.events.append(event)

    def set_tag(self, key: str, value: Any) -> None:
        """Set tag on current span."""
        span_stack = self._get_span_stack()
        if span_stack:
            span_stack[-1].tags[key] = value

    def set_error(self, error: Exception | str) -> None:
        """Set error on current span."""
        span_stack = self._get_span_stack()
        if span_stack:
            current_span = span_stack[-1]
            current_span.status = SpanStatus.ERROR
            if isinstance(error, Exception):
                current_span.error_message = str(error)
                # Could add stack trace here
            else:
                current_span.error_message = str(error)

    def _update_operation_stats(self, span: Span) -> None:
        """Update operation performance statistics."""
        stats = self._operation_stats[span.operation_name]
        stats["count"] += 1
        stats["total_duration"] += span.duration_ms or 0

        if span.duration_ms:
            stats["min_duration"] = min(stats["min_duration"], span.duration_ms)
            stats["max_duration"] = max(stats["max_duration"], span.duration_ms)
            stats["recent_durations"].append(span.duration_ms)

        if span.status == SpanStatus.ERROR:
            stats["error_count"] += 1

    def get_trace(self, trace_id: str) -> Trace | None:
        """Get complete trace by ID."""
        with self._lock:
            return self._traces.get(trace_id)

    def get_recent_traces(self, limit: int = 100) -> list[Trace]:
        """Get recent traces."""
        with self._lock:
            trace_ids = list(self._recent_traces)[-limit:]
            return [self._traces[tid] for tid in trace_ids if tid in self._traces]

    def get_operation_stats(self) -> dict[str, dict[str, Any]]:
        """Get performance statistics for all operations."""
        with self._lock:
            stats = {}
            for operation, raw_stats in self._operation_stats.items():
                if raw_stats["count"] > 0:
                    avg_duration = raw_stats["total_duration"] / raw_stats["count"]
                    error_rate = raw_stats["error_count"] / raw_stats["count"]

                    # Calculate percentiles from recent durations
                    recent = list(raw_stats["recent_durations"])
                    p50 = p95 = p99 = 0.0
                    if recent:
                        recent.sort()
                        p50 = recent[int(len(recent) * 0.5)] if recent else 0
                        p95 = recent[int(len(recent) * 0.95)] if recent else 0
                        p99 = recent[int(len(recent) * 0.99)] if recent else 0

                    stats[operation] = {
                        "count": raw_stats["count"],
                        "avg_duration_ms": avg_duration,
                        "min_duration_ms": raw_stats["min_duration"]
                        if raw_stats["min_duration"] != float("inf")
                        else 0,
                        "max_duration_ms": raw_stats["max_duration"],
                        "p50_duration_ms": p50,
                        "p95_duration_ms": p95,
                        "p99_duration_ms": p99,
                        "error_rate": error_rate,
                        "error_count": raw_stats["error_count"],
                    }

            return stats

    def get_service_dependencies(self) -> dict[str, list[str]]:
        """Get service dependency graph."""
        with self._lock:
            return {
                service: list(dependencies)
                for service, dependencies in self._service_dependencies.items()
            }

    def get_slow_operations(
        self, threshold_ms: float = 1000.0, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get operations that are consistently slow."""
        stats = self.get_operation_stats()

        slow_operations = []
        for operation, stat in stats.items():
            if stat["avg_duration_ms"] > threshold_ms:
                slow_operations.append(
                    {
                        "operation": operation,
                        "avg_duration_ms": stat["avg_duration_ms"],
                        "p95_duration_ms": stat["p95_duration_ms"],
                        "count": stat["count"],
                        "error_rate": stat["error_rate"],
                    }
                )

        return sorted(slow_operations, key=lambda x: x["avg_duration_ms"], reverse=True)[:limit]

    def get_error_prone_operations(
        self, min_error_rate: float = 0.05, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get operations with high error rates."""
        stats = self.get_operation_stats()

        error_prone = []
        for operation, stat in stats.items():
            if stat["error_rate"] > min_error_rate and stat["count"] >= 10:
                error_prone.append(
                    {
                        "operation": operation,
                        "error_rate": stat["error_rate"],
                        "error_count": stat["error_count"],
                        "total_count": stat["count"],
                        "avg_duration_ms": stat["avg_duration_ms"],
                    }
                )

        return sorted(error_prone, key=lambda x: x["error_rate"], reverse=True)[:limit]

    def export_trace_json(self, trace_id: str) -> str | None:
        """Export trace in JSON format."""
        trace = self.get_trace(trace_id)
        if not trace:
            return None

        # Convert to JSON-serializable format
        trace_data = {
            "traceId": trace.trace_id,
            "spans": [
                {
                    "traceId": span.trace_id,
                    "spanId": span.span_id,
                    "parentSpanId": span.parent_span_id,
                    "operationName": span.operation_name,
                    "startTime": span.start_time,
                    "endTime": span.end_time,
                    "duration": span.duration_ms,
                    "kind": span.kind.value,
                    "status": span.status.value,
                    "serviceName": span.service_name,
                    "tags": span.tags,
                    "events": [
                        {
                            "name": event.name,
                            "timestamp": event.timestamp,
                            "attributes": event.attributes,
                        }
                        for event in span.events
                    ],
                    "errorMessage": span.error_message,
                }
                for span in trace.spans
            ],
            "startTime": trace.start_time,
            "endTime": trace.end_time,
            "duration": trace.duration_ms,
            "serviceCount": trace.service_count,
            "spanCount": trace.span_count,
            "errorCount": trace.error_count,
        }

        return json.dumps(trace_data, indent=2)

    def set_sample_rate(self, rate: float) -> None:
        """Set trace sampling rate (0.0 - 1.0)."""
        self._sample_rate = max(0.0, min(1.0, rate))

    def force_sample_operation(self, operation_name: str) -> None:
        """Force sampling for specific operation."""
        self._force_sample_operations.add(operation_name)

    def _should_sample(self, operation_name: str, trace_id: str) -> bool:
        """Determine if trace should be sampled."""
        # Always sample forced operations
        if operation_name in self._force_sample_operations:
            return True

        # Sample based on rate
        # Use trace_id hash for deterministic sampling
        trace_hash = hash(trace_id)
        return (trace_hash % 100) < (self._sample_rate * 100)

    def _generate_trace_id(self) -> str:
        """Generate unique trace ID."""
        return str(uuid.uuid4()).replace("-", "")[:16]

    def _generate_span_id(self) -> str:
        """Generate unique span ID."""
        return str(uuid.uuid4()).replace("-", "")[:8]

    def cleanup_old_traces(self, max_age_hours: int = 24) -> int:
        """Clean up old traces to prevent memory leaks."""
        cutoff_time = time.time() - (max_age_hours * 3600)
        removed_count = 0

        with self._lock:
            trace_ids_to_remove = [
                trace_id
                for trace_id, trace in self._traces.items()
                if trace.start_time and trace.start_time < cutoff_time
            ]

            for trace_id in trace_ids_to_remove:
                del self._traces[trace_id]
                removed_count += 1

        return removed_count

    def get_tracing_summary(self) -> dict[str, Any]:
        """Get comprehensive tracing system summary."""
        with self._lock:
            total_traces = len(self._traces)
            active_spans = len(self._active_spans)

            # Calculate average trace duration
            completed_traces = [t for t in self._traces.values() if t.duration_ms]
            avg_trace_duration = (
                sum(t.duration_ms for t in completed_traces) / len(completed_traces)
                if completed_traces
                else 0
            )

            # Get top operations by volume
            operation_volumes = {op: stats["count"] for op, stats in self._operation_stats.items()}
            top_operations = sorted(operation_volumes.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]

            return {
                "total_traces": total_traces,
                "active_spans": active_spans,
                "avg_trace_duration_ms": avg_trace_duration,
                "sample_rate": self._sample_rate,
                "service_count": len(self._service_dependencies) + 1,  # +1 for current service
                "operation_count": len(self._operation_stats),
                "top_operations": top_operations,
                "memory_usage": {
                    "traces_mb": self._estimate_memory_usage() / (1024 * 1024),
                    "max_traces": self.max_traces,
                },
            }

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage of stored traces (rough calculation)."""
        # Rough estimation: each span ~1KB, each trace ~100 bytes overhead
        span_count = sum(len(trace.spans) for trace in self._traces.values())
        return (span_count * 1024) + (len(self._traces) * 100)


# Global tracer instance
_global_tracer: DistributedTracer | None = None


def get_tracer(service_name: str = "kagami") -> DistributedTracer:
    """Get the global tracer instance."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = DistributedTracer(service_name=service_name)

    return _global_tracer


def trace(
    operation_name: str | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
    tags: dict[str, Any] | None = None,
):
    """Convenience decorator for tracing functions."""
    return get_tracer().trace(operation_name, kind=kind, tags=tags)


def trace_operation(
    operation_name: str, kind: SpanKind = SpanKind.INTERNAL, tags: dict[str, Any] | None = None
):
    """Convenience context manager for tracing operations."""
    return get_tracer().trace_operation(operation_name, kind=kind, tags=tags)
