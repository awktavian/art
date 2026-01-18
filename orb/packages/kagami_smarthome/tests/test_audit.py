"""Tests for audit trail.

Created: January 2, 2026
"""

import pytest

from kagami_smarthome.audit import (
    ActionCategory,
    ActionStatus,
    AuditRecord,
    AuditTrail,
    get_audit_trail,
)


class TestActionCategory:
    """Tests for ActionCategory enum."""

    def test_all_categories(self):
        """All categories exist."""
        categories = [
            ActionCategory.LIGHT,
            ActionCategory.SHADE,
            ActionCategory.AUDIO,
            ActionCategory.HVAC,
            ActionCategory.SECURITY,
            ActionCategory.TV,
            ActionCategory.SCENE,
            ActionCategory.PRESENCE,
            ActionCategory.SYSTEM,
        ]
        assert len(categories) == 9


class TestActionStatus:
    """Tests for ActionStatus enum."""

    def test_all_statuses(self):
        """All statuses exist."""
        statuses = [
            ActionStatus.PENDING,
            ActionStatus.IN_PROGRESS,
            ActionStatus.SUCCESS,
            ActionStatus.FAILED,
            ActionStatus.CANCELLED,
        ]
        assert len(statuses) == 5


class TestAuditRecord:
    """Tests for AuditRecord dataclass."""

    def test_create_record(self):
        """Create basic record."""
        import time

        record = AuditRecord(
            id="test123",
            timestamp=time.time(),
            action="set_lights",
            category=ActionCategory.LIGHT,
            parameters={"level": 50},
        )
        assert record.action == "set_lights"
        assert record.status == ActionStatus.PENDING

    def test_is_complete_property(self):
        """is_complete property works."""
        import time

        record = AuditRecord(
            id="test",
            timestamp=time.time(),
            action="test",
            category=ActionCategory.SYSTEM,
            parameters={},
        )

        # PENDING is not complete
        assert record.is_complete is False

        # IN_PROGRESS is not complete
        record.status = ActionStatus.IN_PROGRESS
        assert record.is_complete is False

        # SUCCESS is complete
        record.status = ActionStatus.SUCCESS
        assert record.is_complete is True

        # FAILED is complete
        record.status = ActionStatus.FAILED
        assert record.is_complete is True

    def test_datetime_property(self):
        """datetime property converts timestamp."""
        import time

        ts = time.time()
        record = AuditRecord(
            id="test",
            timestamp=ts,
            action="test",
            category=ActionCategory.SYSTEM,
            parameters={},
        )
        assert record.datetime.timestamp() == pytest.approx(ts, rel=1)


class TestAuditTrail:
    """Tests for AuditTrail class."""

    def test_start_action(self):
        """Start action returns ID."""
        audit = AuditTrail()
        record_id = audit.start_action(
            action="set_lights",
            category=ActionCategory.LIGHT,
            parameters={"level": 50},
        )
        assert record_id is not None
        assert len(record_id) == 8

    def test_complete_success(self):
        """Complete success marks action done."""
        audit = AuditTrail()
        record_id = audit.start_action(
            action="test",
            category=ActionCategory.SYSTEM,
            parameters={},
        )

        audit.complete_success(record_id, result={"status": "ok"})

        recent = audit.get_recent(count=1)
        assert len(recent) == 1
        assert recent[0].status == ActionStatus.SUCCESS
        assert recent[0].result == {"status": "ok"}

    def test_complete_failure(self):
        """Complete failure marks action failed."""
        audit = AuditTrail()
        record_id = audit.start_action(
            action="test",
            category=ActionCategory.SYSTEM,
            parameters={},
        )

        audit.complete_failure(record_id, error="Something went wrong")

        recent = audit.get_recent(count=1)
        assert len(recent) == 1
        assert recent[0].status == ActionStatus.FAILED
        assert recent[0].error == "Something went wrong"

    def test_cancel(self):
        """Cancel marks action cancelled."""
        audit = AuditTrail()
        record_id = audit.start_action(
            action="test",
            category=ActionCategory.SYSTEM,
            parameters={},
        )

        audit.cancel(record_id, reason="User cancelled")

        recent = audit.get_recent(count=1)
        assert len(recent) == 1
        assert recent[0].status == ActionStatus.CANCELLED

    def test_duration_tracking(self):
        """Duration is calculated."""
        import time

        audit = AuditTrail()
        record_id = audit.start_action(
            action="test",
            category=ActionCategory.SYSTEM,
            parameters={},
        )

        time.sleep(0.1)  # 100ms delay
        audit.complete_success(record_id)

        recent = audit.get_recent(count=1)
        assert recent[0].duration_ms >= 100

    def test_get_recent_filtering(self):
        """Filter recent by category and status."""
        audit = AuditTrail()

        # Create light action (success)
        light_id = audit.start_action("light", ActionCategory.LIGHT, {})
        audit.complete_success(light_id)

        # Create audio action (failed)
        audio_id = audit.start_action("audio", ActionCategory.AUDIO, {})
        audit.complete_failure(audio_id, error="failed")

        # Filter by category
        light_records = audit.get_recent(category=ActionCategory.LIGHT)
        assert all(r.category == ActionCategory.LIGHT for r in light_records)

        # Filter by status
        failures = audit.get_recent(status=ActionStatus.FAILED)
        assert all(r.status == ActionStatus.FAILED for r in failures)

    def test_get_failures(self):
        """get_failures helper works."""
        audit = AuditTrail()

        # Create some failures
        for i in range(3):
            id_ = audit.start_action(f"test{i}", ActionCategory.SYSTEM, {})
            audit.complete_failure(id_, error=f"error{i}")

        failures = audit.get_failures()
        assert len(failures) == 3

    def test_get_stats(self):
        """Stats tracking works."""
        audit = AuditTrail()

        # Create some actions
        id1 = audit.start_action("test1", ActionCategory.SYSTEM, {})
        audit.complete_success(id1)

        id2 = audit.start_action("test2", ActionCategory.SYSTEM, {})
        audit.complete_failure(id2, error="failed")

        stats = audit.get_stats()
        assert stats["total_actions"] == 2
        assert stats["success_count"] == 1
        assert stats["failure_count"] == 1
        assert stats["success_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_track_context_manager_success(self):
        """Context manager tracks success."""
        audit = AuditTrail()

        async with audit.track("test", ActionCategory.SYSTEM, {}) as ctx:
            ctx.result = {"value": 42}

        recent = audit.get_recent(count=1)
        assert len(recent) == 1
        assert recent[0].status == ActionStatus.SUCCESS
        assert recent[0].result == {"value": 42}

    @pytest.mark.asyncio
    async def test_track_context_manager_failure(self):
        """Context manager tracks failure."""
        audit = AuditTrail()

        with pytest.raises(ValueError):
            async with audit.track("test", ActionCategory.SYSTEM, {}):
                raise ValueError("Test error")

        recent = audit.get_recent(count=1)
        assert len(recent) == 1
        assert recent[0].status == ActionStatus.FAILED
        assert "Test error" in recent[0].error

    def test_max_records(self):
        """Max records limit works."""
        audit = AuditTrail(max_records=10)

        # Create 20 records
        for i in range(20):
            id_ = audit.start_action(f"test{i}", ActionCategory.SYSTEM, {})
            audit.complete_success(id_)

        # Should only have 10
        assert audit.get_stats()["records_in_memory"] == 10


class TestGetAuditTrail:
    """Tests for singleton accessor."""

    def test_returns_singleton(self):
        """Returns same instance."""
        trail1 = get_audit_trail()
        trail2 = get_audit_trail()
        assert trail1 is trail2

    def test_is_audit_trail(self):
        """Returns AuditTrail instance."""
        trail = get_audit_trail()
        assert isinstance(trail, AuditTrail)
