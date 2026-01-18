"""Tests for Experience Bus Subscribers.

Tests cover:
- MemoryIndexer storing outcomes in episodic memory
- PatternBuilder learning from successes
- ThreatLearner tracking failure patterns
- Subscriber registration
- Error handling
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import time
from unittest.mock import AsyncMock, Mock, patch

from kagami.core.events import E8Event
from kagami.core.events.subscribers import (
    MemoryIndexer,
    PatternBuilder,
    ThreatLearner,
    register_all_subscribers,
)


@pytest.fixture
def success_outcome():
    """Create successful outcome."""
    payload = {
        "correlation_id": "success-123",
        "operation": "test_operation",
        "app": "test_app",
        "problem_type": "computational",
        "strategy_used": "react_k1",
        "temperature": 0.7,
        "success": True,
        "duration_ms": 100.0,
        "prediction_error_ms": 10.0,
        "valence": 0.8,
        "verification_errors": [],
        "timestamp": time.time(),
    }
    return E8Event(
        topic="experience.test_app",
        correlation_id="success-123",
        payload=payload,
    )


@pytest.fixture
def failure_outcome():
    """Create failed outcome."""
    payload = {
        "correlation_id": "failure-456",
        "operation": "test_operation",
        "app": "test_app",
        "problem_type": "computational",
        "strategy_used": "react_k1",
        "temperature": 0.7,
        "success": False,
        "duration_ms": 200.0,
        "prediction_error_ms": 50.0,
        "valence": -0.9,
        "verification_errors": ["Syntax error", "Type error"],
        "timestamp": time.time(),
    }
    return E8Event(
        topic="experience.test_app",
        correlation_id="failure-456",
        payload=payload,
    )


class TestMemoryIndexer:
    """Test MemoryIndexer subscriber."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """MemoryIndexer can be initialized."""
        indexer = MemoryIndexer()
        assert indexer._initialized is False
        assert indexer._learning_instinct is None

    @pytest.mark.asyncio
    async def test_initialize_connects_learning_instinct(self) -> None:
        """Initialize connects to learning instinct."""
        indexer = MemoryIndexer()

        with patch("kagami.core.instincts.learning_instinct.LearningInstinct") as mock_instinct:
            await indexer.initialize()

            assert indexer._initialized is True
            assert indexer._learning_instinct is not None
            mock_instinct.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_handles_import_error(self) -> None:
        """Initialize handles missing learning instinct gracefully."""
        indexer = MemoryIndexer()

        with patch(
            "kagami.core.instincts.learning_instinct.LearningInstinct",
            side_effect=ImportError("Not available"),
        ):
            await indexer.initialize()

            assert indexer._learning_instinct is None

    @pytest.mark.asyncio
    async def test_handle_outcome_stores_in_memory(self, success_outcome: Any) -> None:
        """handle_outcome stores outcome in episodic memory."""
        indexer = MemoryIndexer()
        indexer._learning_instinct = Mock()  # type: ignore[assignment]
        indexer._learning_instinct.remember = AsyncMock()
        indexer._initialized = True

        await indexer.handle_outcome(success_outcome)

        # Should call remember with correct structure
        indexer._learning_instinct.remember.assert_called_once()
        call_kwargs = indexer._learning_instinct.remember.call_args[1]

        assert call_kwargs["context"]["operation"] == "test_operation"
        assert call_kwargs["context"]["app"] == "test_app"
        assert call_kwargs["context"]["problem_type"] == "computational"
        assert call_kwargs["outcome"]["success"] is True
        assert call_kwargs["valence"] == 0.8

    @pytest.mark.asyncio
    async def test_handle_outcome_auto_initializes(self, success_outcome: Any) -> None:
        """handle_outcome initializes if not yet initialized."""
        indexer = MemoryIndexer()

        with patch("kagami.core.instincts.learning_instinct.LearningInstinct") as mock_instinct:
            mock_instinct.return_value.remember = AsyncMock()
            await indexer.handle_outcome(success_outcome)

            assert indexer._initialized is True

    @pytest.mark.asyncio
    async def test_handle_outcome_gracefully_fails(self, success_outcome: Any) -> None:
        """handle_outcome handles errors gracefully."""
        indexer = MemoryIndexer()
        indexer._learning_instinct = Mock()  # type: ignore[assignment]
        indexer._learning_instinct.remember = AsyncMock(side_effect=ValueError("Test error"))
        indexer._initialized = True

        # Should not raise
        await indexer.handle_outcome(success_outcome)

    @pytest.mark.asyncio
    async def test_handle_outcome_when_instinct_unavailable(self, success_outcome: Any) -> None:
        """handle_outcome returns early if instinct unavailable."""
        indexer = MemoryIndexer()
        indexer._initialized = True
        indexer._learning_instinct = None

        # Should not raise
        await indexer.handle_outcome(success_outcome)


class TestPatternBuilder:
    """Test PatternBuilder subscriber."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """PatternBuilder can be initialized."""
        builder = PatternBuilder()
        assert builder._initialized is False
        assert builder._prediction_instinct is None
        assert builder._pattern_cache == {}

    @pytest.mark.asyncio
    async def test_initialize_connects_prediction_instinct(self) -> None:
        """Initialize connects to prediction instinct."""
        builder = PatternBuilder()

        with patch("kagami.core.instincts.prediction_instinct.PredictionInstinct") as mock_instinct:
            await builder.initialize()

            assert builder._initialized is True
            assert builder._prediction_instinct is not None
            mock_instinct.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_outcome_learns_pattern(self, success_outcome: Any) -> None:
        """handle_outcome updates prediction instinct."""
        builder = PatternBuilder()
        builder._prediction_instinct = Mock()  # type: ignore[assignment]
        builder._prediction_instinct.learn = AsyncMock()
        builder._initialized = True

        await builder.handle_outcome(success_outcome)

        # Should call learn with correct structure
        builder._prediction_instinct.learn.assert_called_once()
        call_kwargs = builder._prediction_instinct.learn.call_args[1]

        assert call_kwargs["context"]["app"] == "test_app"
        assert call_kwargs["context"]["action"] == "test_operation"
        assert call_kwargs["actual_outcome"]["duration_ms"] == 100.0
        assert call_kwargs["actual_outcome"]["status"] == "success"

    @pytest.mark.asyncio
    async def test_handle_outcome_learns_from_failures(self, failure_outcome: Any) -> None:
        """handle_outcome learns from failures too."""
        builder = PatternBuilder()
        builder._prediction_instinct = Mock()  # type: ignore[assignment]
        builder._prediction_instinct.learn = AsyncMock()
        builder._initialized = True

        await builder.handle_outcome(failure_outcome)

        builder._prediction_instinct.learn.assert_called_once()
        call_kwargs = builder._prediction_instinct.learn.call_args[1]
        assert call_kwargs["actual_outcome"]["status"] == "error"

    @pytest.mark.asyncio
    async def test_handle_outcome_auto_initializes(self, success_outcome: Any) -> None:
        """handle_outcome initializes if needed."""
        builder = PatternBuilder()

        with patch("kagami.core.instincts.prediction_instinct.PredictionInstinct") as mock_instinct:
            mock_instinct.return_value.learn = AsyncMock()
            await builder.handle_outcome(success_outcome)

            assert builder._initialized is True

    @pytest.mark.asyncio
    async def test_handle_outcome_handles_errors(self, success_outcome: Any) -> None:
        """handle_outcome handles errors gracefully."""
        builder = PatternBuilder()
        builder._prediction_instinct = Mock()  # type: ignore[assignment]
        builder._prediction_instinct.learn = AsyncMock(side_effect=RuntimeError("Test error"))
        builder._initialized = True

        # Should not raise
        await builder.handle_outcome(success_outcome)


class TestThreatLearner:
    """Test ThreatLearner subscriber."""

    @pytest.mark.asyncio
    async def test_initialization(self) -> None:
        """ThreatLearner can be initialized."""
        learner = ThreatLearner()
        assert learner._initialized is False
        assert learner._failure_patterns == []

    @pytest.mark.asyncio
    async def test_initialize_sets_flag(self) -> None:
        """Initialize sets initialized flag."""
        learner = ThreatLearner()
        await learner.initialize()
        assert learner._initialized is True

    @pytest.mark.asyncio
    async def test_handle_outcome_ignores_successes(self, success_outcome: Any) -> None:
        """handle_outcome ignores successful outcomes."""
        learner = ThreatLearner()
        learner._initialized = True

        await learner.handle_outcome(success_outcome)

        # No patterns stored for successes
        assert len(learner._failure_patterns) == 0

    @pytest.mark.asyncio
    async def test_handle_outcome_stores_failures(self, failure_outcome: Any) -> None:
        """handle_outcome stores failure patterns."""
        learner = ThreatLearner()
        learner._initialized = True

        await learner.handle_outcome(failure_outcome)

        # Pattern should be stored
        assert len(learner._failure_patterns) == 1
        pattern = learner._failure_patterns[0]

        assert pattern["operation"] == "test_operation"
        assert pattern["problem_type"] == "computational"
        assert pattern["strategy"] == "react_k1"
        assert pattern["errors"] == ["Syntax error", "Type error"]
        assert pattern["severity"] == 0.9  # abs(valence)

    @pytest.mark.asyncio
    async def test_handle_outcome_multiple_failures(self) -> None:
        """handle_outcome stores multiple failures."""
        learner = ThreatLearner()
        learner._initialized = True

        # Store 3 failures
        for i in range(3):
            payload = {
                "operation": f"op_{i}",
                "problem_type": "test",
                "strategy_used": "test",
                "verification_errors": [f"error_{i}"],
                "valence": -0.5,
                "success": False,
                "timestamp": time.time(),
            }
            await learner.handle_outcome(E8Event(topic="experience.test", payload=payload))

        assert len(learner._failure_patterns) == 3

    @pytest.mark.asyncio
    async def test_handle_outcome_limits_pattern_storage(self) -> None:
        """handle_outcome keeps only last 200 failures."""
        learner = ThreatLearner()
        learner._initialized = True

        # Store 250 failures
        for i in range(250):
            payload = {
                "operation": f"op_{i}",
                "problem_type": "test",
                "strategy_used": "test",
                "verification_errors": [],
                "valence": -0.5,
                "success": False,
                "timestamp": time.time(),
            }
            await learner.handle_outcome(E8Event(topic="experience.test", payload=payload))

        # Should only keep last 200
        assert len(learner._failure_patterns) == 200

        # First 50 should be dropped
        assert all(int(p["operation"].split("_")[1]) >= 50 for p in learner._failure_patterns)

    @pytest.mark.asyncio
    async def test_get_failure_count(self) -> None:
        """get_failure_count returns count for operation."""
        learner = ThreatLearner()
        learner._initialized = True

        # Add 3 failures for op_a, 2 for op_b
        for _i in range(3):
            payload = {
                "operation": "op_a",
                "problem_type": "test",
                "strategy_used": "test",
                "verification_errors": [],
                "valence": -0.5,
                "success": False,
                "timestamp": time.time(),
            }
            await learner.handle_outcome(E8Event(topic="experience.test", payload=payload))

        for _i in range(2):
            payload = {
                "operation": "op_b",
                "problem_type": "test",
                "strategy_used": "test",
                "verification_errors": [],
                "valence": -0.5,
                "success": False,
                "timestamp": time.time(),
            }
            await learner.handle_outcome(E8Event(topic="experience.test", payload=payload))

        assert learner.get_failure_count("op_a") == 3
        assert learner.get_failure_count("op_b") == 2
        assert learner.get_failure_count("op_c") == 0

    @pytest.mark.asyncio
    async def test_handle_outcome_auto_initializes(self, failure_outcome: Any) -> None:
        """handle_outcome initializes if needed."""
        learner = ThreatLearner()
        await learner.handle_outcome(failure_outcome)
        assert learner._initialized is True


class TestSubscriberRegistration:
    """Test subscriber registration helper."""

    def test_register_all_subscribers(self) -> None:
        """register_all_subscribers registers all 3 subscribers."""
        mock_bus = Mock()
        mock_bus.subscribe = Mock()

        register_all_subscribers(mock_bus)

        # Should register 3 subscribers
        assert mock_bus.subscribe.call_count == 3

        # Verify all handlers are registered to experience.* topic
        topics = [c.args[0] for c in mock_bus.subscribe.call_args_list]
        assert all(t == "experience.*" for t in topics)

        handlers = [c.args[1] for c in mock_bus.subscribe.call_args_list]
        handler_names = [handler.__self__.__class__.__name__ for handler in handlers]

        assert "MemoryIndexer" in handler_names
        assert "PatternBuilder" in handler_names
        assert "ThreatLearner" in handler_names
