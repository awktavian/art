"""Tests for LLM Safety Model Integration with Control Barrier Functions.

Tests the bridge between open-weight LLM safety classifiers and K OS CBF system.

CREATED: December 15, 2025
PURPOSE: Increase coverage for llm_safety_integration.py (currently 0%)
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch

from kagami.core.safety.llm_safety_integration import (
    RiskCategory,
    SafetyClassification,
    SafetyClassifier,
)


class TestRiskCategory:
    """Test RiskCategory enum."""

    def test_risk_category_values(self):
        """Test that risk categories have correct string values."""
        assert RiskCategory.VIOLENCE.value == "violence"
        assert RiskCategory.SELF_HARM.value == "self_harm"
        assert RiskCategory.HATE_SPEECH.value == "hate_speech"
        assert RiskCategory.SEXUAL_CONTENT.value == "sexual_content"

    def test_all_categories_unique(self):
        """Test that all category values are unique."""
        values = [cat.value for cat in RiskCategory]
        assert len(values) == len(set(values))


class TestSafetyClassification:
    """Test SafetyClassification dataclass."""

    def test_creation_defaults(self):
        """Test SafetyClassification creation with defaults."""
        classification = SafetyClassification(
            is_safe=True,
            risk_scores={},
        )
        assert classification.is_safe is True
        assert classification.confidence == 1.0
        assert classification.reasoning is None
        assert classification.raw_output is None

    def test_creation_with_scores(self):
        """Test SafetyClassification with risk scores."""
        risk_scores = {
            RiskCategory.VIOLENCE: 0.1,
            RiskCategory.HATE_SPEECH: 0.05,
        }
        classification = SafetyClassification(
            is_safe=True,
            risk_scores=risk_scores,
            confidence=0.95,
        )
        assert classification.risk_scores == risk_scores
        assert classification.confidence == 0.95

    def test_max_risk_empty(self):
        """Test max_risk with no scores returns default."""
        classification = SafetyClassification(
            is_safe=True,
            risk_scores={},
        )
        cat, score = classification.max_risk()
        assert cat == RiskCategory.VIOLENCE
        assert score == 0.0

    def test_max_risk_single(self):
        """Test max_risk with single category."""
        classification = SafetyClassification(
            is_safe=False,
            risk_scores={RiskCategory.VIOLENCE: 0.8},
        )
        cat, score = classification.max_risk()
        assert cat == RiskCategory.VIOLENCE
        assert score == 0.8

    def test_max_risk_multiple(self):
        """Test max_risk finds highest among multiple categories."""
        classification = SafetyClassification(
            is_safe=False,
            risk_scores={
                RiskCategory.VIOLENCE: 0.3,
                RiskCategory.HATE_SPEECH: 0.7,
                RiskCategory.SEXUAL_CONTENT: 0.2,
            },
        )
        cat, score = classification.max_risk()
        assert cat == RiskCategory.HATE_SPEECH
        assert score == 0.7

    def test_total_risk_empty(self):
        """Test total_risk with no scores returns 0."""
        classification = SafetyClassification(
            is_safe=True,
            risk_scores={},
        )
        assert classification.total_risk() == 0.0

    def test_total_risk_average(self):
        """Test total_risk computes average of scores."""
        classification = SafetyClassification(
            is_safe=False,
            risk_scores={
                RiskCategory.VIOLENCE: 0.2,
                RiskCategory.HATE_SPEECH: 0.4,
                RiskCategory.SEXUAL_CONTENT: 0.6,
            },
        )
        expected = (0.2 + 0.4 + 0.6) / 3
        assert abs(classification.total_risk() - expected) < 1e-6

    def test_to_cbf_state_4d(self):
        """Test conversion to 4D CBF state."""
        classification = SafetyClassification(
            is_safe=False,
            risk_scores={
                RiskCategory.VIOLENCE: 0.7,
                RiskCategory.SELF_HARM: 0.3,
                RiskCategory.DANGEROUS_ACTIVITIES: 0.5,
                RiskCategory.HATE_SPEECH: 0.2,
            },
            confidence=0.9,
        )
        state = classification.to_cbf_state(state_dim=4)

        assert state.shape == (4,)
        assert state.dtype == torch.float32

        # threat = max(violence, self_harm, dangerous_activities)
        assert state[0].item() == pytest.approx(0.7, abs=1e-6)

        # uncertainty = 1 - confidence
        assert state[1].item() == pytest.approx(0.1, abs=1e-6)

        # complexity proportional to number of high-risk categories
        # predictive_risk = average of all scores
        assert state[3].item() > 0

    def test_to_cbf_state_high_dim(self):
        """Test conversion to higher-dimensional state."""
        classification = SafetyClassification(
            is_safe=False,
            risk_scores={
                RiskCategory.VIOLENCE: 0.7,
                RiskCategory.HATE_SPEECH: 0.3,
            },
        )
        state = classification.to_cbf_state(state_dim=16)

        assert state.shape == (16,)
        assert state.dtype == torch.float32

        # First few entries should match risk categories in order
        assert state[0].item() == pytest.approx(0.7, abs=1e-6)  # VIOLENCE

    def test_to_cbf_state_zero_confidence(self):
        """Test edge case: zero confidence produces high uncertainty."""
        classification = SafetyClassification(
            is_safe=True,
            risk_scores={},
            confidence=0.0,
        )
        state = classification.to_cbf_state(state_dim=4)

        # uncertainty = 1 - confidence = 1 - 0 = 1
        assert state[1].item() == pytest.approx(1.0, abs=1e-6)


class MockSafetyClassifier(SafetyClassifier):
    """Mock safety classifier for testing abstract interface."""

    def __init__(self):
        super().__init__()
        self._calls_classify = 0
        self._calls_classify_batch = 0

    def classify(
        self,
        text: str,
        context: str | None = None,
    ) -> SafetyClassification:
        """Mock classify method."""
        self._calls_classify += 1
        return SafetyClassification(
            is_safe=True,
            risk_scores={RiskCategory.VIOLENCE: 0.1},
        )

    def classify_batch(
        self,
        texts: list[str],
        contexts: list[str] | None = None,
    ) -> list[SafetyClassification]:
        """Mock batch classify method."""
        self._calls_classify_batch += 1
        return [
            self.classify(text, ctx)
            for text, ctx in zip(texts, contexts or [None] * len(texts), strict=False)
        ]


class TestSafetyClassifier:
    """Test SafetyClassifier abstract base class."""

    def test_classifier_instantiation(self):
        """Test that mock classifier can be instantiated."""
        classifier = MockSafetyClassifier()
        assert isinstance(classifier, SafetyClassifier)

    def test_classify_method(self):
        """Test classify method works."""
        classifier = MockSafetyClassifier()
        result = classifier.classify("Hello world")

        assert isinstance(result, SafetyClassification)
        assert result.is_safe is True
        assert classifier._calls_classify == 1

    def test_classify_batch_method(self):
        """Test classify_batch method works."""
        classifier = MockSafetyClassifier()
        results = classifier.classify_batch(["Hello", "World"])

        assert len(results) == 2
        assert all(isinstance(r, SafetyClassification) for r in results)
        assert classifier._calls_classify_batch == 1

    def test_forward_creates_head(self):
        """Test forward creates embedding head lazily."""
        classifier = MockSafetyClassifier()
        embeddings = torch.randn(2, 128)  # [batch=2, dim=128]

        scores = classifier.forward(embeddings)

        assert scores.shape == (2, len(RiskCategory))
        assert hasattr(classifier, "_embedding_head")

    def test_forward_validates_shape(self):
        """Test forward rejects invalid input shapes."""
        classifier = MockSafetyClassifier()
        embeddings = torch.randn(2, 3, 128)  # Wrong: 3D tensor

        with pytest.raises(ValueError, match="Expected text_embeddings shape"):
            classifier.forward(embeddings)

    def test_forward_rebuilds_head_on_dim_change(self):
        """Test forward rebuilds head when embedding dimension changes."""
        classifier = MockSafetyClassifier()

        # First call with dim=64
        emb1 = torch.randn(2, 64)
        scores1 = classifier.forward(emb1)
        head1 = classifier._embedding_head

        # Second call with dim=128 (should rebuild)
        emb2 = torch.randn(2, 128)
        scores2 = classifier.forward(emb2)
        head2 = classifier._embedding_head

        # Head should have been rebuilt
        assert head1 is not head2
        assert scores1.shape == (2, len(RiskCategory))
        assert scores2.shape == (2, len(RiskCategory))

    def test_forward_output_range(self):
        """Test forward outputs are in [0, 1] via sigmoid."""
        classifier = MockSafetyClassifier()
        embeddings = torch.randn(4, 256)

        scores = classifier.forward(embeddings)

        assert torch.all(scores >= 0)
        assert torch.all(scores <= 1)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_risk_scores_safe(self):
        """Test that empty risk scores are handled safely."""
        classification = SafetyClassification(
            is_safe=True,
            risk_scores={},
        )

        # All methods should handle empty scores gracefully
        assert classification.max_risk() == (RiskCategory.VIOLENCE, 0.0)
        assert classification.total_risk() == 0.0
        assert classification.to_cbf_state(4).shape == (4,)

    def test_high_confidence_low_uncertainty(self):
        """Test high confidence produces low uncertainty."""
        classification = SafetyClassification(
            is_safe=True,
            risk_scores={},
            confidence=0.99,
        )
        state = classification.to_cbf_state(4)

        # uncertainty = 1 - 0.99 = 0.01
        assert state[1].item() < 0.1

    def test_all_categories_in_state(self):
        """Test that state can hold all risk categories."""
        num_categories = len(RiskCategory)
        classification = SafetyClassification(
            is_safe=False,
            risk_scores=dict.fromkeys(RiskCategory, 0.5),
        )
        state = classification.to_cbf_state(state_dim=num_categories)

        assert state.shape[0] >= num_categories
        assert torch.all(state >= 0)
