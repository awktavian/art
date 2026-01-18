"""Shared types for Kagami observability system.

This module contains type definitions shared across observability components
to avoid circular dependencies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    pass


class MetricProtocol(Protocol):
    """Protocol for Prometheus metric objects."""

    def labels(self, **labelkwargs: str) -> Any:
        """Return child metric with labels."""
        ...


class CounterProtocol(MetricProtocol, Protocol):
    """Protocol for Prometheus Counter metrics."""

    def inc(self, amount: float = 1.0) -> None:
        """Increment counter."""
        ...


class GaugeProtocol(MetricProtocol, Protocol):
    """Protocol for Prometheus Gauge metrics."""

    def set(self, value: float) -> None:
        """Set gauge value."""
        ...

    def inc(self, amount: float = 1.0) -> None:
        """Increment gauge."""
        ...

    def dec(self, amount: float = 1.0) -> None:
        """Decrement gauge."""
        ...


class HistogramProtocol(MetricProtocol, Protocol):
    """Protocol for Prometheus Histogram metrics."""

    def observe(self, amount: float) -> None:
        """Observe value."""
        ...


__all__ = [
    "CounterProtocol",
    "GaugeProtocol",
    "HistogramProtocol",
    "MetricProtocol",
]
