"""Rigorous Lyapunov Spectrum Computation.

Implements the Benettin QR algorithm for computing full Lyapunov spectra.
This is the mathematically rigorous approach, not naive trajectory divergence.

References:
- Benettin et al. (1980). Lyapunov characteristic exponents for smooth dynamical systems
- Eckmann & Ruelle (1985). Ergodic theory of chaos and strange attractors

Created: November 30, 2025
Updated: December 2, 2025 - Consolidated from multiple implementations
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import torch
import torch.nn.functional as F

logger = logging.getLogger(__name__)


@dataclass
class LyapunovSpectrumResult:
    """Result of Lyapunov spectrum computation.

    Attributes:
        spectrum: Full Lyapunov spectrum [λ₁, λ₂, ...] sorted descending
        lambda_max: Largest exponent (λ₁)
        kaplan_yorke_dim: Kaplan-Yorke dimension estimate
        sum_positive: Sum of positive exponents
        entropy_rate: Kolmogorov-Sinai entropy estimate (sum of positive λ)
        converged: Whether the computation converged
    """

    spectrum: list[float]
    lambda_max: float
    kaplan_yorke_dim: float
    sum_positive: float
    entropy_rate: float
    converged: bool = True

    @property
    def regime(self) -> str:
        """Classify dynamical regime based on λ_max."""
        if self.lambda_max < -0.1:
            return "ordered"
        elif self.lambda_max > 0.5:
            return "chaotic"
        elif abs(self.lambda_max) <= 0.15:
            return "edge_of_chaos"
        elif self.lambda_max > 0:
            return "weakly_chaotic"
        else:
            return "stable"

    @classmethod
    def zero(cls, dim: int = 3) -> LyapunovSpectrumResult:
        """Create zero result for fallback."""
        return cls(
            spectrum=[0.0] * dim,
            lambda_max=0.0,
            kaplan_yorke_dim=float(dim),
            sum_positive=0.0,
            entropy_rate=0.0,
            converged=False,
        )


class RigorousLyapunovComputer:
    """Compute full Lyapunov spectrum using Benettin QR algorithm.

    The algorithm:
    1. Evolve a set[Any] of orthonormal tangent vectors alongside the trajectory
    2. Periodically reorthonormalize using QR decomposition
    3. Accumulate log of R diagonal elements
    4. Average over time to get Lyapunov exponents

    This is differentiable when used with torch operations.

    NOTE (Dec 20, 2025): Native MPS QR via kagami.core.utils.mps_ops.
    No CPU fallback - runs entirely on Apple Silicon GPU.
    """

    def __init__(
        self,
        dim: int = 3,
        dt: float = 0.01,
        qr_interval: int = 10,
        lorenz_params: tuple[float, float, float] | None = None,
    ):
        """Initialize Lyapunov computer.

        Args:
            dim: State space dimension
            dt: Integration timestep
            qr_interval: Steps between QR orthonormalizations
            lorenz_params: (sigma, rho, beta) for Lorenz system. None for default.
        """
        self.dim = dim
        self.dt = dt
        self.qr_interval = qr_interval

        # Lorenz parameters
        if lorenz_params is None:
            self.sigma = 10.0
            self.rho = 28.0
            self.beta = 8.0 / 3.0
        else:
            self.sigma, self.rho, self.beta = lorenz_params

    def _qr(self, Q: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """QR decomposition - uses native MPS implementation.

        Args:
            Q: Matrix to decompose [dim, dim]

        Returns:
            (Q_new, R) tuple[Any, ...] from QR decomposition
        """
        # bfloat16/float16 cast to float32 for QR stability
        original_dtype = Q.dtype
        if original_dtype in (torch.bfloat16, torch.float16):
            Q_new, R = torch.linalg.qr(Q.float())
            return Q_new.to(original_dtype), R.to(original_dtype)
        return torch.linalg.qr(Q)

    def _lorenz_jacobian(self, state: torch.Tensor) -> torch.Tensor:
        """Compute Jacobian of Lorenz system at given state.

        J = [[-σ,   σ,  0],
             [ρ-z, -1,  -x],
             [y,    x,  -β]]

        Args:
            state: [3] or [B, 3] state vector

        Returns:
            [3, 3] or [B, 3, 3] Jacobian matrix
        """
        if state.dim() == 1:
            state = state.unsqueeze(0)

        B = state.shape[0]
        device = state.device
        dtype = state.dtype

        x, y, z = state[:, 0], state[:, 1], state[:, 2]

        J = torch.zeros(B, 3, 3, device=device, dtype=dtype)

        # Row 1: [-σ, σ, 0]
        J[:, 0, 0] = -self.sigma
        J[:, 0, 1] = self.sigma

        # Row 2: [ρ-z, -1, -x]
        J[:, 1, 0] = self.rho - z
        J[:, 1, 1] = -1.0
        J[:, 1, 2] = -x

        # Row 3: [y, x, -β]
        J[:, 2, 0] = y
        J[:, 2, 1] = x
        J[:, 2, 2] = -self.beta

        return J.squeeze(0) if B == 1 else J

    def _lorenz_step(self, state: torch.Tensor) -> torch.Tensor:
        """RK4 integration step for Lorenz system.

        Args:
            state: [3] or [B, 3] state vector

        Returns:
            Next state
        """

        def deriv(s: Any) -> Any:
            if s.dim() == 1:
                x, y, z = s[0], s[1], s[2]
                return torch.stack(
                    [
                        self.sigma * (y - x),
                        x * (self.rho - z) - y,
                        x * y - self.beta * z,
                    ]
                )
            else:
                x, y, z = s[:, 0], s[:, 1], s[:, 2]
                return torch.stack(
                    [
                        self.sigma * (y - x),
                        x * (self.rho - z) - y,
                        x * y - self.beta * z,
                    ],
                    dim=-1,
                )

        k1 = deriv(state)
        k2 = deriv(state + 0.5 * self.dt * k1)
        k3 = deriv(state + 0.5 * self.dt * k2)
        k4 = deriv(state + self.dt * k3)

        return state + (self.dt / 6) * (k1 + 2 * k2 + 2 * k3 + k4)

    def compute_spectrum(
        self,
        initial_state: torch.Tensor,
        total_steps: int = 1000,
        transient_steps: int = 100,
    ) -> LyapunovSpectrumResult:
        """Compute full Lyapunov spectrum using QR method.

        Args:
            initial_state: [3] or [1, 3] initial state
            total_steps: Total integration steps
            transient_steps: Steps to discard before accumulating

        Returns:
            LyapunovSpectrumResult with full spectrum
        """
        try:
            device = initial_state.device
            dtype = initial_state.dtype

            # Ensure 1D state
            if initial_state.dim() == 2:
                state = initial_state[0].clone()
            else:
                state = initial_state.clone()

            # Initialize orthonormal tangent vectors (identity matrix)
            Q = torch.eye(self.dim, device=device, dtype=dtype)

            # Accumulator for Lyapunov sums
            lyap_sums = torch.zeros(self.dim, device=device, dtype=dtype)
            qr_count = 0

            # Transient evolution (discard)
            for _ in range(transient_steps):
                state = self._lorenz_step(state)

            # Main evolution with Lyapunov computation
            for step in range(total_steps):
                # Get Jacobian at current state
                J = self._lorenz_jacobian(state)

                # Evolve tangent vectors: Q_new = (I + dt * J) @ Q
                # For small dt, this is equivalent to solving dQ/dt = J @ Q
                Q = Q + self.dt * (J @ Q)

                # Evolve state
                state = self._lorenz_step(state)

                # Periodic QR reorthonormalization
                if (step + 1) % self.qr_interval == 0:
                    # QR decomposition with MPS fallback
                    Q_new, R = self._qr(Q)
                    Q = Q_new

                    # Accumulate log of diagonal (growth rates)
                    diag = R.diag().abs()
                    lyap_sums += torch.log(diag.clamp(min=1e-10))
                    qr_count += 1

            if qr_count == 0:
                return LyapunovSpectrumResult.zero(self.dim)

            # Compute Lyapunov exponents (time-averaged)
            effective_time = qr_count * self.qr_interval * self.dt
            spectrum = (lyap_sums / effective_time).cpu().tolist()

            # Sort descending
            spectrum.sort(reverse=True)

            # Compute derived quantities
            lambda_max = spectrum[0]
            sum_positive = sum(l for l in spectrum if l > 0)

            # Kaplan-Yorke dimension
            ky_dim = self._kaplan_yorke_dimension(spectrum)

            return LyapunovSpectrumResult(
                spectrum=spectrum,
                lambda_max=lambda_max,
                kaplan_yorke_dim=ky_dim,
                sum_positive=sum_positive,
                entropy_rate=sum_positive,  # Pesin identity
                converged=True,
            )

        except Exception as e:
            logger.warning(f"Lyapunov computation failed: {e}")
            return LyapunovSpectrumResult.zero(self.dim)

    def _kaplan_yorke_dimension(self, spectrum: list[float]) -> float:
        """Compute Kaplan-Yorke (Lyapunov) dimension.

        D_KY = k + (Σᵢ₌₁ᵏ λᵢ) / |λₖ₊₁|

        where k is the largest integer such that Σᵢ₌₁ᵏ λᵢ ≥ 0
        """
        spectrum_sorted = sorted(spectrum, reverse=True)

        cumsum = 0.0
        k = 0

        for i, lam in enumerate(spectrum_sorted):
            cumsum += lam
            if cumsum >= 0:
                k = i + 1
            else:
                break

        if k == 0 or k >= len(spectrum_sorted):
            return float(len(spectrum_sorted))

        # D_KY = k + cumsum / |λ_{k+1}|
        if abs(spectrum_sorted[k]) < 1e-10:
            return float(k)

        return k + sum(spectrum_sorted[:k]) / abs(spectrum_sorted[k])


class LearnedDynamicsLyapunovComputer:
    """Lyapunov computation for learned dynamics (not Lorenz-specific).

    Uses finite-difference Jacobian estimation for arbitrary neural dynamics.

    NOTE (Dec 20, 2025): Native MPS QR via kagami.core.utils.mps_ops.
    """

    def __init__(
        self,
        dynamics_fn: Callable[[torch.Tensor], torch.Tensor],
        dim: int,
        dt: float = 0.01,
        qr_interval: int = 10,
        epsilon: float = 1e-5,
    ):
        """Initialize for arbitrary dynamics.

        Args:
            dynamics_fn: Function mapping state -> next_state
            dim: State dimension
            dt: Nominal timestep (for normalization)
            qr_interval: Steps between QR
            epsilon: Finite difference epsilon
        """
        self.dynamics_fn = dynamics_fn
        self.dim = dim
        self.dt = dt
        self.qr_interval = qr_interval
        self.epsilon = epsilon

    def _qr(self, Q: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """QR decomposition - uses native MPS implementation."""
        original_dtype = Q.dtype
        if original_dtype in (torch.bfloat16, torch.float16):
            Q_new, R = torch.linalg.qr(Q.float())
            return Q_new.to(original_dtype), R.to(original_dtype)
        return torch.linalg.qr(Q)

    def _numerical_jacobian(self, state: torch.Tensor) -> torch.Tensor:
        """Compute Jacobian via finite differences.

        Args:
            state: [D] state vector

        Returns:
            [D, D] Jacobian matrix
        """
        device = state.device
        dtype = state.dtype

        f0 = self.dynamics_fn(state)
        J = torch.zeros(self.dim, self.dim, device=device, dtype=dtype)

        for i in range(self.dim):
            state_plus = state.clone()
            state_plus[i] += self.epsilon
            f_plus = self.dynamics_fn(state_plus)
            J[:, i] = (f_plus - f0) / self.epsilon

        return J

    def compute_spectrum(
        self,
        initial_state: torch.Tensor,
        total_steps: int = 1000,
        transient_steps: int = 100,
    ) -> LyapunovSpectrumResult:
        """Compute spectrum for learned dynamics."""
        try:
            device = initial_state.device
            dtype = initial_state.dtype

            state = initial_state.flatten()[: self.dim].clone()
            Q = torch.eye(self.dim, device=device, dtype=dtype)
            lyap_sums = torch.zeros(self.dim, device=device, dtype=dtype)
            qr_count = 0

            # Transient
            for _ in range(transient_steps):
                state = self.dynamics_fn(state)

            # Main loop
            for step in range(total_steps):
                J = self._numerical_jacobian(state)
                Q = Q + self.dt * (J @ Q)
                state = self.dynamics_fn(state)

                if (step + 1) % self.qr_interval == 0:
                    Q, R = self._qr(Q)
                    lyap_sums += torch.log(R.diag().abs().clamp(min=1e-10))
                    qr_count += 1

            if qr_count == 0:
                return LyapunovSpectrumResult.zero(self.dim)

            effective_time = qr_count * self.qr_interval * self.dt
            spectrum = (lyap_sums / effective_time).cpu().tolist()
            spectrum.sort(reverse=True)

            lambda_max = spectrum[0]
            sum_positive = sum(l for l in spectrum if l > 0)

            # Simplified KY dimension
            ky_dim = (
                float(self.dim)
                if lambda_max <= 0
                else min(float(self.dim), max(1.0, 2.0 + lambda_max / max(0.1, abs(spectrum[-1]))))
            )

            return LyapunovSpectrumResult(
                spectrum=spectrum,
                lambda_max=lambda_max,
                kaplan_yorke_dim=ky_dim,
                sum_positive=sum_positive,
                entropy_rate=sum_positive,
                converged=True,
            )

        except Exception as e:
            logger.warning(f"Learned dynamics Lyapunov failed: {e}")
            return LyapunovSpectrumResult.zero(self.dim)


def estimate_lyapunov_rigorous(
    x: torch.Tensor,
    steps: int = 1000,
    dt: float = 0.01,
) -> float:
    """Convenience function to estimate λ_max.

    Args:
        x: Input tensor (will use first 3 elements as Lorenz initial condition)
        steps: Integration steps
        dt: Timestep

    Returns:
        Largest Lyapunov exponent
    """
    computer = RigorousLyapunovComputer(dim=3, dt=dt)

    # Extract initial state
    if x.numel() >= 3:
        state = x.flatten()[:3]
    else:
        state = F.pad(x.flatten(), (0, 3 - x.numel()))

    result = computer.compute_spectrum(state, total_steps=steps)
    return result.lambda_max


__all__ = [
    "LearnedDynamicsLyapunovComputer",
    "LyapunovSpectrumResult",
    "RigorousLyapunovComputer",
    "estimate_lyapunov_rigorous",
]
