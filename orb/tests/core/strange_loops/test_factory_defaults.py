"""Tests for factory functions with default constructors.

Verifies that modules can be constructed without required arguments
using factory functions with sensible defaults.

This addresses gaps identified in usability audit (December 2025).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import torch
import torch.nn as nn

from kagami.core.strange_loops.godelian_self_reference import (
    GodelianSelfReference,
    GodelianConfig,
    create_godelian_self_reference,
)
from kagami.core.world_model.rssm_components import (
    HofstadterStrangeLoop,
    create_hofstadter_strange_loop,
)
from kagami.core.config.unified_config import HofstadterLoopConfig


class TestGodelianFactoryDefaults:
    """Test GodelianSelfReference factory with defaults."""

    def test_create_without_args(self):
        """Test creating GodelianSelfReference without any arguments."""
        godelian = create_godelian_self_reference()

        assert isinstance(godelian, GodelianSelfReference)
        assert isinstance(godelian.base_module, nn.Identity)
        assert isinstance(godelian.config, GodelianConfig)

    def test_create_with_custom_module(self):
        """Test creating with custom base module."""
        custom_module = nn.Linear(32, 32)
        godelian = create_godelian_self_reference(base_module=custom_module)

        assert isinstance(godelian, GodelianSelfReference)
        assert godelian.base_module is custom_module
        assert isinstance(godelian.config, GodelianConfig)

    def test_create_with_custom_config(self):
        """Test creating with custom config."""
        config = GodelianConfig(
            e8_dim=8,
            s7_dim=7,
            enable_llm_modification=False,
        )
        godelian = create_godelian_self_reference(config=config)

        assert isinstance(godelian, GodelianSelfReference)
        assert godelian.config is config
        assert godelian.config.enable_llm_modification is False

    def test_create_with_both_custom(self):
        """Test creating with both custom module and config."""
        custom_module = nn.Linear(64, 64)
        config = GodelianConfig(enable_srwm=True)

        godelian = create_godelian_self_reference(base_module=custom_module, config=config)

        assert isinstance(godelian, GodelianSelfReference)
        assert godelian.base_module is custom_module
        assert godelian.config is config

    def test_forward_with_default_module(self):
        """Test forward pass with default Identity module."""
        godelian = create_godelian_self_reference()

        # Identity module should pass through input
        x = torch.randn(4, 16)
        output = godelian(x)

        # Should return dict with godelian state and wrapped output
        assert isinstance(output, dict)
        assert "output" in output  # Identity output wrapped in dict
        assert "godelian" in output
        assert "self" in output["godelian"]
        assert "e8_code" in output["godelian"]
        assert "s7_phase" in output["godelian"]

        # Verify Identity passed through the input
        assert torch.allclose(output["output"], x)

        # E8 code should be 8D
        assert output["godelian"]["e8_code"].shape == (8,)
        # S7 phase should be 7D
        assert output["godelian"]["s7_phase"].shape == (7,)
        # Combined self should be 30D (code 15 + weights 15)
        assert output["godelian"]["self"].shape == (30,)

    def test_self_inspect_with_default(self):
        """Test self-inspection works with default module."""
        godelian = create_godelian_self_reference()

        inspection = godelian.self_inspect()

        assert isinstance(inspection, dict)
        assert "code" in inspection
        assert "hash" in inspection
        assert isinstance(inspection["code"], str)
        assert isinstance(inspection["hash"], str)

    def test_encode_self_with_default(self):
        """Test self-encoding works with default module."""
        godelian = create_godelian_self_reference()

        encoding = godelian.encode_self()

        assert isinstance(encoding, dict)
        assert "code_embedding" in encoding
        assert "weight_embedding" in encoding
        assert "combined_self" in encoding
        assert "e8_code" in encoding
        assert "s7_phase" in encoding

        # Check dimensions
        assert encoding["code_embedding"].shape == (15,)  # E8(8) + S7(7)
        assert encoding["weight_embedding"].shape == (15,)  # E8(8) + S7(7)
        assert encoding["combined_self"].shape == (30,)  # code + weights
        assert encoding["e8_code"].shape == (8,)
        assert encoding["s7_phase"].shape == (7,)


class TestHofstadterFactoryDefaults:
    """Test HofstadterStrangeLoop factory with defaults."""

    def test_create_without_args(self):
        """Test creating HofstadterStrangeLoop without any arguments."""
        loop = create_hofstadter_strange_loop()

        assert isinstance(loop, HofstadterStrangeLoop)
        assert isinstance(loop.config, HofstadterLoopConfig)

        # Check default dimensions (S7-aligned)
        assert loop.internal_dim == 14  # G2 dimension
        assert loop.self_dim == 7  # S7 dimension
        assert loop.action_dim == 8  # E8 lattice

    def test_create_with_custom_config(self):
        """Test creating with custom config."""
        config = HofstadterLoopConfig(
            internal_dim=14,
            self_dim=7,
            action_dim=8,
            self_momentum=0.95,
            warmup_steps=200,
        )
        loop = create_hofstadter_strange_loop(config)

        assert isinstance(loop, HofstadterStrangeLoop)
        assert loop.config is config
        assert loop.config.self_momentum == 0.95
        assert loop.config.warmup_steps == 200

    def test_forward_with_default(self):
        """Test forward pass with default config."""
        loop = create_hofstadter_strange_loop()

        # Create input tensors
        B = 4
        internal_z = torch.randn(B, loop.internal_dim)  # [4, 14]
        action = torch.randn(B, loop.action_dim)  # [4, 8]

        output = loop(internal_z, action)

        assert isinstance(output, dict)
        assert "coherence" in output
        assert "mu_self" in output
        assert "encoded_self" in output

        # Check dimensions and types
        assert isinstance(output["coherence"], float)  # Scalar float, not tensor
        assert output["mu_self"].shape == (loop.self_dim,)  # [7]
        assert output["encoded_self"].shape == (B, loop.self_dim)  # [4, 7]

    def test_forward_without_action(self):
        """Test forward pass without action (should default to zeros)."""
        loop = create_hofstadter_strange_loop()

        B = 2
        internal_z = torch.randn(B, loop.internal_dim)

        # Should work without action
        output = loop(internal_z, action=None)

        assert isinstance(output, dict)
        assert "coherence" in output
        assert isinstance(output["coherence"], float)  # Scalar float

    def test_mu_self_is_learnable(self):
        """Test that mu_self is a learnable parameter."""
        loop = create_hofstadter_strange_loop()

        # mu_self should be a Parameter
        assert isinstance(loop.mu_self, nn.Parameter)
        assert loop.mu_self.requires_grad

        # Should be 7D (S7)
        assert loop.mu_self.shape == (7,)

    def test_momentum_schedule(self):
        """Test momentum warmup schedule."""
        config = HofstadterLoopConfig(warmup_steps=100, warmup_momentum=0.7, self_momentum=0.99)
        loop = create_hofstadter_strange_loop(config)

        # Before warmup
        assert loop._momentum() == 0.7

        # Simulate steps
        loop._step.fill_(50)  # type: ignore[operator]
        assert loop._momentum() == 0.7

        # After warmup
        loop._step.fill_(100)  # type: ignore[operator]
        assert loop._momentum() == 0.99


class TestFactoryIntegration:
    """Test integration between factories."""

    def test_godelian_wraps_hofstadter(self):
        """Test GodelianSelfReference can wrap HofstadterStrangeLoop."""
        # Create Hofstadter loop with defaults
        loop = create_hofstadter_strange_loop()

        # Wrap with Godelian self-reference
        godelian = create_godelian_self_reference(base_module=loop)

        assert isinstance(godelian, GodelianSelfReference)
        assert isinstance(godelian.base_module, HofstadterStrangeLoop)

    def test_godelian_hofstadter_forward(self):
        """Test forward pass through Godelian-wrapped Hofstadter."""
        loop = create_hofstadter_strange_loop()
        godelian = create_godelian_self_reference(base_module=loop)

        # Create inputs for HofstadterStrangeLoop
        B = 2
        internal_z = torch.randn(B, loop.internal_dim)
        action = torch.randn(B, loop.action_dim)

        # Forward through wrapped module
        output = godelian(internal_z, action)

        # Should have both Hofstadter outputs and Godelian state
        assert isinstance(output, dict)
        assert "coherence" in output  # From Hofstadter
        assert "mu_self" in output  # From Hofstadter
        assert "godelian" in output  # From Godelian wrapper

        # Check Godelian augmentation
        assert "self" in output["godelian"]
        assert "e8_code" in output["godelian"]
        assert "s7_phase" in output["godelian"]
        assert "h" in output["godelian"]  # Consistency
        assert "Δ" in output["godelian"]  # Source changed flag

    def test_inspect_wrapped_hofstadter(self):
        """Test self-inspection of wrapped Hofstadter module."""
        loop = create_hofstadter_strange_loop()
        godelian = create_godelian_self_reference(base_module=loop)

        inspection = godelian.self_inspect()

        # Should inspect the HofstadterStrangeLoop class
        assert "HofstadterStrangeLoop" in inspection["code"]
        assert "mu_self" in inspection["code"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
