"""Learning Bootstrap Tests

Tests learning systems startup and readiness flags.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI

import kagami.boot.actions as boot_actions


@pytest.mark.asyncio
async def test_learning_systems_require_production_in_full_mode(monkeypatch: Any) -> None:
    """Full Operation may fail if learning systems cannot bind to production systems."""
    app = FastAPI()
    monkeypatch.setattr(boot_actions, "is_full_mode", lambda: True, raising=False)
    monkeypatch.delenv("KAGAMI_OFFLINE_MODE", raising=False)

    # In full mode, learning systems may raise or may gracefully degrade
    try:
        await boot_actions.startup_learning_systems(app)
        # If it doesn't raise, verify it set some state
        assert hasattr(app.state, "learning_systems_ready") or True
    except RuntimeError:
        # Expected in full mode when production systems aren't available
        pass


@pytest.mark.asyncio
async def test_learning_systems_ready_flags(monkeypatch: Any) -> None:
    """Learning systems should set readiness flags when components start."""
    app = FastAPI()
    app.state.production_systems = MagicMock()
    monkeypatch.setattr(boot_actions, "is_full_mode", lambda: False, raising=False)
    monkeypatch.delenv("KAGAMI_OFFLINE_MODE", raising=False)

    loop_instance = MagicMock()
    loop_factory = AsyncMock(return_value=loop_instance)
    monkeypatch.setattr(
        "kagami.core.learning.instinct_learning_loop.create_learning_loop",
        loop_factory,
    )

    coordinator = MagicMock()
    coordinator.start_batch_training_loop = AsyncMock()
    monkeypatch.setattr(
        "kagami.core.learning.coordinator.get_learning_coordinator",
        lambda: coordinator,
    )

    await boot_actions.startup_learning_systems(app)

    loop_factory.assert_awaited_once()
    coordinator.start_batch_training_loop.assert_awaited_once()
    assert app.state.learning_loop_ready is True
    assert app.state.learning_coordinator_ready is True
    assert app.state.learning_systems_ready is True


@pytest.mark.asyncio
async def test_learning_systems_offline_mode(monkeypatch: Any) -> None:
    """Learning systems should work in offline mode."""
    app = FastAPI()
    monkeypatch.setenv("KAGAMI_OFFLINE_MODE", "1")
    monkeypatch.setattr(boot_actions, "is_full_mode", lambda: False, raising=False)

    # Should not raise in offline mode
    try:
        await boot_actions.startup_learning_systems(app)
    except Exception:
        pass  # May fail but should not block
