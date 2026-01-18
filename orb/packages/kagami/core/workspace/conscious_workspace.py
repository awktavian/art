from __future__ import annotations

"""processing Workspace - Global Workspace Theory Implementation."""
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceEntry:
    """Entry competing for workspace access."""

    state: Any
    salience: float
    agent: str
    timestamp: float


class ConsciousWorkspace:
    """Global workspace with competitive access (processing_state-like)."""

    def __init__(self, capacity: int = 5) -> None:
        self.capacity = capacity
        self.contents: list[Any] = []
        self.competition_queue: deque[WorkspaceEntry] = deque(maxlen=100)
        self.subscribers: list[Any] = []
        self.ignitions: int = 0
        self._event_times: deque[float] = deque(maxlen=600)

    async def compete_for_access(self, state: Any, salience: float, agent: str) -> None:
        """Submit state for workspace competition."""
        entry = WorkspaceEntry(state, salience, agent, time.time())
        self.competition_queue.append(entry)
        self._event_times.append(entry.timestamp)
        # Update competition rate (states/sec over last 60s)

        if len(self.competition_queue) >= self.capacity:
            await self._run_competition()

    async def _run_competition(self) -> None:
        """Select winners via salience competition."""
        sorted_entries = sorted(self.competition_queue, key=lambda e: e.salience, reverse=True)

        winners = [e.state for e in sorted_entries[: self.capacity]]

        if winners != self.contents:
            self.contents = winners
            await self._broadcast_ignition(winners)

    async def _broadcast_ignition(self, states: list[Any]) -> None:
        """Broadcast to all subscribers (processing_state moment)."""
        self.ignitions += 1

        # Emit metric
        try:
            from kagami_observability.metrics.cognitive import WORKSPACE_IGNITIONS_TOTAL

            WORKSPACE_IGNITIONS_TOTAL.inc()
        except Exception:
            pass

        broadcast = {
            "type": "workspace.ignition",
            "contents": states,
            "timestamp": time.time(),
            "ignition_count": self.ignitions,
        }

        for subscriber in self.subscribers:
            try:
                await subscriber.receive_broadcast(broadcast)
            except Exception:
                pass

    def subscribe(self, agent: Any) -> None:
        """Subscribe to workspace broadcasts."""
        if agent not in self.subscribers:
            self.subscribers.append(agent)


_workspace: ConsciousWorkspace | None = None


def get_conscious_workspace() -> ConsciousWorkspace:
    global _workspace
    if _workspace is None:
        _workspace = ConsciousWorkspace()
        logger.info("🌟 processing Workspace initialized (Global Workspace Theory)")
    return _workspace
