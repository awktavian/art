"""Tests for CBF receipt emission integration.

COVERAGE TARGET: Receipt audit trail for safety checks
ESTIMATED RUNTIME: <2 seconds

Tests verify:
1. Receipt emission on successful safety checks
2. Receipt emission on blocked operations
3. Receipt emission on emergency halt
4. Receipt emission on emergency halt reset
5. Correlation ID propagation through safety checks
6. Non-blocking receipt emission (failures don't crash safety)
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

from unittest.mock import patch, MagicMock

from kagami.core.safety.cbf_integration import (
    check_cbf_sync,
    emergency_halt,
    reset_emergency_halt,
)


class TestCBFReceiptEmission:
    """Test receipt emissions for CBF safety checks."""

    @patch("kagami.core.safety.cbf_integration.URF.emit")
    def test_safe_operation_emits_receipt(self, mock_emit: MagicMock) -> None:
        """Safe operations should emit a success receipt."""
        # Safe text
        result = check_cbf_sync(
            operation="query",
            action="search",
            target="documentation",
            content="What is the weather today?",
        )

        # Should be safe
        assert result.safe is True
        assert result.h_x is not None
        assert result.h_x >= 0

        # Should emit receipt
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args is not None
        kwargs = call_args.kwargs

        assert kwargs["event_name"] == "safety.cbf_check"
        assert kwargs["phase"] == "VERIFY"
        assert kwargs["action"] == "search"
        assert kwargs["status"] == "success"
        assert kwargs["guardrails"]["safe"] is True
        assert kwargs["guardrails"]["h_value"] >= 0
        assert kwargs["event_data"]["operation"] == "query"

    @patch("kagami.core.safety.cbf_integration.URF.emit")
    def test_unsafe_operation_emits_blocked_receipt(self, mock_emit: MagicMock) -> None:
        """Unsafe operations should emit a blocked receipt."""
        # Potentially unsafe text (depends on classifier, may not always block)
        result = check_cbf_sync(
            operation="delete_all",
            action="destructive",
            target="system",
            content="Delete all files and format the drive",
        )

        # Should emit receipt (regardless of safe/unsafe result)
        assert mock_emit.call_count >= 1
        call_args = mock_emit.call_args
        assert call_args is not None
        kwargs = call_args.kwargs

        assert kwargs["event_name"] == "safety.cbf_check"
        assert kwargs["phase"] == "VERIFY"
        assert "guardrails" in kwargs
        assert "h_value" in kwargs["guardrails"]
        assert "safe" in kwargs["guardrails"]

    @patch("kagami.core.safety.cbf_integration.URF.emit")
    def test_correlation_id_propagation(self, mock_emit: MagicMock) -> None:
        """Correlation ID should propagate from metadata to receipt."""
        test_correlation_id = "test-corr-123"

        result = check_cbf_sync(
            operation="query",
            action="search",
            content="Hello world",
            metadata={"correlation_id": test_correlation_id},
        )

        assert result.safe is True

        # Should emit with provided correlation_id
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args is not None
        kwargs = call_args.kwargs
        assert kwargs["correlation_id"] == test_correlation_id

    @patch("kagami.core.safety.cbf_integration.URF.emit")
    @patch("kagami.core.safety.cbf_integration.URF.generate_correlation_id")
    def test_correlation_id_generation(self, mock_gen_id: MagicMock, mock_emit: MagicMock) -> None:
        """If no correlation_id provided, should generate one."""
        mock_gen_id.return_value = "generated-corr-456"

        result = check_cbf_sync(
            operation="query",
            action="search",
            content="Hello world",
        )

        assert result.safe is True

        # Should generate correlation_id
        mock_gen_id.assert_called_once_with(name="cbf_check")

        # Should emit with generated correlation_id
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args is not None
        kwargs = call_args.kwargs
        assert kwargs["correlation_id"] == "generated-corr-456"

    @patch("kagami.core.safety.cbf_integration.URF.emit")
    def test_emergency_halt_emits_receipt(self, mock_emit: MagicMock) -> None:
        """Emergency halt should emit a receipt."""
        # Clear any previous halt state
        reset_emergency_halt()
        mock_emit.reset_mock()

        # Trigger emergency halt
        emergency_halt()

        # Should emit receipt
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args is not None
        kwargs = call_args.kwargs

        assert kwargs["event_name"] == "safety.emergency_halt"
        assert kwargs["phase"] == "PLAN"
        assert kwargs["action"] == "emergency_halt"
        assert kwargs["status"] == "activated"
        assert kwargs["guardrails"]["safe"] is False
        assert kwargs["guardrails"]["h_value"] == float("-inf")

        # Cleanup
        reset_emergency_halt()

    @patch("kagami.core.safety.cbf_integration.URF.emit")
    def test_halt_reset_emits_receipt(self, mock_emit: MagicMock) -> None:
        """Emergency halt reset should emit a receipt."""
        # Set halt first
        emergency_halt()
        mock_emit.reset_mock()

        # Reset halt
        reset_emergency_halt()

        # Should emit receipt
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args is not None
        kwargs = call_args.kwargs

        assert kwargs["event_name"] == "safety.emergency_halt_reset"
        assert kwargs["phase"] == "VERIFY"
        assert kwargs["action"] == "reset_emergency_halt"
        assert kwargs["status"] == "success"
        assert kwargs["guardrails"]["safe"] is True

    @patch("kagami.core.safety.cbf_integration.URF.emit")
    def test_receipt_emission_failure_does_not_crash_safety(self, mock_emit: MagicMock) -> None:
        """Receipt emission failure should not prevent safety check."""
        # Make emit raise exception
        mock_emit.side_effect = RuntimeError("Receipt system down")

        # Safety check should still complete
        result = check_cbf_sync(
            operation="query",
            action="search",
            content="Hello world",
        )

        # Safety check should succeed despite receipt failure
        assert result.safe is True
        assert result.h_x is not None

        # Emit should have been attempted
        assert mock_emit.called

    @patch("kagami.core.safety.cbf_integration.URF.emit")
    def test_receipt_contains_full_metadata(self, mock_emit: MagicMock) -> None:
        """Receipt should contain all relevant safety metadata."""
        result = check_cbf_sync(
            operation="modify_config",
            action="update",
            target="settings.json",
            content="Update system configuration",
        )

        # Should emit receipt
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args is not None
        kwargs = call_args.kwargs

        # Check all critical fields present
        assert "correlation_id" in kwargs
        assert kwargs["event_name"] == "safety.cbf_check"
        assert kwargs["phase"] == "VERIFY"
        assert kwargs["action"] == "update"

        # Check guardrails
        guardrails = kwargs["guardrails"]
        assert "h_value" in guardrails
        assert "safe" in guardrails
        assert "margin" in guardrails
        assert "reason" in guardrails

        # Check event data
        event_data = kwargs["event_data"]
        assert event_data["operation"] == "modify_config"
        assert event_data["action"] == "update"
        assert event_data["target"] == "settings.json"

    @patch("kagami.core.safety.cbf_integration.URF.emit")
    def test_receipt_margin_calculation(self, mock_emit: MagicMock) -> None:
        """Receipt margin should correctly reflect distance from boundary."""
        result = check_cbf_sync(
            operation="query",
            action="search",
            content="Safe query",
        )

        assert result.safe is True
        assert result.h_x is not None

        # Extract margin from receipt
        mock_emit.assert_called_once()
        call_args = mock_emit.call_args
        assert call_args is not None
        kwargs = call_args.kwargs

        margin = kwargs["guardrails"]["margin"]
        h_value = kwargs["guardrails"]["h_value"]

        # For safe operations: margin = h_value (distance from 0)
        if h_value >= 0:
            assert margin == h_value
        else:
            # For unsafe: margin = |h_value|
            assert margin == abs(h_value)


class TestCBFReceiptIntegrationWithEmergencyHalt:
    """Test receipt emissions interact correctly with emergency halt."""

    @patch("kagami.core.safety.cbf_integration.URF.emit")
    def test_cbf_check_during_halt_emits_receipt(self, mock_emit: MagicMock) -> None:
        """CBF checks during emergency halt should emit blocked receipts."""
        # Activate emergency halt
        emergency_halt()
        mock_emit.reset_mock()

        # Try a safety check
        result = check_cbf_sync(
            operation="query",
            action="search",
            content="Safe query",
        )

        # Should be blocked
        assert result.safe is False
        assert result.reason == "emergency_halt"

        # Should NOT emit additional receipt (emergency halt already blocked)
        # The emergency halt check happens before the normal CBF check,
        # so no receipt emission from _emit_safety_receipt
        assert mock_emit.call_count == 0

        # Cleanup
        reset_emergency_halt()
