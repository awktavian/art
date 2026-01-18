"""Attention Schema - Formal internal model of focus and control.

Provides:
- Focus tracking with dwell times and switch costs
- Candidate salience and stability scoring
- Predictive controller recommendations (switch/avoid/reallocate)
- Social attribution of attention (self|peer|user|unknown)
"""

import time
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass
class AttentionTarget:
    """A candidate attention target with social attribution and scores."""

    target_id: str
    owner_type: str  # self|peer|user|unknown
    salience: float = 0.0
    predicted_stability: float = 0.5
    switching_cost: float = 0.1
    last_update_ts: float = 0.0


class AttentionSchema:
    """Meta-attention: internal model for monitoring and controlling attention."""

    def __init__(self) -> None:
        self._attention_history = deque(maxlen=1000)  # type: ignore  # Var
        self._focus_duration: dict[str, float] = {}
        self._current_focus: str | None = None
        self._current_owner: str = "unknown"
        self._focus_start: float | None = None
        self._candidates: dict[str, AttentionTarget] = {}
        self._last_recommendation: dict[str, Any] = {}

    async def set_focus(
        self,
        target: str,
        importance: float,
        *,
        owner_type: str | None = None,
        reason: str | None = None,
    ) -> None:
        """Record an attention switch and emit dwell/metrics.

        Args:
            target: New focus identifier (e.g., "phase:simulate" or "intent:xyz")
            importance: Current importance (used to seed salience when unseen)
            owner_type: Social attribution (self|peer|user|unknown)
            reason: Controller reason for the switch
        """
        now = time.time()

        # Record previous focus dwell time
        if self._current_focus and self._focus_start:
            duration = max(0.0, now - self._focus_start)
            self._attention_history.append(
                {
                    "target": self._current_focus,
                    "owner_type": self._current_owner,
                    "duration_ms": duration * 1000,
                    "timestamp": now,
                    "reason": reason or "switch",
                }
            )
            self._focus_duration[self._current_focus] = (
                self._focus_duration.get(self._current_focus, 0.0) + duration
            )
            # Metric: dwell seconds by owner_type
            try:
                from kagami_observability.metrics import ATTENTION_DWELL_SECONDS

                ATTENTION_DWELL_SECONDS.labels(owner_type=self._current_owner).observe(duration)
            except Exception:
                pass

        # Emit switch metric
        try:
            from kagami_observability.metrics import ATTENTION_SWITCH_TOTAL

            ATTENTION_SWITCH_TOTAL.labels(self._current_focus or "none", target or "none").inc()
        except Exception:
            pass

        # Update current focus
        self._current_focus = target
        self._current_owner = (owner_type or "unknown").strip() or "unknown"
        self._focus_start = now

        # Seed or update candidate entry
        cand = self._candidates.get(target)
        if cand is None:
            cand = AttentionTarget(
                target_id=target,
                owner_type=self._current_owner,
                salience=float(max(0.0, importance)),
                predicted_stability=0.5,
                switching_cost=0.1,
                last_update_ts=now,
            )
            self._candidates[target] = cand
        else:
            cand.owner_type = self._current_owner or cand.owner_type
            cand.salience = max(cand.salience, float(max(0.0, importance)))
            cand.last_update_ts = now

        # Focus confidence gauge
        try:
            from kagami_observability.metrics import ATTENTION_FOCUS_CONFIDENCE

            ATTENTION_FOCUS_CONFIDENCE.labels(owner_type=self._current_owner).set(
                min(1.0, max(0.0, cand.predicted_stability))
            )
        except Exception:
            pass

    def observe_event(self, topic: str, event: dict[str, Any]) -> None:
        """Update candidate salience from an external event and attribute owner.

        Heuristics only (bounded, simple):
        - intent.* → owner=self or peer depending on `agent` field
        - ui.* or presence.* with user_id → owner=user
        - workflow.*, hive.*, world.* → owner=peer/unknown
        """
        try:
            now = time.time()
            target_id = f"event:{topic}"
            owner = self._infer_owner_type(topic, event)
            # Simple salience: recency + coarse relevance
            base = 0.3
            if topic.startswith("intent."):
                base = 0.8
            elif topic.startswith("ui.") or topic.startswith("presence."):
                base = 0.7
            elif topic.startswith("workflow.") or topic.startswith("hive."):
                base = 0.6
            salience = min(1.0, base)

            cand = self._candidates.get(target_id)
            if cand is None:
                cand = AttentionTarget(
                    target_id=target_id,
                    owner_type=owner,
                    salience=salience,
                    predicted_stability=0.5,
                    switching_cost=0.1,
                    last_update_ts=now,
                )
                self._candidates[target_id] = cand
            else:
                cand.owner_type = owner or cand.owner_type
                # Decay then add
                cand.salience = min(1.0, cand.salience * 0.9 + salience * 0.2)
                cand.last_update_ts = now
        except Exception:
            pass

    def recommend_focus(self) -> dict[str, Any]:
        """Predict next focus decision with reason codes.

        Score = salience + 0.5*predicted_stability - 0.2*switching_cost.
        Returns a dict[str, Any] with {decision, target, score, reason}.
        """
        try:
            best: tuple[str, float, AttentionTarget] | None = None
            for tid, cand in self._candidates.items():
                score = (
                    float(cand.salience)
                    + 0.5 * float(cand.predicted_stability)
                    - 0.2 * float(cand.switching_cost)
                )
                if best is None or score > best[1]:
                    best = (tid, score, cand)
            if best is None:
                self._last_recommendation = {
                    "decision": "stay",
                    "reason": "no_candidates",
                }
                return self._last_recommendation

            tid, score, cand = best
            if self._current_focus in (None, tid):
                self._last_recommendation = {
                    "decision": "stay",
                    "target": tid,
                    "owner_type": cand.owner_type,
                    "score": score,
                    "reason": "best_matches_current",
                }
            else:
                # Switch only if significant advantage
                curr = self._candidates.get(self._current_focus)  # type: ignore[arg-type]
                curr_score = 0.0
                if curr is not None:
                    curr_score = (
                        float(curr.salience)
                        + 0.5 * float(curr.predicted_stability)
                        - 0.2 * float(curr.switching_cost)
                    )
                if (score - curr_score) >= 0.2:
                    self._last_recommendation = {
                        "decision": "switch",
                        "target": tid,
                        "owner_type": cand.owner_type,
                        "score": score,
                        "reason": "score_gap",
                    }
                else:
                    self._last_recommendation = {
                        "decision": "avoid_switch",
                        "target": self._current_focus,
                        "owner_type": self._current_owner,
                        "score": curr_score,
                        "reason": "insufficient_gain",
                    }

            # Metric: controller decisions
            try:
                from kagami_observability.metrics import (
                    ATTENTION_CONTROLLER_ADJUSTMENTS_TOTAL,
                )

                ATTENTION_CONTROLLER_ADJUSTMENTS_TOTAL.labels(
                    self._last_recommendation.get("decision", "unknown")
                ).inc()
            except Exception:
                pass

            return dict(self._last_recommendation)
        except Exception:
            return {"decision": "stay", "reason": "error"}

    def get_attention_patterns(self) -> dict[str, Any]:
        """Legacy summary of past focus durations (kept for compatibility)."""
        if not self._focus_duration:
            return {"most_attended": None}

        most_attended = max(self._focus_duration.items(), key=lambda x: x[1])[0]
        return {
            "most_attended": most_attended,
            "total_targets": len(self._focus_duration),
            "recent_shifts": len(self._attention_history),
        }

    def get_snapshot(self, top_k: int = 5) -> dict[str, Any]:
        """Return a snapshot suitable for receipts/UI/metrics."""
        try:
            items = sorted(
                self._candidates.values(),
                key=lambda c: (c.salience + 0.5 * c.predicted_stability),
                reverse=True,
            )[: max(1, int(top_k))]
            return {
                "current_focus": self._current_focus,
                "current_owner": self._current_owner,
                "candidates": [
                    {
                        "target_id": c.target_id,
                        "owner_type": c.owner_type,
                        "salience": c.salience,
                        "stability": c.predicted_stability,
                    }
                    for c in items
                ],
                "recommendation": dict(self._last_recommendation),
            }
        except Exception:
            return {"current_focus": self._current_focus}

    def _infer_owner_type(self, topic: str, event: dict[str, Any]) -> str:
        """Coarse owner attribution from topic and envelope."""
        try:
            if isinstance(event.get("user_id"), (str, int)):
                return "user"
            agent_name = (event.get("agent") or event.get("from_agent") or "").strip()
            if agent_name:
                return "peer"
            if topic.startswith("intent."):
                return "self"
            return "unknown"
        except Exception:
            return "unknown"


_SCHEMA = None


def get_attention_schema() -> AttentionSchema:
    global _SCHEMA
    if _SCHEMA is None:
        _SCHEMA = AttentionSchema()
    return _SCHEMA
