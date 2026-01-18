"""EFE Voice Policy — When to speak autonomously.

Implements Expected Free Energy (EFE) minimization for voice output decisions.
Voice output should reduce Tim's uncertainty about the world state.

Key Principles:
1. Information should reduce surprise/uncertainty
2. Voice should not increase surprise (unwanted interruptions)
3. Context determines value of information
4. Silence can also minimize EFE (don't over-communicate)

EFE Calculation:
    EFE = E[H[P(o|π)]] - E[log P(o)]
        = Expected uncertainty after action - Value of outcomes

For voice:
    EFE_speak = uncertainty_reduction - interruption_cost + relevance_score

Created: January 1, 2026
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.effectors.voice import PresenceContext

logger = logging.getLogger(__name__)


class InformationType(Enum):
    """Types of information that can be communicated."""

    ALERT = "alert"  # Safety/security alerts
    REMINDER = "reminder"  # Calendar, tasks, time-based
    STATUS = "status"  # System status updates
    NOTIFICATION = "notification"  # External notifications (email, messages)
    CONTEXT = "context"  # Contextual information (weather, traffic)
    PROACTIVE = "proactive"  # Anticipatory information
    RESPONSE = "response"  # Direct response to query


@dataclass
class PendingInfo:
    """Information pending potential voice output."""

    content: str
    info_type: InformationType
    source: str  # Where this info came from
    timestamp: float = field(default_factory=time.time)

    # EFE components
    uncertainty_reduction: float = 0.5  # How much this reduces Tim's uncertainty
    relevance: float = 0.5  # How relevant to current context
    time_sensitivity: float = 0.5  # How time-critical (1 = urgent, 0 = can wait)
    novelty: float = 0.5  # How new/surprising (1 = very new, 0 = already known)

    # Delivery preferences
    suggested_priority: int = 3  # 1-5 priority
    can_batch: bool = True  # Can be combined with other info
    max_delay_seconds: float = 300  # Max time before delivery (5 min default)

    @property
    def age_seconds(self) -> float:
        """How old is this info."""
        return time.time() - self.timestamp

    @property
    def urgency(self) -> float:
        """Calculate urgency based on age and time sensitivity."""
        age_factor = min(1.0, self.age_seconds / self.max_delay_seconds)
        return self.time_sensitivity * (1 + age_factor)


@dataclass
class VoicePolicyConfig:
    """Configuration for voice EFE policy."""

    # EFE thresholds
    speak_threshold: float = 0.6  # Minimum EFE reduction to speak
    batch_threshold: float = 0.4  # Threshold for batching info

    # Interruption costs (subtracted from EFE)
    cost_sleeping: float = 0.9  # Very high cost to interrupt sleep
    cost_focused: float = 0.7  # High cost during focus
    cost_movie: float = 0.8  # High cost during movie
    cost_driving: float = 0.5  # Moderate cost while driving
    cost_base: float = 0.1  # Base interruption cost

    # Time-based adjustments
    night_hours: tuple[int, int] = (22, 7)  # 10pm-7am
    night_penalty: float = 0.3  # Additional cost at night

    # Batching settings
    batch_window_seconds: float = 30  # Time to accumulate messages
    max_batch_size: int = 3  # Maximum items in batch

    # Rate limiting
    min_interval_seconds: float = 60  # Minimum time between speaks
    max_speaks_per_hour: int = 10  # Maximum autonomous speaks per hour


@dataclass
class VoicePolicyResult:
    """Result of voice policy evaluation."""

    should_speak: bool
    efe_score: float  # EFE reduction score
    reason: str
    content: str | None = None  # What to say
    priority: int = 3
    batch_items: list[PendingInfo] = field(default_factory=list)
    delay_seconds: float = 0  # Suggested delay before speaking


class VoiceEFEPolicy:
    """EFE-minimizing policy for autonomous voice output.

    Determines when Kagami should speak proactively based on:
    1. Information value (reduces uncertainty)
    2. Context costs (interruption, timing)
    3. Relevance and urgency

    Usage:
        policy = VoiceEFEPolicy()

        # Add pending information
        policy.add_info(PendingInfo(
            content="You have a meeting in 15 minutes",
            info_type=InformationType.REMINDER,
            source="calendar",
            time_sensitivity=0.8,
        ))

        # Evaluate policy
        result = policy.evaluate(presence_context)
        if result.should_speak:
            await speak(result.content, priority=result.priority)
    """

    def __init__(self, config: VoicePolicyConfig | None = None):
        """Initialize voice policy.

        Args:
            config: Policy configuration
        """
        self.config = config or VoicePolicyConfig()

        # Pending information queue
        self._pending: list[PendingInfo] = []

        # Rate limiting state
        self._last_speak_time: float = 0
        self._speaks_this_hour: int = 0
        self._hour_start: float = time.time()

        # Statistics
        self._stats = {
            "evaluations": 0,
            "speaks_approved": 0,
            "speaks_suppressed": 0,
            "batches_created": 0,
            "total_efe_reduction": 0.0,
        }

    def add_info(self, info: PendingInfo) -> None:
        """Add information to pending queue.

        Args:
            info: Information to potentially communicate
        """
        self._pending.append(info)
        self._cleanup_old_info()

    def _cleanup_old_info(self) -> None:
        """Remove expired information."""
        self._pending = [
            info for info in self._pending if info.age_seconds < info.max_delay_seconds * 2
        ]

    def evaluate(self, presence: PresenceContext) -> VoicePolicyResult:
        """Evaluate whether to speak based on EFE.

        Args:
            presence: Tim's current presence context

        Returns:
            VoicePolicyResult with decision
        """
        self._stats["evaluations"] += 1
        self._cleanup_old_info()
        self._update_rate_limits()

        # Check rate limits
        if not self._can_speak_rate():
            return VoicePolicyResult(
                should_speak=False,
                efe_score=0,
                reason="rate_limited",
            )

        # No pending info
        if not self._pending:
            return VoicePolicyResult(
                should_speak=False,
                efe_score=0,
                reason="no_pending_info",
            )

        # Calculate interruption cost based on context
        cost = self._calculate_interruption_cost(presence)

        # Evaluate each pending item
        scored_items: list[tuple[PendingInfo, float]] = []
        for info in self._pending:
            efe = self._calculate_efe(info, cost)
            scored_items.append((info, efe))

        # Sort by EFE (highest reduction first)
        scored_items.sort(key=lambda x: x[1], reverse=True)

        # Check best item against threshold
        best_info, best_efe = scored_items[0]

        if best_efe < self.config.speak_threshold:
            # Not worth speaking yet
            return VoicePolicyResult(
                should_speak=False,
                efe_score=best_efe,
                reason="below_threshold",
            )

        # Check for batching opportunity
        batch_items = self._create_batch(scored_items)

        if batch_items:
            content = self._format_batch(batch_items)
            # Remove batched items from pending
            for item in batch_items:
                if item in self._pending:
                    self._pending.remove(item)

            self._stats["speaks_approved"] += 1
            self._stats["batches_created"] += 1
            self._stats["total_efe_reduction"] += best_efe
            self._last_speak_time = time.time()
            self._speaks_this_hour += 1

            return VoicePolicyResult(
                should_speak=True,
                efe_score=best_efe,
                reason="batch_ready",
                content=content,
                priority=min(item.suggested_priority for item in batch_items),
                batch_items=batch_items,
            )

        # Single item speak
        self._pending.remove(best_info)
        self._stats["speaks_approved"] += 1
        self._stats["total_efe_reduction"] += best_efe
        self._last_speak_time = time.time()
        self._speaks_this_hour += 1

        return VoicePolicyResult(
            should_speak=True,
            efe_score=best_efe,
            reason="efe_threshold_met",
            content=best_info.content,
            priority=best_info.suggested_priority,
            batch_items=[best_info],
        )

    def _calculate_efe(self, info: PendingInfo, cost: float) -> float:
        """Calculate EFE reduction for speaking this info.

        EFE = uncertainty_reduction * relevance * urgency - cost

        Args:
            info: Information to evaluate
            cost: Interruption cost from context

        Returns:
            EFE reduction score (higher = more valuable to speak)
        """
        # Base value from info properties
        value = (
            info.uncertainty_reduction * 0.4
            + info.relevance * 0.3
            + info.time_sensitivity * 0.2
            + info.novelty * 0.1
        )

        # Boost for urgency (time-sensitive items become more valuable)
        urgency_boost = info.urgency * 0.3

        # Penalty for age (old info is less valuable)
        age_penalty = min(0.3, info.age_seconds / 300 * 0.1)

        # Alert type bonus (always important)
        type_bonus = 0.3 if info.info_type == InformationType.ALERT else 0

        # Calculate final EFE reduction
        efe = value + urgency_boost + type_bonus - cost - age_penalty

        return max(0, min(1, efe))  # Clamp to [0, 1]

    def _calculate_interruption_cost(self, presence: PresenceContext) -> float:
        """Calculate cost of interrupting based on context.

        Args:
            presence: Current presence context

        Returns:
            Cost value [0, 1] where higher = more costly to interrupt
        """
        cost = self.config.cost_base

        # State-based costs
        if presence.is_sleeping:
            cost += self.config.cost_sleeping
        if presence.is_focused:
            cost += self.config.cost_focused
        if presence.movie_mode:
            cost += self.config.cost_movie
        if presence.in_vehicle:
            cost += self.config.cost_driving

        # Time-based cost
        hour = time.localtime().tm_hour
        start, end = self.config.night_hours
        is_night = hour >= start or hour < end
        if is_night:
            cost += self.config.night_penalty

        return min(1.0, cost)  # Cap at 1.0

    def _create_batch(
        self,
        scored_items: list[tuple[PendingInfo, float]],
    ) -> list[PendingInfo]:
        """Create a batch of items to communicate together.

        Args:
            scored_items: Items sorted by EFE score

        Returns:
            List of items to batch together
        """
        if len(scored_items) < 2:
            return []

        batch: list[PendingInfo] = []
        for info, efe in scored_items:
            if not info.can_batch:
                continue
            if efe < self.config.batch_threshold:
                break
            if len(batch) >= self.config.max_batch_size:
                break
            batch.append(info)

        # Only batch if 2+ items
        if len(batch) >= 2:
            return batch
        return []

    def _format_batch(self, items: list[PendingInfo]) -> str:
        """Format batched items into a single message.

        Args:
            items: Items to combine

        Returns:
            Combined message string
        """
        if len(items) == 1:
            return items[0].content

        # Group by type
        messages = []
        for item in items:
            messages.append(item.content)

        # Create natural language combination
        if len(messages) == 2:
            return f"{messages[0]}. Also, {messages[1].lower()}"
        else:
            intro = messages[0]
            middle = ". ".join(messages[1:-1])
            last = messages[-1]
            return f"{intro}. {middle}. Finally, {last.lower()}"

    def _can_speak_rate(self) -> bool:
        """Check if speaking is allowed by rate limits.

        Returns:
            True if speaking is allowed
        """
        now = time.time()

        # Minimum interval
        if now - self._last_speak_time < self.config.min_interval_seconds:
            return False

        # Hourly limit
        if self._speaks_this_hour >= self.config.max_speaks_per_hour:
            return False

        return True

    def _update_rate_limits(self) -> None:
        """Update rate limit counters."""
        now = time.time()

        # Reset hourly counter
        if now - self._hour_start > 3600:
            self._hour_start = now
            self._speaks_this_hour = 0

    def clear_pending(self) -> None:
        """Clear all pending information."""
        self._pending.clear()

    def get_pending_count(self) -> int:
        """Get number of pending items."""
        return len(self._pending)

    def get_stats(self) -> dict[str, Any]:
        """Get policy statistics."""
        return {
            **self._stats,
            "pending_count": len(self._pending),
            "speaks_this_hour": self._speaks_this_hour,
            "seconds_since_speak": time.time() - self._last_speak_time,
        }


# Module-level singleton
_voice_policy: VoiceEFEPolicy | None = None


def get_voice_policy() -> VoiceEFEPolicy:
    """Get the voice policy singleton.

    Returns:
        VoiceEFEPolicy instance
    """
    global _voice_policy
    if _voice_policy is None:
        _voice_policy = VoiceEFEPolicy()
    return _voice_policy
