"""Oscillatory Coordinator - Phase-Based Colony Binding.

BRAIN SCIENCE BASIS (December 2025):
====================================
Gamma oscillations (30-100Hz) coordinate distributed processing:

1. NEURAL BINDING
   - Neurons representing same object fire in phase
   - Phase coherence = "belonging together"
   - Solves the binding problem

2. KURAMOTO MODEL
   - Coupled oscillators synchronize naturally
   - Each oscillator has intrinsic frequency
   - Coupling strength determines sync speed

3. CROSS-FREQUENCY COUPLING
   - Theta (4-8Hz) modulates gamma amplitude
   - Phase-amplitude coupling for memory
   - Hierarchical timing organization

This module implements:
- Kuramoto oscillators for colony phase coordination
- Phase-locking detection for binding
- Cross-frequency coupling for hierarchy

References:
- Singer & Gray (1995): Visual feature integration and gamma
- Kuramoto (1984): Chemical Oscillations, Waves, and Turbulence
- Canolty & Knight (2010): The functional role of cross-frequency coupling
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import torch
import torch.nn as nn

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


@dataclass
class OscillatorState:
    """Current state of oscillatory system."""

    # Phase of each colony [7] in radians
    phases: torch.Tensor

    # Kuramoto order parameter (sync measure)
    order_parameter: float  # r ∈ [0, 1], 1 = full sync

    # Mean phase (center of mass on circle)
    mean_phase: float

    # Phase coherence matrix [7, 7]
    coherence_matrix: torch.Tensor

    # Binding groups (colonies in phase)
    bound_groups: list[list[int]]

    @property
    def is_synchronized(self) -> bool:
        """Check if system is synchronized (r > 0.7)."""
        return self.order_parameter > 0.7

    @property
    def binding_strength(self) -> float:
        """Average coherence between colonies."""
        # Off-diagonal mean
        mask = ~torch.eye(7, dtype=torch.bool, device=self.coherence_matrix.device)
        return self.coherence_matrix[mask].mean().item()


class KuramotoOscillator(nn.Module):
    """Kuramoto coupled oscillator model for colony phases.

    Each colony is an oscillator with:
    - Intrinsic frequency ω_i
    - Phase θ_i
    - Coupling strength K_ij to other colonies

    Dynamics:
        dθ_i/dt = ω_i + Σ_j K_ij sin(θ_j - θ_i)

    The Fano plane structure determines which colonies couple.
    """

    def __init__(
        self,
        num_oscillators: int = 7,
        base_frequency: float = 40.0,  # 40 Hz gamma
        coupling_strength: float = 1.0,
        dt: float = 0.001,  # Integration timestep (1ms)
        use_fano_coupling: bool = True,
    ):
        super().__init__()
        self.num_oscillators = num_oscillators
        self.base_frequency = base_frequency
        self.coupling_strength = coupling_strength
        self.dt = dt
        self.use_fano_coupling = use_fano_coupling

        # Natural frequencies (slight variation around base)
        # Each colony has slightly different intrinsic frequency
        omega_init = torch.ones(num_oscillators) * base_frequency * 2 * math.pi
        omega_init += torch.randn(num_oscillators) * 2.0  # ±2 Hz variation
        self.omega = nn.Parameter(omega_init)

        # Coupling matrix
        if use_fano_coupling:
            # Fano plane coupling: only coupled if on same line
            coupling = self._build_fano_coupling()
        else:
            # All-to-all coupling
            coupling = torch.ones(num_oscillators, num_oscillators)
            coupling.fill_diagonal_(0)

        self.register_buffer("coupling_matrix", coupling * coupling_strength)

        # Current phases (initialized randomly)
        self.register_buffer("phases", torch.rand(num_oscillators) * 2 * math.pi)

    def _build_fano_coupling(self) -> torch.Tensor:
        """Build coupling matrix from Fano plane structure."""
        # Fano lines (0-indexed)
        fano_lines = [
            (0, 1, 2),  # e₁ × e₂ = e₃
            (0, 3, 4),  # e₁ × e₄ = e₅
            (0, 6, 5),  # e₁ × e₇ = e₆
            (1, 3, 5),  # e₂ × e₄ = e₆
            (1, 4, 6),  # e₂ × e₅ = e₇
            (2, 3, 6),  # e₃ × e₄ = e₇
            (2, 5, 4),  # e₃ × e₆ = e₅
        ]

        coupling = torch.zeros(7, 7)

        # Colonies on same Fano line couple strongly
        for line in fano_lines:
            for i in range(3):
                for j in range(3):
                    if i != j:
                        coupling[line[i], line[j]] = 1.0

        return coupling

    def step(self, external_input: torch.Tensor | None = None) -> torch.Tensor:
        """Advance oscillator phases by one timestep.

        Args:
            external_input: Optional external phase perturbation [7]

        Returns:
            New phases [7]
        """
        # Compute phase differences
        # θ_j - θ_i for all pairs
        phase_diff = self.phases.unsqueeze(0) - self.phases.unsqueeze(1)  # type: ignore[operator]  # [7, 7]

        # Kuramoto coupling term: K_ij * sin(θ_j - θ_i)
        coupling_term = (self.coupling_matrix * torch.sin(phase_diff)).sum(dim=1)  # type: ignore[operator]

        # Phase update
        dtheta = self.omega + coupling_term

        # Add external input if provided
        if external_input is not None:
            dtheta = dtheta + external_input * 10.0  # Scale external input

        # Euler integration
        new_phases = self.phases + dtheta * self.dt  # type: ignore[operator]

        # Wrap to [0, 2π]
        new_phases = new_phases % (2 * math.pi)

        # Update state
        self.phases.copy_(new_phases)  # type: ignore[operator]

        return new_phases

    def compute_order_parameter(self) -> tuple[float, float]:
        """Compute Kuramoto order parameter.

        The order parameter measures synchronization:
        r * e^(iψ) = (1/N) Σ e^(iθ_j)

        Returns:
            r: Order parameter magnitude [0, 1]
            psi: Mean phase
        """
        # Complex representation
        complex_phases = (1j * self.phases.to(torch.complex64)).clone()  # type: ignore[union-attr, operator]
        z = torch.exp(complex_phases)

        # Mean
        z_mean = z.mean()

        # Extract r and ψ
        r = torch.abs(z_mean).item()
        psi = torch.angle(z_mean).item()

        return r, psi

    def compute_coherence_matrix(self) -> torch.Tensor:
        """Compute phase coherence between all pairs.

        Coherence(i, j) = cos(θ_i - θ_j)
        High coherence (≈1) means in phase, low (≈-1) means anti-phase.
        """
        phase_diff = self.phases.unsqueeze(0) - self.phases.unsqueeze(1)  # type: ignore[operator]
        coherence = torch.cos(phase_diff)
        return coherence


class CrossFrequencyCoupling(nn.Module):
    """Cross-frequency coupling for hierarchical timing.

    Implements theta-gamma coupling where:
    - Slow theta (4-8 Hz) provides timing "windows"
    - Fast gamma (30-100 Hz) encodes content within windows
    - Phase-amplitude coupling links hierarchy levels
    """

    def __init__(
        self,
        theta_frequency: float = 6.0,  # 6 Hz theta
        gamma_frequency: float = 40.0,  # 40 Hz gamma
        coupling_strength: float = 0.5,
    ):
        super().__init__()
        self.theta_freq = theta_frequency * 2 * math.pi
        self.gamma_freq = gamma_frequency * 2 * math.pi
        self.coupling_strength = coupling_strength

        # Theta phase (single global oscillator)
        self.register_buffer("theta_phase", torch.tensor(0.0))

    def step(self, dt: float = 0.001) -> tuple[float, float]:
        """Advance theta oscillator and compute gamma modulation.

        Returns:
            theta_phase: Current theta phase
            gamma_modulation: Amplitude modulation for gamma
        """
        # Update theta
        new_theta = (self.theta_phase + self.theta_freq * dt) % (2 * math.pi)  # type: ignore[operator]
        if isinstance(new_theta, torch.Tensor):
            self.theta_phase.copy_(new_theta)  # type: ignore[operator]
        else:
            self.theta_phase.copy_(torch.tensor(new_theta))  # type: ignore[operator]

        # Gamma modulation: peaks when theta is at preferred phase
        # Using cosine so modulation is 1 at theta=0, 0 at theta=π
        modulation = (1 + torch.cos(self.theta_phase) * self.coupling_strength) / 2  # type: ignore[arg-type]

        return self.theta_phase.item(), modulation.item()  # type: ignore[operator]


class OscillatoryCoordinator(nn.Module):
    """Unified oscillatory coordinator for colony binding.

    Combines:
    1. Kuramoto oscillators for gamma-band colony phases
    2. Cross-frequency coupling for hierarchical timing
    3. Binding detection based on phase coherence

    Usage:
        coordinator = OscillatoryCoordinator()
        for _ in range(100):
            state = coordinator.step()
            if state.is_synchronized:
                print(f"Colonies bound: {state.bound_groups}")
    """

    def __init__(
        self,
        num_colonies: int = 7,
        gamma_frequency: float = 40.0,
        theta_frequency: float = 6.0,
        coupling_strength: float = 1.0,
        binding_threshold: float = 0.8,  # Coherence threshold for binding
        dt: float = 0.001,
    ):
        super().__init__()
        self.num_colonies = num_colonies
        self.binding_threshold = binding_threshold
        self.dt = dt

        # Gamma oscillators (one per colony)
        self.gamma = KuramotoOscillator(
            num_oscillators=num_colonies,
            base_frequency=gamma_frequency,
            coupling_strength=coupling_strength,
            dt=dt,
            use_fano_coupling=True,
        )

        # Theta-gamma coupling
        self.theta_gamma = CrossFrequencyCoupling(
            theta_frequency=theta_frequency,
            gamma_frequency=gamma_frequency,
            coupling_strength=0.3,
        )

        # Input projection (colony activations → phase perturbation)
        self.input_proj = nn.Linear(num_colonies, num_colonies)

    def step(
        self,
        colony_activations: torch.Tensor | None = None,  # [7] or [B, 7]
    ) -> OscillatorState:
        """Advance oscillators by one timestep.

        Args:
            colony_activations: Optional colony activation levels to
                               bias phase evolution

        Returns:
            OscillatorState with current phase configuration
        """
        # Get theta modulation
        _theta_phase, gamma_mod = self.theta_gamma.step(self.dt)

        # Prepare external input
        if colony_activations is not None:
            if colony_activations.dim() > 1:
                colony_activations = colony_activations.mean(dim=0)
            external = self.input_proj(colony_activations) * gamma_mod
        else:
            external = None

        # Step gamma oscillators
        phases = self.gamma.step(external)

        # Compute order parameter
        r, mean_phase = self.gamma.compute_order_parameter()

        # Compute coherence matrix
        coherence = self.gamma.compute_coherence_matrix()

        # Detect bound groups (connected components of high coherence)
        bound_groups = self._detect_bound_groups(coherence)

        return OscillatorState(
            phases=phases,
            order_parameter=r,
            mean_phase=mean_phase,
            coherence_matrix=coherence,
            bound_groups=bound_groups,
        )

    def _detect_bound_groups(
        self,
        coherence: torch.Tensor,
    ) -> list[list[int]]:
        """Detect groups of phase-locked colonies.

        Uses coherence threshold to find connected components.
        """
        # Threshold coherence
        bound = coherence > self.binding_threshold

        # Find connected components (simple union-find)
        visited = set()
        groups = []

        for i in range(self.num_colonies):
            if i in visited:
                continue

            # BFS to find connected component
            group = [i]
            queue = [i]
            visited.add(i)

            while queue:
                node = queue.pop(0)
                for j in range(self.num_colonies):
                    if j not in visited and bound[node, j]:
                        visited.add(j)
                        group.append(j)
                        queue.append(j)

            if len(group) > 1:  # Only include groups with multiple colonies
                groups.append(sorted(group))

        return groups

    def run_to_sync(
        self,
        max_steps: int = 1000,
        target_r: float = 0.7,
    ) -> tuple[OscillatorState, int]:
        """Run oscillators until synchronized or max steps.

        Args:
            max_steps: Maximum number of steps
            target_r: Target order parameter for sync

        Returns:
            Final state and number of steps taken
        """
        for step in range(max_steps):
            state = self.step()
            if state.order_parameter >= target_r:
                return state, step + 1

        return state, max_steps

    def reset_phases(self, random: bool = True) -> None:
        """Reset oscillator phases."""
        if random:
            self.gamma.phases.copy_(  # type: ignore[operator]
                torch.rand(self.num_colonies) * 2 * math.pi
            )
        else:
            self.gamma.phases.zero_()  # type: ignore[operator]

    def get_binding_summary(self, state: OscillatorState) -> dict[str, Any]:
        """Get summary of current binding state."""
        return {
            "order_parameter": state.order_parameter,
            "is_synchronized": state.is_synchronized,
            "num_bound_groups": len(state.bound_groups),
            "bound_groups": state.bound_groups,
            "binding_strength": state.binding_strength,
            "mean_phase": state.mean_phase,
        }


def create_oscillatory_coordinator(
    num_colonies: int = 7,
    gamma_frequency: float = 40.0,
    coupling_strength: float = 1.0,
) -> OscillatoryCoordinator:
    """Factory function for oscillatory coordinator."""
    return OscillatoryCoordinator(
        num_colonies=num_colonies,
        gamma_frequency=gamma_frequency,
        coupling_strength=coupling_strength,
    )


__all__ = [
    "CrossFrequencyCoupling",
    "KuramotoOscillator",
    "OscillatorState",
    "OscillatoryCoordinator",
    "create_oscillatory_coordinator",
]
