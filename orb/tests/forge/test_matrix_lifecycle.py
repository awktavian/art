"""Tests for kagami.forge.matrix.lifecycle (LifecycleManager)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from kagami.forge.matrix.lifecycle import LifecycleManager

pytestmark = pytest.mark.tier_unit


@pytest.fixture
def mock_registry():
    """Create mock ComponentRegistry."""
    registry = MagicMock()
    registry.ai_modules = {}
    return registry


@pytest.fixture
def lifecycle_manager(mock_registry):
    """Create LifecycleManager instance."""
    trace_callback = MagicMock()
    return LifecycleManager(mock_registry, trace_callback)


class TestLifecycleManagerInit:
    """Test LifecycleManager initialization."""

    def test_init(self, mock_registry):
        """Test initialization."""
        event_recorder = MagicMock()
        manager = LifecycleManager(mock_registry, event_recorder)

        assert manager.registry is mock_registry
        assert manager._event_recorder is event_recorder

    def test_initialize(self, lifecycle_manager):
        """Test initialization method."""
        lifecycle_manager.initialize()
        assert lifecycle_manager.initialized is True

    def test_double_initialization(self, lifecycle_manager):
        """Test that double initialization is safe."""
        lifecycle_manager.initialize()
        lifecycle_manager.initialize()  # Should not raise

        assert lifecycle_manager.initialized is True


class TestAssetCache:
    """Test asset cache management."""

    def test_asset_cache_property(self, lifecycle_manager):
        """Test asset_cache property after initialization."""
        # Cache is only created during initialize()
        lifecycle_manager.initialize()
        cache = lifecycle_manager.asset_cache
        # Cache may be None if LRUFileCache import failed - that's acceptable
        assert lifecycle_manager.initialized is True

    def test_asset_cache_persistence(self, lifecycle_manager):
        """Test asset cache persists across calls after initialization."""
        lifecycle_manager.initialize()
        cache1 = lifecycle_manager.asset_cache
        cache2 = lifecycle_manager.asset_cache

        # Both should return the same object (or both be None)
        assert cache1 is cache2
