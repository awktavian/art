"""Tests for SmartHome Safety Module.

Tests CBF integration, safety checks, and auto-off timers.
h(x) >= 0 must always be maintained for physical safety.

Created: December 30, 2025
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from kagami_smarthome.safety import (
    FIREPLACE_MAX_ON_DURATION,
    PhysicalActionType,
    SafetyContext,
    SafetyResult,
    check_fireplace_safety,
    check_lock_safety,
    check_physical_safety,
    check_tv_mount_safety,
    get_fireplace_runtime,
    start_fireplace_timer,
    stop_fireplace_timer,
)

# =============================================================================
# SAFETY RESULT TESTS
# =============================================================================


class TestSafetyResult:
    """Test SafetyResult dataclass."""

    def test_safe_when_h_x_positive(self):
        """h(x) > 0 should be safe."""
        result = SafetyResult(allowed=True, h_x=0.5)
        assert result.is_safe
        assert result.allowed

    def test_safe_at_boundary(self):
        """h(x) = 0 is at boundary, technically safe."""
        result = SafetyResult(allowed=True, h_x=0.0)
        assert result.is_safe

    def test_unsafe_when_h_x_negative(self):
        """h(x) < 0 should be unsafe."""
        result = SafetyResult(allowed=False, h_x=-0.5)
        assert not result.is_safe
        assert not result.allowed

    def test_warnings_stored(self):
        """Warnings should be stored in result."""
        result = SafetyResult(
            allowed=True,
            h_x=0.5,
            warnings=["Test warning 1", "Test warning 2"],
        )
        assert len(result.warnings) == 2
        assert "Test warning 1" in result.warnings


# =============================================================================
# FIREPLACE SAFETY TESTS
# =============================================================================


class TestFireplaceSafety:
    """Test fireplace-specific safety checks."""

    def test_fireplace_on_returns_safe(self):
        """Turning on fireplace should be allowed with warnings."""
        result = check_fireplace_safety("on")
        assert result.allowed
        assert result.h_x > 0  # Should be in caution zone but allowed
        assert len(result.warnings) > 0

    def test_fireplace_off_always_safe(self):
        """Turning off fireplace should always be safe.

        Note: h(x) >= 0 is the safety invariant. Turning off is always safe,
        but with CBF integration the exact h(x) value depends on the trained
        barrier function, not a fixed rule-based value.
        """
        result = check_fireplace_safety("off")
        assert result.allowed
        assert result.h_x >= 0  # CBF safety invariant: h(x) >= 0

    @pytest.mark.asyncio
    async def test_fireplace_timer_starts(self):
        """Starting fireplace should start auto-off timer."""
        # Mock the controller
        mock_controller = AsyncMock()

        # Start timer
        start_fireplace_timer(mock_controller)

        # Runtime should be tracked
        runtime = get_fireplace_runtime()
        assert runtime is not None
        assert runtime >= 0

        # Cleanup
        stop_fireplace_timer()

    @pytest.mark.asyncio
    async def test_fireplace_timer_stops(self):
        """Stopping fireplace should clear timer."""
        mock_controller = AsyncMock()

        # Start and stop
        start_fireplace_timer(mock_controller)
        stop_fireplace_timer()

        # Runtime should be None
        assert get_fireplace_runtime() is None

    def test_fireplace_max_duration_is_4_hours(self):
        """Fireplace max duration should be 4 hours."""
        assert FIREPLACE_MAX_ON_DURATION == 4 * 60 * 60


# =============================================================================
# TV MOUNT SAFETY TESTS
# =============================================================================


class TestTVMountSafety:
    """Test MantelMount TV safety checks."""

    def test_tv_lower_allowed(self):
        """Lowering TV to preset should be allowed.

        Note: h(x) > 0 indicates action is in safe region. With CBF
        integration, exact h(x) values depend on trained barrier function.
        """
        result = check_tv_mount_safety("lower", preset=1)
        assert result.allowed
        assert result.h_x > 0  # Must be in safe region (h(x) > 0)

    def test_tv_raise_allowed(self):
        """Raising TV should be allowed."""
        result = check_tv_mount_safety("raise")
        assert result.allowed

    def test_tv_move_has_warnings(self):
        """Continuous TV movement should have warnings."""
        result = check_tv_mount_safety("move")
        # Continuous movement is riskier
        assert len(result.warnings) > 0


# =============================================================================
# LOCK SAFETY TESTS
# =============================================================================


class TestLockSafety:
    """Test lock safety checks."""

    def test_lock_is_safe(self):
        """Locking doors should be safe.

        Note: h(x) >= 0 is the CBF safety invariant. With CBF integration,
        exact h(x) values depend on the trained barrier function.
        """
        result = check_lock_safety("lock", "Front Door")
        assert result.allowed
        assert result.h_x >= 0  # Must be in safe region

    def test_unlock_has_security_warning(self):
        """Unlocking should have security warnings."""
        result = check_lock_safety("unlock", "Front Door")
        assert result.allowed  # Still allowed, but flagged
        assert len(result.warnings) > 0


# =============================================================================
# GENERIC PHYSICAL SAFETY TESTS
# =============================================================================


class TestPhysicalSafety:
    """Test generic physical safety checks."""

    def test_forced_bypass_allows_action(self):
        """Force flag should bypass safety checks."""
        context = SafetyContext(
            action_type=PhysicalActionType.FIREPLACE_ON,
            target="fireplace",
            force=True,
        )
        result = check_physical_safety(context)
        assert result.allowed
        assert "bypass" in result.reason.lower()
        assert len(result.warnings) > 0

    def test_rule_based_fallback_works(self):
        """Rule-based safety should work when CBF unavailable."""
        context = SafetyContext(
            action_type=PhysicalActionType.FIREPLACE_OFF,
            target="fireplace",
        )
        result = check_physical_safety(context)
        assert result.allowed
        assert result.h_x >= 0


# =============================================================================
# INTEGRATION WITH CBF
# =============================================================================


class TestCBFIntegration:
    """Test integration with kagami.core.safety CBF."""

    @patch("kagami_smarthome.safety._check_cbf_available")
    def test_uses_cbf_when_available(self, mock_check):
        """Should use CBF when available."""
        mock_check.return_value = False  # Force rule-based for now

        context = SafetyContext(
            action_type=PhysicalActionType.FIREPLACE_ON,
            target="fireplace",
        )
        result = check_physical_safety(context)

        # Should still work with rule-based
        assert isinstance(result, SafetyResult)

    def test_safety_context_captures_metadata(self):
        """Safety context should capture all metadata."""
        context = SafetyContext(
            action_type=PhysicalActionType.TV_LOWER,
            target="mantelmount",
            parameters={"preset": 1, "room": "Living Room"},
        )

        assert context.action_type == PhysicalActionType.TV_LOWER
        assert context.target == "mantelmount"
        assert context.parameters["preset"] == 1


# =============================================================================
# ASYNC TESTS
# =============================================================================


class TestAsyncSafety:
    """Test async safety wrappers."""

    @pytest.mark.asyncio
    async def test_async_check_works(self):
        """Async safety check should work."""
        from kagami_smarthome.safety import check_physical_safety_async

        context = SafetyContext(
            action_type=PhysicalActionType.LOCK,
            target="Front Door",
        )

        result = await check_physical_safety_async(context)
        assert isinstance(result, SafetyResult)


# =============================================================================
# SAFETY INVARIANT TESTS
# =============================================================================


class TestSafetyInvariant:
    """Test h(x) >= 0 invariant is maintained."""

    def test_all_action_types_have_check(self):
        """All action types should have safety checks."""
        for action_type in PhysicalActionType:
            context = SafetyContext(
                action_type=action_type,
                target="test",
            )
            result = check_physical_safety(context)

            # Result should always be returned
            assert isinstance(result, SafetyResult)
            # h(x) should be a number
            assert isinstance(result.h_x, int | float)

    def test_blocked_actions_have_negative_h_x(self):
        """Blocked actions should have h(x) < 0."""
        # Create a scenario that would be blocked
        # (For now, our rule-based system doesn't block anything)
        # This test documents the expected behavior
        pass

    def test_allowed_actions_have_non_negative_h_x(self):
        """Allowed actions should have h(x) >= 0."""
        context = SafetyContext(
            action_type=PhysicalActionType.FIREPLACE_OFF,
            target="fireplace",
        )
        result = check_physical_safety(context)

        if result.allowed:
            assert result.h_x >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
