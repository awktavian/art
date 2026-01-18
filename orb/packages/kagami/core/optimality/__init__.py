"""Optimality Module — Bridging Theory and Implementation.

This module contains improvements that address the ~50% gap between
theoretical optimality and current implementation.

IMPROVEMENTS IMPLEMENTED:
========================
1. AdaptiveConvergenceMonitor - Dynamic strange loop iterations
2. AnalyticalEpistemicValue - Closed-form epistemic value
3. ModernHopfieldScaled - √N capacity scaling (Ramsauer et al. 2021)
4. TrueOctonionMultiply - Full non-associative octonion algebra
5. WassersteinIB - Optimal transport for Information Bottleneck
6. UncertaintyCalibrator - Metacognitive calibration
7. AdaptiveEWC - Online Fisher with adaptive λ
8. GradientAlignmentDetector - Conflict detection and projection

NOTE: PrioritizedReplayEnhanced has been removed. Use UnifiedReplayBuffer directly:
    from kagami.core.memory.unified_replay import get_unified_replay

Usage:
    from kagami.core.optimality import get_optimality_improvements

    improvements = get_optimality_improvements()

    # Access individual components
    monitor = improvements.convergence_monitor
    calibrator = improvements.uncertainty_calibrator

    # Enhanced online learning
    from kagami.core.optimality import get_enhanced_online_learning
    online = get_enhanced_online_learning(model)

Created: December 4, 2025
Updated: December 6, 2025 - Removed deprecated PrioritizedReplayEnhanced
Purpose: Close the optimality gap identified in system self-analysis.
"""

from kagami.core.optimality.enhanced_online_learning import (
    AdaptiveEWC,
    EnhancedOnlineLearning,
    GradientAlignmentDetector,
    get_enhanced_online_learning,
)
from kagami.core.optimality.improvements import (
    AdaptiveConvergenceMonitor,
    AdaptiveLoopConfig,
    AnalyticalEpistemicValue,
    ModernHopfieldScaled,
    OptimalityImprovements,
    SinkhornDistance,
    TrueOctonionMultiply,
    UncertaintyCalibrator,
    WassersteinIB,
    get_optimality_improvements,
)
from kagami.core.optimality.integration import (
    OptimalityWiring,
    get_optimality_wiring,
    integrate_all_improvements,
)
from kagami.core.optimality.remaining_gaps import (
    EmpowermentEnhanced,
    FullStructuralEquationModel,
    OctonionFanoCoherence,
    StructuralEquation,
    WorldModelOptimalityBridge,
    get_world_model_optimality_bridge,
)

__all__ = [
    "AdaptiveConvergenceMonitor",
    # Enhanced online learning
    "AdaptiveEWC",
    # Core improvements
    "AdaptiveLoopConfig",
    "AnalyticalEpistemicValue",
    "EmpowermentEnhanced",
    "EnhancedOnlineLearning",
    "FullStructuralEquationModel",
    "GradientAlignmentDetector",
    "ModernHopfieldScaled",
    "OctonionFanoCoherence",
    "OptimalityImprovements",
    # Integration
    "OptimalityWiring",
    "SinkhornDistance",
    # Remaining gaps
    "StructuralEquation",
    "TrueOctonionMultiply",
    "UncertaintyCalibrator",
    "WassersteinIB",
    "WorldModelOptimalityBridge",
    "get_enhanced_online_learning",
    "get_optimality_improvements",
    "get_optimality_wiring",
    "get_world_model_optimality_bridge",
    "integrate_all_improvements",
]
