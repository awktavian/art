"""Comprehensive tests for Octonion Manifold implementation.

Verifies mathematical correctness of:
1. Cayley-Dickson multiplication
2. Norm-preserving property: ||a·b|| = ||a|| · ||b||
3. Non-associativity via associator
4. S⁷ projection (unit octonions)
5. Algebraic identities

Mathematical Reference: John C. Baez, "The Octonions", Bull. Amer. Math. Soc. 39 (2002)
"""

from __future__ import annotations

from typing import Any

import pytest

import math

import torch

from kagami_math.octonions import OctonionManifold



pytestmark = pytest.mark.tier_integration

class TestOctonionBasics:
    """Test basic octonion operations."""

    @pytest.fixture
    def manifold(self) -> Any:
        """Create octonion manifold instance."""
        return OctonionManifold()

    def test_dimension(self, manifold) -> None:
        """Octonions are 8-dimensional."""
        # Create a random octonion
        o = torch.randn(8)
        assert o.shape[-1] == 8, "Octonions must be 8-dimensional"

    def test_identity_element(self, manifold) -> None:
        """1 = (1, 0, 0, 0, 0, 0, 0, 0) is the identity."""
        identity = torch.zeros(8)
        identity[0] = 1.0

        # a * 1 = a
        a = torch.randn(8)
        result = manifold.cayley_dickson_mul(a.unsqueeze(0), identity.unsqueeze(0))

        assert torch.allclose(
            result.squeeze(), a, atol=1e-5
        ), "Multiplying by identity should preserve element"

    def test_left_identity(self, manifold) -> None:
        """1 * a = a."""
        identity = torch.zeros(8)
        identity[0] = 1.0

        a = torch.randn(8)
        result = manifold.cayley_dickson_mul(identity.unsqueeze(0), a.unsqueeze(0))

        assert torch.allclose(
            result.squeeze(), a, atol=1e-5
        ), "Left multiplication by identity should preserve element"


class TestCayleyDicksonMultiplication:
    """Test Cayley-Dickson multiplication formula."""

    @pytest.fixture
    def manifold(self) -> Any:
        return OctonionManifold()

    def test_norm_preserving(self, manifold) -> None:
        """||a·b|| = ||a|| · ||b|| (normed division algebra)."""
        for _ in range(20):  # Test multiple random pairs
            a = torch.randn(1, 8)
            b = torch.randn(1, 8)

            product = manifold.cayley_dickson_mul(a, b)

            norm_a = torch.linalg.norm(a)
            norm_b = torch.linalg.norm(b)
            norm_product = torch.linalg.norm(product)
            expected_norm = norm_a * norm_b

            assert torch.allclose(norm_product, expected_norm, rtol=1e-4), (
                f"Norm not preserved: ||a||={norm_a:.4f}, ||b||={norm_b:.4f}, "
                f"||ab||={norm_product:.4f}, expected {expected_norm:.4f}"
            )

    def test_conjugate_product(self, manifold) -> None:
        """a · a* = |a|² · 1."""
        a = torch.randn(1, 8)
        a_conj = manifold.conjugate(a)

        product = manifold.cayley_dickson_mul(a, a_conj)

        # Should be (|a|², 0, 0, 0, 0, 0, 0, 0)
        norm_sq = torch.sum(a**2)
        expected = torch.zeros(8)
        expected[0] = norm_sq

        assert torch.allclose(product.squeeze(), expected, atol=1e-5), "a·a* should equal |a|²·1"

    def test_inverse_property(self, manifold) -> None:
        """a · a⁻¹ = 1 for non-zero a."""
        a = torch.randn(1, 8)
        a_inv = manifold.inverse(a)

        product = manifold.cayley_dickson_mul(a, a_inv)

        # Should be identity (1, 0, 0, 0, 0, 0, 0, 0)
        identity = torch.zeros(8)
        identity[0] = 1.0

        assert torch.allclose(
            product.squeeze(), identity, atol=1e-4
        ), "a · a⁻¹ should equal identity"

    def test_batch_multiplication(self, manifold) -> None:
        """Batch multiplication works correctly."""
        batch_size = 32
        a = torch.randn(batch_size, 8)
        b = torch.randn(batch_size, 8)

        products = manifold.cayley_dickson_mul(a, b)

        assert products.shape == (
            batch_size,
            8,
        ), f"Expected shape ({batch_size}, 8), got {products.shape}"


class TestNonAssociativity:
    """Test that octonions are non-associative (unlike quaternions)."""

    @pytest.fixture
    def manifold(self) -> Any:
        return OctonionManifold()

    def test_associator_nonzero(self, manifold) -> None:
        """Associator [a,b,c] = (ab)c - a(bc) is generally non-zero."""
        # Use indices NOT on the same Fano line to guarantee non-associativity
        # Fano lines: (1,2,4), (2,3,5), (3,4,6), (4,5,7), (5,6,1), (6,7,2), (7,1,3)
        # Use e₁, e₂, e₃ - but note (7,1,3) is a Fano line, meaning e₁e₃ = ±e₇
        # Instead use e₁, e₄, e₅ which are NOT on the same line together
        a = torch.zeros(1, 8)
        a[0, 1] = 1.0  # e₁

        b = torch.zeros(1, 8)
        b[0, 4] = 1.0  # e₄

        c = torch.zeros(1, 8)
        c[0, 5] = 1.0  # e₅

        associator = manifold.associator(a, b, c)
        associator_norm = torch.linalg.norm(associator)

        # For generic random octonions, test non-associativity
        # If the specific basis happens to associate, try random
        if associator_norm < 1e-6:
            a_rand = torch.randn(1, 8)
            b_rand = torch.randn(1, 8)
            c_rand = torch.randn(1, 8)
            associator_rand = manifold.associator(a_rand, b_rand, c_rand)
            associator_norm = torch.linalg.norm(associator_rand)

        assert (
            associator_norm > 1e-6
        ), f"Associator should be non-zero for generic octonions, got norm {associator_norm:.6f}"

    def test_associator_alternating(self, manifold) -> None:
        """Octonions are alternative: [a,a,b] = [a,b,b] = 0."""
        a = torch.randn(1, 8)
        b = torch.randn(1, 8)

        # [a, a, b] should be zero
        assoc_aab = manifold.associator(a, a, b)
        assert torch.allclose(
            assoc_aab, torch.zeros_like(assoc_aab), atol=1e-5
        ), "[a, a, b] should be zero (alternative property)"

        # [a, b, b] should be zero
        assoc_abb = manifold.associator(a, b, b)
        assert torch.allclose(
            assoc_abb, torch.zeros_like(assoc_abb), atol=1e-5
        ), "[a, b, b] should be zero (alternative property)"


class TestS7Projection:
    """Test projection to S⁷ (unit octonions)."""

    @pytest.fixture
    def manifold(self) -> Any:
        return OctonionManifold()

    def test_project_to_s7_unit_norm(self, manifold) -> None:
        """Projection to S⁷ gives unit norm."""
        o = torch.randn(10, 8)
        projected = manifold.project_to_s7(o)

        norms = torch.linalg.norm(projected, dim=-1)

        assert torch.allclose(
            norms, torch.ones_like(norms), atol=1e-6
        ), f"S⁷ projection should give unit norm, got range [{norms.min():.6f}, {norms.max():.6f}]"

    def test_project_preserves_direction(self, manifold) -> None:
        """Projection preserves direction."""
        o = torch.randn(8)
        o_normalized = o / torch.linalg.norm(o)

        projected = manifold.project_to_s7(o.unsqueeze(0))

        # Direction should be preserved
        cosine_sim = torch.dot(projected.squeeze(), o_normalized)

        assert torch.allclose(
            cosine_sim, torch.tensor(1.0), atol=1e-5
        ), f"Projection should preserve direction, got cosine sim {cosine_sim:.4f}"

    def test_project_idempotent(self, manifold) -> None:
        """Projecting twice gives same result."""
        o = torch.randn(10, 8)
        projected_once = manifold.project_to_s7(o)
        projected_twice = manifold.project_to_s7(projected_once)

        assert torch.allclose(
            projected_once, projected_twice, atol=1e-6
        ), "S⁷ projection should be idempotent"


class TestOctonionConjugate:
    """Test octonion conjugation."""

    @pytest.fixture
    def manifold(self) -> Any:
        return OctonionManifold()

    def test_conjugate_real_unchanged(self, manifold) -> None:
        """Real part unchanged under conjugation."""
        o = torch.randn(1, 8)
        o_conj = manifold.conjugate(o)

        assert o[0, 0] == o_conj[0, 0], "Real part should be unchanged"

    def test_conjugate_imaginary_negated(self, manifold) -> None:
        """Imaginary parts negated under conjugation."""
        o = torch.randn(1, 8)
        o_conj = manifold.conjugate(o)

        assert torch.allclose(
            o[0, 1:], -o_conj[0, 1:], atol=1e-6
        ), "Imaginary parts should be negated"

    def test_double_conjugate_identity(self, manifold) -> None:
        """(a*)* = a."""
        o = torch.randn(10, 8)
        double_conj = manifold.conjugate(manifold.conjugate(o))

        assert torch.allclose(double_conj, o, atol=1e-6), "Double conjugate should equal original"

    def test_conjugate_product_reversed(self, manifold) -> None:
        """(ab)* = b*a*."""
        a = torch.randn(1, 8)
        b = torch.randn(1, 8)

        # (ab)*
        ab = manifold.cayley_dickson_mul(a, b)
        ab_conj = manifold.conjugate(ab)

        # b* a*
        a_conj = manifold.conjugate(a)
        b_conj = manifold.conjugate(b)
        b_conj_a_conj = manifold.cayley_dickson_mul(b_conj, a_conj)

        assert torch.allclose(ab_conj, b_conj_a_conj, atol=1e-5), "(ab)* should equal b*a*"


class TestOctonionExp:
    """Test octonion exponential map."""

    @pytest.fixture
    def manifold(self) -> Any:
        return OctonionManifold()

    def test_exp_zero_is_one(self, manifold) -> None:
        """exp(0) = 1."""
        zero = torch.zeros(1, 8)
        exp_zero = manifold.exp(zero)

        identity = torch.zeros(8)
        identity[0] = 1.0

        assert torch.allclose(
            exp_zero.squeeze(), identity, atol=1e-5
        ), "exp(0) should equal identity"

    def test_exp_pure_imaginary_unit_norm(self, manifold) -> None:
        """exp(pure imaginary) has unit norm."""
        # Pure imaginary octonion (real part = 0)
        pure = torch.randn(1, 8)
        pure[0, 0] = 0.0

        exp_pure = manifold.exp(pure)
        norm = torch.linalg.norm(exp_pure)

        assert torch.allclose(
            norm, torch.tensor(1.0), atol=1e-4
        ), f"exp of pure imaginary should have unit norm, got {norm:.4f}"


class TestOctonionLog:
    """Test octonion logarithm map."""

    @pytest.fixture
    def manifold(self) -> Any:
        return OctonionManifold()

    def test_log_one_is_zero(self, manifold) -> None:
        """log(1) = 0."""
        identity = torch.zeros(1, 8)
        identity[0, 0] = 1.0

        log_one = manifold.log(identity)

        assert torch.allclose(
            log_one, torch.zeros_like(log_one), atol=1e-5
        ), "log(1) should be zero"

    def test_exp_log_inverse(self, manifold) -> None:
        """exp(log(a)) ≈ a for unit octonions."""
        # Start with a unit octonion
        o = torch.randn(1, 8)
        o = manifold.project_to_s7(o)

        log_o = manifold.log(o)
        exp_log_o = manifold.exp(log_o)

        assert torch.allclose(
            exp_log_o, o, atol=1e-4
        ), "exp(log(a)) should equal a for unit octonions"


class TestOctonionInnerProduct:
    """Test octonion inner product."""

    @pytest.fixture
    def manifold(self) -> Any:
        return OctonionManifold()

    def test_inner_product_symmetric(self, manifold) -> None:
        """<a, b> = <b, a>."""
        a = torch.randn(10, 8)
        b = torch.randn(10, 8)

        ab = manifold.inner_product(a, b)
        ba = manifold.inner_product(b, a)

        assert torch.allclose(ab, ba, atol=1e-6), "Inner product should be symmetric"

    def test_inner_product_positive_definite(self, manifold) -> None:
        """<a, a> > 0 for a ≠ 0."""
        a = torch.randn(10, 8)

        # Avoid near-zero vectors
        a = a + 0.1 * torch.randn_like(a)

        aa = manifold.inner_product(a, a)

        assert (aa > 0).all(), "Inner product with self should be positive"

    def test_inner_product_norm_squared(self, manifold) -> None:
        """<a, a> = ||a||²."""
        a = torch.randn(10, 8)

        inner = manifold.inner_product(a, a)
        norm_sq = torch.sum(a**2, dim=-1)

        assert torch.allclose(inner, norm_sq, atol=1e-6), "<a, a> should equal ||a||²"


class TestCommutator:
    """Test octonion commutator [a, b] = ab - ba."""

    @pytest.fixture
    def manifold(self) -> Any:
        return OctonionManifold()

    def test_commutator_antisymmetric(self, manifold) -> None:
        """[a, b] = -[b, a]."""
        a = torch.randn(1, 8)
        b = torch.randn(1, 8)

        comm_ab = manifold.commutator(a, b)
        comm_ba = manifold.commutator(b, a)

        assert torch.allclose(comm_ab, -comm_ba, atol=1e-5), "[a, b] should equal -[b, a]"

    def test_commutator_with_self_zero(self, manifold) -> None:
        """[a, a] = 0."""
        a = torch.randn(1, 8)

        comm_aa = manifold.commutator(a, a)

        assert torch.allclose(
            comm_aa, torch.zeros_like(comm_aa), atol=1e-6
        ), "[a, a] should be zero"
