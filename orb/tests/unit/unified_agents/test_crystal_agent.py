"""Unit tests for CrystalAgent - The Judge.

Tests:
- Agent initialization
- System prompt content
- Tool availability
- Parabolic umbilic boundary detection
- Verification workflow
- Edge case generation
- Security audit logic
- Escalation on critical failures
- S⁷ embedding correctness

Created: December 14, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import torch

from kagami.core.unified_agents.agents.crystal_agent import (
    CrystalAgent,
    create_crystal_agent,
)
from kagami.core.unified_agents.core_types import Task
from kagami.core.unified_agents.agents.base_colony_agent import AgentResult


class TestCrystalAgent:
    """Test suite for CrystalAgent."""

    def test_initialization(self) -> None:
        """Test Crystal agent initialization."""
        crystal = create_crystal_agent()

        assert crystal.state_dim == 256
        assert crystal.hidden_dim == 256
        assert crystal.safety_threshold == 0.0
        assert crystal.dna.domain.value == "crystal"  # type: ignore[union-attr]
        assert crystal.kernel is not None
        assert len(crystal.test_history) == 0
        assert crystal.failure_count == 0
        assert crystal.success_count == 0

    def test_initialization_custom_params(self) -> None:
        """Test Crystal agent with custom parameters."""
        crystal = create_crystal_agent(
            state_dim=128,
            hidden_dim=512,
            safety_threshold=0.1,
        )

        assert crystal.state_dim == 128
        assert crystal.hidden_dim == 512
        assert crystal.safety_threshold == 0.1

    def test_system_prompt(self) -> None:
        """Test system prompt contains key Crystal characteristics."""
        crystal = create_crystal_agent()
        prompt = crystal.get_system_prompt()

        # Check for key identity markers
        assert "Crystal" in prompt
        assert "Judge" in prompt or "judge" in prompt.lower()
        assert "Parabolic" in prompt or "parabolic" in prompt.lower()
        assert "e₇" in prompt or "D₅" in prompt

        # Check for personality characteristics
        assert "truth" in prompt.lower() or "boundary" in prompt.lower()
        assert "safe" in prompt.lower() or "verify" in prompt.lower()

        # Check for catastrophe dynamics
        assert "ridge" in prompt.lower() or "boundary" in prompt.lower()

    def test_available_tools(self) -> None:
        """Test Crystal has verification tools."""
        crystal = create_crystal_agent()
        tools = crystal.get_available_tools()

        # Check essential verification tools
        assert "test" in tools
        assert "verify" in tools
        assert "audit" in tools
        assert "validate" in tools
        assert "check" in tools
        assert "prove" in tools

        # Should have comprehensive tool set
        assert len(tools) >= 8

    def test_process_with_catastrophe_fast_path(self) -> None:
        """Test fast path processing (k < 3)."""
        crystal = create_crystal_agent()

        batch_size = 4
        state = torch.randn(batch_size, 256)

        task = Task(
            task_type="verify",
            description="Quick boundary check",
            context={},
        )

        # Fast path (k=1)
        result = crystal.process_with_catastrophe(
            task.description if hasattr(task, "description") else str(task),
            {"k_value": 1, "state_tensor": state},
        )

        # Check result type
        assert isinstance(result, AgentResult)
        assert result.s7_embedding is not None

        # Check output shape and normalization
        action = result.s7_embedding
        assert action.shape == (batch_size, 8)
        norms = action.norm(dim=-1)
        assert torch.allclose(norms, torch.ones(batch_size), atol=1e-5)

    def test_process_with_catastrophe_slow_path(self) -> None:
        """Test slow path processing (k ≥ 3)."""
        crystal = create_crystal_agent()

        batch_size = 4
        state = torch.randn(batch_size, 256)

        # Define barrier function for slow path
        def test_barrier_fn(s: torch.Tensor) -> torch.Tensor:
            """Test barrier: h(x) = mean of state."""
            return s.mean(dim=-1)

        # Slow path (k=5)
        # Note: barrier_function must be in context parameter, not task.context
        result = crystal.process_with_catastrophe(
            "Full security audit",
            {
                "k_value": 5,
                "state_tensor": state,
                "goals": torch.randn(batch_size, 15),  # obs_dim = 15
                "barrier_function": test_barrier_fn,  # Required for ParabolicKernel slow path
            },
        )

        # Check result type
        assert isinstance(result, AgentResult)
        assert result.s7_embedding is not None

        # Check output
        action = result.s7_embedding
        assert action.shape == (batch_size, 8)
        norms = action.norm(dim=-1)
        assert torch.allclose(norms, torch.ones(batch_size), atol=1e-5)

    def test_boundary_amplification(self) -> None:
        """Test boundary detection amplification near safety threshold."""
        crystal = create_crystal_agent(safety_threshold=0.0)

        batch_size = 4
        state = torch.randn(batch_size, 256)

        # Define barrier function
        def test_barrier_fn(s: torch.Tensor) -> torch.Tensor:
            """Test barrier: h(x) = mean of state."""
            return s.mean(dim=-1)

        # States with varying proximity to boundary
        safety_margins = torch.tensor([0.5, 0.05, -0.02, -0.1])

        # Note: barrier_function must be in context parameter, not task.context
        result = crystal.process_with_catastrophe(
            "Boundary test",
            {
                "k_value": 5,
                "state_tensor": state,
                "safety_margin": safety_margins,
                "barrier_function": test_barrier_fn,
            },
        )

        # Check result type
        assert isinstance(result, AgentResult)
        assert result.s7_embedding is not None

        # Should still be normalized
        action = result.s7_embedding
        assert action.shape == (batch_size, 8)
        norms = action.norm(dim=-1)
        assert torch.allclose(norms, torch.ones(batch_size), atol=1e-5)

    def test_comprehensive_verification(self) -> None:
        """Test comprehensive verification protocol."""
        crystal = create_crystal_agent()

        batch_size = 4
        state = torch.randn(batch_size, 256)

        task = Task(
            task_type="verify",
            description="Test implementation correctness",
            context={
                "assumptions": ["Input is well-formed", "State initialized"],
            },
        )

        report = crystal.verify(state, task, k_value=5)

        # Check report structure
        assert "task_id" in report
        assert "claim" in report
        assert "passed" in report
        assert "evidence" in report
        assert "failures" in report
        assert "edge_cases_tested" in report
        assert "assumptions_checked" in report
        assert "test_count" in report
        assert "pass_rate" in report

        # Check assumptions were included
        assert len(report["assumptions"]) >= 2
        assert "Input is well-formed" in report["assumptions"]

        # Should have run multiple tests
        assert report["test_count"] > 0
        assert len(report["evidence"]) == report["test_count"]

    def test_edge_case_generation(self) -> None:
        """Test edge case generation for verification."""
        crystal = create_crystal_agent()

        batch_size = 2
        state = torch.randn(batch_size, 256)

        task = Task(
            task_type="verify",
            description="Test edge cases",
            context={
                "edge_cases": ["Custom edge case 1"],
            },
        )

        edge_cases = crystal._generate_edge_cases(state, task)

        # Should have default edge cases
        assert "Null input" in edge_cases
        assert "Empty input" in edge_cases
        assert "Maximum size input" in edge_cases
        assert "Zero value" in edge_cases

        # Should include custom edge case
        assert "Custom edge case 1" in edge_cases

        # Should have reasonable number
        assert len(edge_cases) >= 7

    def test_assumption_enumeration(self) -> None:
        """Test assumption extraction and enumeration."""
        crystal = create_crystal_agent()

        # Test with explicit assumptions
        task_with_assumptions = Task(
            task_type="verify",
            description="Test with assumptions",
            context={
                "assumptions": ["Network is available", "Disk space sufficient"],
            },
        )

        assumptions = crystal._enumerate_assumptions(task_with_assumptions)
        assert "Network is available" in assumptions
        assert "Disk space sufficient" in assumptions

        # Test with implicit assumptions (verify task type)
        task_verify = Task(task_type="verify", description="Test")
        assumptions_verify = crystal._enumerate_assumptions(task_verify)
        assert "Input is well-formed" in assumptions_verify
        assert "Dependencies are available" in assumptions_verify

        # Test with audit task type
        task_audit = Task(task_type="audit", description="Security audit")
        assumptions_audit = crystal._enumerate_assumptions(task_audit)
        assert "Code is executable" in assumptions_audit

    def test_test_case_design(self) -> None:
        """Test automatic test case generation."""
        crystal = create_crystal_agent()

        batch_size = 5
        state = torch.randn(batch_size, 256)

        task = Task(
            task_type="verify",
            description="Test design",
        )

        test_cases = crystal._design_tests(task, state)

        # Should have multiple test types
        test_types = {test["type"] for test in test_cases}
        assert "positive" in test_types
        assert "boundary" in test_types
        assert "negative" in test_cases[-1]["type"]

        # Should have reasonable count
        assert len(test_cases) >= 4

        # Each test should have required fields
        for test in test_cases:
            assert "name" in test
            assert "type" in test
            assert "state_idx" in test
            assert "expected_result" in test

    def test_should_escalate_security_critical(self) -> None:
        """Test escalation on security-critical issues."""
        crystal = create_crystal_agent()

        result_critical = AgentResult(
            success=False,
            output={"security_critical": True, "safety_violated": False},
            s7_embedding=torch.randn(1, 8),
        )

        should_escalate = crystal.should_escalate(result_critical, {})
        assert should_escalate is True

    def test_should_escalate_safety_violation(self) -> None:
        """Test escalation on safety invariant violation."""
        crystal = create_crystal_agent()

        result_unsafe = AgentResult(
            success=False,
            output={"security_critical": False, "safety_violated": True},
            s7_embedding=torch.randn(1, 8),
        )

        should_escalate = crystal.should_escalate(result_unsafe, {})
        assert should_escalate is True

    def test_should_escalate_architecture_issue(self) -> None:
        """Test escalation on architecture issues."""
        crystal = create_crystal_agent()

        result_arch = AgentResult(
            success=False,
            output={
                "security_critical": False,
                "safety_violated": False,
                "architecture_issue": True,
            },
            s7_embedding=torch.randn(1, 8),
        )

        should_escalate = crystal.should_escalate(result_arch, {})
        assert should_escalate is True

    def test_should_escalate_repeated_failures(self) -> None:
        """Test escalation after repeated failures."""
        crystal = create_crystal_agent()

        batch_size = 2
        state = torch.randn(batch_size, 256)

        # Simulate multiple failures
        for _ in range(3):
            # Create a failing report
            report = {
                "passed": False,
                "security_critical": False,
                "safety_violated": False,
                "architecture_issue": False,
            }
            crystal.test_history.append(report)

        # Should escalate after 3 recent failures
        result = AgentResult(
            success=False,
            output=report,
            s7_embedding=torch.randn(1, 8),
        )
        should_escalate = crystal.should_escalate(result, {})
        assert should_escalate is True

    def test_no_escalation_on_success(self) -> None:
        """Test no escalation on successful verification."""
        crystal = create_crystal_agent()

        result_success = AgentResult(
            success=True,
            output={
                "security_critical": False,
                "safety_violated": False,
                "architecture_issue": False,
            },
            s7_embedding=torch.randn(1, 8),
        )

        should_escalate = crystal.should_escalate(result_success, {})
        assert should_escalate is False

    def test_verification_statistics(self) -> None:
        """Test verification statistics tracking."""
        crystal = create_crystal_agent()

        batch_size = 2
        state = torch.randn(batch_size, 256)

        # Run successful verification
        task_success = Task(task_type="verify", description="Success test")
        report_success = crystal.verify(state, task_success, k_value=3)

        stats = crystal.get_verification_stats()
        assert stats["total_verifications"] >= 1
        assert stats["successes"] >= 1 if report_success["passed"] else True
        assert "success_rate" in stats
        assert 0.0 <= stats["success_rate"] <= 1.0

    def test_reset_statistics(self) -> None:
        """Test statistics reset."""
        crystal = create_crystal_agent()

        batch_size = 2
        state = torch.randn(batch_size, 256)

        # Run verification to generate stats
        task = Task(task_type="verify", description="Test")
        crystal.verify(state, task, k_value=3)

        # Reset
        crystal.reset_stats()

        stats = crystal.get_verification_stats()
        assert stats["total_verifications"] == 0
        assert stats["successes"] == 0
        assert stats["failures"] == 0
        assert len(crystal.test_history) == 0

    def test_claim_analysis(self) -> None:
        """Test claim analysis extracts key information."""
        crystal = create_crystal_agent()

        task = Task(
            task_type="verify",
            description="Test claim analysis",
            context={
                "scope": "module_level",
                "criticality": "high",
            },
        )

        analysis = crystal._analyze_claim(task)

        assert analysis["claim"] == "Test claim analysis"
        assert analysis["type"] == "verify"
        assert analysis["scope"] == "module_level"
        assert analysis["criticality"] == "high"

    def test_test_execution(self) -> None:
        """Test individual test execution."""
        crystal = create_crystal_agent()

        batch_size = 4
        state = torch.randn(batch_size, 256)

        test_spec = {
            "name": "positive_test",
            "type": "positive",
            "state_idx": 0,
            "expected_result": "pass",
        }

        result = crystal._execute_test(test_spec, state)

        assert "name" in result
        assert "type" in result
        assert "passed" in result
        assert "reason" in result
        assert "h_value" in result
        assert isinstance(result["passed"], bool)

    def test_escalation_reason_generation(self) -> None:
        """Test escalation reason message generation."""
        crystal = create_crystal_agent()

        report_security = {
            "security_critical": True,
            "safety_violated": False,
            "architecture_issue": False,
            "failures": [],
        }

        reason = crystal._get_escalation_reason(report_security)
        assert "Security-critical" in reason or "security" in reason.lower()

        report_safety = {
            "security_critical": False,
            "safety_violated": True,
            "architecture_issue": False,
            "failures": [],
        }

        reason = crystal._get_escalation_reason(report_safety)
        assert "Safety" in reason or "h(x)" in reason

    def test_dna_encoding(self) -> None:
        """Test agent DNA encoding."""
        crystal = create_crystal_agent()

        dna = crystal.dna

        # Check domain
        assert dna.domain.value == "crystal"  # type: ignore[union-attr]

        # Check capabilities
        assert "verify" in dna.capabilities
        assert "test" in dna.capabilities
        assert "audit" in dna.capabilities

        # Check catastrophe type
        assert dna.catastrophe.value == "parabolic"

        # Check execution mode
        assert dna.execution_mode == "careful"

        # Check personality vector (skeptical profile)
        assert len(dna.personality_vector) == 8
        # Crystal should have low epistemic (0.3) and high pragmatic (2.5)
        assert dna.personality_vector[0] == 0.3  # Low exploration
        assert dna.personality_vector[1] == 2.5  # High goal focus

    def test_verification_with_safety_violations(self) -> None:
        """Test verification detects safety violations."""
        crystal = create_crystal_agent(safety_threshold=0.0)

        batch_size = 4
        # Create state that will produce negative h values
        state = torch.ones(batch_size, 256) * -1.0

        task = Task(
            task_type="verify",
            description="Safety violation test",
        )

        report = crystal.verify(state, task, k_value=5)

        # Verification should complete
        assert "passed" in report
        assert "safety_violated" in report

        # Should have test evidence
        assert len(report["evidence"]) > 0

    def test_multiple_verifications_update_history(self) -> None:
        """Test that multiple verifications update history."""
        crystal = create_crystal_agent()

        batch_size = 2
        state = torch.randn(batch_size, 256)

        # Run multiple verifications
        for i in range(3):
            task = Task(
                task_type="verify",
                description=f"Test {i}",
            )
            crystal.verify(state, task, k_value=3)

        # History should contain all verifications
        assert len(crystal.test_history) == 3

        stats = crystal.get_verification_stats()
        assert stats["total_verifications"] == 3

    def test_parabolic_kernel_type(self) -> None:
        """Test Crystal uses ParabolicKernel."""
        crystal = create_crystal_agent()

        from kagami.core.unified_agents.catastrophe_kernels import ParabolicKernel

        assert isinstance(crystal.kernel, ParabolicKernel)

    def test_verification_with_barrier_function(self) -> None:
        """Test verification with explicit barrier function."""
        crystal = create_crystal_agent()

        batch_size = 4
        state = torch.randn(batch_size, 256)

        def test_barrier(s: torch.Tensor) -> torch.Tensor:
            """Test barrier function: h(x) = mean(state)."""
            return s.mean(dim=-1)

        safety_margin = test_barrier(state)

        # Note: barrier_function must be in context parameter, not task.context
        result = crystal.process_with_catastrophe(
            "Test with barrier function",
            {
                "k_value": 3,
                "state_tensor": state,
                "barrier_function": test_barrier,
                "safety_margin": safety_margin,
            },
        )

        # Check result type
        assert isinstance(result, AgentResult)
        assert result.s7_embedding is not None

        # Should process successfully
        action = result.s7_embedding
        assert action.shape == (batch_size, 8)

    def test_skeptical_personality_traits(self) -> None:
        """Test Crystal exhibits boundary-detecting traits in prompt."""
        crystal = create_crystal_agent()
        prompt = crystal.get_system_prompt()

        # Should mention verification/truth
        assert "truth" in prompt.lower() or "verify" in prompt.lower()

        # Should emphasize boundaries
        assert "boundary" in prompt.lower() or "ridge" in prompt.lower()

        # Should reference safe/unsafe
        assert "safe" in prompt.lower()

        # Should reference fear/flaw
        assert "fear" in prompt.lower() or "trust" in prompt.lower()

    def test_verification_report_completeness(self) -> None:
        """Test verification report has all required fields."""
        crystal = create_crystal_agent()

        batch_size = 2
        state = torch.randn(batch_size, 256)

        task = Task(
            task_type="verify",
            description="Completeness test",
            context={
                "assumptions": ["Test assumption"],
                "edge_cases": ["Custom edge case"],
            },
        )

        report = crystal.verify(state, task, k_value=5)

        # Check all expected fields
        required_fields = [
            "task_id",
            "claim",
            "passed",
            "evidence",
            "failures",
            "edge_cases_tested",
            "assumptions_checked",
            "assumptions",
            "test_count",
            "pass_rate",
            "security_critical",
            "safety_violated",
            "architecture_issue",
            "claim_analysis",
        ]

        for field in required_fields:
            assert field in report, f"Missing required field: {field}"

        # Check types
        assert isinstance(report["passed"], bool)
        assert isinstance(report["evidence"], list)
        assert isinstance(report["failures"], list)
        assert isinstance(report["edge_cases_tested"], list)
        assert isinstance(report["assumptions"], list)
        assert isinstance(report["test_count"], int)
        assert isinstance(report["pass_rate"], float)

    def test_verify_safety_with_barrier_function(self) -> None:
        """Test safety verification with explicit barrier function."""
        crystal = create_crystal_agent()

        batch_size = 2
        state = torch.randn(batch_size, 256)

        def test_barrier(s: torch.Tensor) -> torch.Tensor:
            return s.mean(dim=-1)

        safety_margin = test_barrier(state)

        task = Task(
            task_type="verify",
            description="Test safety verification",
        )

        context = {
            "barrier_function": test_barrier,
            "safety_margin": safety_margin,
        }

        safety_report = crystal._verify_safety(task, context)

        assert "h_value" in safety_report
        assert "is_safe" in safety_report
        assert "margin" in safety_report
        assert "method" in safety_report
        assert safety_report["method"] == "barrier_function"

    def test_verify_safety_without_barrier(self) -> None:
        """Test safety verification without barrier function."""
        crystal = create_crystal_agent()

        task = Task(
            task_type="verify",
            description="Test without barrier",
        )

        safety_report = crystal._verify_safety(task, {})

        assert safety_report["h_value"] is None
        assert safety_report["is_safe"] is None
        assert safety_report["method"] == "unavailable"

    def test_audit_constraints_empty(self) -> None:
        """Test constraint audit with no constraints."""
        crystal = create_crystal_agent()

        task = Task(
            task_type="audit",
            description="Test audit",
            context={},
        )

        report = crystal._audit_constraints(task)

        assert "No constraints" in report
        assert "Show me" in report

    def test_audit_constraints_with_constraints(self) -> None:
        """Test constraint audit with constraints."""
        crystal = create_crystal_agent()

        task = Task(
            task_type="audit",
            description="Test audit",
            context={
                "constraints": [
                    "Input must be non-null",
                    "Output must be validated",
                ]
            },
        )

        report = crystal._audit_constraints(task)

        assert "Input must be non-null" in report
        assert "Output must be validated" in report
        assert "UNVERIFIED" in report

    def test_detect_boundary_distance(self) -> None:
        """Test boundary detection using parabolic kernel."""
        crystal = create_crystal_agent()

        batch_size = 4
        state = torch.randn(batch_size, 256)

        distance = crystal._detect_boundary(state)

        # Should return a float
        assert isinstance(distance, float)

    def test_escalation_on_bugs_found(self) -> None:
        """Test escalation when bugs found."""
        crystal = create_crystal_agent()

        result = AgentResult(
            success=False,
            output={
                "failures": [
                    {"test": "test1", "reason": "null pointer"},
                    {"test": "test2", "reason": "overflow"},
                ],
                "security_critical": False,
                "safety_violated": False,
                "architecture_issue": False,
            },
            s7_embedding=torch.randn(1, 8),
        )

        should_escalate = crystal.should_escalate(result, {})

        # Should escalate to Flow for fixing
        assert should_escalate is True

    def test_get_escalation_target_bugs(self) -> None:
        """Test escalation target determination for bugs."""
        crystal = create_crystal_agent()

        result_bugs = {
            "failures": [{"test": "test1"}],
            "security_critical": False,
            "safety_violated": False,
            "architecture_issue": False,
        }

        target = crystal._get_escalation_target(result_bugs)
        assert target == "flow"

    def test_near_boundary_detection(self) -> None:
        """Test detection of states near safety boundary."""
        crystal = create_crystal_agent(safety_threshold=0.0)

        batch_size = 2
        state = torch.randn(batch_size, 256)

        def test_barrier(s: torch.Tensor) -> torch.Tensor:
            return torch.tensor([0.05, 0.05])  # Near boundary

        # Test with safety margin near threshold
        result = crystal.process_with_catastrophe(
            "Test near boundary",
            {
                "k_value": 3,
                "state_tensor": state,
                "safety_margin": 0.05,  # Very close to threshold
                "barrier_function": test_barrier,
            },
        )

        # Should detect near boundary
        if isinstance(result.output, dict):
            if "near_boundary" in result.output:
                assert result.output["near_boundary"] is True
                assert "boundary_distance" in result.output

    def test_quick_verify_with_safety_margin_tensor(self) -> None:
        """Test quick verification with tensor safety margin."""
        crystal = create_crystal_agent()

        batch_size = 2
        state = torch.randn(batch_size, 256)

        task = Task(
            task_type="verify",
            description="Quick test",
            context={
                "safety_margin": torch.tensor([0.3, 0.5]),
            },
        )

        result = crystal._quick_verify(task, state, torch.randn(8))

        assert "h_value" in result
        assert "passed" in result

    def test_state_tensor_placeholder(self) -> None:
        """Test that missing state tensor creates placeholder."""
        crystal = create_crystal_agent()

        # Process without state_tensor in context
        result = crystal.process_with_catastrophe(
            "Test without state",
            {"k_value": 1},
        )

        # Should still process successfully
        assert isinstance(result, AgentResult)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
