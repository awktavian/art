from typing import Any

"""鏡 Mind — Unified Cognitive Architecture for K OS.

The mind/ package provides a unified namespace for all cognitive subsystems.
It does NOT move files - it creates a logical grouping for imports and documentation.

## Architecture

```
mind/
├── affective/       → Emotion-like decision shortcuts
│   ├── AffectiveLayer        # Core affect processing
│   ├── ValenceEvaluator      # Positive/negative assessment
│   ├── ArousalRegulator      # Activation level control
│   └── ThreatAssessment      # Danger evaluation
│
├── cognition/       → Three-layer recursive thinking
│   ├── PhilosophicalLayer    # Question & reconceptualize
│   ├── ScientificLayer       # Study & systematize
│   └── RecursiveFeedback     # Cross-layer coordination
│
├── motivation/      → Intrinsic drives and goals
│   ├── IntrinsicMotivation   # Drive-based motivation
│   ├── GoalHierarchy         # Temporal goal organization
│   └── ValueAlignment        # Ensure goals align with values
│
├── metacognition/   → Thinking about thinking
│   ├── UncertaintyEstimator  # Bayesian confidence
│   └── CapabilityTracker     # What can I do? How well?
│
├── instincts/       → Universal adaptive mechanisms
│   ├── PredictionInstinct    # Pattern learning
│   ├── ThreatInstinct        # Harm avoidance
│   ├── LearningInstinct      # Update from experience
│   └── EthicalInstinct       # Constitutional constraints
│
└── introspection/   → Self-examination
    ├── IntrospectionEngine   # Self-explanation
    └── ReflectionManager     # Periodic reflection loops
```

## LeCun Architecture Mapping

The mind package maps to LeCun's cognitive architecture:

| Mind Subsystem | LeCun Module | Function |
|----------------|--------------|----------|
| affective | Cost Module | Evaluates outcomes (valence, threat) |
| cognition | World Model | Predicts consequences of actions |
| motivation | Configurator | Modulates processing based on goals |
| metacognition | Self-Model | Meta-awareness of capabilities |
| instincts | Intrinsic Cost | Hardwired survival constraints |
| introspection | Self-Model | Explains own reasoning |

## Usage

Import the unified mind namespace:
```python
from kagami.core.cognition import (
    # Affective
    AffectiveLayer,
    ThreatAssessment,
    ValenceEvaluator,
    # Cognition
    PhilosophicalLayer,
    ScientificLayer,
    # Motivation
    IntrinsicMotivationSystem,
    GoalHierarchyManager,
    # Motivation (see kagami.core.motivation for full interface)
    # Instincts
    PredictionInstinct,
    EthicalInstinct,
    # Introspection
    IntrospectionEngine,
)
```

Or import the full subsystem:
```python
from kagami.core import mind
state = mind.get_unified_mind_state()
```

## Mathematical Foundation

The mind subsystems implement a **Markov Blanket** around the self:

```
          Sensory States
               ↓
┌──────────────────────────────────┐
│          Internal States          │
│  ┌─────────┐   ┌─────────┐       │
│  │affective│◄─►│cognition│       │
│  └────┬────┘   └────┬────┘       │
│       │             │             │
│  ┌────▼────┐   ┌────▼─────┐      │
│  │instincts│◄─►│motivation│      │
│  └────┬────┘   └────┬─────┘      │
│       │             │             │
│  ┌────▼──────────────▼────┐      │
│  │     metacognition       │      │
│  │     introspection       │      │
│  └────────────┬───────────┘      │
└───────────────┼──────────────────┘
                ↓
          Active States

h(x) ≥ 0 at all boundaries (safety invariant)
```

Created: December 6, 2025
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AFFECTIVE (emotion-like decision shortcuts)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from kagami.core.affective import (
    AffectiveLayer,
    ArousalRegulator,
    SentimentProfile,
    SocialEmotionProcessor,
    ThreatAssessment,
    ThreatScore,
    ValenceEvaluator,
)
from kagami.core.cognition.embodied import get_embodied_cognitive_state

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COGNITION (three-layer recursive thinking)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from kagami.core.cognition.layer_interface import LayerInterface, LayerMessage
from kagami.core.cognition.metrics import (
    CognitiveState,
    compute_consistency,
    compute_evolution_rate,
    compute_metacognition,
    compute_temporal_coherence,
    get_cognitive_state,
)
from kagami.core.cognition.philosophical_layer import PhilosophicalLayer
from kagami.core.cognition.recursive_feedback import RecursiveFeedbackCoordinator
from kagami.core.cognition.scientific_layer import ScientificLayer
from kagami.core.cognition.state import get_cognitive_state_snapshot
from kagami.core.cognition.unified import get_unified_cognitive_state_snapshot

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# METACOGNITION (consolidated into learning/ and instincts/)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NOTE: BayesianUncertaintyEstimator and CapabilityTracker have been consolidated.
# Use kagami.core.learning.confidence_calibration for uncertainty estimation.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INSTINCTS (universal adaptive mechanisms)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from kagami.core.instincts import (
    JailbreakDetector,
    LearningInstinct,
    PredictionInstinct,
    ThreatInstinct,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MOTIVATION (intrinsic drives and goal hierarchies)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from kagami.core.motivation import (
    AutonomousGoalSafety,
    Drive,
    GoalHierarchyManager,
    ImplicitValue,
    IntrinsicGoal,
    IntrinsicMotivationSystem,
    ValueAlignmentChecker,
    ValueDiscovery,
)

# Alias for backward compatibility (EthicalInstinct -> JailbreakDetector)
EthicalInstinct = JailbreakDetector

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# INTROSPECTION (self-examination)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# UNIFIED MIND STATE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from dataclasses import dataclass, field

from kagami.core.debugging import (
    ErrorDetection,
    IntrospectionEngine,
    IntrospectionManagerProtocol,
    ReasoningTrace,
    SelfExplanation,
    get_introspection_engine,
    reflect_post_intent,
    start_periodic_reflection_loop,
    stop_periodic_reflection_loop,
)


@dataclass
class MindState:
    """Unified snapshot of the mind's state."""

    # Affective
    valence: float = 0.0  # -1 (negative) to +1 (positive)
    arousal: float = 0.5  # 0 (calm) to 1 (activated)
    threat_level: float = 0.0  # 0 (safe) to 1 (danger)

    # Cognitive
    cognitive_state: CognitiveState | None = None
    active_layer: str = "technological"  # technological, scientific, philosophical

    # Motivation
    active_drives: list[str] = field(default_factory=list[Any])
    current_goal: str | None = None

    # Metacognitive
    uncertainty: float = 0.5  # 0 (certain) to 1 (uncertain)
    capability_confidence: float = 0.5

    # Instinct activations
    instinct_activations: dict[str, float] = field(default_factory=dict[str, Any])

    # Introspection
    last_reflection: str | None = None


def get_unified_mind_state() -> MindState:
    """Get a unified snapshot of the mind's state.

    Returns:
        MindState with current values from all subsystems
    """
    state = MindState()

    # Get cognitive state
    try:
        state.cognitive_state = get_cognitive_state()  # type: ignore[call-arg]
    except Exception:
        pass

    # Get uncertainty from confidence calibration module
    # NOTE: get_uncertainty_estimator was removed during consolidation (Dec 2025)
    # Uncertainty estimation now uses kagami.core.learning.confidence_calibration
    try:
        from kagami.core.learning.confidence_calibration import (
            get_calibration_state,  # type: ignore[attr-defined]
        )

        cal_state = get_calibration_state()
        if cal_state and hasattr(cal_state, "uncertainty"):
            state.uncertainty = cal_state.uncertainty
    except Exception:
        pass

    return state


__all__ = [
    # === Affective ===
    "AffectiveLayer",
    "ArousalRegulator",
    "AutonomousGoalSafety",
    "CognitiveState",
    # === Motivation ===
    "Drive",
    "ErrorDetection",
    "EthicalInstinct",  # Alias for JailbreakDetector (backward compat)
    "GoalHierarchyManager",
    "ImplicitValue",
    "IntrinsicGoal",
    "IntrinsicMotivationSystem",
    "IntrospectionEngine",
    "IntrospectionManagerProtocol",
    "JailbreakDetector",
    "LayerInterface",
    "LayerMessage",
    "LearningInstinct",
    # === Unified ===
    "MindState",
    "PhilosophicalLayer",
    # === Metacognition (consolidated) ===
    # Use kagami.core.learning.confidence_calibration for uncertainty
    # === Instincts ===
    "PredictionInstinct",
    # === Introspection ===
    "ReasoningTrace",
    "RecursiveFeedbackCoordinator",
    # === Cognition ===
    "ScientificLayer",
    "SelfExplanation",
    "SentimentProfile",
    "SocialEmotionProcessor",
    "ThreatAssessment",
    "ThreatInstinct",
    "ThreatScore",
    "ValenceEvaluator",
    "ValueAlignmentChecker",
    "ValueDiscovery",
    "compute_consistency",
    "compute_evolution_rate",
    "compute_metacognition",
    "compute_temporal_coherence",
    "get_cognitive_state",
    "get_cognitive_state_snapshot",
    "get_embodied_cognitive_state",
    "get_introspection_engine",
    "get_unified_cognitive_state_snapshot",
    "get_unified_mind_state",
    "reflect_post_intent",
    "start_periodic_reflection_loop",
    "stop_periodic_reflection_loop",
]
