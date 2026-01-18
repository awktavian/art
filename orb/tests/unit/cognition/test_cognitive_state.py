"""Tests for Cognitive State Management.

Tests cover:
- MindState dataclass
- Cognitive state snapshots
- Unified mind state retrieval
- Cognitive metrics computation

Coverage target: kagami/core/cognition/__init__.py, state.py, metrics.py
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_unit



from dataclasses import fields
from typing import Any

from kagami.core.cognition import (
    MindState,
    get_unified_mind_state,
    CognitiveState,
    get_cognitive_state,
    get_cognitive_state_snapshot,
    compute_metacognition,
    compute_temporal_coherence,
    compute_consistency,
    compute_evolution_rate,
)

# =============================================================================
# MIND STATE TESTS
# =============================================================================


class TestMindState:
    """Tests for MindState dataclass."""

    def test_default_init(self) -> None:
        """Test default initialization."""
        state = MindState()

        assert state.valence == 0.0
        assert state.arousal == 0.5
        assert state.threat_level == 0.0
        assert state.uncertainty == 0.5
        assert state.cognitive_state is None
        assert state.active_layer == "technological"
        assert state.active_drives == []
        assert state.current_goal is None

    def test_custom_init(self) -> None:
        """Test initialization with custom values."""
        state = MindState(
            valence=0.8,
            arousal=0.9,
            threat_level=0.2,
            active_layer="philosophical",
            current_goal="achieve enlightenment",
        )

        assert state.valence == 0.8
        assert state.arousal == 0.9
        assert state.threat_level == 0.2
        assert state.active_layer == "philosophical"
        assert state.current_goal == "achieve enlightenment"

    def test_fields_exist(self) -> None:
        """Test all expected fields exist."""
        state = MindState()
        field_names = {f.name for f in fields(state)}

        expected_fields = {
            "valence",
            "arousal",
            "threat_level",
            "cognitive_state",
            "active_layer",
            "active_drives",
            "current_goal",
            "uncertainty",
            "capability_confidence",
            "instinct_activations",
            "last_reflection",
        }

        assert expected_fields.issubset(field_names)

    def test_valence_range(self) -> None:
        """Test valence accepts valid range [-1, 1]."""
        # Negative valence
        state_neg = MindState(valence=-1.0)
        assert state_neg.valence == -1.0

        # Positive valence
        state_pos = MindState(valence=1.0)
        assert state_pos.valence == 1.0

        # Neutral
        state_neutral = MindState(valence=0.0)
        assert state_neutral.valence == 0.0

    def test_arousal_range(self) -> None:
        """Test arousal accepts valid range [0, 1]."""
        state_low = MindState(arousal=0.0)
        assert state_low.arousal == 0.0

        state_high = MindState(arousal=1.0)
        assert state_high.arousal == 1.0

    def test_active_drives_list(self) -> None:
        """Test active drives as list."""
        state = MindState(active_drives=["curiosity", "achievement"])
        assert len(state.active_drives) == 2
        assert "curiosity" in state.active_drives

    def test_instinct_activations_dict(self) -> None:
        """Test instinct activations as dict."""
        state = MindState(
            instinct_activations={
                "prediction": 0.8,
                "threat": 0.2,
                "learning": 0.6,
            }
        )
        assert state.instinct_activations["prediction"] == 0.8


# =============================================================================
# UNIFIED MIND STATE TESTS
# =============================================================================


class TestUnifiedMindState:
    """Tests for get_unified_mind_state function."""

    def test_returns_mind_state(self) -> None:
        """Test function returns MindState."""
        state = get_unified_mind_state()
        assert isinstance(state, MindState)

    def test_handles_missing_subsystems(self) -> None:
        """Test graceful handling when subsystems unavailable."""
        # Should not raise even if subsystems not initialized
        state = get_unified_mind_state()
        assert state is not None

    def test_populates_cognitive_state(self) -> None:
        """Test cognitive state is populated if available."""
        state = get_unified_mind_state()
        # May be None if not initialized, but should not raise
        assert hasattr(state, "cognitive_state")


# =============================================================================
# COGNITIVE STATE TESTS
# =============================================================================


class TestCognitiveState:
    """Tests for CognitiveState."""

    def test_cognitive_state_init(self) -> None:
        """Test CognitiveState initialization with defaults."""
        state = CognitiveState()
        assert state.metacognition == 0.0
        assert state.metacognition_ece == 0.5
        assert state.temporal_coherence == 0.0
        assert state.consistency == 0.0
        assert state.evolution_rate == 0.0
        assert state.timestamp == 0.0
        assert state.agent_id == ""

    def test_cognitive_state_custom_init(self) -> None:
        """Test CognitiveState initialization with custom values."""
        state = CognitiveState(
            metacognition=0.8,
            temporal_coherence=0.7,
            consistency=0.9,
            evolution_rate=0.05,
            agent_id="test_agent",
        )
        assert state.metacognition == 0.8
        assert state.temporal_coherence == 0.7
        assert state.consistency == 0.9
        assert state.evolution_rate == 0.05
        assert state.agent_id == "test_agent"

    def test_to_dict(self) -> None:
        """Test CognitiveState.to_dict() conversion."""
        state = CognitiveState(
            metacognition=0.85,
            metacognition_ece=0.12,
            temporal_coherence=0.75,
            consistency=0.88,
            evolution_rate=0.03,
            timestamp=1234567890.0,
            agent_id="agent_42",
        )
        result = state.to_dict()

        assert isinstance(result, dict)
        assert result["metacognition"] == 0.85
        assert result["metacognition_ece"] == 0.12
        assert result["temporal_coherence"] == 0.75
        assert result["consistency"] == 0.88
        assert result["evolution_rate"] == 0.03
        assert result["timestamp"] == 1234567890.0
        assert result["agent_id"] == "agent_42"

    def test_get_overall_score(self) -> None:
        """Test CognitiveState.get_overall_score() computation."""
        # Test with all metrics at 1.0
        state = CognitiveState(
            metacognition=1.0, temporal_coherence=1.0, consistency=1.0, evolution_rate=1.0
        )
        score = state.get_overall_score()
        # 0.4*1.0 + 0.2*1.0 + 0.2*1.0 + 0.2*1.0 = 1.0
        assert score == 1.0

        # Test with mixed metrics
        state = CognitiveState(
            metacognition=0.8, temporal_coherence=0.6, consistency=0.9, evolution_rate=0.5
        )
        score = state.get_overall_score()
        expected = 0.4 * 0.8 + 0.2 * 0.6 + 0.2 * 0.9 + 0.2 * 0.5
        assert abs(score - expected) < 1e-6

    def test_get_overall_score_negative_evolution(self) -> None:
        """Test get_overall_score clamps negative evolution to 0."""
        state = CognitiveState(
            metacognition=0.8,
            temporal_coherence=0.6,
            consistency=0.7,
            evolution_rate=-0.5,  # Negative evolution
        )
        score = state.get_overall_score()
        # Should clamp evolution_rate to 0
        expected = 0.4 * 0.8 + 0.2 * 0.6 + 0.2 * 0.7 + 0.2 * 0.0
        assert abs(score - expected) < 1e-6

    def test_get_cognitive_state_requires_agent(self) -> None:
        """Test get_cognitive_state requires an agent argument."""

        # Create a mock agent with required attributes
        class MockAgent:
            def __init__(self) -> None:
                self.agent_id = "test_agent"
                self._prediction_confidences: list[float] = []
                self._prediction_outcomes: list[float] = []
                self._plan_history: list[dict[str, Any]] = []
                self._behavior_history: list[dict[str, Any]] = []
                self._fitness_history: list[float] = []

        agent = MockAgent()
        state = get_cognitive_state(agent)

        assert isinstance(state, CognitiveState)
        assert state.agent_id == "test_agent"
        assert state.timestamp > 0

    def test_get_snapshot(self) -> None:
        """Test getting cognitive state snapshot."""
        snapshot = get_cognitive_state_snapshot()

        assert isinstance(snapshot, dict)
        assert "version" in snapshot
        assert "timestamp" in snapshot
        assert "mode" in snapshot
        assert "facets" in snapshot
        assert "rationale" in snapshot
        assert "evidence" in snapshot


# =============================================================================
# COGNITIVE METRICS TESTS
# =============================================================================


class TestCognitiveMetrics:
    """Tests for cognitive metric computations."""

    def test_compute_metacognition_sufficient_data(self) -> None:
        """Test metacognition with sufficient data (10+ samples)."""
        # Perfect calibration: confidence matches outcomes
        predictions = [0.9] * 5 + [0.5] * 5 + [0.1] * 5
        outcomes = [1.0] * 5 + [0.5] * 5 + [0.0] * 5

        calibration_score, ece = compute_metacognition(predictions, outcomes)

        assert isinstance(calibration_score, float)
        assert isinstance(ece, float)
        assert 0.0 <= calibration_score <= 1.0
        assert 0.0 <= ece <= 1.0
        # Perfect calibration should have low ECE
        assert ece < 0.3

    def test_compute_metacognition_insufficient_data(self) -> None:
        """Test metacognition with insufficient data (<10 samples)."""
        predictions = [0.8, 0.6, 0.9]
        outcomes = [1.0, 0.0, 1.0]

        calibration_score, ece = compute_metacognition(predictions, outcomes)

        # Should return default values
        assert calibration_score == 0.5
        assert ece == 0.5

    def test_compute_metacognition_overconfident(self) -> None:
        """Test metacognition detects overconfidence."""
        # High confidence but low success rate
        predictions = [0.9] * 20
        outcomes = [0.0] * 15 + [1.0] * 5  # Only 25% success

        calibration_score, ece = compute_metacognition(predictions, outcomes)

        # Should have high ECE due to overconfidence
        assert ece > 0.3
        assert calibration_score < 0.7

    def test_compute_metacognition_edge_case_empty(self) -> None:
        """Test metacognition with empty lists."""
        calibration_score, ece = compute_metacognition([], [])
        assert calibration_score == 0.5
        assert ece == 0.5

    def test_compute_temporal_coherence_sufficient_data(self) -> None:
        """Test temporal coherence with sufficient plan history."""
        plans = [
            {"action": "plan", "timestamp": 1.0},
            {"action": "plan", "timestamp": 2.0},
            {"action": "plan", "timestamp": 3.0},
            {"action": "execute", "timestamp": 4.0},
            {"action": "plan", "timestamp": 5.0},
        ]

        coherence = compute_temporal_coherence(plans)

        assert isinstance(coherence, float)
        assert 0.0 <= coherence <= 1.0
        # 3 "plan" and 1 "execute" = 2 unique actions out of 5
        # coherence = 1 - (2/5) = 0.6
        assert abs(coherence - 0.6) < 0.01

    def test_compute_temporal_coherence_perfect_consistency(self) -> None:
        """Test temporal coherence with perfectly consistent actions."""
        plans = [{"action": "plan", "timestamp": float(i)} for i in range(10)]

        coherence = compute_temporal_coherence(plans)

        # All same action = 1 unique / 10 total = 1 - 0.1 = 0.9
        assert abs(coherence - 0.9) < 0.01

    def test_compute_temporal_coherence_insufficient_data(self) -> None:
        """Test temporal coherence with insufficient data."""
        plans = [{"action": "plan", "timestamp": 1.0}]

        coherence = compute_temporal_coherence(plans)

        # Less than 2 plans should return 0.0
        assert coherence == 0.0

    def test_compute_temporal_coherence_empty(self) -> None:
        """Test temporal coherence with empty plan list."""
        coherence = compute_temporal_coherence([])
        assert coherence == 0.0

    def test_compute_consistency_sufficient_data(self) -> None:
        """Test consistency with sufficient behavior history."""
        # Create behaviors with consistent confidence
        behaviors = [{"confidence": 0.8 + i * 0.01} for i in range(20)]

        consistency = compute_consistency(behaviors)

        assert isinstance(consistency, float)
        assert 0.0 <= consistency <= 1.0
        # Low variance should mean high consistency
        assert consistency > 0.9

    def test_compute_consistency_high_variance(self) -> None:
        """Test consistency detects high variance behaviors."""
        # Alternating high and low confidence
        behaviors = [{"confidence": 0.9 if i % 2 == 0 else 0.1} for i in range(20)]

        consistency = compute_consistency(behaviors)

        # High variance should mean low consistency
        assert consistency < 0.5

    def test_compute_consistency_insufficient_data(self) -> None:
        """Test consistency with insufficient data."""
        behaviors = [{"confidence": 0.8}, {"confidence": 0.7}]

        consistency = compute_consistency(behaviors)

        # Less than 5 behaviors should return 0.0
        assert consistency == 0.0

    def test_compute_consistency_empty(self) -> None:
        """Test consistency with empty behavior list."""
        consistency = compute_consistency([])
        assert consistency == 0.0

    def test_compute_evolution_rate_positive_growth(self) -> None:
        """Test evolution rate detects positive fitness growth."""
        # Steadily increasing fitness
        fitness_history = [0.5 + i * 0.01 for i in range(50)]

        evolution_rate = compute_evolution_rate(fitness_history)

        assert isinstance(evolution_rate, float)
        # Should detect positive trend
        assert evolution_rate > 0.0

    def test_compute_evolution_rate_negative_growth(self) -> None:
        """Test evolution rate detects negative fitness trend."""
        # Steadily decreasing fitness
        fitness_history = [1.0 - i * 0.01 for i in range(50)]

        evolution_rate = compute_evolution_rate(fitness_history)

        # Should detect negative trend
        assert evolution_rate < 0.0

    def test_compute_evolution_rate_stable(self) -> None:
        """Test evolution rate with stable fitness."""
        fitness_history = [0.7] * 50

        evolution_rate = compute_evolution_rate(fitness_history)

        # Should be near zero for stable fitness
        assert abs(evolution_rate) < 0.01

    def test_compute_evolution_rate_insufficient_data(self) -> None:
        """Test evolution rate with insufficient data."""
        fitness_history = [0.5, 0.6, 0.7]

        evolution_rate = compute_evolution_rate(fitness_history)

        # Less than 10 samples should return 0.0
        assert evolution_rate == 0.0

    def test_compute_evolution_rate_empty(self) -> None:
        """Test evolution rate with empty fitness history."""
        evolution_rate = compute_evolution_rate([])
        assert evolution_rate == 0.0


# =============================================================================
# LAYER TESTS
# =============================================================================


class TestCognitiveLayers:
    """Tests for cognitive layer imports and basic functionality."""

    def test_all_layers_import(self) -> None:
        """Test all cognitive layer classes can be imported."""
        from kagami.core.cognition import (
            PhilosophicalLayer,
            ScientificLayer,
            RecursiveFeedbackCoordinator,
        )
        from inspect import isclass

        # Verify all are classes with constructors
        assert isclass(PhilosophicalLayer)
        assert hasattr(PhilosophicalLayer, "__init__")

        assert isclass(ScientificLayer)
        assert hasattr(ScientificLayer, "__init__")

        assert isclass(RecursiveFeedbackCoordinator)
        assert hasattr(RecursiveFeedbackCoordinator, "__init__")


# =============================================================================
# MOTIVATION IMPORTS TESTS
# =============================================================================


class TestMotivationImports:
    """Tests for motivation system imports and basic functionality."""

    def test_all_motivation_imports(self) -> None:
        """Test all motivation classes can be imported."""
        from kagami.core.cognition import Drive, IntrinsicMotivationSystem, GoalHierarchyManager
        from inspect import isclass

        # Verify Drive is a class/dataclass
        assert isclass(Drive)
        assert hasattr(Drive, "__annotations__") or hasattr(Drive, "__init__")

        # Verify IntrinsicMotivationSystem
        assert isclass(IntrinsicMotivationSystem)
        assert hasattr(IntrinsicMotivationSystem, "__init__")

        # Verify GoalHierarchyManager
        assert isclass(GoalHierarchyManager)
        assert hasattr(GoalHierarchyManager, "__init__")


# =============================================================================
# METACOGNITION / CONFIDENCE CALIBRATION TESTS
# =============================================================================


class TestMetacognitionImports:
    """Tests for metacognition imports.

    NOTE: BayesianUncertaintyEstimator and CapabilityTracker were consolidated
    in December 2025. Uncertainty estimation now uses kagami.core.learning.confidence_calibration.
    """

    def test_confidence_calibrator_import(self) -> None:
        """Test ConfidenceCalibrator import from learning module."""
        from kagami.core.learning.confidence_calibration import ConfidenceCalibrator
        from inspect import isclass

        assert isclass(ConfidenceCalibrator)
        assert hasattr(ConfidenceCalibrator, "__init__")

    def test_confidence_calibrator_functionality(self) -> None:
        """Test ConfidenceCalibrator basic functionality."""
        from kagami.core.learning.confidence_calibration import ConfidenceCalibrator

        calibrator = ConfidenceCalibrator(buckets=10)

        # Observe some predictions
        calibrator.observe(0.9, True)  # High confidence, correct
        calibrator.observe(0.8, True)  # High confidence, correct
        calibrator.observe(0.5, False)  # Low confidence, incorrect

        # Get reliability curve
        curve = calibrator.get_reliability_curve()
        assert len(curve) > 0

        # Calibrate a confidence score
        calibrated = calibrator.calibrate(0.85)
        assert 0.0 <= calibrated <= 1.0


# =============================================================================
# INSTINCTS IMPORTS TESTS
# =============================================================================


class TestInstinctsImports:
    """Tests for instincts imports and basic functionality."""

    def test_all_instincts_import(self) -> None:
        """Test all instinct classes can be imported."""
        from kagami.core.cognition import (
            PredictionInstinct,
            ThreatInstinct,
            LearningInstinct,
            EthicalInstinct,
        )
        from inspect import isclass

        # Verify all instinct classes
        assert isclass(PredictionInstinct)
        assert hasattr(PredictionInstinct, "__init__")

        assert isclass(ThreatInstinct)
        assert hasattr(ThreatInstinct, "__init__")

        assert isclass(LearningInstinct)
        assert hasattr(LearningInstinct, "__init__")

        assert isclass(EthicalInstinct)
        assert hasattr(EthicalInstinct, "__init__")


# =============================================================================
# INTROSPECTION IMPORTS TESTS
# =============================================================================


class TestIntrospectionImports:
    """Tests for introspection imports and basic functionality."""

    def test_introspection_imports(self) -> None:
        """Test introspection classes and functions can be imported."""
        from kagami.core.cognition import IntrospectionEngine, get_introspection_engine
        from inspect import isclass

        # Verify IntrospectionEngine class
        assert isclass(IntrospectionEngine)
        assert hasattr(IntrospectionEngine, "__init__")

        # Test get_introspection_engine function
        engine = get_introspection_engine()
        # Should return None or an object without crashing
        if engine is not None:
            assert hasattr(engine, "__class__")


# =============================================================================
# AFFECTIVE IMPORTS TESTS
# =============================================================================


class TestAffectiveImports:
    """Tests for affective imports and basic functionality."""

    def test_all_affective_imports(self) -> None:
        """Test all affective classes can be imported."""
        from kagami.core.cognition import AffectiveLayer, ThreatAssessment, ValenceEvaluator
        from inspect import isclass

        # Verify all affective classes
        assert isclass(AffectiveLayer)
        assert hasattr(AffectiveLayer, "__init__")

        assert isclass(ThreatAssessment)
        assert hasattr(ThreatAssessment, "__init__")

        assert isclass(ValenceEvaluator)
        assert hasattr(ValenceEvaluator, "__init__")
