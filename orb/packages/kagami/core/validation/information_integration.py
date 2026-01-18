"""Information Integration Measurement for K OS.

Implements entropy-based measurement to quantify information integration in PXO architecture.
Measures how much information the system generates as a whole, beyond what its parts
generate independently. Used for system monitoring, error detection, and integrity checking.

Mathematical formulation:
    Integration = H(whole) - H(parts)

    Where:
    - H(whole): Entropy of the combined system state
    - H(parts): Sum of entropies of independent subsystems

For PXO:
    - System state: (H¹⁴, S⁷) geometric representation
    - Parts: Hyperbolic branch, Octonion branch
    - Integration: Coupling strength between geometric manifolds

Note:
    This measures statistical dependencies between system components.
    Higher integration indicates tighter coupling between H¹⁴ and S⁷ branches.
    NO claims are made about consciousness or sentience.

Created: November 3, 2025
Updated: November 30, 2025 - Information integration measurement (entropy-based, not IIT)
Purpose: Measure system integration and detect anomalies in PXO architecture
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class IntegrationMeasurement:
    """Information integration measurement result."""

    integration_value: float  # Integration = H(whole) - H(parts)
    whole_entropy: float  # H(whole system)
    parts_entropy: float  # H(parts independently)
    coupling_strength: float  # Cross-correlation between branches
    timestamp: float
    layer_id: int | None = None


class InformationIntegrationMeasure:
    """Information integration measurement for PXO.

    Computes integration to measure information coupling in geometric reasoning system.

    Usage:
        measure = InformationIntegrationMeasure(pxo_model)

        # Measure over sequence
        states = [...]  # List of (H¹⁴, S⁷) states
        result = measure.compute_integration(states)

        # Interpret
        if result.integration_value < baseline * 0.6:
            print("Low integration - possible system error")
    """

    def __init__(
        self,
        pxo_model: nn.Module | None = None,
        device: str | None = None,
    ) -> None:
        """Initialize integration measurement.

        Args:
            pxo_model: PXO transformer to measure
            device: Computation device
        """
        self.pxo_model = pxo_model
        self.device = device or ("mps" if torch.backends.mps.is_available() else "cpu")

        # History for temporal integration
        self.state_history: list[tuple[torch.Tensor, torch.Tensor]] = []
        self.max_history = 100

        logger.debug("Information integration measurement initialized")

    def compute_integration(
        self,
        hyperbolic_states: torch.Tensor,
        octonion_states: torch.Tensor,
    ) -> IntegrationMeasurement:
        """Compute information integration for (H¹⁴, S⁷) states.

        Uses entropy difference: Integration = H(whole) - H(parts)
        This measures how much the joint distribution differs from
        the product of marginal distributions.

        Args:
            hyperbolic_states: Sequence of H¹⁴ states [T, B, d_h]
            octonion_states: Sequence of S⁷ states [T, B, d_o]

        Returns:
            Integration measurement
        """
        import time

        _T, _B, _d_h = hyperbolic_states.shape
        _, _, _d_o = octonion_states.shape

        # Store in history
        self.state_history.append((hyperbolic_states[-1], octonion_states[-1]))
        if len(self.state_history) > self.max_history:
            self.state_history = self.state_history[-self.max_history :]

        # Compute whole system entropy
        # Concatenate H¹⁴ and S⁷ for joint distribution
        whole_states = torch.cat([hyperbolic_states, octonion_states], dim=-1)  # [T, B, d_h + d_o]

        whole_entropy = self._compute_entropy(whole_states)

        # Compute parts entropy (independent)
        hyp_entropy = self._compute_entropy(hyperbolic_states)
        oct_entropy = self._compute_entropy(octonion_states)
        parts_entropy = hyp_entropy + oct_entropy

        # Integration = H(whole) - H(parts)
        # Positive when parts are correlated (whole has less entropy than sum of parts)
        integration_value = max(0.0, float(whole_entropy - parts_entropy))

        # Compute coupling strength (cross-correlation between branches)
        coupling_strength = self._compute_coupling(hyperbolic_states, octonion_states)

        measurement = IntegrationMeasurement(
            integration_value=integration_value,
            whole_entropy=float(whole_entropy),
            parts_entropy=float(parts_entropy),
            coupling_strength=float(coupling_strength),
            timestamp=time.time(),
        )

        logger.info(
            f"📊 Integration = {measurement.integration_value:.4f} "
            f"(whole={whole_entropy:.4f}, parts={parts_entropy:.4f}, "
            f"coupling={coupling_strength:.4f})"
        )

        return measurement

    def _compute_entropy(self, states: torch.Tensor) -> torch.Tensor:
        """Compute entropy of state distribution via Gaussian approximation.

        Args:
            states: [T, B, D] state sequence

        Returns:
            Entropy scalar
        """
        T, B, D = states.shape

        # Flatten temporal and batch
        states_flat = states.reshape(-1, D)  # [T*B, D]

        # Estimate entropy via Gaussian approximation
        # H(X) ≈ 0.5 * log((2πe)^D * det(Σ))
        mean = states_flat.mean(dim=0, keepdim=True)
        centered = states_flat - mean
        cov = (centered.T @ centered) / (T * B - 1)

        # Add regularization for numerical stability
        cov = cov + torch.eye(D, device=cov.device) * 1e-6

        # Entropy via log determinant
        _sign, logdet = torch.slogdet(cov)
        entropy = 0.5 * (D * torch.log(2 * torch.tensor(3.14159265) * torch.e) + logdet)

        return entropy

    def _compute_coupling(
        self,
        hyp_states: torch.Tensor,
        oct_states: torch.Tensor,
    ) -> torch.Tensor:
        """Compute coupling strength between branches via cross-correlation.

        Args:
            hyp_states: [T, B, d_h] hyperbolic states
            oct_states: [T, B, d_o] octonion states

        Returns:
            Coupling strength (0-1)
        """
        _T, _B, d_h = hyp_states.shape
        _, _, d_o = oct_states.shape

        # Flatten
        hyp_flat = hyp_states.reshape(-1, d_h)
        oct_flat = oct_states.reshape(-1, d_o)

        # Compute cross-correlation
        hyp_centered = hyp_flat - hyp_flat.mean(dim=0, keepdim=True)
        oct_centered = oct_flat - oct_flat.mean(dim=0, keepdim=True)

        # Normalize
        hyp_norm = F.normalize(hyp_centered, dim=-1)
        oct_norm = F.normalize(oct_centered, dim=-1)

        # Align feature dimensions if branches differ (e.g., H¹⁴ vs S⁷)
        if hyp_norm.shape[-1] != oct_norm.shape[-1]:
            diff = hyp_norm.shape[-1] - oct_norm.shape[-1]
            if diff > 0:
                oct_norm = F.pad(oct_norm, (0, diff))
            else:
                hyp_norm = F.pad(hyp_norm, (0, -diff))

        # Cross-correlation
        cross_corr = torch.abs(hyp_norm @ oct_norm.T)  # [T*B, T*B]

        # Coupling = mean correlation (how much branches predict each other)
        coupling = cross_corr.mean()

        return coupling

    def measure_integration_metrics(
        self,
        pxo_states: list[tuple[torch.Tensor, torch.Tensor]],
        threshold: float = 1.0,
    ) -> dict[str, Any]:
        """Comprehensive integration measurement.

        Args:
            pxo_states: List of (H¹⁴, S⁷) state pairs over time
            threshold: Integration threshold for score normalization

        Returns:
            Integration metrics
        """
        if len(pxo_states) == 0:
            logger.warning("No states provided for integration measurement")
            return {"system_integration_score": 0.0, "integration_value": 0.0}

        # Stack states
        hyp_states = torch.stack([s[0] for s in pxo_states])  # [T, ...]
        oct_states = torch.stack([s[1] for s in pxo_states])  # [T, ...]

        # Add batch dimension if needed
        if hyp_states.ndim == 2:
            hyp_states = hyp_states.unsqueeze(1)  # [T, 1, D]
            oct_states = oct_states.unsqueeze(1)

        # Measure integration
        measurement = self.compute_integration(hyp_states, oct_states)

        # Integration score (0-1)
        integration_score = min(1.0, measurement.integration_value / threshold)
        coupling_score = measurement.coupling_strength

        # Temporal coherence (how stable dynamics are over time)
        temporal_coherence = self._compute_temporal_coherence(hyp_states, oct_states)

        # Overall integration score
        system_integration_score = (
            0.5 * integration_score + 0.3 * coupling_score + 0.2 * temporal_coherence
        )

        return {
            "system_integration_score": float(system_integration_score),
            "integration_value": measurement.integration_value,
            "integration_strength": measurement.coupling_strength,
            "temporal_coherence": float(temporal_coherence),
            "whole_entropy": measurement.whole_entropy,
            "parts_entropy": measurement.parts_entropy,
            "interpretation": self._interpret_score(system_integration_score),  # type: ignore[arg-type]
        }

    def _compute_temporal_coherence(
        self,
        hyp_states: torch.Tensor,
        oct_states: torch.Tensor,
    ) -> torch.Tensor:
        """Measure temporal coherence (stability of coupled dynamics)."""
        T = hyp_states.shape[0]

        if T < 2:
            return torch.tensor(0.0)

        # Compute state-to-state correlation
        coherence = 0.0
        for t in range(T - 1):
            # Current and next state
            curr_hyp = hyp_states[t].flatten()
            next_hyp = hyp_states[t + 1].flatten()
            curr_oct = oct_states[t].flatten()
            next_oct = oct_states[t + 1].flatten()

            # Correlation
            hyp_corr = F.cosine_similarity(curr_hyp, next_hyp, dim=0)
            oct_corr = F.cosine_similarity(curr_oct, next_oct, dim=0)

            coherence += (hyp_corr + oct_corr) / 2  # type: ignore[assignment]

        coherence /= T - 1

        return coherence  # type: ignore[return-value]

    def _interpret_score(self, score: float) -> str:
        """Interpret integration score."""
        if score > 0.8:
            return "High integration (strong information coupling)"
        elif score > 0.6:
            return "Moderate integration (significant coupling)"
        elif score > 0.4:
            return "Low integration (weak coupling)"
        elif score > 0.2:
            return "Minimal integration (fragmented dynamics)"
        else:
            return "No measurable integration (independent parts)"


async def measure_system_integration(
    pxo_model: nn.Module,
    n_steps: int = 100,
    embedding_dim: int = 512,  # Kagami standard
    hyperbolic_dim: int = 14,
    octonion_dim: int = 8,
) -> dict[str, Any]:
    """Measure system integration.

    Args:
        pxo_model: PXO transformer
        n_steps: Measurement steps
        embedding_dim: Semantic dimension
        hyperbolic_dim: H¹⁴ dimension
        octonion_dim: S⁷ dimension (8D)

    Returns:
        Integration measurement report
    """
    logger.info(f"🧠 Measuring system integration over {n_steps} steps...")

    measure = InformationIntegrationMeasure(pxo_model)

    # Collect states over time
    states = []

    for _ in range(n_steps):
        # Generate synthetic input (replace with real operation in production)
        torch.randn(1, 1, embedding_dim)

        # Forward through PXO (generates H¹⁴ × S⁷ states)
        with torch.no_grad():
            # NOTE: In real integration, extract actual geometric states from PXO
            # For now, simulate with synthetic data
            hyp_state = torch.randn(1, hyperbolic_dim)
            oct_state = torch.randn(1, octonion_dim)

            # Project to manifolds
            hyp_state = F.normalize(hyp_state, dim=-1) * 0.9  # < 1 for Poincaré
            oct_state = F.normalize(oct_state, dim=-1)  # Unit sphere S⁷

            states.append((hyp_state, oct_state))

    # Measure integration
    integration_metrics = measure.measure_integration_metrics(states)

    logger.info(
        f"✅ Integration measurement complete:\n"
        f"  Score: {integration_metrics['system_integration_score']:.4f}\n"
        f"  Integration: {integration_metrics['integration_value']:.4f}\n"
        f"  Coupling: {integration_metrics['integration_strength']:.4f}\n"
        f"  Coherence: {integration_metrics['temporal_coherence']:.4f}\n"
        f"  Interpretation: {integration_metrics['interpretation']}"
    )

    return integration_metrics


# Export
__all__ = [
    "InformationIntegrationMeasure",
    "IntegrationMeasurement",
    "measure_system_integration",
]
