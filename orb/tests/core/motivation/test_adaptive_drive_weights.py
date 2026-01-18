"""Tests for adaptive drive weight learning.

Verifies that the motivation system learns from experience by updating
drive weights based on receipt success rates.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from kagami.core.motivation.intrinsic_motivation import Drive, IntrinsicMotivationSystem


@pytest.fixture
def motivation_system() -> IntrinsicMotivationSystem:
    """Create motivation system for testing."""
    return IntrinsicMotivationSystem()


@pytest.fixture
def mock_receipts() -> list[dict]:
    """Create mock receipts with different drive success rates.

    - Curiosity: 8/10 success (80%)
    - Competence: 5/10 success (50%)
    - Autonomy: 9/10 success (90%)
    - Relatedness: 3/10 success (30%)
    - Purpose: 6/10 success (60%)
    """
    receipts = []

    # Curiosity receipts (80% success)
    for i in range(10):
        receipt = MagicMock()
        receipt.status = "success" if i < 8 else "failed"
        receipt.data = {
            "metadata": {
                "drive": "curiosity",
                "autonomous": True,
            }
        }
        receipts.append(receipt)

    # Competence receipts (50% success)
    for i in range(10):
        receipt = MagicMock()
        receipt.status = "success" if i < 5 else "failed"
        receipt.data = {
            "metadata": {
                "drive": "competence",
                "autonomous": True,
            }
        }
        receipts.append(receipt)

    # Autonomy receipts (90% success)
    for i in range(10):
        receipt = MagicMock()
        receipt.status = "success" if i < 9 else "failed"
        receipt.data = {
            "metadata": {
                "drive": "autonomy",
                "autonomous": True,
            }
        }
        receipts.append(receipt)

    # Relatedness receipts (30% success)
    for i in range(10):
        receipt = MagicMock()
        receipt.status = "success" if i < 3 else "failed"
        receipt.data = {
            "metadata": {
                "drive": "relatedness",
                "autonomous": True,
            }
        }
        receipts.append(receipt)

    # Purpose receipts (60% success)
    for i in range(10):
        receipt = MagicMock()
        receipt.status = "success" if i < 6 else "failed"
        receipt.data = {
            "metadata": {
                "drive": "purpose",
                "autonomous": True,
            }
        }
        receipts.append(receipt)

    return receipts


@pytest.mark.asyncio
async def test_adaptive_drive_weights_basic(
    motivation_system: IntrinsicMotivationSystem,
    mock_receipts: list[dict],
) -> None:
    """Test that drive weights adapt based on receipt success rates."""

    # Record initial weights
    initial_weights = motivation_system._drive_weights.copy()

    # Mock the repository to return our test receipts
    mock_repo = AsyncMock()
    mock_repo.find_by_status.return_value = mock_receipts

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("kagami.core.database.connection.get_db_session") as mock_db:
        mock_db.return_value = mock_session
        with patch("kagami.core.storage.receipt_repository.ReceiptRepository") as mock_repo_class:
            mock_repo_class.return_value = mock_repo

            # Update weights from receipts
            await motivation_system.update_drive_weights_from_receipts()

    # Get updated weights
    updated_weights = motivation_system._drive_weights

    # Verify weights changed
    assert updated_weights != initial_weights, "Weights should have changed"

    # Verify high-performing drives increased
    # Autonomy (90% success) should have highest weight increase
    assert (
        updated_weights[Drive.AUTONOMY] > initial_weights[Drive.AUTONOMY]
    ), "Autonomy weight should increase (90% success)"

    # Verify low-performing drives decreased
    # Relatedness (30% success) should have lowest weight
    assert (
        updated_weights[Drive.RELATEDNESS] < initial_weights[Drive.RELATEDNESS]
    ), "Relatedness weight should decrease (30% success)"

    # Verify weights sum to 1.0 (normalized)
    weight_sum = sum(updated_weights.values())
    assert abs(weight_sum - 1.0) < 0.001, f"Weights should sum to 1.0, got {weight_sum}"


@pytest.mark.asyncio
async def test_adaptive_weights_insufficient_data(
    motivation_system: IntrinsicMotivationSystem,
) -> None:
    """Test that weights don't update with insufficient data."""

    initial_weights = motivation_system._drive_weights.copy()

    # Mock repo with only 5 receipts (below 10 threshold)
    mock_receipts = []
    for _ in range(5):
        receipt = MagicMock()
        receipt.status = "success"
        receipt.data = {
            "metadata": {
                "drive": "curiosity",
                "autonomous": True,
            }
        }
        mock_receipts.append(receipt)

    mock_repo = AsyncMock()
    mock_repo.find_by_status.return_value = mock_receipts

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("kagami.core.database.connection.get_db_session") as mock_db:
        mock_db.return_value = mock_session
        with patch("kagami.core.storage.receipt_repository.ReceiptRepository") as mock_repo_class:
            mock_repo_class.return_value = mock_repo

            await motivation_system.update_drive_weights_from_receipts()

    # Weights should remain unchanged (insufficient data)
    updated_weights = motivation_system._drive_weights
    assert updated_weights == initial_weights, "Weights should not change with insufficient data"


@pytest.mark.asyncio
async def test_adaptive_weights_bayesian_blend(
    motivation_system: IntrinsicMotivationSystem,
) -> None:
    """Test Bayesian blending (70% prior, 30% empirical)."""

    # Set initial curiosity weight to 0.3
    initial_curiosity = motivation_system._drive_weights[Drive.CURIOSITY]

    # Create 100 receipts with 100% success for curiosity
    mock_receipts = []
    for _ in range(20):  # 20 receipts for curiosity
        receipt = MagicMock()
        receipt.status = "success"
        receipt.data = {
            "metadata": {
                "drive": "curiosity",
                "autonomous": True,
            }
        }
        mock_receipts.append(receipt)

    # Add receipts for other drives (low success) to ensure total > 10
    for drive in [Drive.COMPETENCE, Drive.AUTONOMY, Drive.RELATEDNESS, Drive.PURPOSE]:
        for _ in range(3):
            receipt = MagicMock()
            receipt.status = "failed"
            receipt.data = {
                "metadata": {
                    "drive": drive.value,
                    "autonomous": True,
                }
            }
            mock_receipts.append(receipt)

    mock_repo = AsyncMock()
    mock_repo.find_by_status.return_value = mock_receipts

    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    with patch("kagami.core.database.connection.get_db_session") as mock_db:
        mock_db.return_value = mock_session
        with patch("kagami.core.storage.receipt_repository.ReceiptRepository") as mock_repo_class:
            mock_repo_class.return_value = mock_repo

            await motivation_system.update_drive_weights_from_receipts()

    updated_curiosity = motivation_system._drive_weights[Drive.CURIOSITY]

    # Verify weight increased but not to maximum (due to Bayesian blending)
    assert updated_curiosity > initial_curiosity, "Curiosity weight should increase"
    assert updated_curiosity < 1.0, "Weight should not reach 1.0 (Bayesian blending)"

    # Verify blend is conservative (70% prior keeps it anchored)
    change = updated_curiosity - initial_curiosity
    assert change < 0.5, "Change should be moderate due to 70% prior weight"


@pytest.mark.asyncio
async def test_adaptive_weights_graceful_failure(
    motivation_system: IntrinsicMotivationSystem,
) -> None:
    """Test that weight update fails gracefully on errors."""

    initial_weights = motivation_system._drive_weights.copy()

    # Mock repository to raise exception
    with patch("kagami.core.database.connection.get_db_session") as mock_db:
        mock_db.side_effect = Exception("Database connection failed")

        # Should not raise exception
        await motivation_system.update_drive_weights_from_receipts()

    # Weights should remain unchanged
    assert (
        motivation_system._drive_weights == initial_weights
    ), "Weights should remain unchanged on error"


@pytest.mark.asyncio
async def test_weights_observable(motivation_system: IntrinsicMotivationSystem) -> None:
    """Test that drive weights are observable via get_drive_weights()."""

    weights = motivation_system.get_drive_weights()

    # Verify all drives present
    assert "curiosity" in weights
    assert "competence" in weights
    assert "autonomy" in weights
    assert "relatedness" in weights
    assert "purpose" in weights

    # Verify weights sum to 1.0
    weight_sum = sum(weights.values())
    assert abs(weight_sum - 1.0) < 0.001, f"Weights should sum to 1.0, got {weight_sum}"

    # Verify all weights positive
    for drive, weight in weights.items():
        assert weight > 0, f"Weight for {drive} should be positive, got {weight}"


def test_drive_enum_complete() -> None:
    """Test that Drive enum has all expected values."""
    expected_drives = {"curiosity", "competence", "autonomy", "relatedness", "purpose"}
    actual_drives = {drive.value for drive in Drive}

    assert (
        actual_drives == expected_drives
    ), f"Drive enum mismatch: expected {expected_drives}, got {actual_drives}"
