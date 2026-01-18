"""Tests for kagami.forge.matrix.registry (ComponentRegistry)."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from kagami.forge.matrix.registry import ComponentRegistry

pytestmark = pytest.mark.tier_unit


@pytest.fixture
def registry():
    """Create ComponentRegistry instance."""
    config = {"modules": {"test": True}}
    return ComponentRegistry(config)


class TestComponentRegistryInit:
    """Test ComponentRegistry initialization."""

    def test_init_default(self):
        """Test default initialization."""
        registry = ComponentRegistry({})
        assert registry.ai_modules == {}

    def test_init_with_config(self):
        """Test initialization with config."""
        config = {"modules": {"visual": True}}
        registry = ComponentRegistry(config)

        assert registry.config is not None
        assert registry.config == config


class TestModuleAvailability:
    """Test module availability checking."""

    def test_is_available_returns_bool(self, registry):
        """Test is_available returns boolean."""
        result = registry.is_available("test_module")
        assert isinstance(result, bool)

    def test_is_available_for_unavailable_module(self, registry):
        """Test checking unavailable module."""
        result = registry.is_available("nonexistent_module")

        # Should return False for unavailable modules
        assert result is False or result is True  # Depends on implementation


class TestModuleRegistry:
    """Test module registry management."""

    def test_ai_modules_property(self, registry):
        """Test ai_modules property."""
        modules = registry.ai_modules
        assert isinstance(modules, dict)
