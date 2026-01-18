"""Tests for three-layer cognitive architecture."""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from datetime import datetime

from kagami.core.cognition import (
    LayerMessage,
    PhilosophicalLayer,
    RecursiveFeedbackCoordinator,
    ScientificLayer,
)


@pytest.mark.asyncio
async def test_scientific_layer_analyzes_receipts():
    """Test that Scientific Layer can analyze receipts and find patterns."""
    layer = ScientificLayer()

    # Simulate some receipts (would come from receipt store)
    receipts = [
        {
            "status": "error",
            "operation": "/api/test",
            "error": "timeout",
            "duration_ms": 1000,
            "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "status": "error",
            "operation": "/api/test",
            "error": "timeout",
            "duration_ms": 1100,
            "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "status": "error",
            "operation": "/api/test",
            "error": "timeout",
            "duration_ms": 900,
            "timestamp": datetime.utcnow().isoformat(),
        },
        {
            "status": "success",
            "operation": "/api/other",
            "duration_ms": 50,
            "timestamp": datetime.utcnow().isoformat(),
        },
    ]

    # Mock receipt cache
    layer._receipt_cache = receipts

    # Override fetch to return our mock data
    async def mock_fetch(hours: Any) -> Any:
        return receipts

    layer._fetch_receipts = mock_fetch  # type: ignore[method-assign]

    # Analyze
    report = await layer.analyze_receipts_window(hours=1)

    # Should identify the timeout pattern
    assert len(report.failure_patterns) > 0
    pattern = report.failure_patterns[0]
    assert pattern.route == "/api/test"
    assert pattern.error_type == "timeout"
    assert pattern.occurrences == 3

    # Should have recommendations
    assert len(report.recommendations) > 0


@pytest.mark.asyncio
async def test_philosophical_layer_detects_paradigm_issues():
    """Test that Philosophical Layer can identify when paradigm shift is needed."""
    layer = PhilosophicalLayer()

    # Create analysis report with persistent failures
    from kagami.core.cognition.scientific_layer import AnalysisReport, FailurePattern

    patterns = [
        FailurePattern(
            route="/api/test",
            error_type="timeout",
            occurrences=15,
            duration_days=10,
            average_duration_ms=1000,
            root_cause_hypothesis="Database slow",
            confidence=0.9,
        ),
        FailurePattern(
            route="/api/other",
            error_type="timeout",
            occurrences=12,
            duration_days=8,
            average_duration_ms=950,
            root_cause_hypothesis="Slow service",
            confidence=0.8,
        ),
        FailurePattern(
            route="/api/another",
            error_type="timeout",
            occurrences=11,
            duration_days=9,
            average_duration_ms=1100,
            root_cause_hypothesis="Network issue",
            confidence=0.7,
        ),
    ]

    report = AnalysisReport(
        timestamp=datetime.utcnow(),
        window_hours=24,
        failure_patterns=patterns,
        experiments=[],
        recommendations=["Many failures"],
        performance_trends={"error_rate": 0.05},
    )

    # Evaluate paradigm
    assessment = await layer.evaluate_paradigm(report)

    # Should detect paradigm issue due to persistent failures
    assert not assessment.current_paradigm_viable
    assert "persistent" in assessment.reason.lower()


@pytest.mark.asyncio
async def test_philosophical_layer_proposes_shift():
    """Test that Philosophical Layer proposes appropriate paradigm shifts."""
    layer = PhilosophicalLayer()

    from kagami.core.cognition.philosophical_layer import ParadigmAssessment
    from kagami.core.cognition.scientific_layer import FailurePattern

    # Repeated timeout failures
    patterns = [
        FailurePattern(
            route="/api/test",
            error_type="timeout",
            occurrences=20,
            duration_days=14,
            average_duration_ms=1000,
            root_cause_hypothesis="Slow sync calls",
            confidence=0.9,
        ),
    ]

    assessment = ParadigmAssessment(
        current_paradigm_viable=False,
        reason="Too many timeouts",
    )

    # Propose shift
    shift = await layer.propose_paradigm_shift(assessment, patterns)

    assert shift is not None
    assert "async" in shift.proposed_shift.lower() or "event" in shift.proposed_shift.lower()
    assert shift.risk_level in ["high", "medium", "low"]


@pytest.mark.asyncio
async def test_recursive_feedback_coordinator():
    """Test that coordinator connects layers properly."""
    coordinator = RecursiveFeedbackCoordinator()

    # Start should not fail
    await coordinator.start()

    # Should have layer instances
    assert coordinator.scientific is not None
    assert coordinator.philosophical is not None
    assert coordinator.interface is not None

    # Cleanup
    await coordinator.stop()


@pytest.mark.asyncio
async def test_layer_messages():
    """Test layer-to-layer message passing."""
    from kagami.core.cognition.layer_interface import LayerInterface

    interface = LayerInterface()

    # Send message from scientific to technological
    msg = LayerMessage(
        from_layer="scientific",
        to_layer="technological",
        message_type="instruction",
        content={"action": "optimize_cache"},
    )
    interface.send_message(msg)

    # Check message is queued
    assert interface.has_messages_for("technological")

    # Retrieve messages
    messages = interface.get_messages_for("technological")
    assert len(messages) == 1
    assert messages[0].content["action"] == "optimize_cache"

    # Should be cleared after retrieval
    assert not interface.has_messages_for("technological")
