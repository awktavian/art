"""Entity-Receipt Learning Bridge — Causal State Understanding.

DEEP INTEGRATION ENHANCEMENT (Dec 30, 2025):

CURRENT STATE:
- EntityMemory (world state) separate from ReceiptLearning
- No causal understanding of state transitions
- Actions executed in isolation from state context

ENHANCED STATE:
- Entity state changes feed into receipt context
- Receipt outcomes update entity relationships
- Causal understanding: "When X state, then Y action succeeds/fails"
- Predictive state modeling based on action history

IMPACT:
- Causal understanding of state transitions
- Context-aware action selection
- Predictive state modeling
- Reduced failures through state awareness

Created: December 30, 2025
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class StateTransitionType(Enum):
    """Types of state transitions to track."""

    ENTITY_UPDATE = "entity_update"  # Entity state changed
    CONTEXT_SHIFT = "context_shift"  # Environmental context changed
    ACTION_OUTCOME = "action_outcome"  # Action changed entity states
    CAUSAL_CHAIN = "causal_chain"  # Multi-step state sequence
    PREDICTION_ERROR = "prediction_error"  # Predicted state != actual state


@dataclass
class StateTransition:
    """A state transition with causal context."""

    transition_id: str
    transition_type: StateTransitionType
    timestamp: datetime

    # State information
    entity_id: str | None = None
    entity_type: str | None = None

    # Before/after states
    state_before: dict[str, Any] = field(default_factory=dict)
    state_after: dict[str, Any] = field(default_factory=dict)

    # Action context
    action_taken: str | None = None
    colonies_involved: list[str] = field(default_factory=list)

    # Outcomes
    action_success: bool = True
    predicted_state: dict[str, Any] = field(default_factory=dict)
    prediction_error: float = 0.0

    # Learning signals
    confidence: float = 1.0
    causal_strength: float = 0.0
    surprise_factor: float = 0.0


@dataclass
class CausalPattern:
    """A learned causal pattern between states and actions."""

    pattern_id: str
    description: str

    # Pattern structure
    state_conditions: dict[str, Any] = field(default_factory=dict)
    action_signature: str = ""
    outcome_probability: float = 0.5

    # Evidence
    supporting_transitions: int = 0
    contradicting_transitions: int = 0
    confidence: float = 0.0

    # Learning metrics
    first_observed: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    prediction_accuracy: float = 0.0


class EntityReceiptBridge:
    """Bridge between EntityMemory and ReceiptLearning for causal understanding.

    This system creates causal understanding by:
    1. Tracking entity state changes before/after actions
    2. Recording action outcomes in context of entity states
    3. Learning causal patterns: State + Action → Outcome
    4. Predicting action success based on current entity states
    5. Updating entity relationships based on action outcomes

    Usage:
        bridge = get_entity_receipt_bridge()

        # Track state transition
        await bridge.record_state_transition(
            entity_id="home_status",
            state_before={"occupancy": "away", "lights": "off"},
            action="lights.welcome_home",
            state_after={"occupancy": "present", "lights": "on"},
            action_success=True
        )

        # Predict action success
        probability = await bridge.predict_action_success(
            entity_states={"home_status": {"occupancy": "present"}},
            action="lights.movie_mode"
        )

        # Get causal insights
        patterns = await bridge.get_causal_patterns("lights")
    """

    def __init__(self) -> None:
        """Initialize entity-receipt bridge."""
        self._initialized = False
        self._transition_buffer: list[StateTransition] = []
        self._causal_patterns: dict[str, CausalPattern] = {}

    async def initialize(self) -> None:
        """Initialize dependencies."""
        if self._initialized:
            return

        try:
            # Import dependencies
            from kagami.core.learning.receipt_learning import get_receipt_learning_engine
            from kagami.core.memory.integration import get_memory_hub
            from kagami.core.services.embedding_service import get_embedding_service
            from kagami.core.world_model.entity_memory import get_entity_memory

            self._entity_memory = get_entity_memory()
            self._receipt_engine = get_receipt_learning_engine()
            self._embedding_service = get_embedding_service()
            self._memory_hub = get_memory_hub()

            # Start background processing
            asyncio.create_task(self._process_transitions_loop())

            self._initialized = True
            logger.info("EntityReceiptBridge initialized")

        except Exception as e:
            logger.error(f"Failed to initialize EntityReceiptBridge: {e}")
            raise

    async def record_state_transition(
        self,
        entity_id: str,
        state_before: dict[str, Any],
        action: str,
        state_after: dict[str, Any],
        action_success: bool,
        colonies_involved: list[str] | None = None,
        predicted_state: dict[str, Any] | None = None,
    ) -> str:
        """Record a state transition for causal learning.

        Args:
            entity_id: ID of entity that changed state
            state_before: Entity state before action
            action: Action that was taken
            state_after: Entity state after action
            action_success: Whether action succeeded
            colonies_involved: Colonies that executed action
            predicted_state: What we predicted the state would be

        Returns:
            Transition ID for tracking
        """
        await self.initialize()

        transition_id = f"trans_{int(datetime.now().timestamp())}_{hash(entity_id)}"

        # Calculate prediction error if we had a prediction
        prediction_error = 0.0
        if predicted_state:
            prediction_error = self._calculate_state_difference(predicted_state, state_after)

        transition = StateTransition(
            transition_id=transition_id,
            transition_type=StateTransitionType.ACTION_OUTCOME,
            timestamp=datetime.now(),
            entity_id=entity_id,
            state_before=state_before,
            state_after=state_after,
            action_taken=action,
            action_success=action_success,
            colonies_involved=colonies_involved or [],
            predicted_state=predicted_state or {},
            prediction_error=prediction_error,
            causal_strength=self._estimate_causal_strength(state_before, state_after),
            surprise_factor=self._calculate_surprise(state_before, state_after, action),
        )

        # Buffer for batch processing
        self._transition_buffer.append(transition)

        logger.debug(
            f"Recorded state transition {transition_id}: {entity_id} "
            f"{action} → {'✓' if action_success else '✗'}"
        )

        return transition_id

    async def predict_action_success(
        self, entity_states: dict[str, dict[str, Any]], action: str
    ) -> float:
        """Predict probability of action success given current entity states.

        Args:
            entity_states: Current entity states
            action: Action to predict

        Returns:
            Probability of success (0.0 - 1.0)
        """
        await self.initialize()

        # Find matching causal patterns
        matching_patterns = []

        for pattern in self._causal_patterns.values():
            if pattern.action_signature == action and self._states_match_pattern(
                entity_states, pattern.state_conditions
            ):
                matching_patterns.append(pattern)

        if not matching_patterns:
            # No patterns found, use base probability
            return 0.7  # Optimistic default

        # Weight by confidence and recency
        total_weight = 0.0
        weighted_probability = 0.0

        for pattern in matching_patterns:
            # Weight by confidence and recency
            recency = max(0.1, 1.0 - (datetime.now() - pattern.last_updated).days / 30.0)
            weight = pattern.confidence * recency

            weighted_probability += pattern.outcome_probability * weight
            total_weight += weight

        if total_weight > 0:
            prediction = weighted_probability / total_weight
        else:
            prediction = 0.7

        logger.debug(
            f"Predicted action success: {action} → {prediction:.2%} "
            f"(based on {len(matching_patterns)} patterns)"
        )

        return prediction

    async def get_causal_patterns(self, entity_type: str | None = None) -> list[CausalPattern]:
        """Get learned causal patterns.

        Args:
            entity_type: Filter by entity type (None for all)

        Returns:
            List of causal patterns
        """
        await self.initialize()

        patterns = list(self._causal_patterns.values())

        if entity_type:
            # Filter patterns that involve the entity type
            patterns = [p for p in patterns if entity_type in p.description.lower()]

        # Sort by confidence and supporting evidence
        patterns.sort(key=lambda p: (p.confidence, p.supporting_transitions), reverse=True)

        return patterns

    async def enhance_receipt_context(
        self, receipt_data: dict[str, Any], entity_states: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Enhance receipt with entity state context.

        Args:
            receipt_data: Original receipt data
            entity_states: Current entity states

        Returns:
            Enhanced receipt with entity context
        """
        await self.initialize()

        enhanced = receipt_data.copy()

        # Add entity state context
        enhanced["entity_context"] = {
            "states_at_execution": entity_states,
            "relevant_entities": self._identify_relevant_entities(receipt_data, entity_states),
            "state_complexity": self._calculate_state_complexity(entity_states),
            "causal_predictions": await self._generate_causal_predictions(
                entity_states, receipt_data.get("action", "")
            ),
        }

        # Add historical context
        similar_contexts = await self._find_similar_contexts(entity_states)
        if similar_contexts:
            enhanced["historical_context"] = {
                "similar_situations": len(similar_contexts),
                "avg_success_rate": np.mean([ctx.action_success for ctx in similar_contexts]),
                "common_failures": self._extract_common_failures(similar_contexts),
            }

        return enhanced

    async def update_entity_relationships(
        self,
        receipt_outcome: dict[str, Any],
        entity_states_before: dict[str, dict[str, Any]],
        entity_states_after: dict[str, dict[str, Any]],
    ) -> None:
        """Update entity relationships based on action outcomes.

        Args:
            receipt_outcome: Receipt with action outcome
            entity_states_before: Entity states before action
            entity_states_after: Entity states after action
        """
        await self.initialize()

        # Calculate state changes
        state_changes = {}
        for entity_id in set(entity_states_before.keys()) | set(entity_states_after.keys()):
            before = entity_states_before.get(entity_id, {})
            after = entity_states_after.get(entity_id, {})

            if before != after:
                state_changes[entity_id] = {
                    "before": before,
                    "after": after,
                    "change_magnitude": self._calculate_state_difference(before, after),
                }

        # Update entity memory with relationship changes
        for entity_id, change_info in state_changes.items():
            await self._entity_memory.update_entity(
                entity_id,
                {
                    "last_action_outcome": receipt_outcome.get("success", True),
                    "last_change_magnitude": change_info["change_magnitude"],
                    "last_updated": datetime.now().isoformat(),
                    "causal_confidence": self._estimate_causal_strength(
                        change_info["before"], change_info["after"]
                    ),
                },
            )

        logger.debug(f"Updated {len(state_changes)} entity relationships from receipt outcome")

    # =========================================================================
    # INTERNAL METHODS
    # =========================================================================

    async def _process_transitions_loop(self) -> None:
        """Background processing of state transitions."""
        while True:
            try:
                await asyncio.sleep(10)  # Process every 10 seconds

                if self._transition_buffer:
                    transitions_to_process = self._transition_buffer.copy()
                    self._transition_buffer.clear()

                    await self._process_transition_batch(transitions_to_process)

            except Exception as e:
                logger.error(f"Error in transition processing loop: {e}")

    async def _process_transition_batch(self, transitions: list[StateTransition]) -> None:
        """Process a batch of transitions for pattern learning."""
        for transition in transitions:
            # Update causal patterns
            await self._update_causal_patterns(transition)

            # Store in memory for historical analysis
            await self._store_transition_in_memory(transition)

        logger.debug(f"Processed {len(transitions)} state transitions")

    async def _update_causal_patterns(self, transition: StateTransition) -> None:
        """Update causal patterns based on transition."""
        pattern_key = (
            f"{transition.action_taken}_{hash(str(sorted(transition.state_before.items())))}"
        )

        if pattern_key not in self._causal_patterns:
            # Create new pattern
            self._causal_patterns[pattern_key] = CausalPattern(
                pattern_id=pattern_key,
                description=f"Action {transition.action_taken} in context {transition.state_before}",
                state_conditions=transition.state_before.copy(),
                action_signature=transition.action_taken or "",
                first_observed=transition.timestamp,
            )

        pattern = self._causal_patterns[pattern_key]

        # Update evidence
        if transition.action_success:
            pattern.supporting_transitions += 1
        else:
            pattern.contradicting_transitions += 1

        # Update probability and confidence
        total_evidence = pattern.supporting_transitions + pattern.contradicting_transitions
        pattern.outcome_probability = pattern.supporting_transitions / total_evidence
        pattern.confidence = min(total_evidence / 10.0, 1.0)  # Max confidence at 10 examples
        pattern.last_updated = transition.timestamp

        # Update prediction accuracy based on prediction error
        if transition.prediction_error is not None:
            accuracy = max(0.0, 1.0 - transition.prediction_error)
            if pattern.prediction_accuracy == 0.0:
                pattern.prediction_accuracy = accuracy
            else:
                # Moving average
                pattern.prediction_accuracy = 0.9 * pattern.prediction_accuracy + 0.1 * accuracy

    async def _store_transition_in_memory(self, transition: StateTransition) -> None:
        """Store transition in episodic memory."""
        try:
            # Create embedding for semantic search
            description = f"Action {transition.action_taken} changed {transition.entity_id} from {transition.state_before} to {transition.state_after}"
            embedding = await self._embedding_service.embed_text_async(description)

            # Store in memory hub
            await self._memory_hub.store_episode(
                {
                    "type": "state_transition",
                    "transition_id": transition.transition_id,
                    "description": description,
                    "embedding": embedding.tolist(),
                    "timestamp": transition.timestamp.isoformat(),
                    "success": transition.action_success,
                    "causal_strength": transition.causal_strength,
                    "surprise_factor": transition.surprise_factor,
                }
            )

        except Exception as e:
            logger.warning(f"Failed to store transition in memory: {e}")

    def _calculate_state_difference(self, state1: dict[str, Any], state2: dict[str, Any]) -> float:
        """Calculate difference between two states."""
        all_keys = set(state1.keys()) | set(state2.keys())

        if not all_keys:
            return 0.0

        differences = 0
        for key in all_keys:
            val1 = state1.get(key)
            val2 = state2.get(key)

            if val1 != val2:
                differences += 1

        return differences / len(all_keys)

    def _estimate_causal_strength(
        self, state_before: dict[str, Any], state_after: dict[str, Any]
    ) -> float:
        """Estimate causal strength of transition."""
        difference = self._calculate_state_difference(state_before, state_after)

        # Strong causal relationship if many state variables changed
        return min(difference * 2.0, 1.0)

    def _calculate_surprise(
        self, state_before: dict[str, Any], state_after: dict[str, Any], action: str
    ) -> float:
        """Calculate surprise factor of transition."""
        # High surprise if unexpected state change
        difference = self._calculate_state_difference(state_before, state_after)

        # Could be enhanced with prediction model
        return difference

    def _states_match_pattern(
        self, current_states: dict[str, dict[str, Any]], pattern_conditions: dict[str, Any]
    ) -> bool:
        """Check if current states match pattern conditions."""
        for condition_key, condition_value in pattern_conditions.items():
            # Simple key-value matching (could be enhanced)
            found_match = False

            for entity_states in current_states.values():
                if entity_states.get(condition_key) == condition_value:
                    found_match = True
                    break

            if not found_match:
                return False

        return True

    def _identify_relevant_entities(
        self, receipt_data: dict[str, Any], entity_states: dict[str, dict[str, Any]]
    ) -> list[str]:
        """Identify entities relevant to the action."""
        action = receipt_data.get("action", "").lower()
        relevant = []

        for entity_id, states in entity_states.items():
            # Simple heuristic: entity is relevant if mentioned in action or has dynamic states
            if (
                any(keyword in action for keyword in entity_id.lower().split("_"))
                or len(states) > 3
            ):
                relevant.append(entity_id)

        return relevant

    def _calculate_state_complexity(self, entity_states: dict[str, dict[str, Any]]) -> float:
        """Calculate complexity score for entity states."""
        total_complexity = 0.0

        for states in entity_states.values():
            # Complexity based on number of state variables and their types
            complexity = len(states)

            for value in states.values():
                if isinstance(value, (dict, list)):
                    complexity += 2  # Complex types add more complexity
                elif isinstance(value, str) and len(value) > 20:
                    complexity += 1  # Long strings add complexity

            total_complexity += complexity

        # Normalize by number of entities
        return total_complexity / max(len(entity_states), 1)

    async def _generate_causal_predictions(
        self, entity_states: dict[str, dict[str, Any]], action: str
    ) -> dict[str, Any]:
        """Generate causal predictions for action in current state."""
        predictions = {}

        # Find patterns that match current state
        matching_patterns = []
        for pattern in self._causal_patterns.values():
            if pattern.action_signature == action and self._states_match_pattern(
                entity_states, pattern.state_conditions
            ):
                matching_patterns.append(pattern)

        if matching_patterns:
            # Aggregate predictions
            success_probabilities = [p.outcome_probability for p in matching_patterns]
            confidences = [p.confidence for p in matching_patterns]

            predictions = {
                "success_probability": np.mean(success_probabilities),
                "confidence": np.mean(confidences),
                "pattern_count": len(matching_patterns),
                "historical_evidence": sum(
                    p.supporting_transitions + p.contradicting_transitions
                    for p in matching_patterns
                ),
            }

        return predictions

    async def _find_similar_contexts(
        self, entity_states: dict[str, dict[str, Any]]
    ) -> list[StateTransition]:
        """Find historical transitions with similar entity states."""
        # Simplified implementation - could use embedding similarity
        similar = []

        self._calculate_state_complexity(entity_states)

        # Would need to search stored transitions - placeholder for now
        # In real implementation, this would query the memory hub for similar contexts

        return similar

    def _extract_common_failures(self, transitions: list[StateTransition]) -> list[str]:
        """Extract common failure patterns from transitions."""
        failures = [t for t in transitions if not t.action_success]

        if not failures:
            return []

        # Group by action type
        failure_actions = {}
        for failure in failures:
            action = failure.action_taken or "unknown"
            if action not in failure_actions:
                failure_actions[action] = 0
            failure_actions[action] += 1

        # Return most common failures
        sorted_failures = sorted(failure_actions.items(), key=lambda x: x[1], reverse=True)
        return [action for action, count in sorted_failures[:3]]


# =============================================================================
# SINGLETON FACTORY (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_entity_receipt_bridge = _singleton_registry.register_sync(
    "entity_receipt_bridge", EntityReceiptBridge
)
