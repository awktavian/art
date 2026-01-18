"""Tests for forge shared_context module."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.shared_context import (
    FlexibleReasoningGenerator,
    SharedContext,
)


class TestSharedContext:
    """Tests for SharedContext class."""

    def test_creation_lazy(self) -> None:
        """Test lazy initialization creation."""
        ctx = SharedContext(lazy_init=True)

        assert ctx._initialized is False

    def test_creation_immediate(self) -> None:
        """Test immediate initialization."""
        ctx = SharedContext(lazy_init=False)

        assert ctx._initialized is True

    def test_get_set(self) -> None:
        """Test get and set context values."""
        ctx = SharedContext(lazy_init=True)

        ctx.set("key1", "value1")
        assert ctx.get("key1") == "value1"
        assert ctx.get("missing") is None
        assert ctx.get("missing", "default") == "default"

    def test_clear(self) -> None:
        """Test clearing context."""
        ctx = SharedContext(lazy_init=True)

        ctx.set("key1", "value1")
        ctx.clear()

        assert ctx.get("key1") is None

    def test_initialize_context(self) -> None:
        """Test initialize_context method."""
        ctx = SharedContext(lazy_init=True)

        result = ctx.initialize_context(key1="value1", key2="value2")

        assert result["key1"] == "value1"
        assert result["key2"] == "value2"

    def test_get_reasoning_strategy(self) -> None:
        """Test get_reasoning_strategy method."""
        from kagami.forge.forge_llm_base import CharacterAspect

        ctx = SharedContext(lazy_init=True)

        strategy = ctx.get_reasoning_strategy(CharacterAspect.VISUAL_DESIGN)
        # Should return a ReasoningStrategy or None

    def test_get_generation_order(self) -> None:
        """Test get_generation_order method."""
        from kagami.forge.forge_llm_base import CharacterAspect

        ctx = SharedContext(lazy_init=True)

        aspects = [
            CharacterAspect.BACKSTORY,
            CharacterAspect.VISUAL_DESIGN,
            CharacterAspect.PERSONALITY,
        ]
        ordered = ctx.get_generation_order(aspects)

        # Visual design should come first
        assert ordered[0] == CharacterAspect.VISUAL_DESIGN
        assert CharacterAspect.PERSONALITY in ordered
        assert CharacterAspect.BACKSTORY in ordered

    def test_reasoning_generator_property(self) -> None:
        """Test reasoning_generator lazy property."""
        ctx = SharedContext(lazy_init=True)

        gen1 = ctx.reasoning_generator
        gen2 = ctx.reasoning_generator

        assert gen1 is gen2  # Same instance
        assert isinstance(gen1, FlexibleReasoningGenerator)


class TestFlexibleReasoningGenerator:
    """Tests for FlexibleReasoningGenerator class."""

    def test_creation(self) -> None:
        """Test generator creation."""
        gen = FlexibleReasoningGenerator()

        assert gen._backends_ready is False

    def test_initialize_backends(self) -> None:
        """Test initialize_backends method."""
        gen = FlexibleReasoningGenerator()

        gen._initialize_backends()

        assert gen._backends_ready is True

    def test_get_available_models(self) -> None:
        """Test get_available_models method."""
        gen = FlexibleReasoningGenerator()

        models = gen.get_available_models()

        assert isinstance(models, dict)
        assert "fast" in models
        assert "medium" in models
        assert "primary" in models

    def test_select_reasoning_for_aspect(self) -> None:
        """Test _select_reasoning_for_aspect method."""
        gen = FlexibleReasoningGenerator()

        assert gen._select_reasoning_for_aspect("visual_design") == "multimodal"
        assert gen._select_reasoning_for_aspect("personality") == "inductive"
        assert gen._select_reasoning_for_aspect("voice") == "creative"
        assert gen._select_reasoning_for_aspect("motion") == "analogical"
        assert gen._select_reasoning_for_aspect("beliefs") == "deductive"
        assert gen._select_reasoning_for_aspect("backstory") == "causal"
        assert gen._select_reasoning_for_aspect("narrative_role") == "abductive"
        assert gen._select_reasoning_for_aspect("unknown") == "inductive"  # Default
