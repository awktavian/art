"""MOBIASM Zero-Overhead Runtime - Production Performance

Eliminates ALL abstraction overhead:
- NO stats recording
- NO validation
- NO wrapper layers
- Direct inline operations (PyTorch MPS optimized)
- torch.compile compatible
- Static shapes only

Target: 1.0× baseline (PyTorch MPS is already optimal).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, overload

import torch
import torch.nn as nn


class ZeroOverheadPoincareOps(nn.Module):
    """Zero-overhead Poincaré operations - direct inline math."""

    # Declare buffer types
    curvature: torch.Tensor
    raw_curvature: torch.Tensor
    sqrt_c: torch.Tensor
    radius: torch.Tensor

    def __init__(
        self,
        dim: int = 7,
        curvature: float = 0.1,
        device: str = "mps",
        dtype: torch.dtype = torch.float32,
    ) -> None:
        super().__init__()
        curvature_tensor = torch.tensor(curvature, device=device, dtype=dtype)
        self.register_buffer("curvature", curvature_tensor)
        raw_curvature_tensor = curvature_tensor.clone()
        self.register_buffer("raw_curvature", raw_curvature_tensor)
        sqrt_c_tensor = torch.sqrt(curvature_tensor)
        self.register_buffer("sqrt_c", sqrt_c_tensor)
        radius_tensor = torch.tensor(1.0, device=device, dtype=dtype) / sqrt_c_tensor
        self.register_buffer("radius", radius_tensor)
        self.dim = dim

    def exp0(self, v: torch.Tensor) -> torch.Tensor:
        """Exponential map at origin - INLINE, no overhead."""
        norm_v = v.norm(dim=-1, keepdim=True, p=2).clamp_min(1e-08)
        lambda_0 = 2.0
        sqrt_c = self.sqrt_c
        tanh_arg = (sqrt_c * lambda_0 * norm_v / 2).clamp(-10.0, 10.0)
        factor = torch.tanh(tanh_arg) / (sqrt_c * norm_v)
        out = factor * v
        return self.project(out)

    def log0(self, z: torch.Tensor) -> torch.Tensor:
        """Logarithmic map at origin - INLINE, no overhead."""
        norm_z = z.norm(dim=-1, keepdim=True, p=2).clamp_min(1e-08)
        atanh_term = torch.atanh((self.sqrt_c * norm_z).clamp(-0.999999, 0.999999))
        factor = atanh_term / (self.sqrt_c * norm_z)
        return factor * z

    def mobius_add(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """Möbius addition - INLINE, no overhead."""
        x2 = (x * x).sum(dim=-1, keepdim=True)
        y2 = (y * y).sum(dim=-1, keepdim=True)
        xy = (x * y).sum(dim=-1, keepdim=True)
        c = self.curvature
        num = (1 + 2 * c * xy + c * y2) * x + (1 - c * x2) * y
        den = 1 + 2 * c * xy + c * c * x2 * y2
        out = num / den.clamp_min(1e-06)
        return self.project(out)

    def mobius_scalar_mul(self, r: float | torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        """Möbius scalar multiplication - INLINE."""
        if isinstance(r, (int, float)):
            r = torch.tensor(r, device=x.device, dtype=x.dtype)
        norm_x = x.norm(dim=-1, keepdim=True, p=2).clamp_min(1e-08)
        sqrt_c = self.sqrt_c
        inner = torch.atanh((sqrt_c * norm_x).clamp(-0.999999, 0.999999))
        tanh_term = torch.tanh((r * inner).clamp(-10.0, 10.0))
        factor = tanh_term / (sqrt_c * norm_x)
        out = factor * x
        return self.project(out)

    def distance(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """Hyperbolic distance - INLINE, no overhead."""
        diff = self.mobius_add(x, -y)
        norm = diff.norm(dim=-1, p=2).clamp_min(1e-08)
        sqrt_c = self.sqrt_c
        atanh_term = torch.atanh((sqrt_c * norm).clamp(-0.999999, 0.999999))
        dist = 2 * atanh_term / sqrt_c
        return dist

    def project(self, x: torch.Tensor) -> torch.Tensor:
        """Project to Poincaré ball - INLINE."""
        norm = x.norm(dim=-1, keepdim=True, p=2)
        max_norm = self.radius * 0.999
        factor = torch.where(
            norm > max_norm, max_norm / norm.clamp_min(1e-08), torch.ones_like(norm)
        )
        return x * factor


class ZeroOverheadOctonionOps(nn.Module):
    """Zero-overhead octonion operations - direct inline math.

    Relationship to other implementations:
    - OctonionManifold (kagami.core.world_model.manifolds.octonion): Primary PyTorch
      implementation with full differentiability and geometric operations.
    - Metal kernels (mobiasm_ops.metal): GPU-accelerated batch operations for
      high-throughput scenarios.
    - This class: Zero-overhead inline PyTorch version for MOBIASM runtime, used
      as CPU fallback when Metal kernels aren't available or for single-sample ops.

    Design: NO validation, NO stats recording - pure inline operations.
    """

    def __init__(self, device: str = "mps", dtype: torch.dtype = torch.float32) -> None:
        super().__init__()
        self.device = device
        self.dtype = dtype

    def cayley_dickson_mul(self, o1: torch.Tensor, o2: torch.Tensor) -> torch.Tensor:
        """Cayley-Dickson multiplication - INLINE, no overhead.

        Assumes last dim = 8 (octonions).
        Uses (a,b) * (c,d) = (ac - d*b, da + bc*)
        """
        a = o1[..., :4]
        b = o1[..., 4:]
        c = o2[..., :4]
        d = o2[..., 4:]
        ac = self._quat_mul(a, c)
        d_conj_b = self._quat_mul(self._quat_conj(d), b)
        first = ac - d_conj_b
        da = self._quat_mul(d, a)
        b_conj_c = self._quat_mul(b, self._quat_conj(c))
        second = da + b_conj_c
        return torch.cat([first, second], dim=-1)

    def _quat_mul(self, q1: torch.Tensor, q2: torch.Tensor) -> torch.Tensor:
        """Quaternion multiplication (Hamilton product) - INLINE."""
        w1, x1, y1, z1 = (q1[..., 0:1], q1[..., 1:2], q1[..., 2:3], q1[..., 3:4])
        w2, x2, y2, z2 = (q2[..., 0:1], q2[..., 1:2], q2[..., 2:3], q2[..., 3:4])
        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2
        return torch.cat([w, x, y, z], dim=-1)

    def _quat_conj(self, q: torch.Tensor) -> torch.Tensor:
        """Quaternion conjugate - INLINE."""
        return torch.cat([q[..., :1], -q[..., 1:]], dim=-1)

    def conjugate(self, o: torch.Tensor) -> torch.Tensor:
        """Octonion conjugate - INLINE."""
        return torch.cat([o[..., :1], -o[..., 1:]], dim=-1)

    def norm(self, o: torch.Tensor) -> torch.Tensor:
        """Octonion norm - INLINE."""
        return o.norm(dim=-1, p=2)

    def project_to_s7(self, o: torch.Tensor) -> torch.Tensor:
        """Project to unit sphere S⁷ - INLINE."""
        norm = o.norm(dim=-1, keepdim=True, p=2).clamp_min(1e-08)
        projected = o / norm
        projected = projected * (1.0 - 1e-06)
        return projected


class MobiASMZeroOverheadRuntime(nn.Module):
    """Zero-overhead MOBIASM runtime for production.

    Design principles:
    - NO stats recording (zero time.perf_counter() calls)
    - NO validation (trust inputs)
    - NO wrapper layers (direct operations)
    - PyTorch MPS native (already optimal)
    - torch.compile friendly
    - Static shapes only

    Expected performance: 1.0× (matches direct PyTorch baseline).
    """

    def __init__(
        self,
        hyperbolic_dim: int = 7,
        curvature: float = 0.1,
        device: str = "mps",
        dtype: torch.dtype = torch.float32,
        use_compile: bool = False,
    ) -> None:
        super().__init__()
        self.hyperbolic_dim = hyperbolic_dim
        self.device = device
        self.dtype = dtype
        self.poincare = ZeroOverheadPoincareOps(
            dim=hyperbolic_dim, curvature=curvature, device=device, dtype=dtype
        )
        self.octonion = ZeroOverheadOctonionOps(device=device, dtype=dtype)

        if use_compile:
            try:
                self.poincare.exp0 = torch.compile(self.poincare.exp0, mode="max-autotune")  # type: ignore[method-assign]
                self.poincare.log0 = torch.compile(self.poincare.log0, mode="max-autotune")  # type: ignore[method-assign]
                self.poincare.mobius_add = torch.compile(  # type: ignore[method-assign]
                    self.poincare.mobius_add, mode="max-autotune"
                )
                self.poincare.distance = torch.compile(self.poincare.distance, mode="max-autotune")  # type: ignore[method-assign]
            except Exception:
                pass

    @overload
    def to(
        self,
        device: str | torch.device | int | None = ...,
        dtype: torch.dtype | None = ...,
        non_blocking: bool = ...,
    ) -> MobiASMZeroOverheadRuntime: ...

    @overload
    def to(self, dtype: torch.dtype, non_blocking: bool = ...) -> MobiASMZeroOverheadRuntime: ...

    @overload
    def to(self, tensor: torch.Tensor, non_blocking: bool = ...) -> MobiASMZeroOverheadRuntime: ...

    def to(self, *args: Any, **kwargs: Any) -> MobiASMZeroOverheadRuntime:
        """Ensure buffers and inner ops move together; return self for chaining."""
        super().to(*args, **kwargs)
        self.poincare.to(*args, **kwargs)
        self.octonion.to(*args, **kwargs)
        # Update device if a device was provided
        if args and (isinstance(args[0], (str, torch.device, int))):
            self.device = str(args[0])
        elif "device" in kwargs:
            self.device = str(kwargs["device"])
        return self

    def h_exp0(self, v: torch.Tensor) -> torch.Tensor:
        """H.EXP0: Zero-overhead exponential map."""
        return self.poincare.exp0(v)

    def h_log0(self, z: torch.Tensor) -> torch.Tensor:
        """H.LOG0: Zero-overhead logarithmic map."""
        return self.poincare.log0(z)

    def h_add(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """H.ADD: Zero-overhead Möbius addition."""
        return self.poincare.mobius_add(x, y)

    def h_mul(self, r: float | torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        """H.MUL: Zero-overhead Möbius scalar multiplication."""
        return self.poincare.mobius_scalar_mul(r, x)

    def h_dist(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """H.DIST: Zero-overhead hyperbolic distance."""
        return self.poincare.distance(x, y)

    def h_project(self, x: torch.Tensor) -> torch.Tensor:
        """H.PROJECT: Zero-overhead projection to ball."""
        return self.poincare.project(x)

    def h_norm(self, x: torch.Tensor) -> torch.Tensor:
        """H.NORM: Zero-overhead norm computation."""
        return x.norm(dim=-1, p=2)

    def h_scalar_mul(self, r: float | torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        """H.SCALAR_MUL: Alias for h_mul."""
        return self.h_mul(r, x)

    def h_exp(self, z: torch.Tensor, v: torch.Tensor) -> torch.Tensor:
        """H.EXP: Exponential map at point."""
        # Use exp0 after parallel transport to origin
        return self.poincare.mobius_add(z, self.poincare.exp0(v))

    def h_log(self, z: torch.Tensor, z_prime: torch.Tensor) -> torch.Tensor:
        """H.LOG: Logarithmic map at point."""
        # Translate to origin, compute log0, transport back
        diff = self.poincare.mobius_add(z_prime, -z)
        return self.poincare.log0(diff)

    def h_parallel_transport(
        self, z1: torch.Tensor, z2: torch.Tensor, v: torch.Tensor
    ) -> torch.Tensor:
        """H.PARALLEL_TRANSPORT: Parallel transport of tangent vector."""
        # Simplified parallel transport using gyration
        lambda_z1 = 2.0 / (
            1.0 - (self.poincare.curvature * (z1 * z1).sum(dim=-1, keepdim=True)).clamp(max=0.999)
        )
        lambda_z2 = 2.0 / (
            1.0 - (self.poincare.curvature * (z2 * z2).sum(dim=-1, keepdim=True)).clamp(max=0.999)
        )
        return v * (lambda_z1 / lambda_z2.clamp_min(1e-6))

    def o_mul(self, o1: torch.Tensor, o2: torch.Tensor) -> torch.Tensor:
        """O.MUL: Zero-overhead Cayley-Dickson multiplication."""
        return self.octonion.cayley_dickson_mul(o1, o2)

    def o_conj(self, o: torch.Tensor) -> torch.Tensor:
        """O.CONJ: Zero-overhead conjugate."""
        return self.octonion.conjugate(o)

    def o_norm(self, o: torch.Tensor) -> torch.Tensor:
        """O.NORM: Zero-overhead norm."""
        return self.octonion.norm(o)

    def o_project(self, o: torch.Tensor) -> torch.Tensor:
        """O.PROJECT: Zero-overhead S⁷ projection."""
        return self.octonion.project_to_s7(o)

    def o_slerp(self, o1: torch.Tensor, o2: torch.Tensor, t: float) -> torch.Tensor:
        """O.SLERP: Spherical linear interpolation on S⁷."""
        # Normalize both
        o1_n = self.octonion.project_to_s7(o1)
        o2_n = self.octonion.project_to_s7(o2)
        # Compute angle
        dot = (o1_n * o2_n).sum(dim=-1, keepdim=True).clamp(-0.9999, 0.9999)
        omega = torch.acos(dot)
        sin_omega = torch.sin(omega).clamp_min(1e-6)
        # Interpolate
        a = torch.sin((1 - t) * omega) / sin_omega
        b = torch.sin(t * omega) / sin_omega
        return a * o1_n + b * o2_n

    # Fiber bundle operations (simplified stubs)
    def f_lift(self, base: torch.Tensor) -> torch.Tensor:
        """F.LIFT: Lift from base space."""
        return torch.cat([base, torch.zeros_like(base[..., :1])], dim=-1)

    def f_project_down(self, fiber: torch.Tensor) -> torch.Tensor:
        """F.PROJECT_DOWN: Project from fiber to base."""
        return fiber[..., :-1]

    def f_horizontal_lift(self, base: torch.Tensor, tangent: torch.Tensor) -> torch.Tensor:
        """F.HORIZONTAL_LIFT: Horizontal lift of tangent vector."""
        return torch.cat([tangent, torch.zeros_like(tangent[..., :1])], dim=-1)

    def f_parallel_transport(
        self, z1: torch.Tensor, z2: torch.Tensor, fiber: torch.Tensor
    ) -> torch.Tensor:
        """F.PARALLEL_TRANSPORT: Parallel transport in fiber."""
        # Simplified: just return fiber (identity connection)
        return fiber

    def f_curvature(self, base: torch.Tensor) -> torch.Tensor:
        """F.CURVATURE: Compute fiber bundle curvature."""
        # Simplified: return small constant curvature
        return torch.full_like(base[..., :1], 0.1)

    # Vector operations
    def v_dot(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """V.DOT: Dot product."""
        return (x * y).sum(dim=-1)

    def v_norm(self, x: torch.Tensor) -> torch.Tensor:
        """V.NORM: Vector norm."""
        return x.norm(dim=-1, p=2)

    def v_add(self, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """V.ADD: Vector addition."""
        return x + y

    def v_scale(self, r: float | torch.Tensor, x: torch.Tensor) -> torch.Tensor:
        """V.SCALE: Vector scaling."""
        if isinstance(r, (int, float)):
            r = torch.tensor(r, device=x.device, dtype=x.dtype)
        return r * x

    def v_normalize(self, x: torch.Tensor) -> torch.Tensor:
        """V.NORMALIZE: Normalize vector."""
        return x / x.norm(dim=-1, keepdim=True, p=2).clamp_min(1e-8)

    def v_map(
        self, operation: Callable[[torch.Tensor], torch.Tensor], batch: list[torch.Tensor]
    ) -> list[torch.Tensor]:
        """V.MAP: Vectorized map (minimal overhead)."""
        return [operation(x) for x in batch]

    def v_reduce(
        self,
        operation: Callable[[torch.Tensor, torch.Tensor], torch.Tensor],
        batch: list[torch.Tensor],
        init: torch.Tensor,
    ) -> torch.Tensor:
        """V.REDUCE: Vectorized reduce."""
        result = init
        for x in batch:
            result = operation(result, x)
        return result

    # State management
    def s_save(self, label: str, *state: torch.Tensor) -> None:
        """S.SAVE: Save state with label."""
        if not hasattr(self, "_saved_states"):
            self._saved_states = {}
        self._saved_states[label] = state

    def s_load(self, label: str) -> tuple[Any, ...]:
        """S.LOAD: Load saved state."""
        if not hasattr(self, "_saved_states"):
            self._saved_states = {}
        return self._saved_states.get(label, ())

    def s_push(self, *state: torch.Tensor) -> None:
        """S.PUSH: Push state to stack."""
        if not hasattr(self, "_state_stack"):
            self._state_stack = []
        self._state_stack.append(state)

    def s_pop(self) -> tuple[Any, ...]:
        """S.POP: Pop state from stack."""
        if not hasattr(self, "_state_stack"):
            self._state_stack = []
        return self._state_stack.pop() if self._state_stack else ()

    def s_clear(self) -> None:
        """S.CLEAR: Clear all saved states."""
        if hasattr(self, "_saved_states"):
            self._saved_states.clear()
        if hasattr(self, "_state_stack"):
            self._state_stack.clear()

    # Comparison operations
    def c_compare(self, op: str, x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
        """C.COMPARE: Generic comparison (LT, EQ, GT)."""
        if op == "LT" or op == "C.LT":
            return (x < y).float()
        elif op == "EQ" or op == "C.EQ":
            return torch.isclose(x, y, rtol=1e-5).float()
        elif op == "GT" or op == "C.GT":
            return (x > y).float()
        else:
            return torch.zeros_like(x)

    def c_near(self, x: torch.Tensor, y: torch.Tensor, epsilon: float = 1e-5) -> torch.Tensor:
        """C.NEAR: Check if values are near."""
        return torch.isclose(x, y, rtol=epsilon, atol=epsilon).float()

    # Geometric queries
    def g_check_property(self, x: torch.Tensor, property_name: str) -> bool:
        """G.CHECK: Check geometric property."""
        norm = x.norm(dim=-1, p=2)
        if property_name == "in_ball":
            return bool((norm < self.poincare.radius * 0.999).all().item())
        elif property_name == "on_sphere":
            return bool(torch.isclose(norm, torch.ones_like(norm), rtol=1e-4).all().item())
        return False

    def g_distance_to_boundary(self, x: torch.Tensor) -> torch.Tensor:
        """G.DISTANCE: Distance to manifold boundary."""
        norm = x.norm(dim=-1, keepdim=True, p=2)
        return self.poincare.radius - norm

    # Aggregation operations
    def a_sum(self, points: list[torch.Tensor]) -> torch.Tensor:
        """A.SUM: Sum in hyperbolic space."""
        result = points[0]
        for p in points[1:]:
            result = self.poincare.mobius_add(result, p)
        return result

    def a_max(self, points: list[torch.Tensor]) -> torch.Tensor:
        """A.MAX: Element-wise maximum."""
        return torch.stack(points).max(dim=0)[0]

    def a_min(self, points: list[torch.Tensor]) -> torch.Tensor:
        """A.MIN: Element-wise minimum."""
        return torch.stack(points).min(dim=0)[0]

    def a_mean(self, points: list[torch.Tensor], max_iter: int = 50) -> torch.Tensor:
        """A.MEAN: Hyperbolic mean (Fréchet mean) - minimal overhead."""
        tangent_sum = torch.stack([self.h_log0(z) for z in points]).mean(dim=0)
        z_mean = self.h_exp0(tangent_sum)
        for _ in range(max_iter):
            grads = torch.stack(
                [
                    self.poincare.log0(
                        self.poincare.mobius_add(self.poincare.mobius_add(z_mean, z_mean * 0), -z)
                    )
                    for z in points
                ]
            )
            grad = grads.mean(dim=0)
            if grad.norm(p=2) < 1e-05:
                break
            z_mean = self.poincare.mobius_add(z_mean, grad * 0.1)
        return z_mean

    # Interpolation operations
    def i_lerp(self, x: torch.Tensor, y: torch.Tensor, t: float) -> torch.Tensor:
        """I.LERP: Linear interpolation."""
        return (1 - t) * x + t * y

    def i_geodesic(self, x: torch.Tensor, y: torch.Tensor, t: float) -> torch.Tensor:
        """I.GEODESIC: Geodesic interpolation in hyperbolic space."""
        # Compute tangent vector from x to y
        v = self.h_log(x, y)
        # Scale by t and map back
        return self.h_exp(x, v * t)

    def i_sample(self, distribution: str = "normal", **params) -> torch.Tensor:  # type: ignore[no-untyped-def]
        """I.SAMPLE: Sample from distribution."""
        shape = params.get("shape", (self.hyperbolic_dim,))
        device = self.device
        if distribution == "normal":
            mean = params.get("mean", 0.0)
            std = params.get("std", 1.0)
            return torch.randn(shape, device=device) * std + mean
        elif distribution == "uniform":
            low = params.get("low", 0.0)
            high = params.get("high", 1.0)
            return torch.rand(shape, device=device) * (high - low) + low
        else:
            return torch.zeros(shape, device=device)

    # Meta operations
    def m_set_curvature(self, c: float) -> None:
        """M.CURVATURE: Set curvature parameter."""
        self.poincare.curvature.data.fill_(c)
        self.poincare.sqrt_c.data.copy_(torch.sqrt(self.poincare.curvature))
        self.poincare.radius.data.copy_(1.0 / self.poincare.sqrt_c)

    def m_set_device(self, device: str) -> None:
        """M.DEVICE: Set compute device."""
        self.device = device
        self.to(device)

    def m_trace(self, enabled: bool = True) -> None:
        """M.TRACE: Enable/disable tracing (no-op in zero-overhead)."""
        # Zero-overhead runtime doesn't emit traces, but we store the flag
        # for introspection / compatibility with other runtimes.
        self._trace_enabled = bool(enabled)
        return None

    def m_validate(self, enabled: bool = True) -> None:
        """M.VALIDATE: Enable/disable validation (no-op in zero-overhead)."""
        # Zero-overhead runtime doesn't perform runtime validation, but we store
        # the flag for parity with validating runtimes.
        self._validation_enabled = bool(enabled)
        return None
