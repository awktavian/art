from __future__ import annotations

from kagami.core.async_utils import cancel_and_await, safe_create_task

"""Global Workspace overlay for salience-ranked broadcast.

UPDATED (Dec 12, 2025 - Science Gap Closure):
=============================================
AttentionManager is now REQUIRED per GNW theory (Baars, Dehaene).
The try/except fallback has been removed. Attention gates workspace entry.

Design goals:
- Do not duplicate transport: reuse AppEventBus fanout and WS bridge.
- Provide a small salience layer that collects recent events and broadcasts a
  summarized, limited-capacity view via a single topic: "workspace.broadcast".
- Expose bounded-label metrics only.
- AttentionManager REQUIRED for proper GNW implementation (Dec 12, 2025)

References:
- Baars (1988): "A Cognitive Theory of Consciousness"
- Dehaene et al. (2006): "Global Neuronal Workspace"
"""
import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from kagami_observability.metrics import (
    WORKSPACE_BROADCAST_DURATION,
    WORKSPACE_BROADCAST_TOTAL,
)

# REQUIRED import (Dec 12, 2025 - Science Gap Closure)
from kagami.core.attention.attention_manager import (
    AttentionManager,
    get_attention_manager,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class _WorkspaceItem:
    topic: str
    event: dict[str, Any]
    ts: float
    priority: float


class GlobalWorkspace:
    """Collects events and periodically emits a salience-ranked broadcast.

    UPDATED (Dec 12, 2025 - Science Gap Closure):
    =============================================
    AttentionManager is now REQUIRED. Per GNW theory, attention gates what
    enters the global workspace. Without attention, there is no consciousness.

    Implementation keeps O(1) memory via a bounded deque[Any] and simple scoring.
    """

    def __init__(
        self,
        *,
        max_queue: int = 512,
        top_k: int = 8,
        attention_manager: AttentionManager | None = None,
    ) -> None:
        self._queue: deque[_WorkspaceItem] = deque(maxlen=max_queue)
        self._top_k = max(1, int(top_k))
        self._task: asyncio.Task | None = None
        self._running = False
        self._bus = None

        # AttentionManager is REQUIRED (Dec 12, 2025)
        self._attention = attention_manager or get_attention_manager()
        logger.info("✅ GlobalWorkspace: AttentionManager integrated (GNW compliant)")

    def attach_bus(self, bus: Any) -> None:
        """Attach AppEventBus and install a mirror handler (idempotent).

        UPDATED (Dec 12, 2025):
        Also attaches bus to AttentionManager for proper GNW integration.
        """
        if self._bus is not None:
            return  # type: ignore[unreachable]
        self._bus = bus

        # Attach bus to AttentionManager (REQUIRED for GNW)
        self._attention.attach_bus(bus)

        async def _mirror(topic: str, event: dict[str, Any]) -> None:
            try:
                # Skip workspace.broadcast to avoid recursive feedback loop
                if topic == "workspace.broadcast":
                    return
                # Score using AttentionManager (GNW compliant)
                ts = time.time()
                priority = self._score(topic, event, ts)
                self._queue.append(
                    _WorkspaceItem(topic=topic, event=dict(event), ts=ts, priority=priority)
                )
            except Exception:
                # Never block producers
                pass

        try:
            self._bus.add_mirror_handler(_mirror)  # type: ignore[attr-defined]
        except Exception:
            logger.warning("Failed to attach mirror handler to bus")

    def _score(self, topic: str, event: dict[str, Any], ts: float) -> float:
        """Salience score using AttentionManager (REQUIRED per GNW).

        UPDATED (Dec 12, 2025 - Science Gap Closure):
        =============================================
        AttentionManager is now the PRIMARY scorer, not an optional boost.
        Per GNW theory, attention determines what enters conscious workspace.

        Components:
        - attention_score: From AttentionManager (primary)
        - topic_prior: Base prior by topic class
        - progress: For intent.* use progress_percent
        """
        try:
            # Topic prior (bounded set[Any])
            if topic.startswith("intent."):
                prior = 0.5
                prog = float(event.get("progress_percent") or 0.0)
                comp = min(1.0, max(0.0, prog / 100.0))
            elif topic.startswith("workflow."):
                prior = 0.4
                comp = 0.0
            elif topic.startswith("ui."):
                prior = 0.3
                comp = 0.0
            else:
                prior = 0.1
                comp = 0.0

            # AttentionManager is REQUIRED (Dec 12, 2025)
            # Ensure bus is attached
            if self._bus is not None:
                self._attention.attach_bus(self._bus)  # type: ignore[unreachable]

            # Attention score is PRIMARY, not a boost
            attention_score = self._attention.score(topic, event)

            # Combined: attention is dominant (0.6), prior + completion secondary (0.4)
            total = 0.6 * attention_score + 0.4 * (prior + comp)

            return max(0.0, min(3.0, total))
        except Exception as e:
            logger.warning(f"GNW scoring error: {e}")
            return 0.1

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = safe_create_task(self._run_loop(), name="_run_loop")

    async def stop(self) -> None:
        self._running = False
        await cancel_and_await(self._task)

    async def _run_loop(self) -> None:
        # Short cadence to keep latency low while batching
        interval_s = 0.05
        while self._running:
            try:
                await asyncio.sleep(interval_s)
                await self._broadcast_once()
            except asyncio.CancelledError:
                break
            except Exception:
                # Do not break on errors; count and continue
                try:
                    WORKSPACE_BROADCAST_TOTAL.labels("error").inc()
                except Exception:
                    pass

    async def _broadcast_once(self) -> None:
        if not self._bus:
            return
        if not self._queue:  # type: ignore  # Defensive/fallback code
            return
        # Collect phase
        t0 = time.perf_counter()
        items = list(self._queue)
        self._queue.clear()
        try:
            WORKSPACE_BROADCAST_DURATION.labels("collect").observe(
                max(0.0, time.perf_counter() - t0)
            )
        except Exception:
            pass

        # Rank and select top-K
        items.sort(key=lambda x: x.priority, reverse=True)
        selected = items[: self._top_k]
        if not selected:
            return

        # Summarize with minimal fields to keep payload light
        drift_score = None
        summary = {
            "type": "workspace.broadcast",
            "topic": "workspace.broadcast",
            "ts": time.time(),
            "drift": drift_score,
            "spotlight": {
                "topic": selected[0].topic,
                "event": selected[0].event,
            },
            "items": [{"topic": it.topic, "event": it.event} for it in selected],
        }

        t1 = time.perf_counter()
        try:
            await self._bus.publish("workspace.broadcast", summary)
            # EventStore removed - using CockroachDB receipts for durability
            WORKSPACE_BROADCAST_TOTAL.labels("ok").inc()
        except Exception:
            WORKSPACE_BROADCAST_TOTAL.labels("error").inc()
        finally:
            try:
                WORKSPACE_BROADCAST_DURATION.labels("broadcast").observe(
                    max(0.0, time.perf_counter() - t1)
                )
            except Exception:
                pass


_GW: GlobalWorkspace | None = None


def get_global_workspace() -> GlobalWorkspace:
    global _GW
    if _GW is None:
        _GW = GlobalWorkspace()
    return _GW
