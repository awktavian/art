"""Tests for forge matrix events module."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


import time

from kagami.forge.matrix.events import EventManager
from kagami.forge.schema import CharacterRequest


class TestEventManager:
    """Tests for EventManager class."""

    def test_creation(self) -> None:
        """Test EventManager creation."""
        manager = EventManager()

        assert manager._execution_trace == []

    def test_record_trace_event_basic(self) -> None:
        """Test recording basic trace event."""
        manager = EventManager()

        manager.record_trace_event("test.component", "success")

        assert len(manager._execution_trace) == 1
        event = manager._execution_trace[0]
        assert event["component"] == "test.component"
        assert event["status"] == "success"
        assert "timestamp" in event

    def test_record_trace_event_with_request(self) -> None:
        """Test recording trace event with request."""
        manager = EventManager()
        request = CharacterRequest(
            request_id="req-123",
            concept="test character",
        )

        manager.record_trace_event("test.component", "success", request)

        event = manager._execution_trace[0]
        assert event["request_id"] == "req-123"
        assert event["concept"] == "test character"

    def test_record_trace_event_with_duration(self) -> None:
        """Test recording trace event with duration."""
        manager = EventManager()

        manager.record_trace_event(
            "test.component",
            "success",
            duration_ms=150.5,
        )

        event = manager._execution_trace[0]
        assert event["duration_ms"] == 150.5

    def test_record_trace_event_with_error(self) -> None:
        """Test recording trace event with error."""
        manager = EventManager()

        manager.record_trace_event(
            "test.component",
            "error",
            error="Something went wrong",
        )

        event = manager._execution_trace[0]
        assert event["error"] == "Something went wrong"

    def test_record_trace_event_error_truncation(self) -> None:
        """Test error message is truncated if too long."""
        manager = EventManager()
        long_error = "x" * 1000

        manager.record_trace_event(
            "test.component",
            "error",
            error=long_error,
        )

        event = manager._execution_trace[0]
        assert len(event["error"]) <= 500

    def test_record_trace_event_extra_kwargs(self) -> None:
        """Test recording trace event with extra kwargs."""
        manager = EventManager()

        manager.record_trace_event(
            "test.component",
            "success",
            custom_field="custom_value",
            another_field=123,
        )

        event = manager._execution_trace[0]
        assert event["custom_field"] == "custom_value"
        assert event["another_field"] == 123

    def test_record_trace_event_filters_none_kwargs(self) -> None:
        """Test None kwargs are filtered out."""
        manager = EventManager()

        manager.record_trace_event(
            "test.component",
            "success",
            should_exist="value",
            should_not_exist=None,
        )

        event = manager._execution_trace[0]
        assert "should_exist" in event
        assert "should_not_exist" not in event

    def test_build_trace_attrs_basic(self) -> None:
        """Test building trace attributes."""
        manager = EventManager()

        attrs = manager.build_trace_attrs("test.component", None, None)

        assert attrs["forge.component"] == "test.component"

    def test_build_trace_attrs_with_request(self) -> None:
        """Test building trace attributes with request."""
        manager = EventManager()
        request = CharacterRequest(
            request_id="req-123",
            concept="test character",
        )

        attrs = manager.build_trace_attrs("test.component", request, None)

        assert attrs["forge.request_id"] == "req-123"
        assert attrs["forge.concept"] == "test character"

    def test_build_trace_attrs_with_extra(self) -> None:
        """Test building trace attributes with extra data."""
        manager = EventManager()

        attrs = manager.build_trace_attrs(
            "test.component",
            None,
            {"module": "test_module", "phase": "start"},
        )

        assert attrs["forge.module"] == "test_module"
        assert attrs["forge.phase"] == "start"

    def test_build_trace_attrs_filters_none_extra(self) -> None:
        """Test None values in extra are filtered."""
        manager = EventManager()

        attrs = manager.build_trace_attrs(
            "test.component",
            None,
            {"valid": "value", "invalid": None},
        )

        assert "forge.valid" in attrs
        assert "forge.invalid" not in attrs

    def test_multiple_events(self) -> None:
        """Test recording multiple events."""
        manager = EventManager()

        manager.record_trace_event("component1", "start")
        manager.record_trace_event("component1", "success")
        manager.record_trace_event("component2", "start")

        assert len(manager._execution_trace) == 3
        assert manager._execution_trace[0]["status"] == "start"
        assert manager._execution_trace[1]["status"] == "success"
        assert manager._execution_trace[2]["component"] == "component2"
