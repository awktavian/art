"""Enhanced Safety Monitor with Failure Mode Detection.

CREATED: December 14, 2025
PURPOSE: Real-time detection and mitigation of all identified safety failure modes

This module extends cbf_monitor.py with comprehensive failure mode detection:
- Component failures (RSSM, EFE, meta-learning, strange loop)
- Compositional failures (feedback loops, emergent behavior)
- Data failures (OOD, adversarial, distributional shift)
- Implementation failures (numerical instability, gradients)
- Operational failures (monitor disabled, barrier untrained)

INTEGRATION:
============
```python
monitor = EnhancedSafetyMonitor()

# At every training step
status = monitor.check_all_failures({
    'rssm_trajectory': trajectory,
    'efe_weights': efe.weights,
    'barrier_values': h_values,
    'gradients': gradients,
    'mu_self': mu_trajectory,
})

if status['critical_failures']:
    emergency_shutdown()
elif status['warnings']:
    log_warnings(status['warnings'])
```

Reference: docs/self_SAFETY.md
"""

from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

import numpy as np
import torch
import torch.nn as nn

from kagami.core.safety.cbf_utils import (
    CompositeMonitor,
)

# SafetyStatus is not in cbf_monitor - using local definition
SafetyStatus = Literal["safe", "warning", "violation"]

logger = logging.getLogger(__name__)


# =============================================================================
# FAILURE MODE RESULTS
# =============================================================================


@dataclass
class FailureModeResult:
    """Result from a failure mode check."""

    failure_mode: str
    status: Literal["safe", "warning", "critical"]
    severity: Literal["MODERATE", "HIGH", "CRITICAL"]
    details: dict[str, Any] = field(default_factory=dict[str, Any])
    timestamp: float = field(default_factory=time.time)
    mitigation_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "failure_mode": self.failure_mode,
            "status": self.status,
            "severity": self.severity,
            "details": self.details,
            "timestamp": self.timestamp,
            "mitigation_action": self.mitigation_action,
        }


# =============================================================================
# COMPONENT FAILURE DETECTORS
# =============================================================================


class RSSMDivergenceDetector:
    """Detector for RSSM contractivity loss (α ≥ 1.0)."""

    def __init__(
        self,
        alpha_warning: float = 0.95,
        alpha_critical: float = 1.0,
        min_trajectory_length: int = 5,
    ):
        self.alpha_warning = alpha_warning
        self.alpha_critical = alpha_critical
        self.min_trajectory_length = min_trajectory_length
        self.alpha_history: deque[float] = deque(maxlen=100)

    def check(self, trajectory: list[torch.Tensor]) -> FailureModeResult:
        """Check for RSSM divergence.

        Args:
            trajectory: List of state tensors [μ_0, μ_1, ..., μ_n]

        Returns:
            FailureModeResult with contractivity status
        """
        if len(trajectory) < self.min_trajectory_length:
            return FailureModeResult(
                failure_mode="RSSM_DIVERGENCE",
                status="safe",
                severity="CRITICAL",
                details={"reason": "Insufficient trajectory length"},
            )

        # Compute distances
        distances = [
            torch.norm(trajectory[i + 1] - trajectory[i]).item() for i in range(len(trajectory) - 1)
        ]

        # Compute contractivity ratios
        ratios = []
        for i in range(1, len(distances)):
            if distances[i - 1] > 1e-8:
                ratio = distances[i] / distances[i - 1]
                if 0 < ratio < 2.0:  # Sanity check
                    ratios.append(ratio)

        if not ratios:
            return FailureModeResult(
                failure_mode="RSSM_DIVERGENCE",
                status="safe",
                severity="CRITICAL",
                details={"reason": "Cannot compute ratios"},
            )

        alpha = float(np.mean(ratios))
        self.alpha_history.append(alpha)

        # Determine status
        if alpha >= self.alpha_critical:
            status: Literal["safe", "warning", "critical"] = "critical"
            mitigation = "Freeze RSSM, rollback checkpoint, reduce LR by 10x"
        elif alpha >= self.alpha_warning:
            status = "warning"
            mitigation = "Monitor closely, consider reducing LR"
        else:
            status = "safe"
            mitigation = ""

        return FailureModeResult(
            failure_mode="RSSM_DIVERGENCE",
            status=status,
            severity="CRITICAL",
            details={
                "alpha": alpha,
                "alpha_mean_100": float(np.mean(self.alpha_history))
                if self.alpha_history
                else alpha,
                "alpha_std_100": float(np.std(self.alpha_history))
                if len(self.alpha_history) > 1
                else 0.0,
                "distances": distances[-5:],  # Last 5 distances
            },
            mitigation_action=mitigation,
        )


class CBFBarrierDegradationDetector:
    """Detector for CBF barrier degradation during meta-learning."""

    def __init__(
        self,
        baseline_mean: float = 0.3,
        baseline_variance: float = 0.1,
        mean_degradation_threshold: float = 0.8,  # 20% decrease
        variance_increase_threshold: float = 2.0,  # 2x increase
    ):
        self.baseline_mean = baseline_mean
        self.baseline_variance = baseline_variance
        self.mean_threshold = mean_degradation_threshold
        self.variance_threshold = variance_increase_threshold
        self.h_history: deque[float] = deque(maxlen=1000)

    def check(self, h_values: torch.Tensor | list[float]) -> FailureModeResult:
        """Check for barrier degradation.

        Args:
            h_values: Barrier values (can be single value or batch)

        Returns:
            FailureModeResult with degradation status
        """
        # Convert to list[Any]
        h_values_list: list[float]
        if isinstance(h_values, torch.Tensor):
            h_values_list = h_values.detach().cpu().numpy().flatten().tolist()
        else:
            h_values_list = h_values

        # Add to history
        self.h_history.extend(h_values_list)

        if len(self.h_history) < 10:
            return FailureModeResult(
                failure_mode="CBF_DEGRADATION",
                status="safe",
                severity="CRITICAL",
                details={"reason": "Insufficient history"},
            )

        # Compute statistics
        h_mean = float(np.mean(self.h_history))
        h_variance = float(np.var(self.h_history))

        # Check degradation
        warnings = []
        critical = False

        if h_mean < self.baseline_mean * self.mean_threshold:
            warnings.append(
                f"Mean decreased: {h_mean:.3f} < {self.baseline_mean * self.mean_threshold:.3f}"
            )
            if h_mean < 0.1:
                critical = True

        if h_variance > self.baseline_variance * self.variance_threshold:
            warnings.append(
                f"Variance increased: {h_variance:.3f} > {self.baseline_variance * self.variance_threshold:.3f}"
            )

        # Determine status
        if critical:
            status: Literal["safe", "warning", "critical"] = "critical"
            mitigation = "Freeze meta-learning, retrain barrier immediately"
        elif warnings:
            status = "warning"
            mitigation = "Monitor closely, prepare barrier retraining"
        else:
            status = "safe"
            mitigation = ""

        return FailureModeResult(
            failure_mode="CBF_DEGRADATION",
            status=status,
            severity="CRITICAL",
            details={
                "h_mean": h_mean,
                "h_variance": h_variance,
                "baseline_mean": self.baseline_mean,
                "baseline_variance": self.baseline_variance,
                "warnings": warnings,
            },
            mitigation_action=mitigation,
        )


class WeightExplosionDetector:
    """Detector for meta-learning weight explosion."""

    def __init__(
        self,
        warning_norm: float = 10.0,
        critical_norm: float = 100.0,
    ):
        self.warning_norm = warning_norm
        self.critical_norm = critical_norm
        self.norm_history: deque[float] = deque(maxlen=100)

    def check(self, weights: torch.Tensor | dict[str, torch.Tensor]) -> FailureModeResult:
        """Check for weight explosion.

        Args:
            weights: Weight tensor or dict[str, Any] of weight tensors

        Returns:
            FailureModeResult with explosion status
        """
        # Compute weight norm
        if isinstance(weights, dict):
            weight_norm = sum(torch.norm(w).item() ** 2 for w in weights.values()) ** 0.5
        else:
            weight_norm = torch.norm(weights).item()

        self.norm_history.append(weight_norm)

        # Determine status
        if weight_norm > self.critical_norm:
            status: Literal["safe", "warning", "critical"] = "critical"
            mitigation = "Clip weights to max_norm=5.0, reduce LR by 100x, rollback checkpoint"
        elif weight_norm > self.warning_norm:
            status = "warning"
            mitigation = "Monitor closely, verify gradient clipping enabled"
        else:
            status = "safe"
            mitigation = ""

        return FailureModeResult(
            failure_mode="WEIGHT_EXPLOSION",
            status=status,
            severity="HIGH",
            details={
                "weight_norm": weight_norm,
                "norm_mean_100": float(np.mean(self.norm_history))
                if self.norm_history
                else weight_norm,
                "norm_max_100": float(np.max(self.norm_history))
                if self.norm_history
                else weight_norm,
                "warning_norm": self.warning_norm,
                "critical_norm": self.critical_norm,
            },
            mitigation_action=mitigation,
        )


class StrangeLoopDivergenceDetector:
    """Detector for strange loop divergence despite theoretical guarantee."""

    def __init__(
        self,
        energy_increase_threshold: float = 0.3,  # 30% of steps
        min_trajectory_length: int = 10,
    ):
        self.energy_increase_threshold = energy_increase_threshold
        self.min_trajectory_length = min_trajectory_length

    def check(self, mu_trajectory: list[torch.Tensor]) -> FailureModeResult:
        """Check for strange loop divergence.

        Args:
            mu_trajectory: List of μ_self states

        Returns:
            FailureModeResult with divergence status
        """
        if len(mu_trajectory) < self.min_trajectory_length:
            return FailureModeResult(
                failure_mode="STRANGE_LOOP_DIVERGENCE",
                status="safe",
                severity="HIGH",
                details={"reason": "Insufficient trajectory length"},
            )

        # Compute Lyapunov energies
        energies = [(0.5 * torch.norm(mu) ** 2).item() for mu in mu_trajectory]

        # Count energy increases
        increases = sum(1 for i in range(1, len(energies)) if energies[i] > energies[i - 1])
        increase_rate = increases / len(energies)

        # Check distance convergence
        distances = [
            torch.norm(mu_trajectory[i + 1] - mu_trajectory[i]).item()
            for i in range(len(mu_trajectory) - 1)
        ]

        # Distance should decrease
        no_convergence = distances[-1] > distances[0] * 0.9

        # Determine status
        if no_convergence:
            status: Literal["safe", "warning", "critical"] = "critical"
            mitigation = "Reset to checkpoint, verify contractivity (α < 1)"
        elif increase_rate > self.energy_increase_threshold:
            status = "warning"
            mitigation = "Monitor Lyapunov energy, reduce meta-learning LR"
        else:
            status = "safe"
            mitigation = ""

        return FailureModeResult(
            failure_mode="STRANGE_LOOP_DIVERGENCE",
            status=status,
            severity="HIGH",
            details={
                "increase_rate": increase_rate,
                "energy_ratio": energies[-1] / energies[0] if energies[0] > 0 else 1.0,
                "distance_ratio": distances[-1] / distances[0] if distances[0] > 0 else 1.0,
                "convergence": not no_convergence,
            },
            mitigation_action=mitigation,
        )


# =============================================================================
# IMPLEMENTATION FAILURE DETECTORS
# =============================================================================


class NumericalInstabilityDetector:
    """Detector for NaN/Inf in computations."""

    def check(self, *tensors: torch.Tensor) -> FailureModeResult:
        """Check for NaN/Inf in tensors.

        Args:
            *tensors: Variable number of tensors to check

        Returns:
            FailureModeResult with numerical stability status
        """
        nan_detected = False
        inf_detected = False
        nan_tensors = []
        inf_tensors = []

        for i, tensor in enumerate(tensors):
            if torch.isnan(tensor).any():
                nan_detected = True
                nan_tensors.append(i)

            if torch.isinf(tensor).any():
                inf_detected = True
                inf_tensors.append(i)

        if nan_detected or inf_detected:
            return FailureModeResult(
                failure_mode="NUMERICAL_INSTABILITY",
                status="critical",
                severity="CRITICAL",
                details={
                    "nan_detected": nan_detected,
                    "inf_detected": inf_detected,
                    "nan_tensors": nan_tensors,
                    "inf_tensors": inf_tensors,
                },
                mitigation_action="Replace NaN/Inf with safe values, halt execution, save debug checkpoint",
            )

        return FailureModeResult(
            failure_mode="NUMERICAL_INSTABILITY",
            status="safe",
            severity="CRITICAL",
            details={},
        )


class GradientAnomalyDetector:
    """Detector for gradient explosion and vanishing."""

    def __init__(
        self,
        explosion_threshold: float = 100.0,
        explosion_warning: float = 10.0,
        vanishing_threshold: float = 1e-6,
    ):
        self.explosion_threshold = explosion_threshold
        self.explosion_warning = explosion_warning
        self.vanishing_threshold = vanishing_threshold

    def check(self, model: nn.Module) -> FailureModeResult:
        """Check for gradient anomalies.

        Args:
            model: PyTorch model with gradients

        Returns:
            FailureModeResult with gradient status
        """
        grad_norms = []
        for param in model.parameters():
            if param.grad is not None:
                grad_norms.append(param.grad.norm().item())

        if not grad_norms:
            return FailureModeResult(
                failure_mode="GRADIENT_ANOMALY",
                status="safe",
                severity="HIGH",
                details={"reason": "No gradients found"},
            )

        max_grad_norm = max(grad_norms)
        min_grad_norm = min(grad_norms)

        # Check for explosion
        if max_grad_norm > self.explosion_threshold:
            return FailureModeResult(
                failure_mode="GRADIENT_EXPLOSION",
                status="critical",
                severity="HIGH",
                details={
                    "max_grad_norm": max_grad_norm,
                    "explosion_threshold": self.explosion_threshold,
                },
                mitigation_action="Clip gradients, reduce LR by 10x, reinitialize if ||∇|| > 1e6",
            )

        if max_grad_norm > self.explosion_warning:
            return FailureModeResult(
                failure_mode="GRADIENT_EXPLOSION",
                status="warning",
                severity="HIGH",
                details={
                    "max_grad_norm": max_grad_norm,
                    "explosion_warning": self.explosion_warning,
                },
                mitigation_action="Monitor closely, verify gradient clipping enabled",
            )

        # Check for vanishing
        if min_grad_norm < self.vanishing_threshold:
            return FailureModeResult(
                failure_mode="GRADIENT_VANISHING",
                status="warning",
                severity="MODERATE",
                details={
                    "min_grad_norm": min_grad_norm,
                    "vanishing_threshold": self.vanishing_threshold,
                },
                mitigation_action="Increase LR or use different optimizer",
            )

        return FailureModeResult(
            failure_mode="GRADIENT_ANOMALY",
            status="safe",
            severity="HIGH",
            details={
                "max_grad_norm": max_grad_norm,
                "min_grad_norm": min_grad_norm,
            },
        )


# =============================================================================
# OPERATIONAL FAILURE DETECTORS
# =============================================================================


class MonitorHeartbeatDetector:
    """Detector for safety monitor being disabled."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.last_heartbeat: float = time.time()

    def heartbeat(self) -> None:
        """Record a heartbeat."""
        self.last_heartbeat = time.time()

    def check(self) -> FailureModeResult:
        """Check if monitor is responding.

        Returns:
            FailureModeResult with monitor status
        """
        current_time = time.time()
        time_since_heartbeat = current_time - self.last_heartbeat

        if time_since_heartbeat > self.timeout:
            return FailureModeResult(
                failure_mode="MONITOR_DISABLED",
                status="critical",
                severity="CRITICAL",
                details={
                    "time_since_heartbeat": time_since_heartbeat,
                    "timeout": self.timeout,
                },
                mitigation_action="Restart monitor, halt system if restart fails",
            )

        return FailureModeResult(
            failure_mode="MONITOR_DISABLED",
            status="safe",
            severity="CRITICAL",
            details={"time_since_heartbeat": time_since_heartbeat},
        )


class BarrierTrainingDetector:
    """Detector for untrained CBF barrier."""

    def check(self, barrier_model: nn.Module) -> FailureModeResult:
        """Check if barrier is trained.

        Args:
            barrier_model: Barrier neural network

        Returns:
            FailureModeResult with training status
        """
        # Compute weight norm
        weight_norm = sum(torch.norm(p).item() ** 2 for p in barrier_model.parameters()) ** 0.5

        # Compute expected initialization norm
        num_params = sum(p.numel() for p in barrier_model.parameters())
        expected_init_norm = num_params**0.5

        # Check if weights are close to initialization
        if abs(weight_norm - expected_init_norm) < 1.0:
            return FailureModeResult(
                failure_mode="BARRIER_UNTRAINED",
                status="critical",
                severity="CRITICAL",
                details={
                    "weight_norm": weight_norm,
                    "expected_init_norm": expected_init_norm,
                },
                mitigation_action="Refuse to run, load pretrained barrier if available",
            )

        return FailureModeResult(
            failure_mode="BARRIER_UNTRAINED",
            status="safe",
            severity="CRITICAL",
            details={
                "weight_norm": weight_norm,
                "num_params": num_params,
            },
        )


# =============================================================================
# ENHANCED SAFETY MONITOR
# =============================================================================


class EnhancedSafetyMonitor:
    """Enhanced safety monitor with comprehensive failure mode detection.

    Combines CBF monitoring with failure mode detection across all categories.

    Args:
        enable_cbf: Enable CBF barrier monitoring
        enable_component_checks: Enable component failure detection
        enable_implementation_checks: Enable implementation failure detection
        enable_operational_checks: Enable operational failure detection
    """

    def __init__(
        self,
        enable_cbf: bool = True,
        enable_component_checks: bool = True,
        enable_implementation_checks: bool = True,
        enable_operational_checks: bool = True,
    ):
        # Base CBF monitor
        self.cbf_monitor = CompositeMonitor() if enable_cbf else None

        # Component failure detectors
        self.rssm_detector: RSSMDivergenceDetector | None
        self.cbf_degradation_detector: CBFBarrierDegradationDetector | None
        self.weight_explosion_detector: WeightExplosionDetector | None
        self.strange_loop_detector: StrangeLoopDivergenceDetector | None

        if enable_component_checks:
            self.rssm_detector = RSSMDivergenceDetector()
            self.cbf_degradation_detector = CBFBarrierDegradationDetector()
            self.weight_explosion_detector = WeightExplosionDetector()
            self.strange_loop_detector = StrangeLoopDivergenceDetector()
        else:
            self.rssm_detector = None
            self.cbf_degradation_detector = None
            self.weight_explosion_detector = None
            self.strange_loop_detector = None

        # Implementation failure detectors
        self.numerical_detector: NumericalInstabilityDetector | None
        self.gradient_detector: GradientAnomalyDetector | None

        if enable_implementation_checks:
            self.numerical_detector = NumericalInstabilityDetector()
            self.gradient_detector = GradientAnomalyDetector()
        else:
            self.numerical_detector = None
            self.gradient_detector = None

        # Operational failure detectors
        self.heartbeat_detector: MonitorHeartbeatDetector | None
        self.barrier_training_detector: BarrierTrainingDetector | None

        if enable_operational_checks:
            self.heartbeat_detector = MonitorHeartbeatDetector()
            self.barrier_training_detector = BarrierTrainingDetector()
        else:
            self.heartbeat_detector = None
            self.barrier_training_detector = None

        # Failure history
        self.failure_history: deque[FailureModeResult] = deque(maxlen=1000)

    def check_all_failures(
        self,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Check all failure modes.

        Args:
            inputs: Dictionary with keys:
                - 'rssm_trajectory': List[Tensor] for RSSM divergence
                - 'h_values': Tensor for CBF degradation
                - 'efe_weights': Tensor for weight explosion
                - 'mu_trajectory': List[Tensor] for strange loop
                - 'tensors': List[Tensor] for numerical stability
                - 'model': nn.Module for gradient checks
                - 'barrier_model': nn.Module for training check

        Returns:
            Dictionary with:
                - 'critical_failures': List of critical failures
                - 'warnings': List of warnings
                - 'safe': List of safe checks
                - 'overall_status': "safe", "warning", or "critical"
                - 'mitigations': List of recommended mitigations
        """
        results = []

        # Component checks
        if self.rssm_detector and "rssm_trajectory" in inputs:
            result = self.rssm_detector.check(inputs["rssm_trajectory"])
            results.append(result)
            self.failure_history.append(result)

        if self.cbf_degradation_detector and "h_values" in inputs:
            result = self.cbf_degradation_detector.check(inputs["h_values"])
            results.append(result)
            self.failure_history.append(result)

        if self.weight_explosion_detector and "efe_weights" in inputs:
            result = self.weight_explosion_detector.check(inputs["efe_weights"])
            results.append(result)
            self.failure_history.append(result)

        if self.strange_loop_detector and "mu_trajectory" in inputs:
            result = self.strange_loop_detector.check(inputs["mu_trajectory"])
            results.append(result)
            self.failure_history.append(result)

        # Implementation checks
        if self.numerical_detector and "tensors" in inputs:
            result = self.numerical_detector.check(*inputs["tensors"])
            results.append(result)
            self.failure_history.append(result)

        if self.gradient_detector and "model" in inputs:
            result = self.gradient_detector.check(inputs["model"])
            results.append(result)
            self.failure_history.append(result)

        # Operational checks
        if self.heartbeat_detector:
            self.heartbeat_detector.heartbeat()  # Record heartbeat
            result = self.heartbeat_detector.check()
            results.append(result)
            self.failure_history.append(result)

        if self.barrier_training_detector and "barrier_model" in inputs:
            result = self.barrier_training_detector.check(inputs["barrier_model"])
            results.append(result)
            self.failure_history.append(result)

        # Categorize results
        critical_failures = [r for r in results if r.status == "critical"]
        warnings = [r for r in results if r.status == "warning"]
        safe = [r for r in results if r.status == "safe"]

        # Determine overall status
        if critical_failures:
            overall_status = "critical"
        elif warnings:
            overall_status = "warning"
        else:
            overall_status = "safe"

        # Collect mitigations
        mitigations = [r.mitigation_action for r in results if r.mitigation_action]

        return {
            "critical_failures": [r.to_dict() for r in critical_failures],
            "warnings": [r.to_dict() for r in warnings],
            "safe": [r.to_dict() for r in safe],
            "overall_status": overall_status,
            "mitigations": mitigations,
            "timestamp": time.time(),
        }

    def report(self) -> dict[str, Any]:
        """Generate comprehensive safety report.

        Returns:
            Dictionary with failure mode statistics
        """
        if not self.failure_history:
            return {
                "total_checks": 0,
                "critical_count": 0,
                "warning_count": 0,
                "safe_count": 0,
            }

        critical_count = sum(1 for r in self.failure_history if r.status == "critical")
        warning_count = sum(1 for r in self.failure_history if r.status == "warning")
        safe_count = sum(1 for r in self.failure_history if r.status == "safe")

        # Per-failure-mode breakdown
        failure_mode_counts = {}
        for result in self.failure_history:
            mode = result.failure_mode
            if mode not in failure_mode_counts:
                failure_mode_counts[mode] = {"critical": 0, "warning": 0, "safe": 0}
            failure_mode_counts[mode][result.status] += 1

        return {
            "total_checks": len(self.failure_history),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "safe_count": safe_count,
            "critical_rate": critical_count / len(self.failure_history),
            "warning_rate": warning_count / len(self.failure_history),
            "failure_mode_breakdown": failure_mode_counts,
        }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "BarrierTrainingDetector",
    "CBFBarrierDegradationDetector",
    "EnhancedSafetyMonitor",
    "FailureModeResult",
    "GradientAnomalyDetector",
    "MonitorHeartbeatDetector",
    "NumericalInstabilityDetector",
    "RSSMDivergenceDetector",
    "StrangeLoopDivergenceDetector",
    "WeightExplosionDetector",
]
