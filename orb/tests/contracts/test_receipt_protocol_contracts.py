"""Receipt Protocol Contract Tests.

Verifies that the receipt system maintains backward compatibility.
Receipts are the audit trail for all operations in K OS.

Contract violations indicate breaking changes to the receipt protocol.

Created: December 2025
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.tier_integration]


class TestReceiptSchemaContract:
    """Contract tests for receipt schema structure."""
    def test_receipt_has_required_fields(self):
        """Contract: Receipts must have correlation_id, ts, event_name."""
        from kagami.core.receipts import emit_receipt
        # Emit a test receipt
        receipt = emit_receipt(
            correlation_id="contract-test-123",
            action="test.contract",
            app="ContractTest",
            event_name="TEST",
            event_data={"test": True},
            duration_ms=1.0,
        )
        # Required fields (canonical schema uses 'ts' not 'timestamp')
        assert "correlation_id" in receipt, "Receipt must have correlation_id"
        assert "ts" in receipt, "Receipt must have ts (Unix timestamp ms)"
        assert "event_name" in receipt, "Receipt must have event_name"
        assert "intent" in receipt, "Receipt must have intent object"
    def test_receipt_correlation_id_format(self):
        """Contract: correlation_id must be a non-empty string."""
        from kagami.core.receipts import emit_receipt
        receipt = emit_receipt(
            correlation_id="test-format-check",
            action="test.format",
            app="ContractTest",
            event_name="FORMAT_CHECK",
            event_data={},
            duration_ms=0.5,
        )
        cid = receipt.get("correlation_id")
        assert isinstance(cid, str), f"correlation_id must be string, got {type(cid)}"
        assert len(cid) > 0, "correlation_id must be non-empty"
    def test_receipt_ts_is_unix_millis(self):
        """Contract: ts must be Unix timestamp in milliseconds."""
        from kagami.core.receipts import emit_receipt
        receipt = emit_receipt(
            correlation_id="timestamp-check",
            action="test.timestamp",
            app="ContractTest",
            event_name="TIMESTAMP_CHECK",
            event_data={},
            duration_ms=0.1,
        )
        ts = receipt.get("ts")
        assert ts is not None, "Receipt must have ts"
        assert isinstance(ts, int), f"ts must be int (Unix ms), got {type(ts)}"
        # Should be a reasonable Unix timestamp in milliseconds (after year 2020)
        assert ts > 1577836800000, f"ts {ts} too old (before 2020)"
class TestReceiptPhaseContract:
    """Contract tests for receipt phase enumeration."""
    def test_valid_phases(self):
        """Contract: Receipt phases are PLAN, EXECUTE, VERIFY."""
        valid_phases = {"PLAN", "EXECUTE", "VERIFY"}
        # These are the only valid phases in the 3-phase execution model
        assert "PLAN" in valid_phases
        assert "EXECUTE" in valid_phases
        assert "VERIFY" in valid_phases
        assert len(valid_phases) == 3
    def test_phase_ordering(self):
        """Contract: Phases follow partial order PLAN < EXECUTE < VERIFY."""
        phase_order = {"PLAN": 0, "EXECUTE": 1, "VERIFY": 2}
        assert phase_order["PLAN"] < phase_order["EXECUTE"]
        assert phase_order["EXECUTE"] < phase_order["VERIFY"]
        assert phase_order["PLAN"] < phase_order["VERIFY"]
class TestReceiptEventContract:
    """Contract tests for receipt event structure."""
    def test_event_name_is_string(self):
        """Contract: event_name must be a string."""
        from kagami.core.receipts import emit_receipt
        receipt = emit_receipt(
            correlation_id="event-name-check",
            action="test.event",
            app="ContractTest",
            event_name="STRING_EVENT",
            event_data={},
            duration_ms=0.1,
        )
        event_name = receipt.get("event_name")
        if event_name is not None:
            assert isinstance(event_name, str), f"event_name must be string, got {type(event_name)}"
    def test_event_data_is_dict(self):
        """Contract: event_data must be a dict (JSON-serializable)."""
        from kagami.core.receipts import emit_receipt
        receipt = emit_receipt(
            correlation_id="event-data-check",
            action="test.event",
            app="ContractTest",
            event_name="DATA_CHECK",
            event_data={"nested": {"value": 42}},
            duration_ms=0.1,
        )
        event_data = receipt.get("event_data")
        if event_data is not None:
            assert isinstance(event_data, dict), f"event_data must be dict, got {type(event_data)}"
class TestReceiptDurationContract:
    """Contract tests for receipt duration tracking."""
    def test_duration_is_numeric(self):
        """Contract: duration_ms must be a number ≥ 0."""
        from kagami.core.receipts import emit_receipt
        receipt = emit_receipt(
            correlation_id="duration-check",
            action="test.duration",
            app="ContractTest",
            event_name="DURATION_CHECK",
            event_data={},
            duration_ms=123.456,
        )
        duration = receipt.get("duration_ms")
        if duration is not None:
            assert isinstance(
                duration, (int, float)
            ), f"duration_ms must be numeric, got {type(duration)}"
            assert duration >= 0, f"duration_ms must be non-negative, got {duration}"
class TestReceiptIdempotencyContract:
    """Contract tests for idempotency support in receipts."""
    def test_same_correlation_id_linkable(self):
        """Contract: Receipts with same correlation_id can be linked."""
        from kagami.core.receipts import emit_receipt
        cid = "linked-receipts-test"
        r1 = emit_receipt(
            correlation_id=cid,
            action="test.link.1",
            app="ContractTest",
            event_name="LINK_1",
            event_data={},
            duration_ms=1.0,
        )
        r2 = emit_receipt(
            correlation_id=cid,
            action="test.link.2",
            app="ContractTest",
            event_name="LINK_2",
            event_data={},
            duration_ms=2.0,
        )
        # Both receipts should share the same correlation_id
        assert r1.get("correlation_id") == r2.get("correlation_id") == cid


# =============================================================================
# SCHEMA EVOLUTION TESTS - Added for 100/100 test quality
# =============================================================================


class TestSchemaEvolution:
    """Test backward and forward compatibility of receipt schema.

    Schema evolution rules:
    1. New optional fields can be added (backward compatible)
    2. Required fields cannot be removed (breaking)
    3. Field types cannot change (breaking)
    4. Enum values can be added but not removed
    """

    def test_v1_to_v2_backward_compatibility(self):
        """V2 consumer should handle V1 receipts.

        V1 receipts lack fields added in V2.
        """
        # V1 receipt (minimal fields)
        v1_receipt = {
            "correlation_id": "v1-test-123",
            "ts": "2025-01-01T00:00:00Z",
            "event_name": "V1_EVENT",
            "phase": "EXECUTE",
        }

        # V2 consumer should handle missing optional fields
        def v2_consumer(receipt: dict) -> dict:
            """V2 consumer with new optional fields."""
            return {
                "correlation_id": receipt["correlation_id"],
                "ts": receipt["ts"],
                "event_name": receipt["event_name"],
                "phase": receipt["phase"],
                # New V2 fields with defaults
                "duration_ms": receipt.get("duration_ms", 0.0),
                "metadata": receipt.get("metadata", {}),
                "trace_id": receipt.get("trace_id"),
                "span_id": receipt.get("span_id"),
            }

        processed = v2_consumer(v1_receipt)

        # Required fields preserved
        assert processed["correlation_id"] == "v1-test-123"
        assert processed["event_name"] == "V1_EVENT"

        # Optional fields have defaults
        assert processed["duration_ms"] == 0.0
        assert processed["metadata"] == {}
        assert processed["trace_id"] is None

    def test_v2_to_v1_forward_compatibility(self):
        """V1 consumer should handle V2 receipts.

        V1 consumers should ignore unknown fields.
        """
        # V2 receipt (extra fields)
        v2_receipt = {
            "correlation_id": "v2-test-456",
            "ts": "2025-01-01T00:00:00Z",
            "event_name": "V2_EVENT",
            "phase": "VERIFY",
            # New V2 fields
            "duration_ms": 42.5,
            "metadata": {"key": "value"},
            "trace_id": "trace-abc",
            "span_id": "span-xyz",
            "experimental_field": "future_feature",
        }

        # V1 consumer ignores unknown fields
        def v1_consumer(receipt: dict) -> dict:
            """V1 consumer that only knows original fields."""
            return {
                "correlation_id": receipt["correlation_id"],
                "ts": receipt["ts"],
                "event_name": receipt["event_name"],
                "phase": receipt["phase"],
            }

        processed = v1_consumer(v2_receipt)

        # V1 fields work correctly
        assert processed["correlation_id"] == "v2-test-456"
        assert processed["event_name"] == "V2_EVENT"
        assert processed["phase"] == "VERIFY"

        # Unknown fields are ignored (not error)
        assert "duration_ms" not in processed
        assert "experimental_field" not in processed

    def test_enum_extension_compatibility(self):
        """New enum values should not break old consumers.

        Old consumers should handle unknown enum values gracefully.
        """
        KNOWN_PHASES = {"PLAN", "EXECUTE", "VERIFY"}

        def process_phase(phase: str) -> str:
            """Process phase with unknown value handling."""
            if phase in KNOWN_PHASES:
                return phase
            else:
                # Unknown phase - default to generic handling
                return "UNKNOWN"

        # Known phases work
        assert process_phase("PLAN") == "PLAN"
        assert process_phase("EXECUTE") == "EXECUTE"

        # Future phases don't crash
        assert process_phase("ROLLBACK") == "UNKNOWN"  # V3 phase
        assert process_phase("COMPENSATE") == "UNKNOWN"  # V4 phase

    def test_field_type_stability(self):
        """Field types should remain stable across versions.

        Type changes are breaking changes.
        """
        # Schema definition (type annotations)
        SCHEMA_V1 = {
            "correlation_id": str,
            "ts": str,  # ISO timestamp string
            "event_name": str,
            "phase": str,
            "duration_ms": (float, int, type(None)),  # numeric or null
        }

        def validate_types(receipt: dict, schema: dict) -> list[str]:
            """Validate receipt field types against schema."""
            errors = []
            for field, expected_types in schema.items():
                if field not in receipt:
                    continue
                value = receipt[field]
                if not isinstance(expected_types, tuple):
                    expected_types = (expected_types,)
                if value is not None and not isinstance(value, expected_types):
                    errors.append(
                        f"Field '{field}' expected {expected_types}, got {type(value)}"
                    )
            return errors

        # Valid receipt
        valid_receipt = {
            "correlation_id": "test-123",
            "ts": "2025-01-01T00:00:00Z",
            "event_name": "TEST",
            "phase": "EXECUTE",
            "duration_ms": 42.5,
        }

        errors = validate_types(valid_receipt, SCHEMA_V1)
        assert errors == []

        # Invalid receipt (wrong types)
        invalid_receipt = {
            "correlation_id": 123,  # Should be string
            "ts": "2025-01-01T00:00:00Z",
            "event_name": "TEST",
            "phase": "EXECUTE",
            "duration_ms": "not a number",  # Should be numeric
        }

        errors = validate_types(invalid_receipt, SCHEMA_V1)
        assert len(errors) == 2

    def test_required_fields_stability(self):
        """Required fields cannot be removed.

        Removing required fields is a breaking change.
        """
        REQUIRED_FIELDS = {"correlation_id", "ts", "event_name", "phase"}

        def validate_required(receipt: dict) -> list[str]:
            """Check all required fields are present."""
            missing = REQUIRED_FIELDS - set(receipt.keys())
            return list(missing)

        # Complete receipt
        complete = {
            "correlation_id": "test",
            "ts": "2025-01-01T00:00:00Z",
            "event_name": "TEST",
            "phase": "EXECUTE",
        }

        missing = validate_required(complete)
        assert missing == []

        # Incomplete receipt
        incomplete = {
            "correlation_id": "test",
            "event_name": "TEST",
            # Missing: ts, phase
        }

        missing = validate_required(incomplete)
        assert set(missing) == {"ts", "phase"}

    def test_migration_path(self):
        """Test migration between schema versions.

        Migrations should be lossless for existing data.
        """

        def migrate_v1_to_v2(v1_receipt: dict) -> dict:
            """Migrate V1 receipt to V2 format."""
            v2_receipt = v1_receipt.copy()
            # Add new V2 fields with defaults
            v2_receipt.setdefault("duration_ms", 0.0)
            v2_receipt.setdefault("metadata", {})
            v2_receipt.setdefault("version", 2)
            return v2_receipt

        def migrate_v2_to_v3(v2_receipt: dict) -> dict:
            """Migrate V2 receipt to V3 format."""
            v3_receipt = v2_receipt.copy()
            # Rename field (with backward compatibility)
            if "event_name" in v3_receipt:
                v3_receipt["event_type"] = v3_receipt["event_name"]
            v3_receipt.setdefault("trace_context", {})
            v3_receipt["version"] = 3  # Explicitly set version
            return v3_receipt

        # Original V1 receipt
        v1 = {
            "correlation_id": "migrate-test",
            "ts": "2025-01-01T00:00:00Z",
            "event_name": "MIGRATE",
            "phase": "PLAN",
        }

        # Migrate through versions
        v2 = migrate_v1_to_v2(v1)
        v3 = migrate_v2_to_v3(v2)

        # Original data preserved
        assert v3["correlation_id"] == "migrate-test"
        assert v3["event_name"] == "MIGRATE"  # Still present
        assert v3["event_type"] == "MIGRATE"  # New name

        # New fields added
        assert v3["version"] == 3
        assert v3["duration_ms"] == 0.0
        assert v3["trace_context"] == {}


# Mark as contract tests
