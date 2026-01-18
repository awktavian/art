"""Tests for MOBIASM Compiler."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch

from kagami.core.mobiasm.compiler import (
    MobiASMCompiler,
    compile_and_execute,
)
from kagami.core.mobiasm.runtime_zero_overhead import MobiASMZeroOverheadRuntime as MobiASMRuntime


class TestMobiASMCompilerParsing:
    """Test MOBIASM source parsing."""

    def test_parse_simple_instruction(self):
        """Test parsing single instruction."""
        compiler = MobiASMCompiler()
        source = "H.EXP0 %r0, %v0"
        ops = compiler.compile(source)

        assert len(ops) == 1
        assert ops[0].opcode == "H.EXP0"
        assert ops[0].dest == "%r0"
        assert ops[0].args == ["%v0"]

    def test_parse_multiple_instructions(self):
        """Test parsing multiple instructions."""
        compiler = MobiASMCompiler()
        source = """
        H.EXP0 %r0, %v0
        H.EXP0 %r1, %v1
        H.DIST %r2, %r0, %r1
        """
        ops = compiler.compile(source)

        assert len(ops) == 3
        assert ops[0].opcode == "H.EXP0"
        assert ops[1].opcode == "H.EXP0"
        assert ops[2].opcode == "H.DIST"

    def test_parse_with_comments(self):
        """Test comment handling."""
        compiler = MobiASMCompiler()
        source = """
        ; This is a comment
        H.EXP0 %r0, %v0  ; Inline comment
        ; Another comment
        H.DIST %r2, %r0, %r1
        """
        ops = compiler.compile(source)

        assert len(ops) == 2  # Comments ignored
        assert ops[0].opcode == "H.EXP0"

    def test_parse_with_labels(self):
        """Test label parsing."""
        compiler = MobiASMCompiler()
        source = """
        start:
        H.EXP0 %r0, %v0
        loop:
        H.ADD %r0, %r0, %r1
        """
        ops = compiler.compile(source)

        assert "start" in compiler.labels
        assert "loop" in compiler.labels
        assert len(ops) == 2  # Labels don't create ops


class TestMobiASMCompilerExecution:
    """Test compiled code execution."""

    def test_execute_hyperbolic_operations(self):
        """Test executing hyperbolic operations."""
        compiler = MobiASMCompiler()
        runtime = MobiASMRuntime(hyperbolic_dim=7, device="cpu")

        source = """
        H.EXP0 %r0, %v0
        H.LOG0 %r1, %r0
        """

        v0 = torch.randn(7)
        inputs = {"%v0": v0}

        compiled = compiler.compile(source)
        registers = compiler.execute(compiled, runtime, inputs)

        assert "%r0" in registers
        assert "%r1" in registers
        # Log of exp should approximately recover input
        r1 = registers["%r1"].to(torch.float32)
        v0_f = v0.to(torch.float32)
        assert torch.allclose(r1, v0_f, atol=1e-2, rtol=2e-3)

    def test_execute_distance_computation(self):
        """Test distance computation."""
        MobiASMCompiler()
        runtime = MobiASMRuntime(device="cpu")

        source = """
        H.EXP0 %r0, %v0
        H.EXP0 %r1, %v1
        H.DIST %r2, %r0, %r1
        """

        inputs = {
            "%v0": torch.randn(14),
            "%v1": torch.randn(14),
        }

        registers = compile_and_execute(source, runtime, inputs)

        assert "%r2" in registers
        dist = registers["%r2"]
        assert dist.item() >= 0


class TestMobiASMCompilerIntegration:
    """Integration tests with full runtime."""

    def test_geodesic_computation(self):
        """Test geodesic path computation."""
        runtime = MobiASMRuntime(device="cpu")

        source = """
        ; Compute geodesic from v0 to v1
        H.EXP0 %r0, %v0
        H.EXP0 %r1, %v1
        """

        inputs = {
            "%v0": torch.randn(14),
            "%v1": torch.randn(14),
        }

        registers = compile_and_execute(source, runtime, inputs)

        # Both points should be on manifold
        assert "%r0" in registers
        assert "%r1" in registers

    def test_complex_workflow(self):
        """Test complex multi-step workflow."""
        runtime = MobiASMRuntime(device="cpu")

        source = """
        ; Multi-step geometric computation
        H.EXP0 %r0, %v0
        H.EXP0 %r1, %v1
        H.ADD %r2, %r0, %r1
        H.NORM %r3, %r2
        """

        inputs = {
            "%v0": torch.randn(14),
            "%v1": torch.randn(14),
        }

        registers = compile_and_execute(source, runtime, inputs)

        assert "%r0" in registers
        assert "%r1" in registers
        assert "%r2" in registers
        assert "%r3" in registers


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
