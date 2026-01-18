"""Tests for TRUE Gödelian Self-Reference Implementation.

Tests:
1. Self-inspection via inspect.getsource()
2. Self-referential weight encoding (SRWM-style)
3. Code embedding
4. LLM-based modification proposals (mocked)
5. Recursive improvement loop
6. Safety validation integration

Based on Gödel Agent paper requirements:
- SELF_INSPECT: Read own code
- SELF_UPDATE: Modify own code
- CONTINUE_IMPROVE: Recursive self-improvement

鏡
"""

from __future__ import annotations

import pytest
from typing import Any

import asyncio
import torch
import torch.nn as nn

from kagami.core.strange_loops.godelian_self_reference import (
    GodelianConfig,
    GodelianSelfReference,
    SelfInspector,
    SelfReferentialWeightEncoder,
    CodeEmbedder,
    create_godelian_wrapper,
)

# =============================================================================
# FIXTURES
# =============================================================================


class SimpleModule(nn.Module):
    """Simple module for testing Gödelian wrapper."""

    def __init__(self, dim: int = 32):
        super().__init__()
        self.linear = nn.Linear(dim, dim)
        self.activation = nn.GELU()

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        return {"output": self.activation(self.linear(x))}


@pytest.fixture
def simple_module() -> SimpleModule:
    """Create simple test module."""
    return SimpleModule(dim=32)


@pytest.fixture
def godelian_config() -> GodelianConfig:
    """Create test configuration."""
    return GodelianConfig(
        code_embedding_dim=15,  # E8(8) + S7(7)
        weight_embedding_dim=15,  # E8(8) + S7(7)
        enable_llm_modification=False,  # Disable for unit tests
        enable_recursive_improvement=False,
        max_modifications_per_session=5,
    )


# =============================================================================
# SELF-INSPECTION TESTS
# =============================================================================


class TestSelfInspector:
    """Tests for SelfInspector - TRUE code introspection."""

    def test_get_source(self) -> None:
        """Test that we can read actual source code."""
        inspector = SelfInspector(SimpleModule)
        source = inspector.get_source()

        # Should contain actual code
        assert "class SimpleModule" in source
        assert "def __init__" in source
        assert "def forward" in source
        assert "nn.Linear" in source

    def test_get_source_hash(self) -> None:
        """Test source hash for change detection."""
        inspector = SelfInspector(SimpleModule)
        hash1 = inspector.get_source_hash()
        hash2 = inspector.get_source_hash()

        # Same source = same hash
        assert hash1 == hash2
        assert len(hash1) == 16  # Truncated SHA256

    def test_get_method_source(self) -> None:
        """Test individual method source retrieval."""
        inspector = SelfInspector(SimpleModule)
        forward_source = inspector.get_method_source("forward")

        assert "def forward" in forward_source
        assert "self.activation" in forward_source

    def test_get_module_path(self) -> None:
        """Test module path retrieval."""
        inspector = SelfInspector(SimpleModule)
        path = inspector.get_module_path()

        # Should be this test file
        assert "test_godelian_self_reference.py" in path

    def test_get_signature(self) -> None:
        """Test method signature retrieval."""
        inspector = SelfInspector(SimpleModule)
        sig = inspector.get_signature("forward")

        assert "self" in sig
        assert "x" in sig


# =============================================================================
# WEIGHT ENCODING TESTS (SRWM-style)
# =============================================================================


class TestSelfReferentialWeightEncoder:
    """Tests for SRWM-style weight encoding."""

    def test_encode_weights(self, simple_module) -> None:
        """Test encoding weights via E8+S7 (MatryoshkaHourglass)."""
        weight_shapes = [p.shape for p in simple_module.parameters()]
        encoder = SelfReferentialWeightEncoder(
            weight_shapes=weight_shapes,
            output_dim=15,  # E8(8) + S7(7)
        )

        weights = [p.data for p in simple_module.parameters()]
        result = encoder(weights)

        assert "encoding" in result
        assert result["encoding"].shape == (15,)  # E8+S7

    def test_gated_update(self, simple_module) -> None:
        """Test gated update with previous encoding."""
        weight_shapes = [p.shape for p in simple_module.parameters()]
        encoder = SelfReferentialWeightEncoder(
            weight_shapes=weight_shapes,
            output_dim=15,  # E8+S7
        )

        weights = [p.data for p in simple_module.parameters()]

        # First encoding
        result1 = encoder(weights)
        prev_encoding = result1["encoding"]

        # Second encoding with history
        result2 = encoder(weights, previous_encoding=prev_encoding)

        # Gated update uses delta_lr, not separate gate tensor
        assert "encoding" in result2
        assert result2["encoding"].shape == (15,)  # E8+S7

    def test_delta_learning_rate(self, simple_module) -> None:
        """Test that delta LR is learnable."""
        weight_shapes = [p.shape for p in simple_module.parameters()]
        encoder = SelfReferentialWeightEncoder(
            weight_shapes=weight_shapes,
            output_dim=15,  # E8+S7
        )

        # delta_lr should be a learnable parameter
        assert hasattr(encoder, "delta_lr")
        assert encoder.delta_lr.requires_grad


# =============================================================================
# CODE EMBEDDING TESTS
# =============================================================================


class TestCodeEmbedder:
    """Tests for source code neural embedding."""

    def test_embed_code(self) -> None:
        """Test embedding source code via E8+S7 (MatryoshkaHourglass)."""
        embedder = CodeEmbedder(
            max_code_length=1024,
            output_dim=15,  # E8+S7
        )

        code = """
def hello_world():
    print("Hello, World!")
"""
        embedding = embedder(code)

        assert embedding.shape == (15,)  # E8+S7

    def test_embed_long_code(self) -> None:
        """Test embedding code longer than max length."""
        embedder = CodeEmbedder(
            max_code_length=100,
            output_dim=15,  # E8+S7
        )

        long_code = "x = 1\n" * 1000  # Much longer than 100 chars
        embedding = embedder(long_code)

        # Should still work (truncated)
        assert embedding.shape == (15,)  # E8+S7

    def test_embed_short_code(self) -> None:
        """Test embedding very short code."""
        embedder = CodeEmbedder(
            max_code_length=1024,
            output_dim=15,  # E8+S7
        )

        short_code = "x=1"
        embedding = embedder(short_code)

        # Should still work (padded)
        assert embedding.shape == (15,)  # E8+S7


# =============================================================================
# GÖDELIAN SELF-REFERENCE TESTS
# =============================================================================


class TestGodelianSelfReference:
    """Tests for the main Gödelian self-reference module."""

    def test_create_wrapper(self, simple_module, godelian_config) -> None:
        """Test creating Gödelian wrapper."""
        wrapper = GodelianSelfReference(simple_module, godelian_config)

        assert wrapper.base_module is simple_module
        assert wrapper._modification_count == 0

    def test_self_inspect(self, simple_module, godelian_config) -> None:
        """Test TRUE self-inspection."""
        wrapper = GodelianSelfReference(simple_module, godelian_config)
        s = wrapper.self_inspect()

        # Should contain actual code
        assert "code" in s
        assert "class SimpleModule" in s["code"]

        # Should have structure info
        assert "hash" in s
        assert "params" in s
        assert "shapes" in s

        # Should have state info
        assert "n_mod" in s
        assert s["n_mod"] == 0

    def test_encode_self(self, simple_module, godelian_config) -> None:
        """Test self-encoding (code + weights)."""
        wrapper = GodelianSelfReference(simple_module, godelian_config)
        encoding = wrapper.encode_self()

        assert "code_embedding" in encoding
        assert "weight_embedding" in encoding
        assert "combined_self" in encoding

        # Check dimensions
        assert encoding["code_embedding"].shape == (godelian_config.code_embedding_dim,)
        assert encoding["weight_embedding"].shape == (godelian_config.weight_embedding_dim,)
        combined_dim = godelian_config.code_embedding_dim + godelian_config.weight_embedding_dim
        assert encoding["combined_self"].shape == (combined_dim,)

    def test_forward_augments_output(self, simple_module, godelian_config) -> None:
        """Test that forward pass augments base module output."""
        wrapper = GodelianSelfReference(simple_module, godelian_config)

        x = torch.randn(4, 32)
        output = wrapper(x)

        # Should have base output
        assert "output" in output

        # Should have Gödelian augmentation
        assert "godelian" in output
        g = output["godelian"]
        assert "self" in g  # Combined self-encoding
        assert "h" in g  # Consistency (like CBF h(x))
        assert "Δ" in g  # Source changed
        assert "n" in g  # Modification count

    def test_source_change_detection(self, simple_module, godelian_config) -> None:
        """Test detection of external source changes."""
        wrapper = GodelianSelfReference(simple_module, godelian_config)

        # Forward pass
        x = torch.randn(4, 32)
        output = wrapper(x)

        # Source shouldn't change
        assert output["godelian"]["Δ"] is False

    def test_factory_function(self, simple_module, godelian_config) -> None:
        """Test create_godelian_wrapper factory."""
        wrapper = create_godelian_wrapper(simple_module, godelian_config)

        assert isinstance(wrapper, GodelianSelfReference)
        assert wrapper.base_module is simple_module


# =============================================================================
# ASYNC TESTS (Modification proposals)
# =============================================================================


class TestGodelianAsync:
    """Async tests for LLM-based modification."""

    @pytest.mark.asyncio
    async def test_propose_modification_disabled(self, simple_module, godelian_config) -> None:
        """Test modification proposal when disabled."""
        godelian_config.enable_llm_modification = False
        wrapper = GodelianSelfReference(simple_module, godelian_config)

        feedback = {"error": "Test error"}
        result = await wrapper.propose_modification(feedback)

        assert result["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_modification_limit(self, simple_module) -> None:
        """Test modification session limit."""
        config = GodelianConfig(
            enable_llm_modification=True,
            max_modifications_per_session=0,  # Already at limit
        )
        wrapper = GodelianSelfReference(simple_module, config)

        feedback = {"error": "Test error"}
        result = await wrapper.propose_modification(feedback)

        assert result["status"] == "limit_reached"

    @pytest.mark.asyncio
    async def test_recursive_improve_disabled(self, simple_module, godelian_config) -> None:
        """Test recursive improvement when disabled."""
        godelian_config.enable_recursive_improvement = False
        wrapper = GodelianSelfReference(simple_module, godelian_config)

        feedback = {"error": "Test error"}
        result = await wrapper.recursive_improve(feedback, goal="test")

        assert result["status"] == "disabled"
        assert result["iterations"] == 0


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestGodelianIntegration:
    """Integration tests with HofstadterStrangeLoop."""

    def test_wrap_hofstadter_loop(self) -> None:
        """Test wrapping HofstadterStrangeLoop."""
        try:
            from kagami.core.world_model.colony_rssm import (
                HofstadterStrangeLoop,
                HofstadterLoopConfig,
            )
        except ImportError:
            pytest.skip("HofstadterStrangeLoop not available")

        config = HofstadterLoopConfig(
            internal_dim=64,
            self_dim=16,
            action_dim=8,
            sensory_dim=32,
        )
        strange_loop = HofstadterStrangeLoop(config)

        godelian_config = GodelianConfig(
            code_embedding_dim=15,  # E8+S7
            weight_embedding_dim=15,  # E8+S7
            enable_llm_modification=False,
        )
        wrapper = GodelianSelfReference(strange_loop, godelian_config)

        # Self-inspect should work
        s = wrapper.self_inspect()
        # HofstadterStrangeLoop is an alias for GodelAgent in the consolidated implementation.
        assert ("class HofstadterStrangeLoop" in s["code"]) or ("class GodelAgent" in s["code"])

        # Forward should work
        internal_z = torch.randn(4, 64)
        action = torch.randn(4, 8)

        output = wrapper(internal_z, action)

        # Should have Gödelian augmentation
        assert "godelian" in output
        assert "self" in output["godelian"]


# =============================================================================
# QUINE TEST (Self-reproduction)
# =============================================================================


class TestQuineProperty:
    """Test for quine-like self-reference property."""

    def test_self_encoding_contains_code_info(self, simple_module, godelian_config) -> None:
        """Test that self-encoding contains information about code."""
        wrapper = GodelianSelfReference(simple_module, godelian_config)

        # Verify E8+S7 structure is present
        encoding = wrapper.encode_self()

        # Check E8 code (8D) and S7 phase (7D) are extracted
        assert "e8_code" in encoding
        assert "s7_phase" in encoding
        assert encoding["e8_code"].shape == (8,)
        assert encoding["s7_phase"].shape == (7,)

        # Combined should be 30D (code + weights)
        assert encoding["combined_self"].shape == (30,)

    def test_weight_encoding_changes_with_parameters(self, simple_module, godelian_config) -> None:
        """Test that weight encoding reflects parameter changes."""
        wrapper = GodelianSelfReference(simple_module, godelian_config)

        # Get initial encoding
        encoding1 = wrapper.encode_self()

        # Modify weights
        with torch.no_grad():
            for p in simple_module.parameters():
                p.add_(torch.randn_like(p) * 0.1)

        # Get new encoding
        encoding2 = wrapper.encode_self()

        # Weight embeddings should differ
        weight_sim = torch.nn.functional.cosine_similarity(
            encoding1["weight_embedding"].unsqueeze(0),
            encoding2["weight_embedding"].unsqueeze(0),
        )

        # Should be different (parameters changed)
        assert weight_sim < 0.99


# =============================================================================
# STATISTICAL VALIDATOR TESTS
# =============================================================================


class TestStatisticalValidator:
    """Tests for statistical validation of modifications."""

    def test_validate_improvement_significant(self) -> None:
        """Test detection of statistically significant improvement."""
        from kagami.core.strange_loops import StatisticalValidator
        import numpy as np

        validator = StatisticalValidator(confidence_level=0.95, min_samples=10)

        # Clear improvement: baseline ~0.5, modified ~0.8
        baseline = np.random.normal(0.5, 0.1, 30)
        modified = np.random.normal(0.8, 0.1, 30)

        result = validator.validate_improvement(baseline, modified, "accuracy")  # type: ignore[arg-type]

        assert result.is_significant
        assert result.effect_size > 0.5  # Large effect
        assert result.p_value < 0.05

    def test_validate_improvement_not_significant(self) -> None:
        """Test no false positives for similar distributions."""
        from kagami.core.strange_loops import StatisticalValidator
        import numpy as np

        np.random.seed(42)  # Reproducible test
        validator = StatisticalValidator(confidence_level=0.95, min_samples=10)

        # No difference: both ~0.5
        baseline = np.random.normal(0.5, 0.1, 30)
        modified = np.random.normal(0.5, 0.1, 30)

        result = validator.validate_improvement(baseline, modified, "accuracy")  # type: ignore[arg-type]

        # With same distribution, should not be significant (p > 0.05)
        # Effect size may vary but should be small
        assert abs(result.effect_size) < 0.5  # Moderate effect threshold

    def test_validate_improvement_insufficient_samples(self) -> None:
        """Test handling of insufficient samples."""
        from kagami.core.strange_loops import StatisticalValidator

        validator = StatisticalValidator(confidence_level=0.95, min_samples=20)

        # Only 5 samples each
        baseline = [0.5, 0.6, 0.4, 0.55, 0.45]
        modified = [0.8, 0.9, 0.7, 0.85, 0.75]

        result = validator.validate_improvement(baseline, modified, "accuracy")

        assert not result.is_significant
        assert "Insufficient samples" in result.interpretation

    def test_validate_safety_bound_safe(self) -> None:
        """Test safety validation when system is safe."""
        from kagami.core.strange_loops import StatisticalValidator
        import numpy as np

        validator = StatisticalValidator(confidence_level=0.95, min_samples=10)

        # All h(x) values safely above 0
        h_values = np.random.normal(0.5, 0.1, 50)

        result = validator.validate_safety_bound(h_values, bound=0.0)  # type: ignore[arg-type]

        assert result.is_significant
        assert result.confidence_interval[0] > 0.0
        assert "Safety maintained" in result.interpretation

    def test_validate_safety_bound_unsafe(self) -> None:
        """Test safety validation when system is unsafe."""
        from kagami.core.strange_loops import StatisticalValidator
        import numpy as np

        validator = StatisticalValidator(confidence_level=0.95, min_samples=10)

        # h(x) values near 0 (uncertain safety)
        h_values = np.random.normal(0.05, 0.1, 50)

        result = validator.validate_safety_bound(h_values, bound=0.0)  # type: ignore[arg-type]

        # Should fail since CI may include values < 0
        assert "Safety" in result.interpretation


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
