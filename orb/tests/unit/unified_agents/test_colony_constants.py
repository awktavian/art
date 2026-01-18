"""Tests for Colony Constants and S7 Embeddings.

Validates:
1. Colony name constants and mappings
2. Catastrophe type mappings
3. S7 embeddings (differentiable)
4. DomainType enum

Created: December 14, 2025
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import torch

from kagami.core.unified_agents.colony_constants import (
    # Colony names
    COLONY_NAMES,
    CATASTROPHE_NAMES,
    # Index mappings
    COLONY_TO_INDEX,
    INDEX_TO_COLONY,
    COLONY_TO_INDEX_1BASED,
    INDEX_TO_COLONY_1BASED,
    # Catastrophe mappings
    COLONY_TO_CATASTROPHE,
    CATASTROPHE_TO_COLONY,
    # S7 embeddings
    get_s7_basis,
    get_colony_embedding,
    get_all_colony_embeddings,
    # Enum
    DomainType,
)

# =============================================================================
# TEST COLONY CONSTANTS
# =============================================================================


class TestColonyConstants:
    """Test colony name constants."""

    def test_colony_names_count(self) -> None:
        """Should have exactly 7 colonies."""
        assert len(COLONY_NAMES) == 7

    def test_colony_names_content(self) -> None:
        """Should have expected colony names."""
        expected = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]
        assert COLONY_NAMES == tuple(expected)

    def test_catastrophe_names_count(self) -> None:
        """Should have exactly 7 catastrophe types."""
        assert len(CATASTROPHE_NAMES) == 7

    def test_catastrophe_names_content(self) -> None:
        """Should have expected catastrophe types."""
        expected = [
            "fold",
            "cusp",
            "swallowtail",
            "butterfly",
            "hyperbolic",
            "elliptic",
            "parabolic",
        ]
        assert CATASTROPHE_NAMES == tuple(expected)


# =============================================================================
# TEST INDEX MAPPINGS
# =============================================================================


class TestIndexMappings:
    """Test colony index mappings."""

    def test_colony_to_index_0based(self) -> None:
        """0-based index should start at 0."""
        assert COLONY_TO_INDEX["spark"] == 0
        assert COLONY_TO_INDEX["crystal"] == 6

    def test_index_to_colony_0based(self) -> None:
        """0-based reverse mapping should work."""
        assert INDEX_TO_COLONY[0] == "spark"
        assert INDEX_TO_COLONY[6] == "crystal"

    def test_colony_to_index_1based(self) -> None:
        """1-based index should start at 1."""
        assert COLONY_TO_INDEX_1BASED["spark"] == 1
        assert COLONY_TO_INDEX_1BASED["crystal"] == 7

    def test_index_to_colony_1based(self) -> None:
        """1-based reverse mapping should work."""
        assert INDEX_TO_COLONY_1BASED[1] == "spark"
        assert INDEX_TO_COLONY_1BASED[7] == "crystal"

    def test_all_colonies_in_0based_map(self) -> None:
        """All colonies should be in 0-based map."""
        for colony in COLONY_NAMES:
            assert colony in COLONY_TO_INDEX
            idx = COLONY_TO_INDEX[colony]
            assert INDEX_TO_COLONY[idx] == colony


# =============================================================================
# TEST CATASTROPHE MAPPINGS
# =============================================================================


class TestCatastropheMappings:
    """Test catastrophe type mappings."""

    def test_colony_to_catastrophe(self) -> None:
        """Each colony should map to a catastrophe."""
        assert len(COLONY_TO_CATASTROPHE) == 7
        assert COLONY_TO_CATASTROPHE["spark"] == "fold"
        assert COLONY_TO_CATASTROPHE["forge"] == "cusp"
        assert COLONY_TO_CATASTROPHE["crystal"] == "parabolic"

    def test_catastrophe_to_colony(self) -> None:
        """Reverse mapping should work."""
        assert CATASTROPHE_TO_COLONY["fold"] == "spark"
        assert CATASTROPHE_TO_COLONY["cusp"] == "forge"
        assert CATASTROPHE_TO_COLONY["parabolic"] == "crystal"

    def test_bijection(self) -> None:
        """Mapping should be bijective."""
        for colony, catastrophe in COLONY_TO_CATASTROPHE.items():
            assert CATASTROPHE_TO_COLONY[catastrophe] == colony


# =============================================================================
# TEST S7 EMBEDDINGS
# =============================================================================


class TestS7Embeddings:
    """Test differentiable S7 embeddings."""

    def test_s7_basis_shape(self) -> None:
        """S7 basis should be 7x7."""
        basis = get_s7_basis()
        assert basis.shape == (7, 7)

    def test_s7_basis_orthonormal(self) -> None:
        """S7 basis should be orthonormal."""
        basis = get_s7_basis()

        # Check orthogonality
        gram = basis @ basis.T
        identity = torch.eye(7)

        assert torch.allclose(gram, identity, atol=1e-5)

    def test_s7_basis_device(self) -> None:
        """S7 basis should respect device."""
        basis_cpu = get_s7_basis(device="cpu")
        assert basis_cpu.device.type == "cpu"

    def test_colony_embedding_shape(self) -> None:
        """Colony embedding should be 1D vector."""
        emb = get_colony_embedding("forge")
        assert emb.shape == (7,)

    def test_colony_embedding_unit_vector(self) -> None:
        """Colony embedding should be unit vector."""
        emb = get_colony_embedding("spark")
        norm = torch.norm(emb)
        assert torch.allclose(norm, torch.tensor(1.0))

    def test_colony_embeddings_orthogonal(self) -> None:
        """Different colony embeddings should be orthogonal."""
        spark = get_colony_embedding("spark")
        forge = get_colony_embedding("forge")

        dot = torch.dot(spark, forge)
        assert torch.allclose(dot, torch.tensor(0.0), atol=1e-5)

    def test_all_colony_embeddings_shape(self) -> None:
        """All embeddings should be 7x7."""
        embeddings = get_all_colony_embeddings()
        assert embeddings.shape == (7, 7)

    def test_all_colony_embeddings_matches_basis(self) -> None:
        """All embeddings should match S7 basis."""
        embeddings = get_all_colony_embeddings()
        basis = get_s7_basis()

        assert torch.allclose(embeddings, basis)

    def test_embedding_differentiable(self) -> None:
        """Embeddings should be differentiable."""
        emb = get_colony_embedding("nexus")
        assert not emb.requires_grad  # Default

        # Can attach gradients
        emb_grad = emb.clone().requires_grad_(True)
        loss = emb_grad.sum()
        loss.backward()
        assert emb_grad.grad is not None


# =============================================================================
# TEST DOMAIN TYPE ENUM
# =============================================================================


class TestDomainType:
    """Test DomainType enum."""

    def test_all_domains_exist(self) -> None:
        """All 7 domains should exist."""
        domains = list(DomainType)
        assert len(domains) == 7

    def test_domain_values(self) -> None:
        """Domain values should match colony names."""
        assert DomainType.SPARK.value == "spark"
        assert DomainType.FORGE.value == "forge"
        assert DomainType.CRYSTAL.value == "crystal"

    def test_to_index(self) -> None:
        """Should convert to 0-based index."""
        assert DomainType.SPARK.to_index() == 0
        assert DomainType.CRYSTAL.to_index() == 6

    def test_from_index(self) -> None:
        """Should create from index."""
        domain = DomainType.from_index(1)
        assert domain == DomainType.FORGE

    def test_to_embedding(self) -> None:
        """Should get S7 embedding."""
        emb = DomainType.FORGE.to_embedding()

        assert emb.shape == (7,)
        assert torch.allclose(torch.norm(emb), torch.tensor(1.0))

    def test_embedding_matches_colony(self) -> None:
        """Embedding should match colony embedding."""
        domain_emb = DomainType.NEXUS.to_embedding()
        colony_emb = get_colony_embedding("nexus")

        assert torch.allclose(domain_emb, colony_emb)

    def test_round_trip(self) -> None:
        """Index conversion should round-trip."""
        for domain in DomainType:
            idx = domain.to_index()
            recovered = DomainType.from_index(idx)
            assert recovered == domain
