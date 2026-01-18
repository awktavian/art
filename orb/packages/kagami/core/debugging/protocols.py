"""Introspection Protocols.

Defines contracts for system introspection and reflection.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class IntrospectionManagerProtocol(Protocol):
    """Protocol for introspection manager."""

    async def reflect_post_intent(self, intent: Any, receipt: dict[str, Any] | None) -> None:
        """Queue a post-intent reflection task."""
        ...

    async def start_periodic_reflection_loop(self, interval_seconds: float = 600.0) -> None:
        """Start a periodic reflection loop."""
        ...

    async def stop_periodic_reflection_loop(self) -> None:
        """Stop the periodic reflection loop."""
        ...
