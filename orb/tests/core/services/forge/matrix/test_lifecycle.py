"""Tests for forge matrix lifecycle module."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from unittest.mock import Mock, MagicMock

from kagami.forge.matrix.lifecycle import LifecycleManager
from kagami.forge.matrix.registry import ComponentRegistry


class TestLifecycleManager:
    """Tests for LifecycleManager class."""

    def test_creation(self):
        """Test lifecycle manager creation."""
        registry = Mock(spec=ComponentRegistry)
        registry.initialize_all = Mock()
        registry.import_errors = {}
        event_recorder = Mock()

        manager = LifecycleManager(registry, event_recorder)

        assert manager.initialized is False
        assert manager.registry is registry

    def test_initialize(self):
        """Test initialization."""
        registry = Mock(spec=ComponentRegistry)
        registry.initialize_all = Mock()
        registry.import_errors = {}
        event_recorder = Mock()

        manager = LifecycleManager(registry, event_recorder)
        manager.initialize()

        assert manager.initialized is True
        registry.initialize_all.assert_called_once()

    def test_initialize_idempotent(self):
        """Test initialization is idempotent."""
        registry = Mock(spec=ComponentRegistry)
        registry.initialize_all = Mock()
        registry.import_errors = {}
        event_recorder = Mock()

        manager = LifecycleManager(registry, event_recorder)
        manager.initialize()
        manager.initialize()  # Should not error

        # Only called once due to idempotency
        registry.initialize_all.assert_called_once()

    def test_import_errors_property(self):
        """Test import_errors property."""
        registry = Mock(spec=ComponentRegistry)
        registry.initialize_all = Mock()
        registry.import_errors = {"TestModule": Exception("test")}
        event_recorder = Mock()

        manager = LifecycleManager(registry, event_recorder)

        assert "TestModule" in manager.import_errors
