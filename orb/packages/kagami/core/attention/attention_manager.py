from __future__ import annotations

from kagami.core.async_utils import cancel_and_await, safe_create_task

"""Attention Manager — explicit attention schema and scoring.

Collects events via AppEventBus mirror and maintains a small foreground set[Any].
Provides a score() helper that other overlays (e.g., Global Workspace) can use.
"""
import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass
class AttentionItem:
    topic: str
    event: dict[str, Any]
    ts: float
    relevance: float
    recency: float


class AttentionManager:
    def __init__(self, *, max_items: int = 256, decay: float = 0.95) -> None:
        self._items: deque[AttentionItem] = deque(maxlen=max_items)
        self._decay = max(0.5, min(0.999, float(decay)))
        self._task: asyncio.Task | None = None
        self._running = False
        self._bus: Any = None
        # Learned attention weights (contextual bandit). Simple per-topic-prefix weight.
        # feature vector: [bias, recency, relevance]
        self._weights: dict[str, list[float]] = {
            "intent": [0.3, 0.5, 0.6],
            "workflow": [0.2, 0.5, 0.4],
            "ui": [0.2, 0.4, 0.3],
            "other": [0.1, 0.3, 0.2],
        }
        self._alpha = 0.05  # learning rate
        # Try to load persisted weights
        self._redis: Any | None = None
        try:
            from kagami.core.caching.redis import RedisClientFactory

            async def _getr() -> Any:
                return RedisClientFactory.get_client(
                    purpose="default",
                    async_mode=True,
                    decode_responses=True,
                )

            self._redis = _getr  # store factory
        except Exception:
            pass

    def attach_bus(self, bus: Any) -> None:
        if self._bus is not None:
            return
        self._bus = bus

        async def _mirror(topic: str, event: dict[str, Any]) -> None:
            try:
                now = time.time()
                rel = self._estimate_relevance(topic, event)
                self._items.append(
                    AttentionItem(
                        topic=topic,
                        event=dict(event),
                        ts=now,
                        relevance=rel,
                        recency=1.0,
                    )
                )
                # Online update from rewards: observe task outcomes on intent.result
                if topic == "intent.result":
                    str(((event.get("intent") or {}).get("action")) or "")
                    str(((event.get("intent") or {}).get("app")) or "")
                    prefix = "intent"
                    status = str((event.get("result") or {}).get("status") or "")
                    reward = 1.0 if status in ("accepted", "success", "ok") else 0.0
                    # Features from last foreground intent item if available
                    x = [1.0, 1.0, rel]
                    self._bandit_update(prefix, x, reward)
                    await self._persist_weights()
            except Exception:
                pass

        try:
            self._bus.add_mirror_handler(_mirror)
        except Exception:
            pass

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = safe_create_task(self._loop(), name="_loop")

    async def stop(self) -> None:
        self._running = False
        await cancel_and_await(self._task)

    async def _loop(self) -> None:
        while self._running:
            try:
                await asyncio.sleep(0.2)
                # Decay recency; keep queue bounded automatically
                for it in list(self._items):
                    it.recency *= self._decay
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def score(self, topic: str, event: dict[str, Any]) -> float:
        """Return a salience score (0..3) based on relevance and recency priors."""
        try:
            base = self._estimate_relevance(topic, event)
            # Boost if similar topic in foreground
            boost = 0.0
            t = topic.split(".")[0] if "." in topic else topic
            for it in self._items:
                if it.topic.startswith(t):
                    boost = max(boost, it.recency * 0.5)
            # Learned weight contribution
            w = self._weights.get(t, self._weights.get("other", [0.1, 0.3, 0.2]))
            x = [1.0, 1.0, base]
            learned = sum(wi * xi for wi, xi in zip(w, x, strict=False))
            return max(0.0, min(3.0, base + boost + learned * 0.2))
        except Exception:
            return 0.0

    def get_focus(self, top_k: int = 5) -> list[dict[str, Any]]:
        try:
            items = list(self._items)
            items.sort(key=lambda x: (x.relevance + x.recency), reverse=True)
            out = []
            for it in items[: max(1, int(top_k))]:
                out.append(
                    {
                        "topic": it.topic,
                        "event": it.event,
                        "score": it.relevance + it.recency,
                    }
                )
            return out
        except Exception:
            return []

    def _estimate_relevance(self, topic: str, event: dict[str, Any]) -> float:
        # Coarse priors
        if topic.startswith("intent."):
            prog = 0.0
            try:
                prog = float(event.get("progress_percent") or 0.0)
            except Exception:
                prog = 0.0
            return 0.8 + min(0.7, prog / 100.0)
        if topic.startswith("workflow."):
            return 0.7
        if topic.startswith("ui."):
            return 0.6
        return 0.3

    def _bandit_update(self, prefix: str, x: list[float], reward: float) -> None:
        try:
            w = self._weights.get(prefix, [0.1, 0.3, 0.2])
            # Simple gradient step toward reward with bounded magnitude
            y_hat = sum(wi * xi for wi, xi in zip(w, x, strict=False))
            err = max(-1.0, min(1.0, reward - y_hat))
            for i in range(min(len(w), len(x))):
                w[i] = w[i] + self._alpha * err * x[i]
            # Clamp weights to a safe range
            self._weights[prefix] = [max(-1.0, min(1.0, wi)) for wi in w]
        except Exception:
            pass

    async def _persist_weights(self) -> None:
        if self._redis is None:
            return  # Defensive/fallback code
        try:
            r = await self._redis()
            import json

            await r.setex("kagami:attention:weights", 3600, json.dumps(self._weights))
        except Exception:
            pass


_AM: AttentionManager | None = None


def get_attention_manager() -> AttentionManager:
    global _AM
    if _AM is None:
        _AM = AttentionManager()
    return _AM
