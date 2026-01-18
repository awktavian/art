"""Tests for receipt emitter refactoring (TRAIL-010).

Tests that the emitter registry correctly constructs receipts
without the high cyclomatic complexity of the original implementation.
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_unit


class TestCoreEmitter:
    """Test CoreEmitter constructs basic receipt structure."""

    def test_core_emitter_basic(self) -> None:
        """Test core emitter creates basic receipt."""

        from kagami.core.receipts.emitters import CoreEmitter

        emitter = CoreEmitter()
        receipt = emitter.emit(
            correlation_id="test-123",
            event_name="test.event",
            action="test_action",
            app="test_app",
        )

        assert receipt["correlation_id"] == "test-123"
        assert receipt["event_name"] == "test.event"
        assert receipt["action"] == "test_action"
        assert receipt["app"] == "test_app"
        assert receipt["status"] == "success"
        assert "intent" in receipt
        assert "event" in receipt
        assert receipt["intent"]["action"] == "test_action"
        assert receipt["event"]["name"] == "test.event"

    def test_core_emitter_with_phase(self) -> None:
        """Test core emitter handles phase."""
        from kagami.core.receipts.emitters import CoreEmitter

        emitter = CoreEmitter()
        receipt = emitter.emit(
            correlation_id="test-123",
            event_name="test.event",
            phase="EXECUTE",
        )

        assert receipt["phase"] == "EXECUTE"

    def test_core_emitter_with_colony(self) -> None:
        """Test core emitter handles colony."""
        from kagami.core.receipts.emitters import CoreEmitter

        emitter = CoreEmitter()
        receipt = emitter.emit(
            correlation_id="test-123",
            event_name="test.event",
            colony="forge",
        )

        assert receipt["colony"] == "forge"

    def test_core_emitter_with_event_data(self) -> None:
        """Test core emitter handles event_data."""
        from kagami.core.receipts.emitters import CoreEmitter

        emitter = CoreEmitter()
        receipt = emitter.emit(
            correlation_id="test-123",
            event_name="test.event",
            event_data={"key": "value"},
        )

        assert receipt["event_data"] == {"key": "value"}
        assert receipt["event"]["data"] == {"key": "value"}

    def test_core_emitter_with_args(self) -> None:
        """Test core emitter handles args."""
        from kagami.core.receipts.emitters import CoreEmitter

        emitter = CoreEmitter()
        receipt = emitter.emit(
            correlation_id="test-123",
            event_name="test.event",
            args={"param": "value"},
        )

        assert receipt["args"] == {"param": "value"}
        assert receipt["intent"]["args"] == {"param": "value"}


class TestMetricsEmitter:
    """Test MetricsEmitter adds observability fields."""

    def test_metrics_emitter_duration(self) -> None:
        """Test metrics emitter adds duration_ms."""
        from kagami.core.receipts.emitters import MetricsEmitter

        emitter = MetricsEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, duration_ms=100)

        assert result["duration_ms"] == 100

    def test_metrics_emitter_metrics_dict(self) -> None:
        """Test metrics emitter adds metrics dict."""
        from kagami.core.receipts.emitters import MetricsEmitter

        emitter = MetricsEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, metrics={"cpu": 50})

        assert result["metrics"] == {"cpu": 50}

    def test_metrics_emitter_prediction(self) -> None:
        """Test metrics emitter adds prediction fields."""
        from kagami.core.receipts.emitters import MetricsEmitter

        emitter = MetricsEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, prediction={"next": "state"}, prediction_error_ms=10)

        assert result["prediction"] == {"next": "state"}
        assert result["prediction_error_ms"] == 10

    def test_metrics_emitter_valence(self) -> None:
        """Test metrics emitter adds valence."""
        from kagami.core.receipts.emitters import MetricsEmitter

        emitter = MetricsEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, valence=0.8)

        assert result["valence"] == 0.8

    def test_metrics_emitter_learning(self) -> None:
        """Test metrics emitter adds learning metadata."""
        from kagami.core.receipts.emitters import MetricsEmitter

        emitter = MetricsEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, learning={"reward": 1.0})

        assert result["learning"] == {"reward": 1.0}


class TestSafetyEmitter:
    """Test SafetyEmitter adds safety metadata."""

    def test_safety_emitter_guardrails(self) -> None:
        """Test safety emitter adds guardrails."""
        from kagami.core.receipts.emitters import SafetyEmitter

        emitter = SafetyEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, guardrails={"auth": "ok"})

        assert result["guardrails"] == {"auth": "ok"}

    def test_safety_emitter_quality_gates(self) -> None:
        """Test safety emitter adds quality_gates."""
        from kagami.core.receipts.emitters import SafetyEmitter

        emitter = SafetyEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, quality_gates={"coverage": 0.8})

        assert result["quality_gates"] == {"coverage": 0.8}

    def test_safety_emitter_verifier(self) -> None:
        """Test safety emitter adds verifier."""
        from kagami.core.receipts.emitters import SafetyEmitter

        emitter = SafetyEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, verifier="crystal")

        assert result["verifier"] == "crystal"


class TestContextEmitter:
    """Test ContextEmitter adds context metadata."""

    def test_context_emitter_workspace_hash(self) -> None:
        """Test context emitter adds workspace_hash."""
        from kagami.core.receipts.emitters import ContextEmitter

        emitter = ContextEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, workspace_hash="abc123")

        assert result["workspace_hash"] == "abc123"

    def test_context_emitter_self_pointer(self) -> None:
        """Test context emitter adds self_pointer."""
        from kagami.core.receipts.emitters import ContextEmitter

        emitter = ContextEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, self_pointer="system")

        assert result["self_pointer"] == "system"

    def test_context_emitter_loop_depth(self) -> None:
        """Test context emitter adds loop_depth."""
        from kagami.core.receipts.emitters import ContextEmitter

        emitter = ContextEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, loop_depth=2)

        assert result["loop_depth"] == 2

    def test_context_emitter_tool_calls(self) -> None:
        """Test context emitter adds tool_calls."""
        from kagami.core.receipts.emitters import ContextEmitter

        emitter = ContextEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, tool_calls=[{"tool": "search"}])

        assert result["tool_calls"] == [{"tool": "search"}]


class TestIdentityEmitter:
    """Test IdentityEmitter adds identity metadata."""

    def test_identity_emitter_user_id(self) -> None:
        """Test identity emitter adds user_id."""
        from kagami.core.receipts.emitters import IdentityEmitter

        emitter = IdentityEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, user_id="user-123")

        assert result["user_id"] == "user-123"

    def test_identity_emitter_tenant_id(self) -> None:
        """Test identity emitter adds tenant_id."""
        from kagami.core.receipts.emitters import IdentityEmitter

        emitter = IdentityEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, tenant_id="tenant-456")

        assert result["tenant_id"] == "tenant-456"

    def test_identity_emitter_actor(self) -> None:
        """Test identity emitter adds actor."""
        from kagami.core.receipts.emitters import IdentityEmitter

        emitter = IdentityEmitter()
        receipt = {"correlation_id": "test"}
        result = emitter.emit(receipt, actor="user@example.com")

        assert result["actor"] == "user@example.com"

    def test_identity_emitter_preserves_existing_actor(self) -> None:
        """Test identity emitter doesn't overwrite existing actor."""
        from kagami.core.receipts.emitters import IdentityEmitter

        emitter = IdentityEmitter()
        receipt = {"correlation_id": "test", "actor": "existing"}
        result = emitter.emit(receipt, actor="new")

        assert result["actor"] == "existing"


class TestEmitterRegistry:
    """Test EmitterRegistry coordinates all emitters."""

    def test_registry_emit_basic(self) -> None:
        """Test registry creates basic receipt."""
        from kagami.core.receipts.emitters import EmitterRegistry

        registry = EmitterRegistry()
        receipt = registry.emit(
            correlation_id="test-123",
            event_name="test.event",
            action="test_action",
        )

        assert receipt["correlation_id"] == "test-123"
        assert receipt["event_name"] == "test.event"
        assert receipt["action"] == "test_action"

    def test_registry_emit_with_all_fields(self) -> None:
        """Test registry handles all field types."""
        from kagami.core.receipts.emitters import EmitterRegistry

        registry = EmitterRegistry()
        receipt = registry.emit(
            correlation_id="test-123",
            event_name="test.event",
            action="test_action",
            app="test_app",
            phase="EXECUTE",
            colony="forge",
            duration_ms=100,
            guardrails={"auth": "ok"},
            workspace_hash="abc123",
            user_id="user-123",
        )

        assert receipt["correlation_id"] == "test-123"
        assert receipt["duration_ms"] == 100
        assert receipt["guardrails"] == {"auth": "ok"}
        assert receipt["workspace_hash"] == "abc123"
        assert receipt["user_id"] == "user-123"

    def test_registry_handles_legacy_data_param(self) -> None:
        """Test registry handles legacy 'data' parameter."""
        from kagami.core.receipts.emitters import EmitterRegistry

        registry = EmitterRegistry()
        receipt = registry.emit(
            correlation_id="test-123",
            event_name="test.event",
            data={"legacy": "value"},
        )

        # Should convert data to event_data
        assert receipt["event_data"] == {"legacy": "value"}

    def test_registry_emit_preserves_kwargs(self) -> None:
        """Test registry preserves remaining kwargs as intent args."""
        from kagami.core.receipts.emitters import EmitterRegistry

        registry = EmitterRegistry()
        receipt = registry.emit(
            correlation_id="test-123",
            event_name="test.event",
            custom_field="custom_value",
        )

        # Remaining kwargs should end up in args
        assert "args" in receipt
        assert receipt["args"]["custom_field"] == "custom_value"


class TestUnifiedReceiptFacade:
    """Test UnifiedReceiptFacade uses emitter registry."""

    def test_facade_emit_uses_registry(self, monkeypatch: Any) -> None:
        """Test facade.emit delegates to emitter registry."""
        from kagami.core.receipts.facade import UnifiedReceiptFacade

        # Mock add_receipt to avoid persistence
        monkeypatch.setattr(
            "kagami.core.receipts.ingestor.add_receipt",
            lambda x: None,
        )

        receipt = UnifiedReceiptFacade.emit(
            correlation_id="test-123",
            event_name="test.event",
            action="test_action",
            duration_ms=100,
            guardrails={"auth": "ok"},
        )

        # Verify receipt structure
        assert receipt["correlation_id"] == "test-123"
        assert receipt["event_name"] == "test.event"
        assert receipt["action"] == "test_action"
        assert receipt["duration_ms"] == 100
        assert receipt["guardrails"] == {"auth": "ok"}

    def test_facade_emit_returns_awaitable(self, monkeypatch: Any) -> None:
        """Test facade.emit returns awaitable ReceiptResult."""
        from kagami.core.receipts.facade import UnifiedReceiptFacade

        # Mock add_receipt
        monkeypatch.setattr(
            "kagami.core.receipts.ingestor.add_receipt",
            lambda x: None,
        )

        receipt = UnifiedReceiptFacade.emit(
            correlation_id="test-123",
            event_name="test.event",
        )

        # Should be awaitable
        assert hasattr(receipt, "__await__")


class TestComplexity:
    """Test cyclomatic complexity reduction."""

    def test_core_emitter_low_complexity(self) -> None:
        """Test CoreEmitter has low cyclomatic complexity.

        Original emit() had CC=63 due to many if statements.
        CoreEmitter.emit should have much lower CC (<10).
        """
        from kagami.core.receipts.emitters import CoreEmitter
        import inspect

        # Get source code
        source = inspect.getsource(CoreEmitter.emit)

        # Count if statements (rough CC estimate)
        if_count = source.count("if ")

        # CoreEmitter should have low CC (few conditionals)
        assert if_count < 10, f"CoreEmitter.emit has {if_count} conditionals (too high)"

    def test_metrics_emitter_low_complexity(self) -> None:
        """Test MetricsEmitter has low cyclomatic complexity."""
        from kagami.core.receipts.emitters import MetricsEmitter
        import inspect

        source = inspect.getsource(MetricsEmitter.emit)
        if_count = source.count("if ")

        assert if_count < 10, f"MetricsEmitter.emit has {if_count} conditionals (too high)"

    def test_facade_emit_low_complexity(self) -> None:
        """Test facade.emit has low cyclomatic complexity after refactoring."""
        from kagami.core.receipts.facade import UnifiedReceiptFacade
        import inspect

        source = inspect.getsource(UnifiedReceiptFacade.emit)
        if_count = source.count("if ")

        # After refactoring, facade.emit should have minimal conditionals
        assert if_count < 10, f"UnifiedReceiptFacade.emit has {if_count} conditionals (too high)"
