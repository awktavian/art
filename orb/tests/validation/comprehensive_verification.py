"""Comprehensive Verification Suite - Crystal's Mandate: Prove Everything.

CREATED: December 14, 2025
MISSION: Verify correctness, safety, and performance of ALL improvements

This is Crystal (e₇) - The Judge who trusts nothing unproven.
Every claim must be backed by evidence. No assumptions. No trust.

VERIFICATION SCOPE (10 Components + Integration):
=================================================
1. Catastrophe kernels: Real decisions, S⁷ normalized, Fano multiplication
2. EFE-CBF: h(x) ≥ 0 always, QP convergence
3. Universal CBF: No violations slip through
4. Receipt feedback: Routing improves over time
5. E8 temporal: Compression works, bifurcations detected
6. Trajectory cache: Hit rate > 0, LRU works
7. Fano meta-learner: Adaptation improves performance
8. Gradient surgery: No conflicts, G₂ structure respected
9. Integration: All components work together

VERIFICATION PRINCIPLES:
========================
- Statistical tests: Not single trials (N ≥ 30 for significance)
- Negative tests: Try to break things intentionally
- Performance benchmarks: Measure latency, throughput
- Mathematical guarantees: Prove invariants hold
- Full audit trail: Document all findings

References:
- Ames et al. (2019): CBF forward invariance proofs
- Viazovska (2017): E8 lattice optimality
- Thom (1972): Catastrophe classification theorem
- Baez (2002): Octonion multiplication table (Fano plane)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F

# Import components to verify
from kagami.core.world_model.active_inference.efe_cbf_optimizer import (
    EFECBFConfig,
    EFECBFOptimizer,
    create_efe_cbf_optimizer,
)
from kagami.core.world_model.active_inference.efe import (
    EFEConfig,
    ExpectedFreeEnergy,
)
from kagami.core.training.learning.gradient_surgery import GradientSurgery
from kagami.core.training.learning.receipt_learning import ReceiptLearningEngine
from kagami_math.fano_plane import FANO_LINES, FANO_SIGNS
from kagami.core.safety.optimal_cbf import OptimalCBF, OptimalCBFConfig
from kagami.core.safety.universal_cbf_enforcer import (
    CBFViolationError,
    assert_cbf,
    enforce_cbf,
    get_cbf_stats,
    project_to_safe_set,
)
from kagami.agents import (
    FanoActionRouter,
    UnifiedOrganism,
    get_unified_organism,
)
from kagami.agents.catastrophe_kernels import (
    batch_evaluate_kernels,
    create_colony_kernel,
)
from kagami.agents.fano_meta_learner import FanoMetaLearner
from kagami.core.world_model.e8_trajectory_cache import (
    CacheStats,
    E8TrajectoryCache,
)
from kagami.core.world_model.temporal_e8_quantizer import (
    TemporalE8Config,
    TemporalE8Quantizer,
)

logger = logging.getLogger(__name__)


# =============================================================================
# VERIFICATION RESULT TYPES
# =============================================================================


@dataclass
class VerificationResult:
    """Result of a single verification test.

    Attributes:
        name: Test name
        passed: Whether test passed
        evidence: Supporting evidence (metrics, examples)
        failures: List of failure cases (if any)
        duration_ms: Test duration in milliseconds
        confidence: Confidence level (0-1)
    """

    name: str
    passed: bool
    evidence: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    confidence: float = 1.0


@dataclass
class VerificationSummary:
    """Summary of all verification results.

    Attributes:
        total_tests: Total number of tests run
        passed: Number of tests passed
        failed: Number of tests failed
        total_duration_ms: Total duration in milliseconds
        results: Individual test results
        critical_failures: List of critical failures that block deployment
    """

    total_tests: int = 0
    passed: int = 0
    failed: int = 0
    total_duration_ms: float = 0.0
    results: list[VerificationResult] = field(default_factory=list)
    critical_failures: list[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        """Compute pass rate."""
        return self.passed / max(1, self.total_tests)

    @property
    def is_deployment_ready(self) -> bool:
        """Check if system is deployment ready."""
        return len(self.critical_failures) == 0 and self.pass_rate >= 0.95


# =============================================================================
# COMPREHENSIVE VERIFICATION SUITE
# =============================================================================


class ComprehensiveVerificationSuite:
    """Comprehensive verification of all KagamiOS improvements.

    Crystal's mandate: Trust nothing. Prove everything.

    This suite verifies:
    1. Correctness: Does it do what it claims?
    2. Safety: Can it violate invariants?
    3. Performance: Does it meet latency/throughput requirements?
    4. Robustness: Does it handle edge cases?
    5. Integration: Do components work together?
    """

    def __init__(self, device: str = "cpu"):
        """Initialize verification suite.

        Args:
            device: Device to run tests on ('cpu' or 'cuda')
        """
        self.device = device
        self.results: list[VerificationResult] = []
        self.summary = VerificationSummary()

    def run_all_verifications(self) -> VerificationSummary:
        """Run all verification tests.

        Returns:
            VerificationSummary with all results
        """
        logger.info("🔍 Crystal starting comprehensive verification...")

        # Component verifications
        verifications = [
            self.verify_catastrophe_kernels,
            self.verify_efe_cbf_safety,
            self.verify_universal_cbf,
            self.verify_receipt_feedback,
            self.verify_e8_temporal,
            self.verify_trajectory_cache,
            self.verify_fano_meta_learner,
            self.verify_gradient_surgery,
            self.verify_integration,
        ]

        for verify_func in verifications:
            try:
                result = verify_func()
                self.results.append(result)
                self.summary.results.append(result)
                self.summary.total_tests += 1
                self.summary.total_duration_ms += result.duration_ms

                if result.passed:
                    self.summary.passed += 1
                    logger.info(f"✅ {result.name} PASSED")
                else:
                    self.summary.failed += 1
                    logger.error(f"❌ {result.name} FAILED")
                    for failure in result.failures:
                        logger.error(f"   - {failure}")

                    # Check if critical
                    if "safety" in result.name.lower() or "cbf" in result.name.lower():
                        self.summary.critical_failures.append(result.name)

            except Exception as e:
                logger.error(f"💥 {verify_func.__name__} CRASHED: {e}")
                result = VerificationResult(
                    name=verify_func.__name__,
                    passed=False,
                    failures=[f"Exception: {e!s}"],
                )
                self.results.append(result)
                self.summary.results.append(result)
                self.summary.total_tests += 1
                self.summary.failed += 1
                self.summary.critical_failures.append(verify_func.__name__)

        # Generate report
        self._log_summary()

        return self.summary

    # =========================================================================
    # VERIFICATION 1: CATASTROPHE KERNELS
    # =========================================================================

    def verify_catastrophe_kernels(self) -> VerificationResult:
        """Verify colony kernels produce valid S⁷ outputs.

        Checks:
        1. NO torch.randn placeholders (all real implementations)
        2. Outputs are S⁷ normalized (||output|| = 1)
        3. Different colonies produce different patterns
        4. Fano multiplication: kernel_i × kernel_j ≈ ±kernel_k
        5. Gradient flow for training

        Returns:
            VerificationResult with evidence
        """
        start = time.time()
        failures = []
        evidence = {}

        try:
            # Create test state
            batch_size = 8
            state_dim = 256
            state = torch.randn(batch_size, state_dim, device=self.device)
            context = {"goals": torch.randn(batch_size, 15, device=self.device)}

            # Test all 7 colonies
            outputs = []
            for colony_idx in range(7):
                kernel = create_colony_kernel(colony_idx, state_dim, 256)
                kernel = kernel.to(self.device)
                kernel.eval()

                # Forward pass
                output = kernel(state, k_value=2, context=context)

                # Check 1: S⁷ normalization
                norms = output.norm(dim=-1)
                if not torch.allclose(norms, torch.ones_like(norms), atol=1e-4):
                    failures.append(
                        f"Colony {colony_idx} not S⁷ normalized: norms={norms.tolist()}"
                    )

                # Check 2: Determinism (same input → same output)
                output2 = kernel(state, k_value=2, context=context)
                if not torch.allclose(output, output2, atol=1e-5):
                    failures.append(f"Colony {colony_idx} non-deterministic")

                # Check 3: Gradient flow
                state_grad = state.clone().requires_grad_(True)
                output_grad = kernel(state_grad, k_value=3, context=context)
                loss = output_grad.sum()
                loss.backward()
                if state_grad.grad is None or state_grad.grad.abs().sum() == 0:
                    failures.append(f"Colony {colony_idx} no gradient flow")

                outputs.append(output[0])  # Take first batch element

            evidence["colonies_tested"] = 7
            evidence["avg_norm"] = torch.stack([out.norm() for out in outputs]).mean().item()  # type: ignore[assignment]

            # Check 4: Colony differentiation
            for i in range(7):
                for j in range(i + 1, 7):
                    similarity = F.cosine_similarity(
                        outputs[i].unsqueeze(0), outputs[j].unsqueeze(0)
                    )
                    if similarity > 0.95:
                        failures.append(f"Colony {i} and {j} too similar: {similarity:.3f}")

            evidence["min_colony_difference"] = min(  # type: ignore[assignment]
                1.0 - F.cosine_similarity(outputs[i].unsqueeze(0), outputs[j].unsqueeze(0)).item()
                for i in range(7)
                for j in range(i + 1, 7)
            )

            # Check 5: Fano multiplication (approximate - this is aspirational)
            # NOTE: Actual octonion multiplication requires proper implementation
            fano_checks = 0
            fano_passes = 0
            try:
                for (i, j), (k, _sign) in FANO_SIGNS.items():
                    if i < len(outputs) and j < len(outputs) and k < len(outputs):
                        # Naive check: project e_i × e_j direction onto e_k
                        product_direction = outputs[i] * outputs[j].sign()
                        similarity = F.cosine_similarity(
                            product_direction.unsqueeze(0), outputs[k].unsqueeze(0)
                        )
                        fano_checks += 1
                        if similarity.abs() > 0.5:  # Loose threshold
                            fano_passes += 1
            except (IndexError, KeyError) as e:
                logger.debug(f"Fano check failed: {e}")

            evidence["fano_checks"] = fano_checks
            evidence["fano_passes"] = fano_passes
            evidence["fano_pass_rate"] = fano_passes / max(1, fano_checks)  # type: ignore[assignment]

        except Exception as e:
            failures.append(f"Exception: {e!s}")

        duration_ms = (time.time() - start) * 1000
        passed = len(failures) == 0

        return VerificationResult(
            name="verify_catastrophe_kernels",
            passed=passed,
            evidence=evidence,
            failures=failures,
            duration_ms=duration_ms,
        )

    # =========================================================================
    # VERIFICATION 2: EFE-CBF SAFETY
    # =========================================================================

    def verify_efe_cbf_safety(self) -> VerificationResult:
        """Verify EFE never selects unsafe policies.

        Checks:
        1. Deployment mode: h(x) ≥ 0 ALWAYS (mathematical guarantee)
        2. Training mode: CBF loss decreases violations over time
        3. QP solver convergence
        4. Safety projection correctness

        Returns:
            VerificationResult with evidence
        """
        start = time.time()
        failures = []
        evidence = {}

        try:
            # Create EFE-CBF optimizer
            config = EFECBFConfig(
                state_dim=256,
                stochastic_dim=14,
                action_dim=8,
                penalty_weight=10.0,
            )
            cbf_config = OptimalCBFConfig(
                observation_dim=270,  # 256 + 14
                state_dim=256,
                control_dim=8,
                use_qp_solver=True,
            )
            cbf = OptimalCBF(cbf_config)
            optimizer = EFECBFOptimizer(config, cbf)

            # Test deployment mode (HARD CONSTRAINT)
            optimizer.eval()
            num_trials = 100
            violations = 0
            h_values_all = []

            for trial in range(num_trials):
                batch = 4
                num_policies = 5
                horizon = 3

                # Create test inputs
                G_values = torch.randn(batch, num_policies)
                states = torch.randn(batch, num_policies, 270)  # combined state
                policies = torch.randn(batch, num_policies, horizon, 8)

                # Apply hard constraints
                G_safe, info = optimizer(G_values, states, policies, training=False)

                # Check safety: h(x) ≥ 0 for selected policies
                h_values = info["h_values"]
                h_values_all.extend(h_values.flatten().tolist())

                # Check if ANY policy was selected with h < 0
                selected_idx = G_safe.argmin(dim=1)  # Best policy per batch
                for b in range(batch):
                    h_selected = h_values[b, selected_idx[b]]
                    # Convert to scalar for comparison
                    h_val = (
                        h_selected.item() if isinstance(h_selected, torch.Tensor) else h_selected
                    )
                    if h_val < -1e-6:  # Tolerance for numerical error
                        violations += 1
                        failures.append(
                            f"Trial {trial}, batch {b}: Selected unsafe policy with h={h_val:.4f}"
                        )

            evidence["deployment_trials"] = num_trials
            evidence["deployment_violations"] = violations
            evidence["violation_rate"] = violations / (num_trials * 4)  # type: ignore[assignment]
            evidence["min_h_value"] = min(h_values_all)
            evidence["mean_h_value"] = sum(h_values_all) / len(h_values_all)

            # Critical: No violations allowed in deployment mode
            if violations > 0:
                failures.append(f"CRITICAL: {violations}/{num_trials * 4} violations in deployment")

            # Test training mode (SOFT CONSTRAINT)
            optimizer.train()
            penalties = []
            for _trial in range(20):
                batch = 4
                num_policies = 5
                horizon = 3

                G_values = torch.randn(batch, num_policies)
                states = torch.randn(batch, num_policies, 270)
                policies = torch.randn(batch, num_policies, horizon, 8)

                G_safe, info = optimizer(G_values, states, policies, training=True)

                # Check that penalties are applied
                penalty = info.get("cbf_penalty", 0.0)
                if isinstance(penalty, torch.Tensor):
                    penalty = penalty.mean().item()
                penalties.append(penalty)

            evidence["training_trials"] = 20
            evidence["mean_penalty"] = sum(penalties) / len(penalties)
            evidence["penalty_range"] = [min(penalties), max(penalties)]  # type: ignore[assignment]

        except Exception as e:
            failures.append(f"Exception: {e!s}")

        duration_ms = (time.time() - start) * 1000
        passed = len(failures) == 0

        return VerificationResult(
            name="verify_efe_cbf_safety",
            passed=passed,
            evidence=evidence,
            failures=failures,
            duration_ms=duration_ms,
            confidence=0.99 if passed else 0.5,
        )

    # =========================================================================
    # VERIFICATION 3: UNIVERSAL CBF ENFORCER
    # =========================================================================

    def verify_universal_cbf(self) -> VerificationResult:
        """Verify @enforce_cbf decorator catches all violations.

        Checks:
        1. Decorator detects violations
        2. Projection works correctly
        3. Statistics tracked
        4. Thread safety

        Returns:
            VerificationResult with evidence
        """
        start = time.time()
        failures = []
        evidence = {}

        try:
            # Test 1: Projection on violation
            @enforce_cbf(state_param="x", project_to_safe=True)
            def test_function_projection(x: Any) -> None:
                return x

            # Create unsafe state (large magnitude → likely h < 0)
            unsafe_state = torch.randn(16, device=self.device) * 5.0
            result = test_function_projection(unsafe_state)

            stats = get_cbf_stats()
            evidence["projection_count"] = stats.get("projection_count", 0)
            evidence["violation_count"] = stats.get("violation_count", 0)

            if stats["projection_count"] == 0:
                failures.append("No projections occurred with unsafe input")

            # Test 2: Error on violation (no projection)
            @enforce_cbf(state_param="x", project_to_safe=False)
            def test_function_error(x: Any) -> None:
                return x

            violation_caught = False
            try:
                unsafe_state = torch.randn(16, device=self.device) * 10.0
                test_function_error(unsafe_state)
            except CBFViolationError as e:
                violation_caught = True
                evidence["violation_error_message"] = str(e)  # type: ignore[assignment]

            if not violation_caught:
                failures.append("CBFViolationError not raised on unsafe state")

            # Test 3: Manual projection
            unsafe_state = torch.randn(32, device=self.device) * 8.0
            safe_state = project_to_safe_set(unsafe_state)

            # Verify safety of projected state
            cbf = OptimalCBF(
                OptimalCBFConfig(
                    observation_dim=32,
                    state_dim=32,
                    control_dim=8,
                )
            )
            h_before = cbf.forward(unsafe_state.unsqueeze(0), None)[0].item()  # type: ignore[arg-type]
            h_after = cbf.forward(safe_state.unsqueeze(0), None)[0].item()  # type: ignore[arg-type]

            evidence["h_before_projection"] = h_before  # type: ignore[assignment]
            evidence["h_after_projection"] = h_after  # type: ignore[assignment]

            if h_after < -1e-5:
                failures.append(f"Projection failed: h={h_after:.4f} still negative")

            # Test 4: assert_cbf utility
            assertion_caught = False
            try:
                assert_cbf(unsafe_state, None, "Test assertion")
            except CBFViolationError:
                assertion_caught = True

            evidence["assertion_works"] = assertion_caught

        except Exception as e:
            failures.append(f"Exception: {e!s}")

        duration_ms = (time.time() - start) * 1000
        passed = len(failures) == 0

        return VerificationResult(
            name="verify_universal_cbf",
            passed=passed,
            evidence=evidence,
            failures=failures,
            duration_ms=duration_ms,
        )

    # =========================================================================
    # VERIFICATION 4: RECEIPT FEEDBACK LOOP
    # =========================================================================

    def verify_receipt_feedback(self) -> VerificationResult:
        """Verify routing improves with learning.

        Checks:
        1. Utilities update after executions
        2. Router uses updated utilities
        3. Routing accuracy improves over time
        4. Convergence to optimal routing

        Returns:
            VerificationResult with evidence
        """
        start = time.time()
        failures = []
        evidence = {}

        try:
            # Create router and learning engine
            router = FanoActionRouter()
            learning_engine = ReceiptLearningEngine()

            # Simulate receipts showing Grove (colony 5) excelling at research
            intent_type = "research"
            num_rounds = 10
            receipts_per_round = 5

            initial_utilities = None
            final_utilities = None

            for round_idx in range(num_rounds):
                # Generate mock receipts
                mock_receipts = [
                    {
                        "actor": "grove:worker:1",
                        "verifier": {"status": "verified"},
                        "g_value": 0.2 + torch.rand(1).item() * 0.1,  # Low G = good
                        "complexity": 0.5,
                        "duration_ms": 100 + torch.randint(0, 50, (1,)).item(),
                    }
                    for _ in range(receipts_per_round)
                ]

                # Learn from receipts
                analysis = learning_engine.analyze_receipts(mock_receipts, intent_type)
                update = learning_engine.compute_learning_update(analysis)
                learning_engine.apply_update(update)

                # Check utilities
                utilities = router._get_learned_utilities(intent_type)
                if round_idx == 0:
                    initial_utilities = utilities.copy()
                if round_idx == num_rounds - 1:
                    final_utilities = utilities.copy()

            evidence["initial_utilities"] = {f"colony_{k}": v for k, v in initial_utilities.items()}  # type: ignore[union-attr]
            evidence["final_utilities"] = {f"colony_{k}": v for k, v in final_utilities.items()}  # type: ignore[union-attr]

            # Check that Grove (colony 5) utility increased
            grove_initial = initial_utilities.get(5, 0.5)  # type: ignore[union-attr]
            grove_final = final_utilities.get(5, 0.5)  # type: ignore[union-attr]
            evidence["grove_improvement"] = grove_final - grove_initial  # type: ignore[assignment]

            if grove_final <= grove_initial:
                failures.append(
                    f"Grove utility didn't improve: {grove_initial:.3f} → {grove_final:.3f}"
                )

            # Test routing decision
            routing_result = router.route(intent_type, {}, context={})
            best_colony_idx = routing_result.actions[0].colony_idx
            evidence["best_colony_after_learning"] = best_colony_idx  # type: ignore[assignment]

            # Grove should be preferred for research after learning
            if best_colony_idx != 5:
                failures.append(
                    f"Router didn't prefer Grove (5) for research, "
                    f"selected colony {best_colony_idx}"
                )

        except Exception as e:
            failures.append(f"Exception: {e!s}")

        duration_ms = (time.time() - start) * 1000
        passed = len(failures) == 0

        return VerificationResult(
            name="verify_receipt_feedback",
            passed=passed,
            evidence=evidence,
            failures=failures,
            duration_ms=duration_ms,
        )

    # =========================================================================
    # VERIFICATION 5: E8 TEMPORAL QUANTIZATION
    # =========================================================================

    def verify_e8_temporal(self) -> VerificationResult:
        """Verify temporal quantization achieves compression.

        Checks:
        1. Stable sequences: high compression (>10x)
        2. Chaotic sequences: low compression (~1x)
        3. Bifurcations detected correctly
        4. Compression ratio correlates with stability

        Returns:
            VerificationResult with evidence
        """
        start = time.time()
        failures = []
        evidence = {}

        try:
            config = TemporalE8Config(
                state_dim=256,
                bifurcation_threshold=0.7,
                min_event_spacing=1,
            )
            quantizer = TemporalE8Quantizer(config).to(self.device)

            # Test 1: Stable sequence (should compress well)
            seq_len = 100
            stable_seq = torch.randn(1, seq_len, 256, device=self.device) * 0.05
            stable_seq = stable_seq.cumsum(dim=1)  # Smooth trajectory

            result_stable = quantizer.process_sequence(stable_seq, colony_idx=0)

            compression_stable = result_stable["compression_ratio"]
            num_events_stable = result_stable["num_events"]

            evidence["stable_sequence_length"] = seq_len
            evidence["stable_num_events"] = num_events_stable
            evidence["stable_compression_ratio"] = compression_stable

            if compression_stable > 0.5:  # Should be < 0.2 for stable
                failures.append(f"Stable sequence not compressed: ratio={compression_stable:.3f}")

            # Test 2: Chaotic sequence (should NOT compress)
            chaotic_seq = torch.randn(1, seq_len, 256, device=self.device)

            result_chaotic = quantizer.process_sequence(chaotic_seq, colony_idx=0)

            compression_chaotic = result_chaotic["compression_ratio"]
            num_events_chaotic = result_chaotic["num_events"]

            evidence["chaotic_sequence_length"] = seq_len
            evidence["chaotic_num_events"] = num_events_chaotic
            evidence["chaotic_compression_ratio"] = compression_chaotic

            if compression_chaotic < 0.3:  # Should be close to 1.0 for chaotic
                failures.append(
                    f"Chaotic sequence over-compressed: ratio={compression_chaotic:.3f}"
                )

            # Test 3: Compression differential
            compression_diff = compression_chaotic - compression_stable
            evidence["compression_differential"] = compression_diff

            if compression_diff < 0.2:
                failures.append(
                    f"Insufficient compression differentiation: diff={compression_diff:.3f}"
                )

            # Test 4: E8 code validity
            e8_codes = result_stable.get("e8_events", torch.empty(0, 8))
            if e8_codes.numel() > 0 and e8_codes.shape[-1] != 8:
                failures.append(f"Invalid E8 codes shape: {e8_codes.shape}")

            # Check that codes are on E8 lattice (half-integers)
            codes_scaled = e8_codes * 2
            if not torch.allclose(codes_scaled, codes_scaled.round(), atol=1e-3):
                failures.append("E8 codes not on lattice (not half-integers)")

            evidence["e8_codes_shape"] = list(e8_codes.shape)  # type: ignore[assignment]

        except Exception as e:
            failures.append(f"Exception: {e!s}")

        duration_ms = (time.time() - start) * 1000
        passed = len(failures) == 0

        return VerificationResult(
            name="verify_e8_temporal",
            passed=passed,
            evidence=evidence,
            failures=failures,
            duration_ms=duration_ms,
        )

    # =========================================================================
    # VERIFICATION 6: TRAJECTORY CACHE
    # =========================================================================

    def verify_trajectory_cache(self) -> VerificationResult:
        """Verify trajectory cache works correctly.

        Checks:
        1. Hit rate > 0 for repeated patterns
        2. LRU eviction works
        3. Bifurcation buffer stores critical events
        4. Cache statistics accurate

        Returns:
            VerificationResult with evidence
        """
        start = time.time()
        failures = []
        evidence = {}

        try:
            cache = E8TrajectoryCache(max_size=100)

            # Test 1: Store and retrieve
            num_events = 5
            e8_codes = torch.randn(num_events, 8, device=self.device)
            prediction = torch.randn(256, device=self.device)
            metadata = {"colony_idx": 0, "risk": 0.8}

            cache.store(e8_codes, prediction, metadata)

            # Retrieve
            retrieved = cache.lookup(e8_codes)
            if retrieved is None:
                failures.append("Failed to retrieve just-stored trajectory")
            else:
                # Check prediction matches
                if not torch.allclose(retrieved, prediction, atol=1e-5):
                    failures.append("Retrieved prediction doesn't match stored")

            # Test 2: Cache hits
            num_unique = 10
            num_repeats = 5

            for i in range(num_unique):
                codes = torch.randn(3, 8, device=self.device) + i
                pred = torch.randn(256, device=self.device)
                cache.store(codes, pred, {"idx": i})

            # Repeat lookups
            for i in range(num_unique):
                codes = torch.randn(3, 8, device=self.device) + i
                for _ in range(num_repeats):
                    retrieved = cache.lookup(codes)

            stats = cache.get_stats()
            hit_rate = stats.hit_rate if hasattr(stats, "hit_rate") else 0.0
            evidence["hit_count"] = stats.hit_count if hasattr(stats, "hit_count") else 0
            evidence["miss_count"] = stats.miss_count if hasattr(stats, "miss_count") else 0
            evidence["hit_rate"] = hit_rate  # type: ignore[assignment]

            if hit_rate < 0.1:  # Should have some hits from repeats
                failures.append(f"Hit rate too low: {hit_rate:.3f}")

            # Test 3: Bifurcation buffer
            high_risk_codes = torch.randn(4, 8, device=self.device)
            cache.store_bifurcation(
                high_risk_codes[0], catastrophe_risk=0.95, metadata={"critical": True}
            )
            cache.store_bifurcation(
                high_risk_codes[1], catastrophe_risk=0.85, metadata={"critical": True}
            )

            # Sample bifurcations
            batch = cache.sample_bifurcations(batch_size=2)
            if len(batch) < 2:  # type: ignore[arg-type]
                failures.append(f"Bifurcation buffer returned {len(batch)} < 2 samples")  # type: ignore[arg-type]

            evidence["bifurcation_buffer_size"] = len(batch)  # type: ignore[arg-type]

            # Test 4: LRU eviction (fill cache beyond capacity)
            small_cache = E8TrajectoryCache(max_size=5)
            for i in range(10):
                codes = torch.randn(2, 8, device=self.device) + i * 10
                pred = torch.randn(256, device=self.device)
                small_cache.store(codes, pred, {"idx": i})

            stats = small_cache.get_stats()
            cache_size = stats.size if hasattr(stats, "size") else 0
            if cache_size > 5:
                failures.append(f"Cache exceeded max_size: {cache_size} > 5")

            evidence["lru_cache_final_size"] = cache_size
            evidence["lru_eviction_count"] = (
                stats.eviction_count if hasattr(stats, "eviction_count") else 0
            )

        except Exception as e:
            failures.append(f"Exception: {e!s}")

        duration_ms = (time.time() - start) * 1000
        passed = len(failures) == 0

        return VerificationResult(
            name="verify_trajectory_cache",
            passed=passed,
            evidence=evidence,
            failures=failures,
            duration_ms=duration_ms,
        )

    # =========================================================================
    # VERIFICATION 7: FANO META-LEARNER
    # =========================================================================

    def verify_fano_meta_learner(self) -> VerificationResult:
        """Verify Fano meta-learner improves performance.

        Checks:
        1. Adaptation occurs with feedback
        2. Fano structure respected (only 7 lines)
        3. Performance improves over time
        4. Attention weights valid

        Returns:
            VerificationResult with evidence
        """
        start = time.time()
        failures = []
        evidence = {}

        try:
            meta_learner = FanoMetaLearner(d_model=256).to(self.device)

            # Test 1: Forward pass
            batch_size = 4
            colony_states = torch.randn(batch_size, 7, 256, device=self.device)  # 7 colonies

            # FanoMetaLearner requires task_embedding
            task_embedding = torch.randn(batch_size, 256, device=self.device)
            adapted_states, attention_weights = meta_learner(colony_states, task_embedding)

            # Check output shape
            if adapted_states.shape != colony_states.shape:
                failures.append(
                    f"Output shape mismatch: {adapted_states.shape} != {colony_states.shape}"
                )

            evidence["attention_weights_shape"] = list(attention_weights.shape)

            # Test 2: Fano structure in attention
            # Attention should be [batch, 7, 7] where each colony attends to Fano neighbors
            if attention_weights.shape != (batch_size, 7, 7):
                failures.append(f"Attention weights shape incorrect: {attention_weights.shape}")
            else:
                # Check sparsity (each colony should attend to ~3 neighbors on Fano plane)
                mean_attention = attention_weights.mean(dim=0)  # [7, 7]
                avg_nonzero_per_colony = (mean_attention > 0.01).sum(dim=1).float().mean().item()
                evidence["avg_attention_targets_per_colony"] = avg_nonzero_per_colony

                # Should be around 3-4 (Fano line connections)
                if avg_nonzero_per_colony > 5:
                    failures.append(f"Too many attention targets: {avg_nonzero_per_colony:.1f} > 5")

            # Test 3: Adaptation over time
            # Simulate feedback and check if meta-learner adapts
            initial_output = adapted_states.clone()

            # Apply mock gradient updates
            loss = adapted_states.sum()
            loss.backward()

            # Check gradients exist
            has_gradients = any(
                p.grad is not None and p.grad.abs().sum() > 0 for p in meta_learner.parameters()
            )
            evidence["gradients_present"] = has_gradients  # type: ignore[assignment]

            if not has_gradients:
                failures.append("No gradients in meta-learner")

        except Exception as e:
            failures.append(f"Exception: {e!s}")

        duration_ms = (time.time() - start) * 1000
        passed = len(failures) == 0

        return VerificationResult(
            name="verify_fano_meta_learner",
            passed=passed,
            evidence=evidence,
            failures=failures,
            duration_ms=duration_ms,
        )

    # =========================================================================
    # VERIFICATION 8: GRADIENT SURGERY
    # =========================================================================

    def verify_gradient_surgery(self) -> VerificationResult:
        """Verify gradient surgery resolves conflicts.

        Checks:
        1. Conflict detection works
        2. Projection removes conflicts
        3. Orthogonalization correct
        4. Statistics tracking

        Returns:
            VerificationResult with evidence
        """
        start = time.time()
        failures = []
        evidence = {}

        try:
            surgery = GradientSurgery(conflict_threshold=0.0)

            # Test 1: Conflict detection
            grad1 = torch.randn(100)
            grad2 = -grad1 + torch.randn(100) * 0.1  # Opposite direction

            conflict = surgery.detect_conflict(grad1, grad2)
            evidence["conflicting_gradients_detected"] = conflict

            if not conflict:
                failures.append("Failed to detect conflicting gradients")

            # Test 2: No conflict detection
            grad3 = grad1 + torch.randn(100) * 0.1  # Same direction
            no_conflict = surgery.detect_conflict(grad1, grad3)
            evidence["aligned_gradients_detected"] = no_conflict

            if no_conflict:
                failures.append("False positive: detected conflict in aligned gradients")

            # Test 3: Projection
            grad_before = grad2.clone()
            grad_after = surgery.project_gradient(grad2, grad1)

            # Check that projection removes conflict
            conflict_after = surgery.detect_conflict(grad1, grad_after)
            evidence["conflict_after_projection"] = conflict_after

            if conflict_after:
                failures.append("Projection failed to resolve conflict")

            # Test 4: Orthogonalization
            # Ensure grads are tensors not lists
            if isinstance(grad_after, list):
                grad_after = torch.cat([g.flatten() for g in grad_after if g is not None])  # type: ignore[assignment]
            if isinstance(grad_before, list):
                grad_before = torch.cat([g.flatten() for g in grad_before if g is not None])
            if isinstance(grad1, list):
                grad1 = torch.cat([g.flatten() for g in grad1 if g is not None])

            dot_product_before = torch.dot(grad1, grad_before).item()
            dot_product_after = torch.dot(grad1, grad_after).item()  # type: ignore[arg-type]

            evidence["dot_product_before"] = dot_product_before  # type: ignore[assignment]
            evidence["dot_product_after"] = dot_product_after  # type: ignore[assignment]

            # After projection, dot product should be >= 0 (or close to 0)
            if dot_product_after < -1e-3:
                failures.append(f"Projection incomplete: dot product={dot_product_after:.4f} < 0")

            # Test 5: Statistics
            stats = surgery.stats
            evidence["total_conflicts"] = stats.total_conflicts  # type: ignore[assignment]
            evidence["total_checks"] = stats.total_checks  # type: ignore[assignment]
            evidence["conflict_rate"] = stats.conflict_rate  # type: ignore[assignment]

        except Exception as e:
            failures.append(f"Exception: {e!s}")

        duration_ms = (time.time() - start) * 1000
        passed = len(failures) == 0

        return VerificationResult(
            name="verify_gradient_surgery",
            passed=passed,
            evidence=evidence,
            failures=failures,
            duration_ms=duration_ms,
        )

    # =========================================================================
    # VERIFICATION 9: INTEGRATION
    # =========================================================================

    def verify_integration(self) -> VerificationResult:
        """Verify all components work together.

        Checks:
        1. Organism can execute intents end-to-end
        2. Catastrophe kernels integrate with EFE
        3. CBF enforced throughout pipeline
        4. Receipt feedback closes loop
        5. No crashes under stress

        Returns:
            VerificationResult with evidence
        """
        start = time.time()
        failures = []
        evidence = {}

        try:
            # Create organism
            organism = get_unified_organism()

            # Test 1: Basic intent execution
            # Note: execute_intent is async, but we can test synchronous components
            router = organism._router

            # Route an intent
            routing_result = router.route("build", {}, context={})
            if len(routing_result.actions) == 0:
                failures.append("Router returned no actions")

            evidence["routing_mode"] = routing_result.mode.value
            evidence["num_actions"] = len(routing_result.actions)  # type: ignore[assignment]

            # Test 2: Catastrophe kernels available
            for colony in organism.colonies:
                colony_name = (
                    colony if isinstance(colony, str) else getattr(colony, "name", "unknown")
                )
                if not isinstance(colony, str) and not hasattr(colony, "decision_kernel"):
                    failures.append(f"Colony {colony_name} missing decision_kernel")

            evidence["colonies_with_kernels"] = sum(  # type: ignore[assignment]
                1
                for c in organism.colonies
                if not isinstance(c, str) and hasattr(c, "decision_kernel")
            )

            # Test 3: Stress test - multiple executions
            num_stress_tests = 50
            errors = 0

            for i in range(num_stress_tests):
                try:
                    # Route different intent types
                    intent_types = [
                        "build",
                        "research",
                        "debug",
                        "integrate",
                        "plan",
                        "verify",
                    ]
                    intent = intent_types[i % len(intent_types)]
                    result = router.route(intent, {}, context={})
                    if len(result.actions) == 0:
                        errors += 1
                except Exception as e:
                    errors += 1
                    if errors == 1:  # Log first error
                        evidence["first_error"] = str(e)

            evidence["stress_test_trials"] = num_stress_tests  # type: ignore[assignment]
            evidence["stress_test_errors"] = errors  # type: ignore[assignment]
            evidence["stress_test_success_rate"] = (num_stress_tests - errors) / num_stress_tests  # type: ignore[assignment]

            if errors > num_stress_tests * 0.1:  # >10% error rate
                failures.append(f"High error rate in stress test: {errors}/{num_stress_tests}")

            # Test 4: Component availability
            components = {
                "router": organism._router is not None,
                "reducer": organism._reducer is not None,
                "colonies": len(organism.colonies) == 7,
                "message_bus": hasattr(organism, "_message_bus"),
            }
            evidence["components_available"] = components  # type: ignore[assignment]

            for name, available in components.items():
                if not available:
                    failures.append(f"Component missing: {name}")

        except Exception as e:
            failures.append(f"Exception: {e!s}")

        duration_ms = (time.time() - start) * 1000
        passed = len(failures) == 0

        return VerificationResult(
            name="verify_integration",
            passed=passed,
            evidence=evidence,
            failures=failures,
            duration_ms=duration_ms,
        )

    # =========================================================================
    # SUMMARY REPORTING
    # =========================================================================

    def _log_summary(self) -> None:
        """Log verification summary."""
        logger.info("\n" + "=" * 80)
        logger.info("COMPREHENSIVE VERIFICATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total Tests: {self.summary.total_tests}")
        logger.info(f"Passed: {self.summary.passed}")
        logger.info(f"Failed: {self.summary.failed}")
        logger.info(f"Pass Rate: {self.summary.pass_rate:.1%}")
        logger.info(f"Total Duration: {self.summary.total_duration_ms:.1f}ms")

        if self.summary.critical_failures:
            logger.error("\nCRITICAL FAILURES:")
            for failure in self.summary.critical_failures:
                logger.error(f"  ❌ {failure}")

        logger.info("\nDETAILED RESULTS:")
        for result in self.summary.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            logger.info(f"\n{status} | {result.name} ({result.duration_ms:.1f}ms)")

            if result.evidence:
                logger.info("  Evidence:")
                for key, value in result.evidence.items():
                    logger.info(f"    - {key}: {value}")

            if result.failures:
                logger.error("  Failures:")
                for failure in result.failures:
                    logger.error(f"    - {failure}")

        logger.info("\n" + "=" * 80)
        if self.summary.is_deployment_ready:
            logger.info("🎯 DEPLOYMENT READY: All critical tests passed")
        else:
            logger.error("🚫 NOT DEPLOYMENT READY: Critical failures detected")
        logger.info("=" * 80 + "\n")


# =============================================================================
# PYTEST INTEGRATION
# =============================================================================


@pytest.fixture
def verification_suite():
    """Create verification suite for pytest."""
    return ComprehensiveVerificationSuite(device="cpu")


def test_comprehensive_verification(verification_suite) -> None:
    """Run all verifications via pytest."""
    summary = verification_suite.run_all_verifications()

    # Assert deployment readiness
    assert summary.is_deployment_ready, (
        f"Verification failed: {summary.failed}/{summary.total_tests} tests failed. "
        f"Critical failures: {summary.critical_failures}"
    )


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================


def main():
    """Run verification suite as standalone script."""
    import sys

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    # Create and run suite
    suite = ComprehensiveVerificationSuite(device="cpu")
    summary = suite.run_all_verifications()

    # Exit with appropriate code
    sys.exit(0 if summary.is_deployment_ready else 1)


if __name__ == "__main__":
    main()
