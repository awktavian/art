"""Tests for forge matrix registry module."""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from unittest.mock import Mock

from kagami.forge.matrix.registry import (
    ComponentRegistry,
    MODULE_DEPENDENCIES,
)


class TestComponentRegistry:
    """Tests for ComponentRegistry class."""

    def test_creation(self) -> None:
        """Test registry creation."""
        config = {}
        registry = ComponentRegistry(config)

        assert registry is not None
        assert registry.config == config
        assert registry.ai_modules == {}

    def test_creation_with_config(self) -> None:
        """Test registry creation with config."""
        config = {"modules": {"rigging": {"method": "unirig"}}}
        registry = ComponentRegistry(config)

        assert registry.config == config

    def test_import_errors_tracked(self) -> None:
        """Test import errors are tracked."""
        config = {}
        registry = ComponentRegistry(config)

        # Should have dict of import errors
        assert isinstance(registry.import_errors, dict)

    def test_get_module_returns_none_before_init(self) -> None:
        """Test get_module returns None before initialization."""
        config = {}
        registry = ComponentRegistry(config)

        result = registry.get_module("visual_designer")

        assert result is None

    def test_is_available_false_before_init(self) -> None:
        """Test is_available returns False before init."""
        config = {}
        registry = ComponentRegistry(config)

        assert registry.is_available("visual_designer") is False

    def test_initialize_all_creates_modules(self) -> None:
        """Test initialize_all creates module instances."""
        config = {}
        registry = ComponentRegistry(config)

        trace_calls = []

        def mock_trace(component: Any, status: Any, **kwargs) -> None:
            trace_calls.append((component, status))

        registry.initialize_all(mock_trace)

        # Should have attempted to initialize modules
        assert len(trace_calls) > 0

    def test_initialize_with_trace_callback(self) -> None:
        """Test initialization with trace callback."""
        config = {}
        registry = ComponentRegistry(config)

        trace_events = []

        def trace_callback(component: Any, status: Any, **kwargs) -> None:
            trace_events.append(
                {
                    "component": component,
                    "status": status,
                    **kwargs,
                }
            )

        registry.initialize_all(trace_callback)

        # Should have generated trace events
        assert len(trace_events) > 0


class TestModuleDependencies:
    """Tests for MODULE_DEPENDENCIES."""

    def test_dependencies_defined(self) -> None:
        """Test MODULE_DEPENDENCIES is defined."""
        assert isinstance(MODULE_DEPENDENCIES, dict)

    def test_visual_designer_has_no_deps(self) -> None:
        """Test visual_designer has no dependencies."""
        assert MODULE_DEPENDENCIES["visual_designer"] == set()

    def test_character_profiler_depends_on_visual(self) -> None:
        """Test character_profiler depends on visual_designer."""
        assert "visual_designer" in MODULE_DEPENDENCIES["character_profiler"]

    def test_rigging_depends_on_profiler(self) -> None:
        """Test rigging depends on character_profiler."""
        assert "character_profiler" in MODULE_DEPENDENCIES["rigging"]

    def test_animation_depends_on_rigging(self) -> None:
        """Test animation depends on rigging."""
        assert "rigging" in MODULE_DEPENDENCIES["animation"]

    def test_export_manager_deps(self) -> None:
        """Test export_manager dependencies."""
        deps = MODULE_DEPENDENCIES["export_manager"]
        assert "rigging" in deps
        assert "animation" in deps
