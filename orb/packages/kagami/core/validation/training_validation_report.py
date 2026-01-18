"""Training Validation Report Generator for K OS.

Combines benchmark results, integration metrics, and safety audits into a
comprehensive post-training validation report with pass/fail verdict.

This module integrates:
1. BenchmarkRunner.full_benchmark() - performance metrics
2. IntegrationValidator.generate_report() - system integration metrics
3. TrainingMonitor health diagnostics - safety audit

Created: December 14, 2025
Purpose: Comprehensive training validation with quality gates
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TrainingValidationReport:
    """Comprehensive training validation report with pass/fail verdict.

    Integrates benchmark results, integration metrics, and safety audits
    into a single validation report for post-training assessment.

    Quality Gates (PASS criteria):
    - prediction_mse < 0.05
    - reconstruction_r2 > 0.85
    - integration_score > 0.7
    - cbf_violations < 100
    - converged == True
    """

    # Training summary
    model_size: str
    total_steps: int
    final_loss: float
    converged: bool
    plateau_detected: bool

    # Benchmark metrics (from BenchmarkRunner.full_benchmark())
    prediction_mse: float
    reconstruction_r2: float
    temporal_coherence: float
    compression_ratio: float

    # Integration metrics (from IntegrationValidator)
    integration_score: float
    integration_interpretation: str

    # Safety audit (from TrainingMonitor)
    cbf_violations: int
    gradient_explosions: int
    recovery_attempts: int

    # Metadata
    timestamp: float = field(default_factory=time.time)

    # Quality gate thresholds
    PREDICTION_MSE_THRESHOLD: float = field(default=0.05, repr=False)
    RECONSTRUCTION_R2_THRESHOLD: float = field(default=0.85, repr=False)
    INTEGRATION_SCORE_THRESHOLD: float = field(default=0.7, repr=False)
    CBF_VIOLATIONS_THRESHOLD: int = field(default=100, repr=False)

    def passes_quality_gates(self) -> bool:
        """Check if training passes all quality gates.

        Returns:
            True if all quality criteria are met, False otherwise.
        """
        return (
            self.prediction_mse < self.PREDICTION_MSE_THRESHOLD
            and self.reconstruction_r2 > self.RECONSTRUCTION_R2_THRESHOLD
            and self.integration_score > self.INTEGRATION_SCORE_THRESHOLD
            and self.cbf_violations < self.CBF_VIOLATIONS_THRESHOLD
            and self.converged
        )

    def _generate_conclusion(self) -> str:
        """Generate pass/fail verdict with reasoning.

        Returns:
            Formatted conclusion string with verdict and details.
        """
        if self.passes_quality_gates():
            return (
                "✅ **PASS** - Training validation successful\n\n"
                "All quality gates satisfied:\n"
                f"  - Prediction accuracy: {self.prediction_mse:.4f} < {self.PREDICTION_MSE_THRESHOLD}\n"
                f"  - Reconstruction quality: {self.reconstruction_r2:.4f} > {self.RECONSTRUCTION_R2_THRESHOLD}\n"
                f"  - System integration: {self.integration_score:.4f} > {self.INTEGRATION_SCORE_THRESHOLD}\n"
                f"  - Safety violations: {self.cbf_violations} < {self.CBF_VIOLATIONS_THRESHOLD}\n"
                "  - Training converged successfully\n\n"
                "Model is ready for deployment."
            )

        # Failed - determine primary failure reasons
        failures = []

        if not self.converged:
            failures.append("Training did not converge")

        if self.prediction_mse >= self.PREDICTION_MSE_THRESHOLD:
            failures.append(
                f"Prediction MSE too high: {self.prediction_mse:.4f} >= {self.PREDICTION_MSE_THRESHOLD}"
            )

        if self.reconstruction_r2 <= self.RECONSTRUCTION_R2_THRESHOLD:
            failures.append(
                f"Reconstruction R² too low: {self.reconstruction_r2:.4f} <= {self.RECONSTRUCTION_R2_THRESHOLD}"
            )

        if self.integration_score <= self.INTEGRATION_SCORE_THRESHOLD:
            failures.append(
                f"Integration score too low: {self.integration_score:.4f} <= {self.INTEGRATION_SCORE_THRESHOLD}"
            )

        if self.cbf_violations >= self.CBF_VIOLATIONS_THRESHOLD:
            failures.append(
                f"Too many safety violations: {self.cbf_violations} >= {self.CBF_VIOLATIONS_THRESHOLD}"
            )

        failure_list = "\n".join(f"  - {failure}" for failure in failures)

        return (
            f"❌ **FAIL** - Training validation failed ({len(failures)} issues)\n\n"
            "Quality gate failures:\n"
            f"{failure_list}\n\n"
            "Model requires additional training or architecture adjustments."
        )

    def generate_markdown(self) -> str:
        """Generate comprehensive markdown report.

        Returns:
            Formatted markdown report string.
        """
        verdict = "PASS" if self.passes_quality_gates() else "FAIL"
        verdict_emoji = "✅" if self.passes_quality_gates() else "❌"

        report = f"""# Training Validation Report: {self.model_size}

**Status**: {verdict_emoji} **{verdict}**

**Generated**: {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp))}

---

## Training Summary

| Metric | Value | Status |
|--------|-------|--------|
| Total Steps | {self.total_steps:,} | - |
| Final Loss | {self.final_loss:.4f} | - |
| Convergence | {"✅ YES" if self.converged else "❌ NO"} | {"✅" if self.converged else "❌"} |
| Plateau Detected | {"Yes" if self.plateau_detected else "No"} | - |

---

## Benchmark Results

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Prediction MSE** | {self.prediction_mse:.4f} | < {self.PREDICTION_MSE_THRESHOLD} | {"✅" if self.prediction_mse < self.PREDICTION_MSE_THRESHOLD else "❌"} |
| **Reconstruction R²** | {self.reconstruction_r2:.4f} | > {self.RECONSTRUCTION_R2_THRESHOLD} | {"✅" if self.reconstruction_r2 > self.RECONSTRUCTION_R2_THRESHOLD else "❌"} |
| **Temporal Coherence** | {self.temporal_coherence:.4f} | - | - |
| **Compression Ratio** | {self.compression_ratio:.2f}x | - | - |

### Interpretation

- **Prediction MSE**: Lower is better. Measures next-step prediction accuracy.
- **Reconstruction R²**: Higher is better. Measures reconstruction quality (0-1).
- **Temporal Coherence**: Cosine similarity between consecutive outputs (0-1).
- **Compression Ratio**: Input dimension / latent dimension.

---

## Integration Metrics

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| **Integration Score** | {self.integration_score:.4f} | > {self.INTEGRATION_SCORE_THRESHOLD} | {"✅" if self.integration_score > self.INTEGRATION_SCORE_THRESHOLD else "❌"} |

**Interpretation**: {self.integration_interpretation}

### What This Means

The integration score measures how well the world model maintains coherent internal
dynamics across the PXO (Perception-Transformation-Action) manifold. It combines:

- Information integration (H(whole) - H(parts))
- Self-recognition capability
- Metacognitive accuracy
- Temporal stability

High integration (> 0.7) indicates the model has learned a unified world representation
rather than disconnected feature extractors.

---

## Safety Audit

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| **CBF Violations** | {self.cbf_violations} | < {self.CBF_VIOLATIONS_THRESHOLD} | {"✅" if self.cbf_violations < self.CBF_VIOLATIONS_THRESHOLD else "❌"} |
| **Gradient Explosions** | {self.gradient_explosions} | - | {"⚠️" if self.gradient_explosions > 10 else "✅"} |
| **Recovery Attempts** | {self.recovery_attempts} | - | {"⚠️" if self.recovery_attempts > 5 else "✅"} |

### Safety Status

{"✅ **SAFE** - No critical safety violations detected." if self.cbf_violations < self.CBF_VIOLATIONS_THRESHOLD else f"⚠️ **WARNING** - {self.cbf_violations} CBF violations detected. Model may exhibit unsafe behavior."}

{"" if self.gradient_explosions <= 10 else f"⚠️ Training exhibited {self.gradient_explosions} gradient explosions, indicating numerical instability."}

{"" if self.recovery_attempts <= 5 else f"⚠️ Required {self.recovery_attempts} recovery attempts, suggesting unstable training dynamics."}

---

## Conclusion

{self._generate_conclusion()}

---

## Recommendations

"""

        # Add targeted recommendations based on failure modes
        recommendations = []

        if not self.converged:
            recommendations.append(
                "- **Convergence**: Increase training steps or adjust learning rate schedule."
            )

        if self.prediction_mse >= self.PREDICTION_MSE_THRESHOLD:
            recommendations.append(
                "- **Prediction Accuracy**: Consider increasing model capacity or improving "
                "dynamics loss weighting."
            )

        if self.reconstruction_r2 <= self.RECONSTRUCTION_R2_THRESHOLD:
            recommendations.append(
                "- **Reconstruction Quality**: Increase autoencoder capacity or reduce "
                "information bottleneck strength."
            )

        if self.integration_score <= self.INTEGRATION_SCORE_THRESHOLD:
            recommendations.append(
                "- **Integration**: Strengthen cross-branch coupling or increase training duration "
                "to develop unified representations."
            )

        if self.cbf_violations >= self.CBF_VIOLATIONS_THRESHOLD:
            recommendations.append(
                "- **Safety**: Review CBF constraint parameters or add gradient clipping. "
                "High violation count suggests model may violate safety invariants."
            )

        if self.gradient_explosions > 10:
            recommendations.append(
                "- **Numerical Stability**: Reduce learning rate, add stronger gradient clipping, "
                "or normalize inputs."
            )

        if recommendations:
            report += "\n".join(recommendations)
        else:
            report += "No specific recommendations - all metrics within acceptable ranges."

        report += "\n\n---\n\n*Report generated by K OS Training Validation System*\n"

        return report

    def save(self, path: Path | str) -> None:
        """Save report to markdown file.

        Args:
            path: Output file path (will be created if it doesn't exist).
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        markdown = self.generate_markdown()
        path.write_text(markdown)

    def to_json(self) -> dict[str, Any]:
        """Convert report to JSON-serializable dictionary.

        Returns:
            Dictionary containing all report data for programmatic access.
        """
        return {
            "model_size": self.model_size,
            "total_steps": self.total_steps,
            "final_loss": self.final_loss,
            "converged": self.converged,
            "plateau_detected": self.plateau_detected,
            "benchmark_metrics": {
                "prediction_mse": self.prediction_mse,
                "reconstruction_r2": self.reconstruction_r2,
                "temporal_coherence": self.temporal_coherence,
                "compression_ratio": self.compression_ratio,
            },
            "integration_metrics": {
                "integration_score": self.integration_score,
                "interpretation": self.integration_interpretation,
            },
            "safety_audit": {
                "cbf_violations": self.cbf_violations,
                "gradient_explosions": self.gradient_explosions,
                "recovery_attempts": self.recovery_attempts,
            },
            "quality_gates": {
                "passed": self.passes_quality_gates(),
                "thresholds": {
                    "prediction_mse": self.PREDICTION_MSE_THRESHOLD,
                    "reconstruction_r2": self.RECONSTRUCTION_R2_THRESHOLD,
                    "integration_score": self.INTEGRATION_SCORE_THRESHOLD,
                    "cbf_violations": self.CBF_VIOLATIONS_THRESHOLD,
                },
            },
            "timestamp": self.timestamp,
        }

    def save_json(self, path: Path | str) -> None:
        """Save report as JSON for programmatic processing.

        Args:
            path: Output JSON file path.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w") as f:
            json.dump(self.to_json(), f, indent=2)


def create_validation_report_from_training(
    model_size: str,
    total_steps: int,
    final_loss: float,
    benchmark_result: Any,  # FullBenchmarkResult
    integration_metrics: Any,  # SystemIntegrationMetrics
    training_monitor: Any,  # TrainingMonitor
) -> TrainingValidationReport:
    """Create validation report from training components.

    This is the primary factory function for generating reports after training.

    Args:
        model_size: Model size identifier (e.g., "base", "large").
        total_steps: Total training steps completed.
        final_loss: Final training loss value.
        benchmark_result: FullBenchmarkResult from BenchmarkRunner.full_benchmark().
        integration_metrics: SystemIntegrationMetrics from IntegrationValidator.
        training_monitor: TrainingMonitor instance with health diagnostics.

    Returns:
        Complete TrainingValidationReport ready for generation.

    Example:
        ```python
        # After training completes
        benchmark_result = benchmark_runner.full_benchmark()
        integration_metrics = integration_validator.measure_system_integration()

        report = create_validation_report_from_training(
            model_size="base",
            total_steps=trainer.global_step,
            final_loss=final_loss,
            benchmark_result=benchmark_result,
            integration_metrics=integration_metrics,
            training_monitor=trainer.training_monitor,
        )

        report.save("artifacts/validation_report.md")
        print(report.generate_markdown())
        ```
    """
    # Extract benchmark metrics
    prediction_mse = getattr(benchmark_result, "dynamics_prediction_mse", 0.0)
    reconstruction_r2 = getattr(benchmark_result, "prediction_r2", 0.0)
    temporal_coherence = getattr(benchmark_result, "temporal_coherence", 0.0)
    compression_ratio = getattr(benchmark_result, "compression_ratio", 0.0)

    # Extract integration metrics
    integration_score = getattr(integration_metrics, "system_integration_score", 0.0)
    integration_interpretation = getattr(
        integration_metrics,
        "interpretation",
        "No integration metrics available",
    )

    # Extract safety audit from training monitor
    # Note: CBF violations tracked separately in world model safety layer
    # Here we use divergence_events as proxy for safety violations
    cbf_violations = getattr(training_monitor, "divergence_events", 0)

    # Count gradient explosions from loss history
    # A gradient explosion is when loss jumps by >10x or becomes NaN/Inf
    gradient_explosions = 0
    loss_history = getattr(training_monitor, "loss_history", [])
    for i in range(1, len(loss_history)):
        if (
            loss_history[i] > loss_history[i - 1] * 10
            or math.isnan(loss_history[i])
            or math.isinf(loss_history[i])
        ):
            gradient_explosions += 1

    recovery_attempts = getattr(training_monitor, "recovery_attempts", 0)

    # Determine convergence and plateau status
    # Training converged if we didn't hit max recovery attempts
    converged = recovery_attempts < 3

    # Plateau detected from monitor's plateau tracking
    plateau_detected = getattr(training_monitor, "steps_since_improvement", 0) >= getattr(
        training_monitor, "plateau_patience", 100
    )

    return TrainingValidationReport(
        model_size=model_size,
        total_steps=total_steps,
        final_loss=final_loss,
        converged=converged,
        plateau_detected=plateau_detected,
        prediction_mse=prediction_mse,
        reconstruction_r2=reconstruction_r2,
        temporal_coherence=temporal_coherence,
        compression_ratio=compression_ratio,
        integration_score=integration_score,
        integration_interpretation=integration_interpretation,
        cbf_violations=cbf_violations,
        gradient_explosions=gradient_explosions,
        recovery_attempts=recovery_attempts,
    )


# Export
__all__ = [
    "TrainingValidationReport",
    "create_validation_report_from_training",
]
