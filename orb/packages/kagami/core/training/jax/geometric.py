"""JAX Geometric Modules — Geometric Mamba & Strange Loops.

Ports from PyTorch:
1. GeometricMamba — State space model on manifolds (H14×S7)
2. FixedPointNetwork — Iterative strange loop computation
3. Parallel associative scan — O(log n) SSM computation

References:
- Gu & Dao (2023): Mamba: Linear-Time Sequence Modeling
- Blelloch (1990): Parallel Prefix Algorithms
- Hofstadter (1979): Gödel, Escher, Bach

Created: January 12, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
from flax import linen as nn

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATIONS
# =============================================================================


@dataclass(frozen=True)
class GeometricMambaConfig:
    """Configuration for geometric Mamba."""

    d_model: int = 256
    d_state: int = 16  # SSM state dimension
    d_conv: int = 4  # Convolution width
    expand: int = 2  # Expansion factor

    # Manifold parameters
    hyperbolic_dim: int = 14  # H14 dimension
    spherical_dim: int = 7  # S7 dimension
    curvature: float = 1.0  # Hyperbolic curvature

    dt_rank: str = "auto"  # or int
    dt_min: float = 0.001
    dt_max: float = 0.1
    dt_init: str = "random"  # or "constant"

    dropout: float = 0.0


@dataclass(frozen=True)
class StrangeLoopConfig:
    """Configuration for iterative strange loop."""

    s7_dim: int = 7
    hidden_dim: int = 64

    max_iterations: int = 10
    convergence_threshold: float = 1e-4
    damping: float = 0.5

    num_layers: int = 2
    use_layer_norm: bool = True
    dropout: float = 0.0


# =============================================================================
# OUTPUT TYPES
# =============================================================================


class GeometricMambaOutput(NamedTuple):
    """Output from geometric Mamba."""

    output: jnp.ndarray  # [B, L, D] output sequence
    ssm_state: jnp.ndarray  # [B, D, N] final SSM state
    manifold_coords: jnp.ndarray | None  # [B, L, 21] H14×S7 coords


class StrangeLoopOutput(NamedTuple):
    """Output from strange loop computation."""

    mu_self: jnp.ndarray  # [B, 7] converged self-model
    iterations: int  # Number of iterations
    converged: jnp.ndarray  # [B] whether converged
    trajectory: jnp.ndarray | None  # [B, K, 7] iteration trajectory


# =============================================================================
# PARALLEL ASSOCIATIVE SCAN
# =============================================================================


def parallel_associative_scan(
    A: jnp.ndarray,
    Bu: jnp.ndarray,
) -> jnp.ndarray:
    """Parallel associative scan for linear recurrences.

    JAX port of PyTorch geometric_mamba.py:parallel_associative_scan

    Computes h[t] = A[t]*h[t-1] + Bu[t] in O(log L) parallel depth.

    Args:
        A: [B, L, D] decay coefficients
        Bu: [B, L, D] input contributions

    Returns:
        [B, L, D] hidden states
    """
    B, L, D = A.shape

    # For short sequences, use sequential scan
    if L <= 64:
        return _sequential_scan(A, Bu)

    # JAX-native associative scan using lax.associative_scan
    def combine_fn(carry1, carry2):
        a1, b1 = carry1
        a2, b2 = carry2
        return a1 * a2, a2 * b1 + b2

    # Stack A and Bu for associative scan
    init = (A, Bu)

    # Use JAX's built-in associative scan
    _, result = jax.lax.associative_scan(combine_fn, init, axis=1)

    return result


def _sequential_scan(A: jnp.ndarray, Bu: jnp.ndarray) -> jnp.ndarray:
    """Sequential scan for short sequences."""
    B, L, D = A.shape

    def scan_fn(carry, inputs):
        h = carry
        a, bu = inputs
        h_new = a * h + bu
        return h_new, h_new

    # Transpose for scan: [L, B, D]
    A_t = jnp.transpose(A, (1, 0, 2))
    Bu_t = jnp.transpose(Bu, (1, 0, 2))

    h_init = jnp.zeros((B, D))
    _, outputs = jax.lax.scan(scan_fn, h_init, (A_t, Bu_t))

    # Transpose back: [B, L, D]
    return jnp.transpose(outputs, (1, 0, 2))


# =============================================================================
# SELECTIVE SSM CORE
# =============================================================================


class SelectiveSSM(nn.Module):
    """Selective State Space Model core.

    JAX port of PyTorch geometric_mamba.py:SelectiveScan (simplified)
    """

    config: GeometricMambaConfig

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        ssm_state: jnp.ndarray | None = None,
    ) -> tuple[jnp.ndarray, jnp.ndarray]:
        """Run selective SSM.

        Args:
            x: [B, L, D] input sequence
            ssm_state: [B, D, N] initial state (optional)

        Returns:
            output: [B, L, D] output sequence
            final_state: [B, D, N] final SSM state
        """
        cfg = self.config
        B, L, D = x.shape

        d_inner = D * cfg.expand
        dt_rank = D // 16 if cfg.dt_rank == "auto" else int(cfg.dt_rank)

        # Initialize SSM state
        if ssm_state is None:
            ssm_state = jnp.zeros((B, d_inner, cfg.d_state))

        # Input projection
        x_proj = nn.Dense(d_inner * 2, name="in_proj")(x)
        x_inner, gate = jnp.split(x_proj, 2, axis=-1)

        # Convolution
        x_conv = nn.Conv(
            features=d_inner,
            kernel_size=(cfg.d_conv,),
            padding="SAME",
            feature_group_count=d_inner,
            name="conv",
        )(x_inner)
        x_conv = jax.nn.silu(x_conv)

        # Selective parameters
        x_dt = nn.Dense(dt_rank, name="dt_proj")(x_conv)
        dt = nn.Dense(d_inner, name="dt_expand")(x_dt)
        dt = jax.nn.softplus(dt)  # Ensure positive

        # SSM parameters (discretization)
        A_log = self.param(
            "A_log",
            lambda key, shape: -jnp.ones(shape) * 4.0,  # Initialize stable
            (d_inner, cfg.d_state),
        )
        A = -jnp.exp(A_log)  # A is negative for stability

        B_proj = nn.Dense(cfg.d_state, name="B_proj")(x_conv)
        C_proj = nn.Dense(cfg.d_state, name="C_proj")(x_conv)

        D_param = self.param(
            "D",
            nn.initializers.ones,
            (d_inner,),
        )

        # Discretize: A_bar = exp(dt * A), B_bar = dt * B
        dt_expanded = dt[:, :, :, None]  # [B, L, D, 1]
        A_bar = jnp.exp(dt_expanded * A[None, None, :, :])  # [B, L, D, N]
        B_bar = dt_expanded * B_proj[:, :, None, :]  # [B, L, D, N]

        # Run SSM via scan
        def ssm_step(h, inputs):
            a_bar, b_bar, c, x_t = inputs
            # h = A_bar * h + B_bar * x
            h_new = a_bar * h + b_bar * x_t[:, :, None]
            # y = C * h + D * x
            y = jnp.sum(c[:, None] * h_new, axis=-1) + D_param * x_t
            return h_new, y

        # Transpose for scan
        final_state, y_seq = jax.lax.scan(
            ssm_step,
            ssm_state,
            (
                jnp.transpose(A_bar, (1, 0, 2, 3)),
                jnp.transpose(B_bar, (1, 0, 2, 3)),
                jnp.transpose(C_proj, (1, 0, 2)),
                jnp.transpose(x_conv, (1, 0, 2)),
            ),
        )

        # Transpose output back
        y = jnp.transpose(y_seq, (1, 0, 2))

        # Gate and project output
        y = y * jax.nn.silu(gate)
        output = nn.Dense(D, name="out_proj")(y)

        return output, final_state


# =============================================================================
# MANIFOLD PROJECTIONS
# =============================================================================


def project_to_hyperbolic(x: jnp.ndarray, curvature: float = 1.0) -> jnp.ndarray:
    """Project to hyperboloid model H^n.

    Hyperboloid: -x0^2 + x1^2 + ... + xn^2 = -1/c
    """
    c = curvature

    # Compute time component
    spatial_norm_sq = jnp.sum(x**2, axis=-1, keepdims=True)
    x0 = jnp.sqrt(spatial_norm_sq + 1.0 / c)

    # Stack: [x0, x1, ..., xn]
    return jnp.concatenate([x0, x], axis=-1)


def project_to_sphere(x: jnp.ndarray) -> jnp.ndarray:
    """Project to unit sphere S^n."""
    return x / (jnp.linalg.norm(x, axis=-1, keepdims=True) + 1e-8)


# =============================================================================
# GEOMETRIC MAMBA BLOCK
# =============================================================================


class GeometricMambaBlock(nn.Module):
    """Geometric Mamba block operating on H14×S7 manifold.

    JAX port of PyTorch geometric_mamba.py:GeometricMambaBlock
    """

    config: GeometricMambaConfig

    def setup(self):
        self.ssm = SelectiveSSM(self.config)

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        ssm_state: jnp.ndarray | None = None,
        return_manifold: bool = False,
    ) -> GeometricMambaOutput:
        """Forward pass.

        Args:
            x: [B, L, D] input sequence
            ssm_state: [B, D, N] initial state (optional)
            return_manifold: Whether to return manifold coordinates

        Returns:
            GeometricMambaOutput
        """
        cfg = self.config
        B, L, D = x.shape

        # Layer norm
        x_norm = nn.LayerNorm(name="ln")(x)

        # SSM
        y, final_state = self.ssm(x_norm, ssm_state)

        # Residual
        output = x + y

        # Manifold projection (optional)
        manifold_coords = None
        if return_manifold:
            # Project to H14×S7
            h14 = nn.Dense(cfg.hyperbolic_dim, name="to_h14")(output)
            s7 = nn.Dense(cfg.spherical_dim, name="to_s7")(output)

            h14_proj = project_to_hyperbolic(h14, cfg.curvature)
            s7_proj = project_to_sphere(s7)

            manifold_coords = jnp.concatenate([h14_proj, s7_proj], axis=-1)

        return GeometricMambaOutput(
            output=output,
            ssm_state=final_state,
            manifold_coords=manifold_coords,
        )


# =============================================================================
# GEOMETRIC MAMBA (FULL MODEL)
# =============================================================================


class GeometricMamba(nn.Module):
    """Full geometric Mamba model with multiple blocks.

    JAX port of PyTorch geometric_mamba.py:GeometricMamba
    """

    config: GeometricMambaConfig
    num_layers: int = 4

    @nn.compact
    def __call__(
        self,
        x: jnp.ndarray,
        ssm_states: list[jnp.ndarray] | None = None,
    ) -> tuple[jnp.ndarray, list[jnp.ndarray]]:
        """Forward pass through all layers.

        Args:
            x: [B, L, D] input sequence
            ssm_states: List of SSM states per layer

        Returns:
            output: [B, L, D] output sequence
            final_states: List of final SSM states
        """
        if ssm_states is None:
            ssm_states = [None] * self.num_layers

        final_states = []

        for i in range(self.num_layers):
            block = GeometricMambaBlock(self.config, name=f"block_{i}")
            out = block(x, ssm_states[i], return_manifold=(i == self.num_layers - 1))
            x = out.output
            final_states.append(out.ssm_state)

        return x, final_states


# =============================================================================
# FIXED POINT NETWORK
# =============================================================================


class FixedPointNetwork(nn.Module):
    """Network for computing fixed-point updates.

    JAX port of PyTorch strange_loop_improvements.py:FixedPointNetwork
    """

    config: StrangeLoopConfig

    @nn.compact
    def __call__(
        self,
        mu_self: jnp.ndarray,
        s7_context: jnp.ndarray,
    ) -> jnp.ndarray:
        """Compute one fixed-point iteration.

        Args:
            mu_self: [B, 7] current self-model
            s7_context: [B, 7] context

        Returns:
            [B, 7] updated self-model
        """
        cfg = self.config

        # Concatenate inputs
        x = jnp.concatenate([mu_self, s7_context], axis=-1)

        # MLP
        for i in range(cfg.num_layers - 1):
            x = nn.Dense(cfg.hidden_dim, name=f"fc_{i}")(x)
            if cfg.use_layer_norm:
                x = nn.LayerNorm(name=f"ln_{i}")(x)
            x = nn.gelu(x)

        # Final layer
        update = nn.Dense(cfg.s7_dim, name="out")(x)

        # Normalize to S7
        update = update / (jnp.linalg.norm(update, axis=-1, keepdims=True) + 1e-8)

        return update


# =============================================================================
# ITERATIVE STRANGE LOOP
# =============================================================================


class IterativeStrangeLoop(nn.Module):
    """Iterative fixed-point computation for μ_self.

    JAX port of PyTorch strange_loop_improvements.py:IterativeStrangeLoop

    At equilibrium: μ_self* = f(μ_self*, context)
    """

    config: StrangeLoopConfig

    def setup(self):
        self.fixed_point_net = FixedPointNetwork(self.config)

    @nn.compact
    def __call__(
        self,
        s7_context: jnp.ndarray,
        mu_self_init: jnp.ndarray | None = None,
        return_trajectory: bool = False,
    ) -> StrangeLoopOutput:
        """Compute converged μ_self via iteration.

        Args:
            s7_context: [B, 7] context from S7 hierarchy
            mu_self_init: [B, 7] initial μ_self (optional)
            return_trajectory: Whether to return iteration trajectory

        Returns:
            StrangeLoopOutput
        """
        cfg = self.config
        B = s7_context.shape[0]

        # Initialize μ_self
        if mu_self_init is None:
            mu_self = jnp.ones((B, cfg.s7_dim)) / jnp.sqrt(cfg.s7_dim)
        else:
            mu_self = mu_self_init

        trajectory = [mu_self] if return_trajectory else None

        # Fixed-point iteration
        converged = jnp.zeros(B, dtype=bool)

        for k in range(cfg.max_iterations):
            # Compute update
            mu_next = self.fixed_point_net(mu_self, s7_context)

            # Damped update
            mu_new = (1 - cfg.damping) * mu_self + cfg.damping * mu_next

            # Check convergence
            diff = jnp.linalg.norm(mu_new - mu_self, axis=-1)
            converged = converged | (diff < cfg.convergence_threshold)

            mu_self = mu_new

            if return_trajectory:
                trajectory.append(mu_self)

            # Early exit if all converged (can't do in JAX traced code easily)

        trajectory_arr = None
        if return_trajectory and trajectory is not None:
            trajectory_arr = jnp.stack(trajectory, axis=1)

        return StrangeLoopOutput(
            mu_self=mu_self,
            iterations=cfg.max_iterations,
            converged=converged,
            trajectory=trajectory_arr,
        )


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================


def create_geometric_mamba(
    config: GeometricMambaConfig | None = None,
    num_layers: int = 4,
) -> GeometricMamba:
    """Create geometric Mamba model."""
    if config is None:
        config = GeometricMambaConfig()
    return GeometricMamba(config, num_layers=num_layers)


def create_strange_loop(
    config: StrangeLoopConfig | None = None,
) -> IterativeStrangeLoop:
    """Create iterative strange loop module."""
    if config is None:
        config = StrangeLoopConfig()
    return IterativeStrangeLoop(config)


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    # Configs
    "GeometricMambaConfig",
    "StrangeLoopConfig",
    # Outputs
    "GeometricMambaOutput",
    "StrangeLoopOutput",
    # Functions
    "parallel_associative_scan",
    "project_to_hyperbolic",
    "project_to_sphere",
    # Modules
    "SelectiveSSM",
    "GeometricMambaBlock",
    "GeometricMamba",
    "FixedPointNetwork",
    "IterativeStrangeLoop",
    # Factories
    "create_geometric_mamba",
    "create_strange_loop",
]
