from __future__ import annotations

"""Enhanced Global Workspace with multimodal fusion and narrative construction."""
import logging
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class UnifiedPercept:
    """Unified perception across all modalities."""

    timestamp: float
    modalities: dict[str, Any]  # events, metrics, intents, spatial
    associations: list[dict[str, Any]]  # Causal links
    coherence_score: float


@dataclass
class AttentionMap:
    """Map of attention weights across topics."""

    weights: dict[str, float]
    focus: list[str]  # Current focus topics


@dataclass
class MicroNarrative:
    """Small narrative thread."""

    actors: list[str]
    goals: list[str]
    obstacles: list[str]
    current_state: dict[str, Any]
    predictions: list[dict[str, Any]]


@dataclass
class Narrative:
    """Global narrative of system state."""

    micro_narratives: list[MicroNarrative]
    global_state: str
    predicted_futures: list[str]


class MultimodalFusion:
    """Integrate data from different sources into unified percepts."""

    async def fuse_percepts(self) -> UnifiedPercept:
        """Combine vision, language, metrics, events into coherent understanding."""
        # Gather streams
        recent_events = await self._get_recent_events(seconds=5)  # type: ignore[call-arg]
        current_metrics = await self._snapshot_metrics()
        active_intents = await self._get_in_flight_intents()
        spatial_state = await self._get_spatial_awareness()

        # Temporal alignment (align by timestamp)
        aligned = self._align_temporal_streams(
            {
                "events": recent_events,
                "metrics": current_metrics,
                "intents": active_intents,
                "spatial": spatial_state,
            }
        )

        # Cross-modal associations
        associations = self._find_causal_links(aligned)

        # Build unified percept
        return UnifiedPercept(
            timestamp=time.time(),
            modalities=aligned,
            associations=associations,
            coherence_score=self._compute_coherence(associations),
        )

    async def _get_recent_events(self, _seconds: int) -> list[dict[str, Any]]:
        """Get recent events from bus."""
        try:
            from kagami.core.events import get_unified_bus

            bus = get_unified_bus()
            return bus.recent_events(limit=100)  # type: ignore[return-value]
        except Exception:
            return []

    async def _snapshot_metrics(self) -> dict[str, float]:
        """Snapshot key metrics."""
        try:
            from kagami_observability.metrics import (
                ACTIVE_REQUESTS,
                WEBSOCKET_CONNECTIONS,
            )

            return {
                "active_requests": ACTIVE_REQUESTS._value._value,
                "websocket_connections": WEBSOCKET_CONNECTIONS._value._value,
                "timestamp": time.time(),
            }
        except Exception:
            return {}

    async def _get_in_flight_intents(self) -> list[dict[str, Any]]:
        """Get currently executing intents."""
        # Would track in orchestrator - simplified
        return []

    async def _get_spatial_awareness(self) -> dict[str, Any]:
        """Get spatial state from embodiment layer."""
        try:
            from kagami.core.embodiment.embodied_cognition import (
                EmbodiedCognition,  # type: ignore[attr-defined]
            )

            # Try to get spatial state from embodiment layer
            embodied = EmbodiedCognition()
            spatial_state = embodied.get_spatial_state()
            return {
                "type": "spatial_state",
                "entities": spatial_state.get("entities", []),
                "spatial_model": spatial_state.get("spatial_model"),
                "sensorimotor_state": spatial_state.get("sensorimotor_state"),
            }
        except ImportError:
            logger.debug("EmbodiedCognition not available, returning minimal spatial state")
            return {"type": "spatial_state", "entities": []}
        except Exception as e:
            logger.warning(f"Failed to get spatial awareness from embodiment: {e}")
            return {"type": "spatial_state", "entities": []}

    def _align_temporal_streams(self, streams: dict[str, Any]) -> dict[str, Any]:
        """Align different data streams by timestamp."""
        # All streams already timestamped - return as-is
        return streams

    def _find_causal_links(self, aligned: dict[str, Any]) -> list[dict[str, Any]]:
        """Find causal associations across modalities."""
        associations = []

        events = aligned.get("events", [])
        metrics = aligned.get("metrics", {})

        # Example: High active_requests + intent.execute events → load spike
        active_reqs = metrics.get("active_requests", 0)
        intent_events = [e for e in events if e.get("topic", "").startswith("intent.")]

        if active_reqs > 50 and len(intent_events) > 10:
            associations.append(
                {
                    "type": "load_spike",
                    "cause": "high_intent_volume",
                    "effect": "increased_active_requests",
                    "confidence": 0.8,
                }
            )

        return associations

    def _compute_coherence(self, associations: list[dict[str, Any]]) -> float:
        """Compute how coherent the overall perception is."""
        # More associations = more integrated understanding
        if not associations:
            return 0.0  # No associations = no coherence

        # Average confidence weighted by number of associations
        confidences = [a.get("confidence", 0.0) for a in associations]
        base_coherence = float(np.mean(confidences))
        # Bonus for having multiple associations
        association_bonus = min(0.2, len(associations) * 0.02)
        return min(1.0, base_coherence + association_bonus)


class SelectiveAttention:
    """Focus on relevant information while suppressing noise."""

    def __init__(self) -> None:
        self._focus_set: set[str] = set()
        self._suppression_set: set[str] = set()
        self._attention_weights: dict[str, float] = {}
        self._current_focus: str | None = None

    async def compute_attention(self, items: list[Any]) -> AttentionMap:
        """Determine what to amplify and what to suppress."""
        attention_map = {}

        for item in items:
            topic = item.get("topic", "") if isinstance(item, dict) else ""

            # Amplify focused topics
            if any(topic.startswith(f) for f in self._focus_set):
                attention_map[topic] = 2.0  # Amplify 2x

            # Suppress noise
            elif any(topic.startswith(s) for s in self._suppression_set):
                attention_map[topic] = 0.1  # Suppress 90%

            # Default: use learned weights
            else:
                attention_map[topic] = self._attention_weights.get(topic, 1.0)

        # Compute new focus
        new_focus = self._compute_new_focus(attention_map)

        # Emit attention switch if changed
        if new_focus != self._current_focus:
            await self._emit_attention_switch(self._current_focus, new_focus)
            self._current_focus = new_focus

        return AttentionMap(weights=attention_map, focus=[new_focus] if new_focus else [])

    def _compute_new_focus(self, attention_map: dict[str, float]) -> str | None:
        """Determine primary focus."""
        if not attention_map:
            return None

        # Highest weight is focus
        return max(attention_map.items(), key=lambda x: x[1])[0]

    async def _emit_attention_switch(self, from_topic: str | None, to_topic: str | None) -> None:
        """Emit attention switch event."""
        try:
            from kagami.core.events import get_unified_bus

            bus = get_unified_bus()
            await bus.publish(
                "attention.switched",
                {
                    "type": "attention_switch",
                    "from": from_topic or "none",
                    "to": to_topic or "none",
                    "timestamp": time.time(),
                },
            )
        except Exception as e:
            logger.debug(f"Could not emit attention switch: {e}")


class NarrativeConstructor:
    """Maintain coherent models of ongoing situations."""

    async def construct_narrative(self, events: list[dict[str, Any]]) -> Narrative:
        """Build story of what's happening and what will likely happen next."""
        # Cluster by causal threads
        threads = self._identify_causal_threads(events)

        # Build micro-narratives
        micro_narratives = []
        for thread in threads:
            actors = self._extract_actors(thread)
            goals = self._infer_goals(thread)
            obstacles = self._identify_obstacles(thread)
            predictions = await self._predict_next_steps(thread)

            micro_narratives.append(
                MicroNarrative(
                    actors=actors,
                    goals=goals,
                    obstacles=obstacles,
                    current_state=thread[-1] if thread else {},
                    predictions=predictions,
                )
            )

        # Synthesize global narrative
        global_state = self._summarize_state(micro_narratives)
        predicted_futures = self._merge_predictions(micro_narratives)

        return Narrative(
            micro_narratives=micro_narratives,
            global_state=global_state,
            predicted_futures=predicted_futures,
        )

    def _identify_causal_threads(self, events: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Group events into causal sequences."""
        threads = []
        visited = set()

        for i, event in enumerate(events):
            if i in visited:
                continue

            # Start new thread
            thread = [event]
            visited.add(i)

            # Find related events via correlation_id
            corr_id = event.get("correlation_id")
            if corr_id:
                for j, other in enumerate(events):
                    if j != i and other.get("correlation_id") == corr_id:
                        thread.append(other)
                        visited.add(j)

            if len(thread) > 1:  # Only keep threads with multiple events
                threads.append(thread)

        return threads

    def _extract_actors(self, thread: list[dict[str, Any]]) -> list[str]:
        """Identify actors in thread."""
        actors = set()
        for event in thread:
            if "app" in event:
                actors.add(str(event["app"]))
            if "source" in event:
                actors.add(str(event["source"]))
        return list(actors)

    def _infer_goals(self, thread: list[dict[str, Any]]) -> list[str]:
        """Infer goals from event sequence."""
        goals = []
        for event in thread:
            action = event.get("action", "")
            if action:
                goals.append(f"Execute {action}")
        return goals

    def _identify_obstacles(self, thread: list[dict[str, Any]]) -> list[str]:
        """Identify obstacles in thread."""
        obstacles = []
        for event in thread:
            if event.get("status") == "error":
                obstacles.append(event.get("error", "Unknown error"))
        return obstacles

    async def _predict_next_steps(self, thread: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Predict what will happen next in this thread."""
        if not thread:
            return []

        last_event = thread[-1]

        # Simple prediction: if error, retry; if success, continue
        predictions = []
        if last_event.get("status") == "error":
            predictions.append({"action": "retry", "probability": 0.7})
        elif last_event.get("status") == "success":
            predictions.append({"action": "complete", "probability": 0.8})

        return predictions

    def _summarize_state(self, narratives: list[MicroNarrative]) -> str:
        """Summarize overall system state."""
        if not narratives:
            return "System idle"

        active_actors = set()
        for n in narratives:
            active_actors.update(n.actors)

        obstacles_count = sum(len(n.obstacles) for n in narratives)

        if obstacles_count > 3:
            return f"{len(active_actors)} actors active, {obstacles_count} obstacles present"
        else:
            return f"{len(active_actors)} actors active, operating normally"

    def _merge_predictions(self, narratives: list[MicroNarrative]) -> list[str]:
        """Merge predictions from all threads."""
        predictions = []
        for n in narratives:
            for pred in n.predictions:
                predictions.append(f"{pred.get('action')} (p={pred.get('probability', 0):.0%})")
        return predictions[:5]  # Top 5


class EnhancedGlobalWorkspace:
    """Enhanced global workspace with processing_state-like integration."""

    def __init__(self) -> None:
        self._fusion = MultimodalFusion()
        self._attention = SelectiveAttention()
        self._narrative = NarrativeConstructor()
        self._bus = None

    def attach_bus(self, bus: Any) -> None:
        """Attach event bus."""
        self._bus = bus

    async def generate_conscious_broadcast(self) -> dict[str, Any]:
        """Generate integrated, narrative broadcast."""
        # Fuse modalities
        percept = await self._fusion.fuse_percepts()

        # Apply attention
        events_list = percept.modalities.get("events", [])
        attention = await self._attention.compute_attention(events_list)

        # Construct narrative
        narrative = await self._narrative.construct_narrative(events_list)

        # Build broadcast
        broadcast = {
            "type": "workspace.conscious_broadcast",
            "topic": "workspace.conscious_broadcast",
            "timestamp": time.time(),
            "percept": {
                "coherence": percept.coherence_score,
                "associations": percept.associations,
            },
            "attention": {
                "focus": attention.focus,
                "top_topics": sorted(attention.weights.items(), key=lambda x: x[1], reverse=True)[
                    :5
                ],
            },
            "narrative": {
                "global_state": narrative.global_state,
                "threads": len(narrative.micro_narratives),
                "predictions": narrative.predicted_futures,
            },
        }

        # Publish
        if self._bus:
            try:  # type: ignore  # Defensive/fallback code
                await self._bus.publish("workspace.conscious_broadcast", broadcast)
            except Exception as e:
                logger.debug(f"Could not publish broadcast: {e}")

        return broadcast


# Singleton
_ENHANCED_WORKSPACE: EnhancedGlobalWorkspace | None = None


def get_enhanced_global_workspace() -> EnhancedGlobalWorkspace:
    """Get singleton enhanced workspace."""
    global _ENHANCED_WORKSPACE
    if _ENHANCED_WORKSPACE is None:
        _ENHANCED_WORKSPACE = EnhancedGlobalWorkspace()
    return _ENHANCED_WORKSPACE
