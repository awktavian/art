"""Tests for debugging protocols.

Tests the introspection protocols defined in kagami/core/debugging/protocols.py.
These define contracts for system introspection and reflection.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


from typing import Any

from kagami.core.debugging.protocols import IntrospectionManagerProtocol


class TestIntrospectionManagerProtocol:
    """Test IntrospectionManagerProtocol."""

    def test_protocol_is_runtime_checkable(self) -> None:
        """Protocol should be runtime checkable."""
        from typing import runtime_checkable

        # A runtime_checkable Protocol can be used with isinstance()
        # This is verified by the _is_runtime_protocol attribute
        assert getattr(IntrospectionManagerProtocol, "_is_runtime_protocol", False)

    def test_protocol_has_required_methods(self) -> None:
        """Protocol should define required methods."""
        # Check protocol defines these methods
        protocol_methods = set(dir(IntrospectionManagerProtocol))
        assert "reflect_post_intent" in protocol_methods
        assert "start_periodic_reflection_loop" in protocol_methods
        assert "stop_periodic_reflection_loop" in protocol_methods

    def test_conforming_class_is_instance(self) -> None:
        """Class with correct methods should pass isinstance check."""

        class ConformingManager:
            """Implements IntrospectionManagerProtocol."""

            async def reflect_post_intent(
                self, intent: Any, receipt: dict[str, Any] | None
            ) -> None:
                pass

            async def start_periodic_reflection_loop(self, interval_seconds: float = 600.0) -> None:
                pass

            async def stop_periodic_reflection_loop(self) -> None:
                pass

        manager = ConformingManager()
        assert isinstance(manager, IntrospectionManagerProtocol)

    def test_non_conforming_class_not_instance(self) -> None:
        """Class without correct methods should fail isinstance check."""

        class NonConformingManager:
            """Missing required methods."""

            async def reflect_post_intent(
                self, intent: Any, receipt: dict[str, Any] | None
            ) -> None:
                pass

            # Missing start_periodic_reflection_loop
            # Missing stop_periodic_reflection_loop

        manager = NonConformingManager()
        assert not isinstance(manager, IntrospectionManagerProtocol)

    def test_partial_conforming_not_instance(self) -> None:
        """Class with only some methods should fail isinstance check."""

        class PartialManager:
            """Only implements some methods."""

            async def reflect_post_intent(
                self, intent: Any, receipt: dict[str, Any] | None
            ) -> None:
                pass

            async def start_periodic_reflection_loop(self, interval_seconds: float = 600.0) -> None:
                pass

            # Missing stop_periodic_reflection_loop

        manager = PartialManager()
        assert not isinstance(manager, IntrospectionManagerProtocol)


class TestIntrospectionManagerImplementation:
    """Test that implementations can be used correctly."""

    @pytest.fixture
    def manager(self) -> Any:
        """Create a conforming manager instance."""

        class TestManager:
            """Test implementation of IntrospectionManagerProtocol."""

            def __init__(self):
                self.reflections = []
                self.loop_running = False
                self.interval = None

            async def reflect_post_intent(
                self, intent: Any, receipt: dict[str, Any] | None
            ) -> None:
                self.reflections.append({"intent": intent, "receipt": receipt})

            async def start_periodic_reflection_loop(self, interval_seconds: float = 600.0) -> None:
                self.loop_running = True
                self.interval = interval_seconds

            async def stop_periodic_reflection_loop(self) -> Any:
                self.loop_running = False

        return TestManager()

    @pytest.mark.asyncio
    async def test_reflect_post_intent(self, manager: Any) -> Any:
        """reflect_post_intent should store reflections."""
        await manager.reflect_post_intent("test_intent", {"status": "ok"})
        assert len(manager.reflections) == 1
        assert manager.reflections[0]["intent"] == "test_intent"

    @pytest.mark.asyncio
    async def test_start_stop_loop(self, manager: Any) -> None:
        """Loop methods should track state."""
        assert manager.loop_running is False

        await manager.start_periodic_reflection_loop(300.0)
        assert manager.loop_running is True
        assert manager.interval == 300.0

        await manager.stop_periodic_reflection_loop()
        assert manager.loop_running is False

    @pytest.mark.asyncio
    async def test_default_interval(self, manager: Any) -> None:
        """Default interval should be 600 seconds."""
        await manager.start_periodic_reflection_loop()
        assert manager.interval == 600.0
