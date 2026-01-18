"""Brain-Inspired Systems - Unified Neural Mechanisms.

This package consolidates all brain-inspired enhancements:

1. INHIBITION (inhibitory_gate.py)
   - Fast (PV) lateral inhibition for competition
   - Slow (SST) context-dependent gating
   - Disinhibition (VIP) for meta-control

2. NEUROMODULATION (neuromodulation/)
   - Dopamine: Reward prediction, motivation
   - Norepinephrine: Arousal, exploration
   - Acetylcholine: Attention, learning rate
   - Serotonin: Patience, risk aversion

3. CONSOLIDATION (memory/brain_consolidation.py)
   - Prioritized replay (SWR analog)
   - Schema extraction
   - Synaptic homeostasis

4. OSCILLATION (dynamics/oscillatory_coordinator.py)
   - Kuramoto oscillators for phase coordination
   - Gamma synchrony for binding
   - Theta-gamma coupling for hierarchy

5. FEEDBACK (feedback.py)
   - Top-down predictions
   - Hierarchical recurrence
   - Prediction error signals

Integration with Kagami:
- FanoActionRouter uses InhibitoryGate for colony competition
- OrganismRSSM uses FeedbackProjection for recurrence
- EFE calculator uses NeuromodulatorSystem for weight modulation
- Parallel executor uses OscillatoryCoordinator for binding

December 2025 - Brain Science × Kagami Integration
"""

from kagami.core.dynamics.oscillatory_coordinator import (
    OscillatorState,
    OscillatoryCoordinator,
    create_oscillatory_coordinator,
)
from kagami.core.memory.brain_consolidation import (
    BrainConsolidation,
    get_brain_consolidation,
)
from kagami.core.neuromodulation import (
    NeuromodulatorState,
    NeuromodulatorSystem,
    create_neuromodulator_system,
)
from kagami.core.unified_agents.inhibitory_gate import (
    InhibitionState,
    InhibitoryGate,
    create_inhibitory_gate,
)

from .feedback import FeedbackProjection, create_feedback_projection
from .unified_brain import UnifiedBrainSystem, create_unified_brain_system

__all__ = [
    # Consolidation
    "BrainConsolidation",
    # Feedback
    "FeedbackProjection",
    "InhibitionState",
    # Inhibition
    "InhibitoryGate",
    "NeuromodulatorState",
    # Neuromodulation
    "NeuromodulatorSystem",
    "OscillatorState",
    # Oscillation
    "OscillatoryCoordinator",
    # Unified
    "UnifiedBrainSystem",
    "create_feedback_projection",
    "create_inhibitory_gate",
    "create_neuromodulator_system",
    "create_oscillatory_coordinator",
    "create_unified_brain_system",
    "get_brain_consolidation",
]
