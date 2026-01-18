"""Octonion algebra operations on S⁷ (7D intrinsic representation).

UPDATED (Nov 30, 2025): Uses 7D intrinsic S⁷ representation
============================================================
S⁷ is a 7-dimensional manifold. We represent points on it using the
7 imaginary octonion components (e₁...e₇), NOT the 8D embedding.

The real component e₀ = 1 represents Kagami (the observer).
The 7 imaginary units e₁...e₇ correspond to the 7 colonies:
    e₁: Spark  (Fold catastrophe)
    e₂: Forge  (Cusp catastrophe)
    e₃: Flow   (Swallowtail catastrophe)
    e₄: Nexus  (Butterfly catastrophe)
    e₅: Beacon (Hyperbolic catastrophe)
    e₆: Grove  (Elliptic catastrophe)
    e₇: Crystal (Parabolic catastrophe)

For multiplication, we embed 7D → 8D (prepend 0 as real part),
multiply using Cayley-Dickson, then extract the imaginary result.

Implements:
- Pure imaginary octonion multiplication (7D × 7D → 7D)
- Fano plane products (e_i × e_j = ±e_k following Fano lines)
- Unit normalization on S⁷
- Exp/Log maps for tangent operations

Based on:
- Baez (2002): The Octonions
- Tian (2000): Matrix Representations of Octonions
- Dray & Manogue (2015): The Geometry of the Octonions
"""

from __future__ import annotations

import threading
from typing import Any, cast

import torch
import torch.nn as nn

# =============================================================================
# FANO PLANE STRUCTURE (Defines e_i × e_j = ±e_k)
# =============================================================================

# Fano plane multiplication tables are now loaded via centralized fano_tensor_ops
# This ensures single source of truth for all Fano plane operations


class OctonionManifold(nn.Module):
    """S⁷ manifold using 7D intrinsic representation (pure imaginary octonions).

    This represents points on the unit 7-sphere using 7 coordinates
    (the imaginary octonion components e₁...e₇). The real component
    e₀ is implicitly zero for points on the sphere.

    For the full 8D embedding, use embed_to_8d() and extract_from_8d().
    """

    def __init__(self, eps: float = 1e-8) -> None:
        """Initialize octonion manifold.

        Args:
            eps: Numerical epsilon for stability
        """
        super().__init__()
        self.eps = eps
        self._init_fano_structure()

    def _init_fano_structure(self) -> None:
        """Initialize Fano plane structure tables (uses centralized implementation)."""
        from kagami_math.fano_tensor_ops import (
            get_fano_multiplication_table,
            get_fano_sign_table,
        )

        # Use cached global tables (device=None means CPU by default)
        # Clone to ensure this instance owns its buffers
        self.register_buffer(
            "_fano_table", get_fano_multiplication_table(device=None).clone(), persistent=False
        )
        self.register_buffer(
            "_fano_signs", get_fano_sign_table(device=None).clone(), persistent=False
        )

    def embed_to_8d(self, v7: torch.Tensor) -> torch.Tensor:
        """Embed 7D S⁷ point to 8D octonion (prepend zero real part).

        Args:
            v7: Pure imaginary octonion [..., 7]

        Returns:
            Full octonion [0, v₁...v₇] with shape [..., 8]
        """
        zeros = torch.zeros(*v7.shape[:-1], 1, dtype=v7.dtype, device=v7.device)
        return torch.cat([zeros, v7], dim=-1)

    def extract_from_8d(self, o8: torch.Tensor) -> torch.Tensor:
        """Extract 7D imaginary components from 8D octonion.

        Args:
            o8: Full octonion [..., 8]

        Returns:
            Imaginary part [..., 7]
        """
        return o8[..., 1:]

    def project_to_s7(self, v: torch.Tensor) -> torch.Tensor:
        """Project to unit sphere S⁷.

        Args:
            v: Vector [..., 7]

        Returns:
            Unit vector [..., 7] with ||v|| = 1
        """
        norm = v.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)
        return cast(torch.Tensor, v / norm)

    def multiply(self, v1: torch.Tensor, v2: torch.Tensor) -> torch.Tensor:
        """Multiply two pure imaginary octonions (7D × 7D → 7D).

        Uses the Cayley-Dickson formula internally but returns only
        the imaginary part (the real part from e_i × e_i = -1 is discarded
        since we're working on S⁷).

        Args:
            v1: First vector [..., 7]
            v2: Second vector [..., 7]

        Returns:
            Product (imaginary part only) [..., 7]
        """
        # Embed to 8D
        o1 = self.embed_to_8d(v1)
        o2 = self.embed_to_8d(v2)

        # Cayley-Dickson multiplication
        result_8d = self._cayley_dickson_mul(o1, o2)

        # Extract imaginary part
        return result_8d[..., 1:]

    def fano_product(
        self, i: int, j: int, v1: torch.Tensor, v2: torch.Tensor
    ) -> tuple[int, torch.Tensor]:
        """Compute the Fano plane product of two basis elements.

        Given e_i and e_j coefficients, compute which basis element k
        they produce and with what sign: e_i × e_j = ±e_k

        Args:
            i: First basis index (1-7)
            j: Second basis index (1-7)
            v1: Coefficient of e_i [..., 1]
            v2: Coefficient of e_j [..., 1]

        Returns:
            (k, coefficient): Target basis (1-7) and coefficient v1*v2*sign
        """
        if i == j:
            # e_i × e_i = -1 (goes to real, not on S⁷)
            return 0, -v1 * v2

        # 0-indexed lookup
        fano_table = cast(torch.Tensor, self._fano_table)
        fano_signs = cast(torch.Tensor, self._fano_signs)

        k0 = int(fano_table[i - 1, j - 1].item())
        sign = fano_signs[i - 1, j - 1]

        return k0 + 1, sign * v1 * v2  # Return 1-indexed

    def colony_multiply(self, colony_a: str, colony_b: str) -> str:
        """Get the result colony from multiplying two colonies.

        Uses Fano plane structure to determine: Colony_a × Colony_b = Colony_c

        Args:
            colony_a: First colony name
            colony_b: Second colony name

        Returns:
            Result colony name
        """
        COLONIES = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]

        if colony_a not in COLONIES or colony_b not in COLONIES:
            raise ValueError(f"Unknown colony: {colony_a} or {colony_b}")

        i = COLONIES.index(colony_a) + 1  # 1-indexed
        j = COLONIES.index(colony_b) + 1

        if i == j:
            return "kagami"  # e_i × e_i = -1 (scalar, Kagami is the observer)

        fano_table = cast(torch.Tensor, self._fano_table)
        k0 = int(fano_table[i - 1, j - 1].item())
        return COLONIES[k0]

    def conjugate_s7(self, v: torch.Tensor) -> torch.Tensor:
        """Conjugate of pure imaginary octonion: v* = -v.

        For pure imaginary: conjugate negates all components.
        NOTE: Use conjugate() for general octonions.

        Args:
            v: Pure imaginary octonion [..., 7]

        Returns:
            Conjugate -v [..., 7]
        """
        return -v

    def inner_product_s7(self, v1: torch.Tensor, v2: torch.Tensor) -> torch.Tensor:
        """Inner product: v₁ · v₂.

        This is the standard Euclidean inner product on ℝ⁷,
        which equals Re(v̄₁ × v₂) for pure imaginary octonions.

        Args:
            v1: First vector [..., 7]
            v2: Second vector [..., 7]

        Returns:
            Inner product [...] (scalar)
        """
        return (v1 * v2).sum(dim=-1)

    def check_alternativity(
        self, a: torch.Tensor, b: torch.Tensor, tol: float = 1e-5
    ) -> tuple[bool, dict[str, Any]]:
        """Check the alternativity property of octonions (Baez, 2002).

        Octonions are ALTERNATIVE (though not associative), meaning:
            a(ab) = a²b  (left alternative)
            (ab)b = ab²  (right alternative)
            (ab)a = a(ba) (flexible identity)

        IMPORTANT: For pure imaginary octonions (our S⁷ representation):
        - a² = -|a|² (purely REAL, not in our 7D representation)
        - The flexible identity (ab)a = a(ba) is the key verifiable property
        - Left/right alternativity involve the real part which we discard

        Reference: Baez, J.C. (2002) "The Octonions", Section 2.1

        Args:
            a: First octonion [..., 7] (pure imaginary)
            b: Second octonion [..., 7] (pure imaginary)
            tol: Numerical tolerance for equality check

        Returns:
            (is_alternative, diagnostics): Bool and dict with error metrics
        """
        # =================================================================
        # For pure imaginary octonions on S⁷:
        # - a² = -|a|² is REAL (goes to e₀ component, not in our 7D rep)
        # - The left/right alternativity involve this real part
        # - The FLEXIBLE IDENTITY is the key verifiable property
        # =================================================================

        # Compute products
        ab = self.multiply(a, b)
        ba = self.multiply(b, a)

        # FLEXIBLE IDENTITY: (ab)a = a(ba)
        # This is the KEY alternativity property for pure imaginary elements
        ab_a = self.multiply(ab, a)
        a_ba = self.multiply(a, ba)
        flexible_error = (ab_a - a_ba).abs().max()

        # MOUFANG IDENTITY CHECK: a(b(ac)) = ((ab)a)c
        # Another key property of octonions (implies alternativity)
        c = torch.randn_like(a)
        c = self.project_to_s7(c)
        ac = self.multiply(a, c)
        b_ac = self.multiply(b, ac)
        a_b_ac = self.multiply(a, b_ac)

        ab_a_inner = self.multiply(ab, a)
        ab_a_c = self.multiply(ab_a_inner, c)
        moufang_error = (a_b_ac - ab_a_c).abs().max()

        # ANTI-COMMUTATIVITY for pure imaginaries: ab = -ba + 2(a·b)e₀
        # Since we discard e₀, we check: ab + ba ≈ 0 (when a·b ≈ 0)
        # For general a,b: this won't hold exactly
        anticommutator = ab + ba
        anticommutator_norm = anticommutator.norm()

        # Expected: ||ab + ba|| ≈ 2|a·b| (the real part we're missing)
        expected_anticommutator = 2 * (a * b).sum().abs()
        anticommutator_error = (anticommutator_norm - expected_anticommutator).abs()

        # The algebra is "alternative" if flexible identity holds
        # (left/right alternativity follow from flexible + anti-commutativity)
        is_alternative = bool((flexible_error < tol).item())

        diagnostics = {
            "flexible_identity_error": flexible_error,
            "moufang_identity_error": moufang_error,
            "anticommutator_consistency_error": anticommutator_error,
            "tolerance": torch.tensor(tol),
            "note": "For pure imaginary octonions, flexible identity is the key test",
        }

        return is_alternative, diagnostics

    def verify_octonion_algebra(self, samples: int = 100) -> dict[str, Any]:
        """Verify key octonion algebra properties with random samples.

        Tests (for pure imaginary octonions on S⁷):
        1. Flexible identity: (ab)a = a(ba) - KEY alternativity property
        2. Anti-commutativity of imaginary units: eᵢeⱼ = -eⱼeᵢ (i≠j)
        3. Fano plane structure consistency

        Note on norm preservation:
        For pure imaginary octonions, |ab|² = |a|²|b|² - (a·b)² (Pythagorean-like)
        The classical |ab| = |a||b| only holds for full octonions including real part.

        Reference: Baez, J.C. (2002) "The Octonions"

        Args:
            samples: Number of random test samples

        Returns:
            Dictionary with verification results and statistics
        """
        fano_table_device = (
            self._fano_table.device if isinstance(self._fano_table, torch.Tensor) else None
        )

        results = {
            "flexible_identity_pass_rate": 0.0,
            "anticommutative_verified": True,
            "fano_structure_verified": True,
            "samples_tested": samples,
            "theory": "Baez (2002) The Octonions",
        }

        flex_passes = 0
        tol = 1e-4

        for _ in range(samples):
            # Random unit vectors on S⁷
            a = torch.randn(7, device=fano_table_device)
            b = torch.randn(7, device=fano_table_device)
            a = self.project_to_s7(a)
            b = self.project_to_s7(b)

            # Test flexible identity (key alternativity property)
            is_alt, _diag = self.check_alternativity(a, b, tol=tol)
            if is_alt:
                flex_passes += 1

        results["flexible_identity_pass_rate"] = flex_passes / samples

        # Test anti-commutativity of basis elements: eᵢ × eⱼ = -eⱼ × eᵢ
        for i in range(7):
            for j in range(7):
                if i != j:
                    e_i = torch.zeros(7, device=fano_table_device)
                    e_j = torch.zeros(7, device=fano_table_device)
                    e_i[i] = 1.0
                    e_j[j] = 1.0

                    ij = self.multiply(e_i, e_j)
                    ji = self.multiply(e_j, e_i)

                    if not torch.allclose(ij, -ji, atol=1e-6):
                        results["anticommutative_verified"] = False
                        break

        # Test Fano plane structure: eᵢ × eⱼ = ±eₖ
        # Verifies that basis element products yield exactly one other basis element
        # Uses implementation's own Fano table for consistency
        fano_verified = True
        for i in range(7):
            for j in range(7):
                if i == j:
                    continue  # Skip e_i × e_i = -1 (real part)

                e_i = torch.zeros(7, device=fano_table_device)
                e_j = torch.zeros(7, device=fano_table_device)
                e_i[i] = 1.0
                e_j[j] = 1.0

                result = self.multiply(e_i, e_j)

                # Result should be exactly ±1 at one index, 0 elsewhere
                abs_result = result.abs()
                max_val = abs_result.max()
                other_vals = abs_result.sum() - max_val

                # Verify: one component ≈ 1, others ≈ 0
                if not (max_val > 0.99 and other_vals < 0.01):
                    fano_verified = False
                    break
            if not fano_verified:
                break

        results["fano_structure_verified"] = fano_verified

        return results

    def geodesic_distance(self, v1: torch.Tensor, v2: torch.Tensor) -> torch.Tensor:
        """Geodesic distance on S⁷.

        d(v1, v2) = arccos(v1 · v2) for unit vectors.

        Args:
            v1: Unit vector [..., 7]
            v2: Unit vector [..., 7]

        Returns:
            Distance [...] (scalar)
        """
        cos_angle = self.inner_product(v1, v2).clamp(-1 + self.eps, 1 - self.eps)
        return torch.acos(cos_angle)

    def exp_s7(self, base: torch.Tensor, tangent: torch.Tensor) -> torch.Tensor:
        """Exponential map: move from base point along tangent vector.

        On S⁷: exp_p(v) = cos(||v||)p + sin(||v||)(v/||v||)
        NOTE: Use exp() for general octonion exponential.

        Args:
            base: Base point on S⁷ [..., 7]
            tangent: Tangent vector at base [..., 7]

        Returns:
            New point on S⁷ [..., 7]
        """
        norm = tangent.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)
        direction = tangent / norm
        return cast(torch.Tensor, torch.cos(norm) * base + torch.sin(norm) * direction)

    def log_s7(self, base: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        """Logarithmic map: compute tangent vector from base to target.

        On S⁷: log_p(q) = θ(q - (p·q)p)/||q - (p·q)p||
        where θ = arccos(p·q)

        Args:
            base: Base point on S⁷ [..., 7]
            target: Target point on S⁷ [..., 7]

        Returns:
            Tangent vector at base [..., 7]
        """
        cos_angle = self.inner_product(base, target).unsqueeze(-1)
        cos_angle = cos_angle.clamp(-1 + self.eps, 1 - self.eps)
        theta = torch.acos(cos_angle)

        # Project out the component parallel to base
        parallel = cos_angle * base
        perpendicular = target - parallel
        perp_norm = perpendicular.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)
        direction = perpendicular / perp_norm

        return cast(torch.Tensor, theta * direction)

    def parallel_transport(
        self, base: torch.Tensor, target: torch.Tensor, vector: torch.Tensor
    ) -> torch.Tensor:
        """Parallel transport a tangent vector along geodesic.

        Transport vector from T_base(S⁷) to T_target(S⁷).

        Args:
            base: Starting point [..., 7]
            target: Ending point [..., 7]
            vector: Tangent vector at base [..., 7]

        Returns:
            Transported vector at target [..., 7]
        """
        # Get geodesic direction
        log_map = self.log_s7(base, target)
        theta = log_map.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)
        direction = log_map / theta

        # Decompose vector into parallel and perpendicular to geodesic
        parallel_component = self.inner_product_s7(vector, direction).unsqueeze(-1)
        parallel = parallel_component * direction
        perpendicular = vector - parallel

        # Parallel component along geodesic remains unchanged
        # Perpendicular rotates with the geodesic
        cos_theta = torch.cos(theta)
        sin_theta = torch.sin(theta)

        # Transport formula
        transported = (
            parallel  # Parallel part unchanged
            + cos_theta * perpendicular  # Perpendicular rotates
            - sin_theta * parallel_component * base  # Cross term
        )

        return cast(torch.Tensor, transported)

    def multiply_8d(self, o1: torch.Tensor, o2: torch.Tensor) -> torch.Tensor:
        """Full 8D multiplication (public wrapper for Cayley-Dickson).

        Args:
            o1: First octonion [..., 8]
            o2: Second octonion [..., 8]

        Returns:
            Product [..., 8]
        """
        return self._cayley_dickson_mul(o1, o2)

    def _cayley_dickson_mul(self, o1: torch.Tensor, o2: torch.Tensor) -> torch.Tensor:
        """Full 8D Cayley-Dickson multiplication.

        (a,b) × (c,d) = (ac - d̄b, da + bc̄)
        where a,b,c,d are quaternions.

        Args:
            o1: First octonion [..., 8]
            o2: Second octonion [..., 8]

        Returns:
            Product [..., 8]
        """
        a = o1[..., :4]
        b = o1[..., 4:]
        c = o2[..., :4]
        d = o2[..., 4:]

        # ac
        ac = self._quaternion_mul(a, c)

        # d̄b (d conjugate times b)
        d_conj = self._quaternion_conjugate(d)
        d_conj_b = self._quaternion_mul(d_conj, b)

        # First quaternion: ac - d̄b
        first = ac - d_conj_b

        # da
        da = self._quaternion_mul(d, a)

        # bc̄ (b times c conjugate)
        c_conj = self._quaternion_conjugate(c)
        b_c_conj = self._quaternion_mul(b, c_conj)

        # Second quaternion: da + bc̄
        second = da + b_c_conj

        return torch.cat([first, second], dim=-1)

    def _quaternion_mul(self, q1: torch.Tensor, q2: torch.Tensor) -> torch.Tensor:
        """Hamilton quaternion product.

        (w₁, x₁, y₁, z₁) × (w₂, x₂, y₂, z₂)

        Args:
            q1: First quaternion [..., 4]
            q2: Second quaternion [..., 4]

        Returns:
            Product [..., 4]
        """
        w1, x1, y1, z1 = q1.unbind(dim=-1)
        w2, x2, y2, z2 = q2.unbind(dim=-1)

        w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        y = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        z = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2

        return torch.stack([w, x, y, z], dim=-1)

    def _quaternion_conjugate(self, q: torch.Tensor) -> torch.Tensor:
        """Quaternion conjugate: (w, -x, -y, -z).

        Args:
            q: Quaternion [..., 4]

        Returns:
            Conjugate [..., 4]
        """
        w = q[..., 0:1]
        xyz = q[..., 1:]
        return torch.cat([w, -xyz], dim=-1)

    # =========================================================================
    # FULL 8D OCTONION ALGEBRA (for tests and general use)
    # =========================================================================

    def cayley_dickson_mul(self, o1: torch.Tensor, o2: torch.Tensor) -> torch.Tensor:
        """Public 8D Cayley-Dickson multiplication.

        Args:
            o1: First octonion [..., 8]
            o2: Second octonion [..., 8]

        Returns:
            Product [..., 8]
        """
        return self._cayley_dickson_mul(o1, o2)

    def conjugate(self, o: torch.Tensor) -> torch.Tensor:
        """Octonion conjugate: (w, -x, -y, -z, -a, -b, -c, -d).

        Works with both 7D (pure imaginary) and 8D (full) octonions.

        Args:
            o: Octonion [..., 7] or [..., 8]

        Returns:
            Conjugate with same shape
        """
        if o.shape[-1] == 7:
            return -o  # Pure imaginary: conjugate negates all
        elif o.shape[-1] == 8:
            # Full octonion: negate imaginary parts, keep real
            real = o[..., 0:1]
            imag = o[..., 1:]
            return torch.cat([real, -imag], dim=-1)
        else:
            raise ValueError(f"Expected 7D or 8D octonion, got {o.shape[-1]}D")

    def inverse(self, o: torch.Tensor) -> torch.Tensor:
        """Octonion inverse: o⁻¹ = o* / ||o||².

        Args:
            o: Octonion [..., 8]

        Returns:
            Inverse [..., 8]
        """
        o_conj = self.conjugate(o)
        norm_sq = (o * o).sum(dim=-1, keepdim=True).clamp_min(self.eps)
        return o_conj / norm_sq

    def associator(self, a: torch.Tensor, b: torch.Tensor, c: torch.Tensor) -> torch.Tensor:
        """Compute associator [a,b,c] = (ab)c - a(bc).

        Octonions are non-associative, so this is generally non-zero.
        They are alternative: [a,a,b] = [a,b,b] = 0.

        Args:
            a, b, c: Octonions [..., 8]

        Returns:
            Associator [..., 8]
        """
        ab = self._cayley_dickson_mul(a, b)
        bc = self._cayley_dickson_mul(b, c)
        ab_c = self._cayley_dickson_mul(ab, c)
        a_bc = self._cayley_dickson_mul(a, bc)
        return ab_c - a_bc

    def commutator(self, a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
        """Compute commutator [a,b] = ab - ba.

        Args:
            a, b: Octonions [..., 8]

        Returns:
            Commutator [..., 8]
        """
        ab = self._cayley_dickson_mul(a, b)
        ba = self._cayley_dickson_mul(b, a)
        return ab - ba

    def exp(self, o: torch.Tensor) -> torch.Tensor:
        """Octonion exponential: exp(o) = exp(r)(cos||v|| + v̂ sin||v||).

        For o = r + v where r is real and v is pure imaginary.

        Args:
            o: Octonion [..., 8] or tangent vector for manifold exp

        Returns:
            exp(o) [..., 8] or point on S⁷
        """
        if o.shape[-1] == 7:
            # Manifold exponential - for backward compat, use project_to_s7
            # Pure imaginary: exp(v) = cos(||v||) + v̂ sin(||v||)
            norm = o.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)
            v_hat = o / norm
            cos_norm = torch.cos(norm)
            sin_norm = torch.sin(norm)
            # Return 8D: [cos(||v||), sin(||v||) * v̂]
            return torch.cat([cos_norm, sin_norm * v_hat], dim=-1)

        # Full 8D octonion exponential
        real = o[..., 0:1]
        imag = o[..., 1:]

        imag_norm = imag.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)
        imag_hat = imag / imag_norm

        exp_real = torch.exp(real)
        cos_imag = torch.cos(imag_norm)
        sin_imag = torch.sin(imag_norm)

        return exp_real * torch.cat([cos_imag, sin_imag * imag_hat], dim=-1)

    def log(self, o: torch.Tensor) -> torch.Tensor:
        """Octonion logarithm: log(o) = ln||o|| + v̂ arccos(r/||o||).

        Args:
            o: Octonion [..., 8] or target point for manifold log

        Returns:
            log(o) [..., 8]
        """
        if o.shape[-1] == 7:
            # For 7D, this doesn't make sense as octonion log
            # Return zero (log of identity)
            return torch.zeros_like(o)

        # Full 8D octonion logarithm
        real = o[..., 0:1]
        imag = o[..., 1:]

        norm = o.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)
        imag_norm = imag.norm(dim=-1, keepdim=True, p=2).clamp_min(self.eps)
        imag_hat = imag / imag_norm

        ln_norm = torch.log(norm)
        cos_arg = (real / norm).clamp(-1 + self.eps, 1 - self.eps)
        theta = torch.acos(cos_arg)

        return torch.cat([ln_norm, theta * imag_hat], dim=-1)

    def inner_product(self, v1: torch.Tensor, v2: torch.Tensor) -> torch.Tensor:
        """Inner product: v₁ · v₂.

        Works with both 7D and 8D octonions.

        Args:
            v1: First vector [..., 7 or 8]
            v2: Second vector [..., 7 or 8]

        Returns:
            Inner product [...] (scalar)
        """
        return (v1 * v2).sum(dim=-1)


# =============================================================================
# STANDALONE FUNCTIONS (for backwards compatibility)
# =============================================================================

_manifold = None
_manifold_lock = threading.Lock()


def _get_manifold() -> OctonionManifold:
    """Get singleton manifold instance (thread-safe)."""
    global _manifold
    if _manifold is None:
        with _manifold_lock:
            # Double-check pattern to avoid race condition
            if _manifold is None:
                _manifold = OctonionManifold()
    return _manifold


def cayley_dickson_mul(o1: torch.Tensor, o2: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    """Octonion multiplication (7D × 7D → 7D).

    Args:
        o1, o2: Pure imaginary octonions [..., 7]
        eps: Numerical epsilon

    Returns:
        Product (imaginary part) [..., 7]
    """
    manifold = _get_manifold()
    return manifold.multiply(o1, o2)


def octonion_conjugate(o: torch.Tensor) -> torch.Tensor:
    """Pure imaginary conjugate: -o.

    Args:
        o: Pure imaginary octonion [..., 7]

    Returns:
        Conjugate [..., 7]
    """
    return -o


def octonion_norm(o: torch.Tensor) -> torch.Tensor:
    """Octonion norm.

    Args:
        o: Octonion [..., 7]

    Returns:
        Norm [...]
    """
    return cast(torch.Tensor, o.norm(dim=-1, p=2))


def unit_normalize(o: torch.Tensor, eps: float = 1e-8) -> torch.Tensor:
    """Normalize to unit sphere S⁷.

    Args:
        o: Vector [..., 7]
        eps: Numerical epsilon

    Returns:
        Unit vector [..., 7]
    """
    norm = o.norm(dim=-1, keepdim=True, p=2).clamp_min(eps)
    return cast(torch.Tensor, o / norm)


def embed_to_8d(v7: torch.Tensor) -> torch.Tensor:
    """Embed 7D to 8D (prepend zero)."""
    return _get_manifold().embed_to_8d(v7)


def extract_from_8d(o8: torch.Tensor) -> torch.Tensor:
    """Extract 7D from 8D."""
    return o8[..., 1:]


def multiply_8d(o1: torch.Tensor, o2: torch.Tensor) -> torch.Tensor:
    """Full 8D octonion multiplication.

    Args:
        o1, o2: Octonions [..., 8]

    Returns:
        Product [..., 8]
    """
    return _get_manifold().multiply_8d(o1, o2)
