"""Tests for Fano neighbor verification in Byzantine consensus.

Tests:
1. Basic verification workflow
2. CBF constraint checking
3. Fano compatibility checking
4. Lease validity checking
5. Global quorum computation
6. Faulty colony detection

Created: December 15, 2025
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
from unittest.mock import AsyncMock, MagicMock

import torch

from kagami.core.coordination.fano_neighbor_verification import (
    ColonyAction,
    ColonyConsensusState,
    FanoNeighborVerifier,
    check_global_quorum,
    create_fano_verifier,
    get_faulty_colonies,
    FANO_NEIGHBORS,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_etcd_client():
    """Mock etcd client with lease checking."""
    client = MagicMock()

    # Mock lease TTL response
    class MockTTLResponse:
        TTL = 10  # 10 seconds remaining

    client.time_to_live = MagicMock(return_value=MockTTLResponse())
    return client


@pytest.fixture
def valid_proposals():
    """Create 7 valid colony proposals."""
    proposals = []
    for i in range(7):
        z_state = torch.randn(14)
        action = ColonyAction(
            colony_id=i,
            action_type="route",
            fano_line=None,
            routing_bias={j: 0.5 for j in range(7) if j != i},
        )
        proposal = ColonyConsensusState(
            colony_id=i,
            z_state=z_state,
            h_value=0.5,  # Safe
            proposed_action=action,
            lease_id=1000 + i,
        )
        proposals.append(proposal)
    return proposals


@pytest.fixture
def verifier():
    """Create verifier with testing configuration."""
    return create_fano_verifier(
        cbf_threshold=0.0,
        quorum_required=4,
        enable_metrics=False,
    )


# =============================================================================
# TESTS
# =============================================================================


def test_fano_neighbors_structure():
    """Test that FANO_NEIGHBORS has correct structure."""
    assert len(FANO_NEIGHBORS) == 7, "Should have 7 colonies"

    for colony_id, neighbors in FANO_NEIGHBORS.items():
        assert 0 <= colony_id <= 6, f"Invalid colony ID: {colony_id}"
        assert len(neighbors) == 6, f"Colony {colony_id} should have 6 neighbors"
        assert colony_id not in neighbors, "Colony should not be its own neighbor"

        # All neighbors should be valid colony IDs
        for neighbor in neighbors:
            assert 0 <= neighbor <= 6, f"Invalid neighbor ID: {neighbor}"


def test_colony_consensus_state_validation():
    """Test ColonyConsensusState validation."""
    # Valid state
    z_state = torch.randn(14)
    action = ColonyAction(
        colony_id=0,
        action_type="route",
    )
    state = ColonyConsensusState(
        colony_id=0,
        z_state=z_state,
        h_value=0.5,
        proposed_action=action,
        lease_id=1000,
    )
    assert state.colony_id == 0

    # Invalid colony_id
    with pytest.raises(ValueError, match="Invalid colony_id"):
        ColonyConsensusState(
            colony_id=7,  # Invalid
            z_state=z_state,
            h_value=0.5,
            proposed_action=action,
            lease_id=1000,
        )

    # Invalid z_state shape
    with pytest.raises(ValueError, match="Invalid z_state shape"):
        ColonyConsensusState(
            colony_id=0,
            z_state=torch.randn(10),  # Wrong shape
            h_value=0.5,
            proposed_action=action,
            lease_id=1000,
        )


def test_verifier_initialization():
    """Test FanoNeighborVerifier initialization."""
    verifier = FanoNeighborVerifier(
        cbf_threshold=0.2,
        quorum_required=4,
        enable_metrics=False,
    )

    assert verifier.cbf_threshold == 0.2
    assert verifier.quorum_required == 4

    # Invalid quorum
    with pytest.raises(ValueError):
        FanoNeighborVerifier(quorum_required=0)

    with pytest.raises(ValueError):
        FanoNeighborVerifier(quorum_required=7)


@pytest.mark.asyncio
async def test_cbf_constraint_checking(verifier) -> None:
    """Test CBF constraint verification."""
    # Safe proposal
    safe_proposal = ColonyConsensusState(
        colony_id=0,
        z_state=torch.randn(14),
        h_value=0.5,  # Above threshold
        proposed_action=ColonyAction(colony_id=0, action_type="route"),
        lease_id=1000,
    )

    result = await verifier._check_cbf_constraint(safe_proposal)
    assert result is True, "Safe proposal should pass CBF check"

    # Unsafe proposal
    unsafe_proposal = ColonyConsensusState(
        colony_id=1,
        z_state=torch.randn(14),
        h_value=-0.1,  # Below threshold
        proposed_action=ColonyAction(colony_id=1, action_type="route"),
        lease_id=1001,
    )

    result = await verifier._check_cbf_constraint(unsafe_proposal)
    assert result is False, "Unsafe proposal should fail CBF check"


@pytest.mark.asyncio
async def test_fano_compatibility_checking(verifier, valid_proposals) -> None:
    """Test Fano compatibility verification."""
    proposal_map = {p.colony_id: p for p in valid_proposals}

    # Test valid Fano line: (0, 1, 2) is a valid Fano line
    from kagami_math.fano_plane import get_fano_lines_zero_indexed

    valid_lines = get_fano_lines_zero_indexed()
    test_line = valid_lines[0]  # First Fano line

    target_action = ColonyAction(
        colony_id=test_line[0],
        action_type="compose",
        fano_line=test_line,
    )
    target_proposal = ColonyConsensusState(
        colony_id=test_line[0],
        z_state=torch.randn(14),
        h_value=0.5,
        proposed_action=target_action,
        lease_id=2000,
    )

    result = await verifier._check_fano_compatibility(
        source_id=test_line[1],
        target_proposal=target_proposal,
        proposal_map=proposal_map,
    )
    assert result is True, "Valid Fano line should pass compatibility check"

    # Test invalid Fano line
    invalid_action = ColonyAction(
        colony_id=0,
        action_type="compose",
        fano_line=(0, 1, 99),  # Invalid colony
    )
    invalid_proposal = ColonyConsensusState(
        colony_id=0,
        z_state=torch.randn(14),
        h_value=0.5,
        proposed_action=invalid_action,
        lease_id=2001,
    )

    result = await verifier._check_fano_compatibility(
        source_id=1,
        target_proposal=invalid_proposal,
        proposal_map=proposal_map,
    )
    assert result is False, "Invalid Fano line should fail compatibility check"


@pytest.mark.asyncio
async def test_verify_fano_neighbors(verifier, valid_proposals, mock_etcd_client) -> None:
    """Test full neighbor verification workflow."""
    results = await verifier.verify_fano_neighbors(valid_proposals, mock_etcd_client)

    assert len(results) == 7, "Should verify all 7 colonies"

    for colony_id, result in results.items():
        assert result.colony_id == colony_id
        assert len(result.neighbor_validities) == 6, "Should verify 6 neighbors"

        # Check that neighbors match FANO_NEIGHBORS structure
        expected_neighbors = set(FANO_NEIGHBORS[colony_id])
        actual_neighbors = set(result.neighbor_validities.keys())
        assert expected_neighbors == actual_neighbors


@pytest.mark.asyncio
async def test_verify_with_cbf_violations(verifier, mock_etcd_client) -> None:
    """Test verification with CBF violations."""
    proposals = []
    for i in range(7):
        z_state = torch.randn(14)
        action = ColonyAction(colony_id=i, action_type="route")

        # Make colony 3 unsafe
        h_value = -0.5 if i == 3 else 0.5

        proposal = ColonyConsensusState(
            colony_id=i,
            z_state=z_state,
            h_value=h_value,
            proposed_action=action,
            lease_id=1000 + i,
        )
        proposals.append(proposal)

    results = await verifier.verify_fano_neighbors(proposals, mock_etcd_client)

    # Colonies that have colony 3 as neighbor should report CBF violation
    for colony_id, result in results.items():
        if 3 in FANO_NEIGHBORS[colony_id]:
            assert (
                3 in result.cbf_violations
            ), f"Colony {colony_id} should detect CBF violation in colony 3"


@pytest.mark.asyncio
async def test_verify_with_wrong_number_of_proposals(verifier, mock_etcd_client) -> None:
    """Test that verification fails with wrong number of proposals."""
    # Only 5 proposals instead of 7
    proposals = [
        ColonyConsensusState(
            colony_id=i,
            z_state=torch.randn(14),
            h_value=0.5,
            proposed_action=ColonyAction(colony_id=i, action_type="route"),
            lease_id=1000 + i,
        )
        for i in range(5)
    ]

    with pytest.raises(ValueError, match="Expected 7 proposals"):
        await verifier.verify_fano_neighbors(proposals, mock_etcd_client)


def test_check_global_quorum():
    """Test global Byzantine quorum checking."""
    # Create mock results where 5/7 colonies have quorum
    from kagami.core.coordination.fano_neighbor_verification import (
        NeighborVerificationResult,
    )

    results = {}
    for i in range(7):
        # First 5 colonies have quorum
        quorum = i < 5

        results[i] = NeighborVerificationResult(
            colony_id=i,
            neighbor_validities=dict.fromkeys(range(6), True),
            quorum_achieved=quorum,
        )

    # 5/7 = 0.714 >= 0.714 threshold
    assert check_global_quorum(results) is True

    # Now only 4/7 have quorum (below threshold)
    results[4].quorum_achieved = False
    assert check_global_quorum(results) is False


def test_get_faulty_colonies():
    """Test faulty colony detection."""
    from kagami.core.coordination.fano_neighbor_verification import (
        NeighborVerificationResult,
    )

    # Create results where majority marks colony 3 as invalid
    results = {}
    for i in range(7):
        neighbor_validities = {}

        # All colonies mark colony 3 as invalid (if it's a neighbor)
        for neighbor_id in FANO_NEIGHBORS[i]:
            neighbor_validities[neighbor_id] = neighbor_id != 3

        results[i] = NeighborVerificationResult(
            colony_id=i,
            neighbor_validities=neighbor_validities,
            quorum_achieved=True,
        )

    faulty = get_faulty_colonies(results)

    # Colony 3 should be detected as faulty
    assert 3 in faulty, "Colony 3 should be detected as faulty by majority"


def test_neighbor_verification_result_properties():
    """Test NeighborVerificationResult computed properties."""
    from kagami.core.coordination.fano_neighbor_verification import (
        NeighborVerificationResult,
    )

    result = NeighborVerificationResult(
        colony_id=0,
        neighbor_validities={
            1: True,
            2: True,
            3: False,
            4: True,
            5: False,
            6: True,
        },
        quorum_achieved=True,
        cbf_violations=[3, 5],
    )

    assert result.valid_neighbor_count == 4
    assert result.invalid_neighbors == [3, 5]


@pytest.mark.asyncio
async def test_factory_function():
    """Test create_fano_verifier factory."""
    verifier = create_fano_verifier(
        cbf_threshold=0.1,
        quorum_required=3,
        enable_metrics=True,
    )

    assert isinstance(verifier, FanoNeighborVerifier)
    assert verifier.cbf_threshold == 0.1
    assert verifier.quorum_required == 3
    assert verifier.enable_metrics is True


# =============================================================================
# INTEGRATION TEST (requires etcd mock)
# =============================================================================


@pytest.mark.asyncio
async def test_integration_with_kagami_consensus(valid_proposals, monkeypatch) -> None:
    """Test integration with KagamiConsensus workflow."""
    # This test verifies that the verification module integrates correctly
    # with the overall consensus system

    verifier = create_fano_verifier()

    # Mock etcd_operation at the source (kagami.core.consensus.etcd_client)
    from contextlib import contextmanager

    @contextmanager
    def mock_etcd_operation(operation_name):
        # Mock client with valid lease checking
        class MockEtcdClient:
            class MockLease:
                TTL = 10

            def time_to_live(self, lease_id):
                return self.MockLease()

        yield MockEtcdClient()

    # Patch at the source module
    monkeypatch.setattr(
        "kagami.core.consensus.etcd_client.etcd_operation",
        mock_etcd_operation,
    )

    # Mock etcd client (not actually used due to patch)
    etcd_client = MagicMock()

    # Run verification
    results = await verifier.verify_fano_neighbors(valid_proposals, etcd_client)

    # All colonies should achieve quorum (all proposals are valid)
    for colony_id, result in results.items():
        assert result.quorum_achieved, f"Colony {colony_id} should achieve quorum"

    # Global quorum should be achieved
    assert check_global_quorum(results) is True

    # No faulty colonies
    faulty = get_faulty_colonies(results)
    assert len(faulty) == 0, "No colonies should be faulty with all-valid proposals"
