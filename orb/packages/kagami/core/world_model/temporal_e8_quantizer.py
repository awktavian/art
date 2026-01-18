"""Temporal E8 Quantization with Catastrophe-Based Event Segmentation.

KEY INSIGHT FROM SPARK:
======================
Don't quantize TIME - quantize EVENTS.

Traditional approach: Fixed temporal grid, quantize states at t=0, Δt, 2Δt, ...
KagamiOS approach: Dynamic event grid, quantize states at BIFURCATIONS.

Time is segmented by CATASTROPHE CROSSINGS (singularities in the state manifold).
Each bifurcation point is E8-quantized into a discrete event token.
Sequence of E8 codes = compressed episodic memory.

MULTI-SCALE TEMPORAL RESOLUTION:
================================
Each colony operates at different temporal resolution based on catastrophe type:
- Spark (Fold A₂): High frequency - many small bifurcations (rapid ideation)
- Cusp (A₃): Medium frequency - moderate transitions (implementation)
- Swallowtail (A₄): Lower frequency - complex transitions (adaptation)
- Butterfly (A₅): Rare large bifurcations (integration)
- Umbilic types (D₄±, D₅): Spatial bifurcations (planning, research, verification)

Result: Natural compression - only encode SIGNIFICANT transitions, not every timestep.

MATHEMATICAL FOUNDATION:
=======================
- E8 lattice: Optimal 8D sphere packing (Viazovska 2017)
- Catastrophe theory: Singularity detection (Thom 1972)
- Event compression ratio: num_events / seq_len (typical: 0.05-0.3)

Created: December 14, 2025
Colony: Forge (e₂) - Implementation with quality
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn as nn
from kagami_math.e8_lattice_quantizer import nearest_e8

from kagami.core.world_model.dynamics.analytical_catastrophe import (
    AnalyticalCatastropheDetector,
)

logger = logging.getLogger(__name__)


@dataclass
class TemporalE8Config:
    """Configuration for Temporal E8 Quantizer.

    Attributes:
        state_dim: Input state dimension (typically RSSM h state, 256D)
        bifurcation_threshold: Risk threshold for bifurcation detection (0-1)
            Lower = more events, higher = fewer events
        catastrophe_dim: Dimension for catastrophe detector input (default 64)
        multi_colony: Enable multi-colony encoding (all 7 perspectives)
        risk_weighting: Weight events by catastrophe risk (importance)
        min_event_spacing: Minimum timesteps between events (prevents over-sampling)
    """

    state_dim: int = 256
    bifurcation_threshold: float = 0.7
    catastrophe_dim: int = 64
    multi_colony: bool = False
    risk_weighting: bool = True
    min_event_spacing: int = 1


class TemporalE8Quantizer(nn.Module):
    """E8-based temporal quantization with catastrophe-driven segmentation.

    Core insight: Time is segmented by BIFURCATIONS (catastrophe crossings).
    Each bifurcation point is E8-quantized into discrete event.
    Sequence of E8 codes = episodic memory.

    Multi-scale: Each colony operates at different temporal resolution:
    - Spark (Fold): High frequency (many small bifurcations)
    - Crystal (Parabolic): Low frequency (rare large bifurcations)

    Usage:
        >>> quantizer = TemporalE8Quantizer(state_dim=256)
        >>> state_seq = torch.randn(1, 100, 256)  # [batch, time, state]
        >>> result = quantizer.process_sequence(state_seq, colony_idx=0)
        >>> print(f"Compression: {result['compression_ratio']:.2%}")
        >>> print(f"Events: {result['num_events']}")
    """

    def __init__(
        self,
        config: TemporalE8Config | None = None,
        catastrophe_detector: AnalyticalCatastropheDetector | None = None,
    ):
        """Initialize temporal E8 quantizer.

        Args:
            config: Configuration object
            catastrophe_detector: Optional pre-initialized detector
        """
        super().__init__()
        self.config = config or TemporalE8Config()

        # Catastrophe detector for bifurcation detection
        if catastrophe_detector is None:
            self.catastrophe_detector = AnalyticalCatastropheDetector(
                input_dim=self.config.catastrophe_dim,
                singularity_threshold=self.config.bifurcation_threshold,
            )
        else:
            self.catastrophe_detector = catastrophe_detector

        # State encoder: state_dim → catastrophe_dim → 8D for E8
        self.state_to_catastrophe = nn.Linear(self.config.state_dim, self.config.catastrophe_dim)
        self.state_to_e8 = nn.Sequential(
            nn.Linear(self.config.state_dim, 64),
            nn.GELU(),
            nn.Linear(64, 8),
        )

        # Colony embeddings (learnable 8D vectors for each catastrophe type)
        self.colony_embeddings = nn.Parameter(torch.randn(7, 8) * 0.1)

        # Initialize orthogonally for better conditioning
        with torch.no_grad():
            nn.init.orthogonal_(self.colony_embeddings)

        logger.debug(
            "TemporalE8Quantizer: state_dim=%d, threshold=%.2f",
            self.config.state_dim,
            self.config.bifurcation_threshold,
        )

    def detect_bifurcation(
        self,
        current_state: torch.Tensor,
        prev_state: torch.Tensor,
        colony_idx: int,
        timestep: int,
    ) -> tuple[bool, float]:
        """Detect if current state represents a bifurcation (significant transition).

        A bifurcation is a catastrophe crossing - when the system transitions
        through a singularity in the manifold. These are the EVENTS we encode.

        Uses multiple criteria:
        1. Catastrophe risk crossing threshold
        2. Large catastrophe risk jumps
        3. Large state change magnitude (Euclidean distance)

        Args:
            current_state: [batch, state_dim] Current state
            prev_state: [batch, state_dim] Previous state
            colony_idx: Which colony's catastrophe to check (0-6)
            timestep: Current timestep (for min_event_spacing)

        Returns:
            is_bifurcation: Boolean - is this a significant event?
            catastrophe_risk: Float in [0,1] (high = near singularity)
        """
        # Project to catastrophe detector space
        current_cat = self.state_to_catastrophe(current_state)
        prev_cat = self.state_to_catastrophe(prev_state)

        # Detect catastrophe risk for both states
        with torch.no_grad():
            _curr_risk, curr_risks, _ = self.catastrophe_detector(current_cat)
            _prev_risk, prev_risks, _ = self.catastrophe_detector(prev_cat)

        # Get risk for specific colony type
        colony_risk_curr = curr_risks[0, colony_idx].item()
        colony_risk_prev = prev_risks[0, colony_idx].item()

        # Criterion 1: Risk crosses threshold (either direction)
        # This detects TRANSITIONS through singularities
        threshold = self.config.bifurcation_threshold
        crosses_threshold = (colony_risk_prev < threshold <= colony_risk_curr) or (
            colony_risk_prev > threshold >= colony_risk_curr
        )

        # Criterion 2: Large risk jumps (rapid transitions)
        risk_jump = abs(colony_risk_curr - colony_risk_prev)
        large_risk_jump = risk_jump > 0.3

        # Criterion 3: Large state change (Euclidean distance)
        # This catches significant transitions even if catastrophe risk is low
        state_delta = (current_state - prev_state).norm(dim=-1).mean().item()
        state_change_threshold = 0.5  # Tunable parameter
        large_state_change = state_delta > state_change_threshold

        # Bifurcation if ANY criterion is met
        is_bifurcation = crosses_threshold or large_risk_jump or large_state_change

        return is_bifurcation, colony_risk_curr

    def encode_event(
        self,
        state: torch.Tensor,
        colony_idx: int,
        catastrophe_risk: float,
    ) -> torch.Tensor:
        """Encode state at bifurcation point into E8 code.

        Args:
            state: [batch, state_dim] State at bifurcation
            colony_idx: Which colony detected this event (0-6)
            catastrophe_risk: Risk value (encodes event importance)

        Returns:
            e8_code: [batch, 8] E8 lattice point (discrete token)
        """
        # Project state to 8D
        state_8d = self.state_to_e8(state)  # [batch, 8]

        # Add colony embedding (encode which catastrophe type)
        colony_embedding = self.colony_embeddings[colony_idx]
        state_8d = state_8d + colony_embedding

        # Optionally weight by risk (importance-weighted encoding)
        if self.config.risk_weighting:
            # Higher risk = more important event, amplify signal
            state_8d = state_8d * (1.0 + catastrophe_risk)

        # Quantize to E8 lattice
        e8_code = nearest_e8(state_8d)

        return e8_code

    def process_sequence(
        self,
        state_sequence: torch.Tensor,
        colony_idx: int = 0,
    ) -> dict[str, Any]:
        """Process a sequence of states, extracting bifurcation events.

        This is the core method: converts continuous trajectory into
        discrete event sequence via catastrophe-based segmentation.

        Args:
            state_sequence: [batch, seq_len, state_dim]
            colony_idx: Which colony's perspective (0-6)

        Returns:
            Dict with:
            - e8_events: [num_events, 8] E8 codes at bifurcations
            - event_times: List of timesteps where bifurcations occurred
            - catastrophe_risks: List of risk values
            - compression_ratio: (num_events / seq_len) - lower = more compression
            - num_events: Total number of events detected
        """
        batch_size, seq_len, state_dim = state_sequence.shape

        if batch_size != 1:
            raise ValueError(f"process_sequence only supports batch_size=1, got {batch_size}")

        if state_dim != self.config.state_dim:
            raise ValueError(
                f"State dim mismatch: expected {self.config.state_dim}, got {state_dim}"
            )

        e8_events = []
        event_times = []
        catastrophe_risks = []
        last_event_time = -self.config.min_event_spacing  # Allow first event

        for t in range(1, seq_len):
            current_state = state_sequence[:, t, :]  # [1, state_dim]
            prev_state = state_sequence[:, t - 1, :]

            # Enforce minimum spacing
            if t - last_event_time < self.config.min_event_spacing:
                continue

            # Detect bifurcation
            is_bifurcation, risk = self.detect_bifurcation(current_state, prev_state, colony_idx, t)

            if is_bifurcation:
                # Encode event
                e8_code = self.encode_event(current_state, colony_idx, risk)
                e8_events.append(e8_code.squeeze(0))  # [8]
                event_times.append(t)
                catastrophe_risks.append(risk)
                last_event_time = t

        # Stack events
        if e8_events:
            e8_events_tensor = torch.stack(e8_events)  # [num_events, 8]
        else:
            e8_events_tensor = torch.empty(0, 8, device=state_sequence.device)

        compression_ratio = len(e8_events) / seq_len if seq_len > 0 else 0.0

        return {
            "e8_events": e8_events_tensor,
            "event_times": event_times,
            "catastrophe_risks": catastrophe_risks,
            "compression_ratio": compression_ratio,
            "num_events": len(e8_events),
            "sequence_length": seq_len,
        }

    def encode_multi_colony(
        self,
        state_sequence: torch.Tensor,
    ) -> dict[int | str, dict[str, Any]]:
        """Encode sequence from all 7 colony perspectives.

        Different colonies detect different bifurcations based on their
        catastrophe type:
        - Spark (Fold): Many small transitions (high temporal resolution)
        - Cusp: Moderate transitions
        - Swallowtail: Complex transitions
        - Butterfly: Rare large transitions
        - Hyperbolic/Elliptic/Parabolic: Spatial bifurcations

        Returns:
            Dict mapping colony_idx (int) → event data, plus "aggregate" key
        """
        if not self.config.multi_colony:
            logger.warning(
                "multi_colony=False but encode_multi_colony called. "
                "Enable config.multi_colony for full functionality."
            )

        results: dict[int | str, dict[str, Any]] = {}
        for colony_idx in range(7):
            results[colony_idx] = self.process_sequence(state_sequence, colony_idx)

        # Add aggregate statistics
        total_events = sum(r["num_events"] for k, r in results.items() if isinstance(k, int))
        avg_compression = (
            sum(r["compression_ratio"] for k, r in results.items() if isinstance(k, int)) / 7
        )

        results["aggregate"] = {
            "total_events": total_events,
            "avg_compression": avg_compression,
            "events_per_colony": {i: results[i]["num_events"] for i in range(7)},
        }

        return results

    def decode_events(
        self,
        e8_events: torch.Tensor,
        event_times: list[int],
        sequence_length: int,
    ) -> torch.Tensor:
        """Reconstruct approximate state sequence from E8 events.

        NOTE: This is lossy reconstruction - we can't perfectly recover
        the original continuous trajectory from discrete events. This is
        the COMPRESSION: we keep only bifurcations, lose smooth interpolation.

        Args:
            e8_events: [num_events, 8] E8 codes
            event_times: List of timesteps for each event
            sequence_length: Original sequence length

        Returns:
            reconstructed: [sequence_length, 8] Reconstructed 8D trajectory
                (NOT state_dim - downstream decoder needed)
        """
        device = e8_events.device
        num_events = e8_events.shape[0]

        if num_events == 0:
            # No events - return zeros
            return torch.zeros(sequence_length, 8, device=device)

        # Initialize with first event
        reconstructed = torch.zeros(sequence_length, 8, device=device)

        # Fill in events
        for i, t in enumerate(event_times):
            if t < sequence_length:
                reconstructed[t] = e8_events[i]

        # Linear interpolation between events
        for i in range(num_events - 1):
            t_start = event_times[i]
            t_end = event_times[i + 1]

            if t_end >= sequence_length:
                break

            # Interpolate
            steps = t_end - t_start
            if steps > 1:
                start_code = e8_events[i]
                end_code = e8_events[i + 1]

                for step in range(1, steps):
                    alpha = step / steps
                    interpolated = (1 - alpha) * start_code + alpha * end_code
                    reconstructed[t_start + step] = interpolated

        # Forward-fill first segment
        if event_times[0] > 0:
            reconstructed[: event_times[0]] = e8_events[0]

        # Backward-fill last segment
        if event_times[-1] < sequence_length - 1:
            reconstructed[event_times[-1] :] = e8_events[-1]

        return reconstructed

    def get_compression_stats(
        self,
        results: dict[str, Any],
    ) -> dict[str, Any]:
        """Extract compression statistics from processing results.

        Args:
            results: Output from process_sequence or encode_multi_colony

        Returns:
            Dict with compression metrics
        """
        if "aggregate" in results:
            # Multi-colony results
            return {
                "total_events": results["aggregate"]["total_events"],
                "avg_compression_ratio": results["aggregate"]["avg_compression"],
                "events_per_colony": results["aggregate"]["events_per_colony"],
                "compression_factor": 1.0 / results["aggregate"]["avg_compression"]
                if results["aggregate"]["avg_compression"] > 0
                else float("inf"),
            }
        else:
            # Single colony results
            return {
                "num_events": results["num_events"],
                "compression_ratio": results["compression_ratio"],
                "sequence_length": results["sequence_length"],
                "compression_factor": 1.0 / results["compression_ratio"]
                if results["compression_ratio"] > 0
                else float("inf"),
                "avg_risk": (
                    sum(results["catastrophe_risks"]) / len(results["catastrophe_risks"])
                    if results["catastrophe_risks"]
                    else 0.0
                ),
            }


# Factory function for easy instantiation
def create_temporal_quantizer(
    state_dim: int = 256,
    bifurcation_threshold: float = 0.7,
    multi_colony: bool = False,
) -> TemporalE8Quantizer:
    """Create a temporal E8 quantizer with default settings.

    Args:
        state_dim: Input state dimension
        bifurcation_threshold: Risk threshold for bifurcation detection
        multi_colony: Enable multi-colony encoding

    Returns:
        Configured TemporalE8Quantizer
    """
    config = TemporalE8Config(
        state_dim=state_dim,
        bifurcation_threshold=bifurcation_threshold,
        multi_colony=multi_colony,
    )
    return TemporalE8Quantizer(config)


__all__ = [
    "TemporalE8Config",
    "TemporalE8Quantizer",
    "create_temporal_quantizer",
]
