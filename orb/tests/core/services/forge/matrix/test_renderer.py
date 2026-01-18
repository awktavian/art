"""Tests for forge matrix renderer module."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from unittest.mock import Mock, MagicMock

from kagami.forge.matrix.renderer import ForgeStageContext
from kagami.forge.schema import CharacterRequest


class MockMatrix:
    """Mock matrix for testing ForgeStageContext."""

    def __init__(self):
        self.trace_events = []

    def _build_trace_attrs(self, component, request, extra):
        attrs = {"forge.component": component}
        if request:
            attrs["forge.request_id"] = getattr(request, "request_id", None)
        if extra:
            for k, v in extra.items():
                if v is not None:
                    attrs[f"forge.{k}"] = v
        return attrs

    def _record_trace_event(self, component, status, request=None, **kwargs):
        self.trace_events.append(
            {
                "component": component,
                "status": status,
                "request": request,
                **kwargs,
            }
        )


class TestForgeStageContext:
    """Tests for ForgeStageContext context manager."""

    def test_creation(self) -> None:
        """Test context creation."""
        matrix = MockMatrix()
        ctx = ForgeStageContext(matrix, "test_stage")

        assert ctx._component == "test_stage"
        assert ctx._request is None

    def test_creation_with_request(self) -> None:
        """Test context creation with request."""
        matrix = MockMatrix()
        request = CharacterRequest(concept="test")
        ctx = ForgeStageContext(matrix, "test_stage", request=request)

        assert ctx._request is request

    def test_context_manager_records_start(self) -> None:
        """Test context manager records stage start."""
        matrix = MockMatrix()

        with ForgeStageContext(matrix, "test_stage"):
            pass

        # Should have recorded start event
        assert any(e["status"] == "start" for e in matrix.trace_events)

    def test_context_manager_records_success(self) -> None:
        """Test context manager records success on clean exit."""
        matrix = MockMatrix()

        with ForgeStageContext(matrix, "test_stage"):
            pass

        # Should have recorded success
        assert any(e["status"] == "success" for e in matrix.trace_events)

    def test_context_manager_records_error(self) -> None:
        """Test context manager records error on exception."""
        matrix = MockMatrix()

        try:
            with ForgeStageContext(matrix, "test_stage"):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Should have recorded error
        error_events = [e for e in matrix.trace_events if e["status"] == "error"]
        assert len(error_events) > 0
        assert error_events[0]["error"] is not None

    def test_context_manager_records_duration(self) -> None:
        """Test context manager records duration."""
        import time

        matrix = MockMatrix()

        with ForgeStageContext(matrix, "test_stage"):
            time.sleep(0.01)

        # Should have recorded duration
        success_events = [e for e in matrix.trace_events if e["status"] == "success"]
        assert len(success_events) > 0
        assert success_events[0].get("duration_ms", 0) > 0

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """Test async context manager usage."""
        matrix = MockMatrix()

        async with ForgeStageContext(matrix, "async_stage"):
            pass

        assert any(e["status"] == "start" for e in matrix.trace_events)
        assert any(e["status"] == "success" for e in matrix.trace_events)

    def test_extra_attrs_passed(self) -> None:
        """Test extra attributes are passed."""
        matrix = MockMatrix()

        with ForgeStageContext(matrix, "test_stage", extra={"custom_key": "custom_value"}):
            pass

        # Extra should be in recorded events
        start_events = [e for e in matrix.trace_events if e["status"] == "start"]
        assert len(start_events) > 0
