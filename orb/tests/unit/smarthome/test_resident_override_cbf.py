"""Tests for Resident Override CBF — Safety-Critical h(x) >= 0 Enforcement.

Tests the Control Barrier Function that protects manual device changes from
being overridden by automation before the cooldown period expires.

SAFETY INVARIANT: h(x) >= 0 always.

Created: January 12, 2026
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from kagami_smarthome.resident_override_cbf import (
    DeviceType,
    ManualChangeRecord,
    ResidentOverrideCBF,
    get_resident_override_cbf,
    reset_resident_override_cbf,
)


class TestDeviceType:
    """Tests for DeviceType enum."""

    def test_all_device_types_defined(self) -> None:
        """All expected device types should be defined."""
        expected_types = ["light", "shade", "lock", "thermostat", "tv", "fireplace"]
        actual_types = [dt.value for dt in DeviceType]
        for expected in expected_types:
            assert expected in actual_types, f"Missing device type: {expected}"

    def test_device_type_string_enum(self) -> None:
        """Device types should be string enums."""
        assert DeviceType.LIGHT == "light"
        assert DeviceType.SHADE == "shade"
        assert DeviceType.LOCK == "lock"
        assert DeviceType.THERMOSTAT == "thermostat"
        assert DeviceType.TV == "tv"
        assert DeviceType.FIREPLACE == "fireplace"


class TestManualChangeRecord:
    """Tests for ManualChangeRecord dataclass."""

    def test_record_creation(self) -> None:
        """Should create a record with all fields."""
        record = ManualChangeRecord(
            device_id=100,
            device_type=DeviceType.LIGHT,
            old_value=50,
            new_value=100,
        )
        assert record.device_id == 100
        assert record.device_type == DeviceType.LIGHT
        assert record.old_value == 50
        assert record.new_value == 100
        assert record.source == "manual"
        assert record.timestamp > 0

    def test_record_default_timestamp(self) -> None:
        """Record should have timestamp near now by default."""
        before = time.time()
        record = ManualChangeRecord(
            device_id=1,
            device_type=DeviceType.SHADE,
            old_value=0,
            new_value=100,
        )
        after = time.time()
        assert before <= record.timestamp <= after

    def test_record_custom_source(self) -> None:
        """Record should accept custom source."""
        record = ManualChangeRecord(
            device_id=1,
            device_type=DeviceType.LIGHT,
            old_value=0,
            new_value=50,
            source="wall_switch",
        )
        assert record.source == "wall_switch"


class TestResidentOverrideCBFCooldowns:
    """Tests for cooldown period enforcement."""

    def test_default_cooldowns(self) -> None:
        """Default cooldowns should match documented values."""
        cbf = ResidentOverrideCBF()
        # 1-4 hours by device type
        assert cbf._cooldowns[DeviceType.LIGHT] == 3600  # 1 hour
        assert cbf._cooldowns[DeviceType.SHADE] == 7200  # 2 hours
        assert cbf._cooldowns[DeviceType.LOCK] == 14400  # 4 hours (security)
        assert cbf._cooldowns[DeviceType.THERMOSTAT] == 7200  # 2 hours
        assert cbf._cooldowns[DeviceType.TV] == 1800  # 30 minutes
        assert cbf._cooldowns[DeviceType.FIREPLACE] == 3600  # 1 hour

    def test_custom_global_cooldown(self) -> None:
        """Single cooldown value should apply to all types."""
        cbf = ResidentOverrideCBF(cooldown_seconds=900)  # 15 minutes
        for device_type in DeviceType:
            assert cbf._cooldowns[device_type] == 900

    def test_custom_per_type_cooldowns(self) -> None:
        """Per-type cooldowns should override defaults."""
        cbf = ResidentOverrideCBF(
            cooldowns_by_type={
                DeviceType.LIGHT: 600,
                DeviceType.LOCK: 28800,  # 8 hours
            }
        )
        assert cbf._cooldowns[DeviceType.LIGHT] == 600
        assert cbf._cooldowns[DeviceType.LOCK] == 28800
        # Others should remain default
        assert cbf._cooldowns[DeviceType.SHADE] == 7200

    def test_lock_has_longest_cooldown(self) -> None:
        """Lock should have longest cooldown for security."""
        cbf = ResidentOverrideCBF()
        max_cooldown = max(cbf._cooldowns.values())
        assert cbf._cooldowns[DeviceType.LOCK] == max_cooldown


class TestManualOverrideDetection:
    """Tests for manual override detection."""

    def test_record_manual_change(self) -> None:
        """Should record a manual change."""
        cbf = ResidentOverrideCBF()
        cbf.record_manual_change(
            device_id=100,
            device_type=DeviceType.LIGHT,
            old_value=0,
            new_value=75,
        )
        assert (100, DeviceType.LIGHT) in cbf._manual_changes

    def test_multiple_manual_changes(self) -> None:
        """Should track multiple device changes."""
        cbf = ResidentOverrideCBF()
        cbf.record_manual_change(100, DeviceType.LIGHT)
        cbf.record_manual_change(200, DeviceType.SHADE)
        cbf.record_manual_change(300, DeviceType.LOCK)

        assert len(cbf._manual_changes) == 3
        assert (100, DeviceType.LIGHT) in cbf._manual_changes
        assert (200, DeviceType.SHADE) in cbf._manual_changes
        assert (300, DeviceType.LOCK) in cbf._manual_changes

    def test_same_device_overwrites_record(self) -> None:
        """Multiple changes to same device should update timestamp."""
        cbf = ResidentOverrideCBF()

        # First change
        cbf.record_manual_change(100, DeviceType.LIGHT, new_value=50)
        first_record = cbf._manual_changes[(100, DeviceType.LIGHT)]

        # Brief delay then second change
        time.sleep(0.01)
        cbf.record_manual_change(100, DeviceType.LIGHT, new_value=75)
        second_record = cbf._manual_changes[(100, DeviceType.LIGHT)]

        assert second_record.timestamp > first_record.timestamp
        assert second_record.new_value == 75

    def test_stats_track_manual_changes(self) -> None:
        """Stats should count manual changes."""
        cbf = ResidentOverrideCBF()
        assert cbf._stats["manual_changes_recorded"] == 0

        cbf.record_manual_change(100, DeviceType.LIGHT)
        assert cbf._stats["manual_changes_recorded"] == 1

        cbf.record_manual_change(200, DeviceType.SHADE)
        assert cbf._stats["manual_changes_recorded"] == 2


class TestBarrierValueCalculation:
    """Tests for h(x) barrier value calculation."""

    def test_no_manual_change_returns_infinity(self) -> None:
        """No recorded change means always safe (h=inf)."""
        cbf = ResidentOverrideCBF()
        h = cbf.barrier_value(100, DeviceType.LIGHT)
        assert h == float("inf")

    def test_h_x_negative_during_cooldown(self) -> None:
        """h(x) should be negative during cooldown period."""
        cbf = ResidentOverrideCBF(cooldown_seconds=100)

        # Record manual change
        cbf.record_manual_change(100, DeviceType.LIGHT)

        # Immediately after, h(x) should be negative
        h = cbf.barrier_value(100, DeviceType.LIGHT)
        assert h < 0, "h(x) should be negative during cooldown"
        # h(x) = time_since_change - cooldown ≈ 0 - 100 = -100
        assert h <= -99  # Allow small timing variance

    def test_h_x_positive_after_cooldown(self) -> None:
        """h(x) should be positive after cooldown expires."""
        cbf = ResidentOverrideCBF(cooldown_seconds=0.01)  # Very short cooldown

        cbf.record_manual_change(100, DeviceType.LIGHT)

        # Wait for cooldown
        time.sleep(0.02)

        h = cbf.barrier_value(100, DeviceType.LIGHT)
        assert h >= 0, "h(x) should be >= 0 after cooldown"

    def test_h_x_formula_correct(self) -> None:
        """h(x) = time_since_change - cooldown."""
        cooldown = 100
        cbf = ResidentOverrideCBF(cooldown_seconds=cooldown)

        # Record change and manually set timestamp
        cbf.record_manual_change(100, DeviceType.LIGHT)
        record = cbf._manual_changes[(100, DeviceType.LIGHT)]
        base_time = record.timestamp

        # Check barrier value at a known later time (50 seconds later)
        with patch("time.time", return_value=base_time + 50):
            h = cbf.barrier_value(100, DeviceType.LIGHT)
            # h(x) = 50 - 100 = -50
            assert h == -50, f"Expected h(x) = -50, got {h}"

    def test_barrier_value_per_device_type(self) -> None:
        """Different device types should have different cooldowns."""
        cbf = ResidentOverrideCBF()

        # Record changes
        cbf.record_manual_change(100, DeviceType.TV)  # 30 min cooldown
        cbf.record_manual_change(200, DeviceType.LOCK)  # 4 hour cooldown

        # Get actual timestamps
        tv_record = cbf._manual_changes[(100, DeviceType.TV)]
        lock_record = cbf._manual_changes[(200, DeviceType.LOCK)]
        base_time = tv_record.timestamp

        # Check 1 hour later
        check_time = base_time + 3600
        with patch("time.time", return_value=check_time):
            h_tv = cbf.barrier_value(100, DeviceType.TV)
            h_lock = cbf.barrier_value(200, DeviceType.LOCK)

            # TV: 3600 - 1800 = 1800 (positive, allowed)
            assert h_tv > 0, "TV should be safe after 1 hour"
            # Lock: 3600 - 14400 = -10800 (negative, blocked)
            assert h_lock < 0, "Lock should still be blocked after 1 hour"


class TestAutomationBlocking:
    """Tests for automation blocking when h(x) < 0."""

    def test_automation_blocked_during_cooldown(self) -> None:
        """Automation should be blocked when h(x) < 0."""
        cbf = ResidentOverrideCBF(cooldown_seconds=100)
        cbf.record_manual_change(100, DeviceType.LIGHT)

        allowed = cbf.is_automation_allowed(100, DeviceType.LIGHT)
        assert allowed is False, "Automation should be BLOCKED during cooldown"

    def test_automation_allowed_after_cooldown(self) -> None:
        """Automation should be allowed when h(x) >= 0."""
        cbf = ResidentOverrideCBF(cooldown_seconds=0.01)
        cbf.record_manual_change(100, DeviceType.LIGHT)

        time.sleep(0.02)

        allowed = cbf.is_automation_allowed(100, DeviceType.LIGHT)
        assert allowed is True, "Automation should be ALLOWED after cooldown"

    def test_automation_allowed_no_manual_change(self) -> None:
        """Automation should be allowed when no manual change recorded."""
        cbf = ResidentOverrideCBF()
        allowed = cbf.is_automation_allowed(100, DeviceType.LIGHT)
        assert allowed is True, "Automation should be allowed for untracked devices"

    def test_automation_tracking_stats(self) -> None:
        """Stats should track allowed/blocked automation attempts."""
        cbf = ResidentOverrideCBF(cooldown_seconds=0.01)

        # First: no change recorded, should allow
        cbf.is_automation_allowed(100, DeviceType.LIGHT)
        assert cbf._stats["automation_allowed"] == 1
        assert cbf._stats["automation_blocked"] == 0

        # Second: record change, should block
        cbf.record_manual_change(100, DeviceType.LIGHT)
        cbf.is_automation_allowed(100, DeviceType.LIGHT)
        assert cbf._stats["automation_blocked"] == 1

        # Third: wait for cooldown, should allow again
        time.sleep(0.02)
        cbf.is_automation_allowed(100, DeviceType.LIGHT)
        assert cbf._stats["automation_allowed"] == 2

    def test_record_automation_change_clears_override(self) -> None:
        """Recording automation change should clear manual override."""
        cbf = ResidentOverrideCBF(cooldown_seconds=100)
        cbf.record_manual_change(100, DeviceType.LIGHT)

        # Should be blocked
        assert not cbf.is_automation_allowed(100, DeviceType.LIGHT)

        # Record automation change (e.g., automation successfully applied)
        cbf.record_automation_change(100, DeviceType.LIGHT)

        # Should now be allowed
        assert cbf.is_automation_allowed(100, DeviceType.LIGHT)


class TestCooldownRemaining:
    """Tests for cooldown remaining calculation."""

    def test_cooldown_remaining_during_cooldown(self) -> None:
        """Should return remaining seconds during cooldown."""
        cbf = ResidentOverrideCBF(cooldown_seconds=100)

        cbf.record_manual_change(100, DeviceType.LIGHT)
        record = cbf._manual_changes[(100, DeviceType.LIGHT)]
        base_time = record.timestamp

        # 30 seconds later
        with patch("time.time", return_value=base_time + 30):
            remaining = cbf.get_cooldown_remaining(100, DeviceType.LIGHT)
            assert remaining == 70, "Should have 70 seconds remaining"

    def test_cooldown_remaining_after_cooldown(self) -> None:
        """Should return 0 after cooldown expires."""
        cbf = ResidentOverrideCBF(cooldown_seconds=0.01)
        cbf.record_manual_change(100, DeviceType.LIGHT)

        time.sleep(0.02)

        remaining = cbf.get_cooldown_remaining(100, DeviceType.LIGHT)
        assert remaining == 0.0

    def test_cooldown_remaining_no_change(self) -> None:
        """Should return None for untracked device."""
        cbf = ResidentOverrideCBF()
        remaining = cbf.get_cooldown_remaining(100, DeviceType.LIGHT)
        assert remaining is None


class TestOverrideManagement:
    """Tests for override clearing and management."""

    def test_clear_override(self) -> None:
        """Should clear a specific override."""
        cbf = ResidentOverrideCBF(cooldown_seconds=100)
        cbf.record_manual_change(100, DeviceType.LIGHT)
        cbf.record_manual_change(200, DeviceType.SHADE)

        result = cbf.clear_override(100, DeviceType.LIGHT)

        assert result is True
        assert (100, DeviceType.LIGHT) not in cbf._manual_changes
        assert (200, DeviceType.SHADE) in cbf._manual_changes

    def test_clear_override_returns_false_for_nonexistent(self) -> None:
        """Should return False for non-existent override."""
        cbf = ResidentOverrideCBF()
        result = cbf.clear_override(100, DeviceType.LIGHT)
        assert result is False

    def test_clear_all_overrides(self) -> None:
        """Should clear all overrides."""
        cbf = ResidentOverrideCBF(cooldown_seconds=100)
        cbf.record_manual_change(100, DeviceType.LIGHT)
        cbf.record_manual_change(200, DeviceType.SHADE)
        cbf.record_manual_change(300, DeviceType.LOCK)

        count = cbf.clear_all_overrides()

        assert count == 3
        assert len(cbf._manual_changes) == 0

    def test_get_active_overrides(self) -> None:
        """Should return list of active overrides."""
        cbf = ResidentOverrideCBF(cooldown_seconds=100)
        cbf.record_manual_change(100, DeviceType.LIGHT, new_value=75)

        overrides = cbf.get_active_overrides()

        assert len(overrides) == 1
        assert overrides[0]["device_id"] == 100
        assert overrides[0]["device_type"] == "light"
        assert overrides[0]["new_value"] == 75
        assert overrides[0]["cooldown_remaining"] > 0
        assert overrides[0]["h_x"] < 0

    def test_get_active_overrides_excludes_expired(self) -> None:
        """Expired overrides should not be returned."""
        cbf = ResidentOverrideCBF(cooldown_seconds=0.01)
        cbf.record_manual_change(100, DeviceType.LIGHT)

        time.sleep(0.02)

        overrides = cbf.get_active_overrides()
        assert len(overrides) == 0


class TestCleanup:
    """Tests for expired record cleanup."""

    def test_cleanup_expired_removes_old_records(self) -> None:
        """Cleanup should remove expired records."""
        cbf = ResidentOverrideCBF(cooldown_seconds=0.01)
        cbf.record_manual_change(100, DeviceType.LIGHT)

        time.sleep(0.02)

        removed = cbf.cleanup_expired()
        assert removed == 1
        assert len(cbf._manual_changes) == 0

    def test_cleanup_preserves_active_records(self) -> None:
        """Cleanup should preserve non-expired records."""
        cbf = ResidentOverrideCBF(cooldown_seconds=100)
        cbf.record_manual_change(100, DeviceType.LIGHT)

        removed = cbf.cleanup_expired()
        assert removed == 0
        assert len(cbf._manual_changes) == 1


class TestSingleton:
    """Tests for singleton pattern."""

    def setup_method(self) -> None:
        """Reset singleton before each test."""
        reset_resident_override_cbf()

    def test_get_singleton(self) -> None:
        """Should return singleton instance."""
        cbf1 = get_resident_override_cbf()
        cbf2 = get_resident_override_cbf()
        assert cbf1 is cbf2

    def test_reset_singleton(self) -> None:
        """Reset should clear singleton."""
        cbf1 = get_resident_override_cbf()
        cbf1.record_manual_change(100, DeviceType.LIGHT)

        reset_resident_override_cbf()

        cbf2 = get_resident_override_cbf()
        assert cbf2 is not cbf1
        assert len(cbf2._manual_changes) == 0


class TestSafetyInvariant:
    """Critical tests verifying h(x) >= 0 safety invariant."""

    def test_h_x_never_allows_automation_during_cooldown(self) -> None:
        """SAFETY: h(x) < 0 must ALWAYS block automation."""
        cbf = ResidentOverrideCBF(cooldown_seconds=100)

        # Record manual change
        cbf.record_manual_change(100, DeviceType.LOCK)

        # Check multiple times during cooldown
        for _ in range(5):
            h = cbf.barrier_value(100, DeviceType.LOCK)
            allowed = cbf.is_automation_allowed(100, DeviceType.LOCK)

            if h < 0:
                assert allowed is False, "h(x) < 0 MUST block automation"
            else:
                assert allowed is True, "h(x) >= 0 MUST allow automation"

    def test_security_device_longest_protection(self) -> None:
        """SAFETY: Security devices (locks) should have longest cooldown."""
        cbf = ResidentOverrideCBF()

        cbf.record_manual_change(100, DeviceType.LOCK)
        cbf.record_manual_change(200, DeviceType.LIGHT)

        lock_record = cbf._manual_changes[(100, DeviceType.LOCK)]
        base_time = lock_record.timestamp

        # Check at 2 hours (light cooldown passed, lock still protected)
        check_time = base_time + 7200  # 2 hours
        with patch("time.time", return_value=check_time):
            light_allowed = cbf.is_automation_allowed(200, DeviceType.LIGHT)
            lock_allowed = cbf.is_automation_allowed(100, DeviceType.LOCK)

            assert light_allowed is True, "Light should be allowed after 2 hours"
            assert lock_allowed is False, "Lock should still be protected after 2 hours"

    def test_barrier_value_math_correctness(self) -> None:
        """SAFETY: h(x) = time_since_change - cooldown must be correct."""
        cooldown = 3600
        cbf = ResidentOverrideCBF(cooldown_seconds=cooldown)

        cbf.record_manual_change(100, DeviceType.LIGHT)
        record = cbf._manual_changes[(100, DeviceType.LIGHT)]
        start_time = record.timestamp

        test_cases = [
            (start_time + 0, -3600),  # Immediate: 0 - 3600 = -3600
            (start_time + 1800, -1800),  # 30 min: 1800 - 3600 = -1800
            (start_time + 3600, 0),  # 1 hour: 3600 - 3600 = 0
            (start_time + 7200, 3600),  # 2 hours: 7200 - 3600 = 3600
        ]

        for check_time, expected_h in test_cases:
            with patch("time.time", return_value=check_time):
                actual_h = cbf.barrier_value(100, DeviceType.LIGHT)
                assert actual_h == expected_h, (
                    f"At t={check_time - start_time}s, expected h(x)={expected_h}, got {actual_h}"
                )


class TestGetStats:
    """Tests for statistics reporting."""

    def test_get_stats_returns_all_metrics(self) -> None:
        """Stats should include all tracked metrics."""
        cbf = ResidentOverrideCBF()

        # Perform some operations
        cbf.record_manual_change(100, DeviceType.LIGHT)
        cbf.is_automation_allowed(100, DeviceType.LIGHT)
        cbf.is_automation_allowed(200, DeviceType.SHADE)

        stats = cbf.get_stats()

        assert "manual_changes_recorded" in stats
        assert "automation_blocked" in stats
        assert "automation_allowed" in stats
        assert "active_overrides" in stats
        assert "cooldowns" in stats

        assert stats["manual_changes_recorded"] == 1
        assert stats["automation_blocked"] == 1
        assert stats["automation_allowed"] == 1
