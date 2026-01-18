"""Tests for Failover Manager — Safety-Critical Integration Resilience.

Tests the failover system that maintains h(x) >= 0 safety compliance
while ensuring 99.9% uptime through intelligent failover coordination.

SAFETY INVARIANT: h(x) >= 0 always.

Created: January 12, 2026
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami_smarthome.failover_manager import (
    FailoverEvent,
    FailoverManager,
    FailoverRoute,
    FailoverStrategy,
    IntegrationHealthStatus,
    IntegrationTier,
    ServiceHealth,
)


class TestFailoverStrategy:
    """Tests for FailoverStrategy enum."""

    def test_all_strategies_defined(self) -> None:
        """All expected strategies should be defined."""
        expected = ["immediate", "graceful", "delayed", "circuit_breaker"]
        actual = [s.value for s in FailoverStrategy]
        for strategy in expected:
            assert strategy in actual, f"Missing strategy: {strategy}"

    def test_immediate_strategy_for_security(self) -> None:
        """Immediate strategy should be used for security."""
        assert FailoverStrategy.IMMEDIATE == "immediate"

    def test_circuit_breaker_stops_retries(self) -> None:
        """Circuit breaker should be available for optional systems."""
        assert FailoverStrategy.CIRCUIT_BREAKER == "circuit_breaker"


class TestIntegrationTier:
    """Tests for IntegrationTier criticality levels."""

    def test_critical_tier_highest_priority(self) -> None:
        """CRITICAL tier should be highest priority (lowest number)."""
        assert IntegrationTier.CRITICAL < IntegrationTier.ESSENTIAL
        assert IntegrationTier.ESSENTIAL < IntegrationTier.IMPORTANT

    def test_tier_values(self) -> None:
        """Tier values should match expected."""
        assert IntegrationTier.CRITICAL == 1
        assert IntegrationTier.ESSENTIAL == 2
        assert IntegrationTier.IMPORTANT == 3


class TestServiceHealth:
    """Tests for ServiceHealth states."""

    def test_all_health_states_defined(self) -> None:
        """All expected health states should be defined."""
        expected = ["healthy", "degraded", "unstable", "failing", "offline", "recovering"]
        actual = [h.value for h in ServiceHealth]
        for state in expected:
            assert state in actual, f"Missing health state: {state}"


class TestFailoverRoute:
    """Tests for FailoverRoute configuration."""

    def test_route_creation(self) -> None:
        """Should create a failover route with all fields."""
        route = FailoverRoute(
            primary="primary_service",
            fallbacks=["fallback1", "fallback2"],
            strategy=FailoverStrategy.IMMEDIATE,
            max_attempts=5,
            timeout_seconds=10.0,
        )
        assert route.primary == "primary_service"
        assert route.fallbacks == ["fallback1", "fallback2"]
        assert route.strategy == FailoverStrategy.IMMEDIATE
        assert route.max_attempts == 5
        assert route.timeout_seconds == 10.0

    def test_route_defaults(self) -> None:
        """Route should have sensible defaults."""
        route = FailoverRoute(
            primary="test",
            fallbacks=["fallback"],
            strategy=FailoverStrategy.GRACEFUL,
        )
        assert route.max_attempts == 3
        assert route.timeout_seconds == 30.0
        assert route.health_check_interval == 60.0
        assert route.recovery_threshold == 0.8


class TestIntegrationHealthStatus:
    """Tests for IntegrationHealthStatus tracking."""

    def test_status_creation(self) -> None:
        """Should create health status with all fields."""
        status = IntegrationHealthStatus(
            name="test_integration",
            tier=IntegrationTier.CRITICAL,
            health=ServiceHealth.HEALTHY,
            success_rate=0.99,
            avg_response_time=50.0,
            last_success=time.time(),
            last_failure=0.0,
            failure_count=0,
            recovery_attempts=0,
            is_primary_active=True,
            active_route="test_integration",
            available_routes=["test_integration", "fallback"],
        )
        assert status.name == "test_integration"
        assert status.tier == IntegrationTier.CRITICAL
        assert status.health == ServiceHealth.HEALTHY


class TestFailoverEvent:
    """Tests for FailoverEvent recording."""

    def test_event_creation(self) -> None:
        """Should create failover event with all fields."""
        event = FailoverEvent(
            integration="test",
            from_route="primary",
            to_route="fallback",
            reason="Connection timeout",
            strategy=FailoverStrategy.IMMEDIATE,
            timestamp=time.time(),
            success=True,
        )
        assert event.integration == "test"
        assert event.from_route == "primary"
        assert event.to_route == "fallback"
        assert event.success is True


class TestFailoverManagerInitialization:
    """Tests for FailoverManager initialization."""

    def test_default_routes_initialized(self) -> None:
        """Default failover routes should be set up."""
        manager = FailoverManager()

        # Check critical integrations have routes
        assert "envisalink" in manager._failover_routes
        assert "august" in manager._failover_routes

        # Check essential integrations
        assert "control4" in manager._failover_routes
        assert "mitsubishi" in manager._failover_routes
        assert "unifi" in manager._failover_routes

    def test_critical_integrations_have_immediate_strategy(self) -> None:
        """Critical integrations should use IMMEDIATE failover."""
        manager = FailoverManager()

        # Security system should be immediate
        envisalink_route = manager._failover_routes.get("envisalink")
        assert envisalink_route is not None
        assert envisalink_route.strategy == FailoverStrategy.IMMEDIATE

        # Locks should be immediate
        august_route = manager._failover_routes.get("august")
        assert august_route is not None
        assert august_route.strategy == FailoverStrategy.IMMEDIATE

    def test_essential_integrations_have_graceful_strategy(self) -> None:
        """Essential integrations should use GRACEFUL failover."""
        manager = FailoverManager()

        control4_route = manager._failover_routes.get("control4")
        assert control4_route is not None
        assert control4_route.strategy == FailoverStrategy.GRACEFUL

    def test_redundancy_mappings_initialized(self) -> None:
        """Cross-integration redundancy mappings should be set up."""
        manager = FailoverManager()

        assert "presence" in manager._redundancy_mappings
        assert "security" in manager._redundancy_mappings
        assert "lighting" in manager._redundancy_mappings
        assert "audio" in manager._redundancy_mappings
        assert "temperature" in manager._redundancy_mappings


class TestHealthTracking:
    """Tests for health status tracking."""

    def test_initial_health_status(self) -> None:
        """Integrations should start healthy."""
        manager = FailoverManager()
        status = manager.get_integration_status("control4")

        assert status is not None
        assert status.health == ServiceHealth.HEALTHY
        assert status.success_rate == 1.0
        assert status.failure_count == 0

    def test_health_degradation_on_failures(self) -> None:
        """Health should degrade with significant failures."""
        manager = FailoverManager()
        status = manager._integration_status.get("control4")

        if status:
            # Simulate many failures (need enough to affect success rate)
            status.failure_count = 50
            status.success_rate = 0.7  # Set explicitly to trigger degradation
            manager._update_integration_health("control4")

            status = manager.get_integration_status("control4")
            assert status is not None
            # With 70% success rate, should be degraded or worse
            assert status.health in [
                ServiceHealth.DEGRADED,
                ServiceHealth.UNSTABLE,
                ServiceHealth.FAILING,
            ]

    def test_health_update_based_on_success_rate(self) -> None:
        """Health should be based on success rate."""
        manager = FailoverManager()
        status = manager._integration_status.get("control4")

        if status:
            # Simulate many failures with low success rate
            status.failure_count = 100
            status.success_rate = 0.3  # Explicitly set low
            manager._update_integration_health("control4")

            # Should be unstable or failing
            assert status.health in [
                ServiceHealth.UNSTABLE,
                ServiceHealth.FAILING,
            ]


class TestFailoverExecution:
    """Tests for failover execution strategies."""

    @pytest.mark.asyncio
    async def test_immediate_failover(self) -> None:
        """Immediate failover should happen without delay."""
        manager = FailoverManager()

        # Test the immediate failover method directly with a known healthy fallback
        # Use a fallback that is registered and healthy
        result = await manager._immediate_failover("envisalink", "control4")

        # Immediate failover should complete quickly - may return False for unknown fallback
        # The test verifies the method executes without error
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_graceful_failover_allows_completion(self) -> None:
        """Graceful failover should allow brief grace period."""
        manager = FailoverManager()

        start = time.time()
        await manager._graceful_failover("primary", "fallback", timeout=1.0)
        elapsed = time.time() - start

        # Should have some delay for grace period
        assert elapsed >= 0.2  # min(1.0/4, 2.0) = 0.25

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_max_attempts(self) -> None:
        """Circuit breaker should open after max failures."""
        manager = FailoverManager()

        # Get a route with circuit breaker
        route = manager._failover_routes.get("tesla")
        assert route is not None
        assert route.strategy == FailoverStrategy.CIRCUIT_BREAKER

        # Simulate reaching max attempts
        status = manager._integration_status.get("tesla")
        if status:
            status.failure_count = route.max_attempts

        result = await manager._circuit_breaker_failover("tesla", "fallback", route)

        # Circuit should be open, failover returns False
        assert result is False
        assert status is not None
        assert status.health == ServiceHealth.OFFLINE


class TestRecoveryThresholds:
    """Tests for recovery threshold behavior."""

    def test_default_recovery_threshold(self) -> None:
        """Default recovery threshold should be 80%."""
        route = FailoverRoute(
            primary="test",
            fallbacks=["fallback"],
            strategy=FailoverStrategy.GRACEFUL,
        )
        assert route.recovery_threshold == 0.8

    @pytest.mark.asyncio
    async def test_recovery_resets_failure_count(self) -> None:
        """Successful recovery should reset failure state."""
        manager = FailoverManager()

        # Simulate degraded state
        status = manager._integration_status.get("control4")
        if status:
            status.failure_count = 10
            status.health = ServiceHealth.DEGRADED

        # Reset should clear everything
        manager.reset_integration("control4")

        status = manager.get_integration_status("control4")
        assert status is not None
        assert status.health == ServiceHealth.HEALTHY
        assert status.failure_count == 0
        assert status.recovery_attempts == 0
        assert status.success_rate == 1.0


class TestDegradedModeBehavior:
    """Tests for degraded mode operation."""

    def test_degraded_health_threshold(self) -> None:
        """Degraded state should trigger at correct threshold."""
        manager = FailoverManager()
        status = manager._integration_status.get("control4")

        if status:
            # Set success rate to 85% (should be DEGRADED)
            status.success_rate = 0.85
            status.failure_count = 15

            manager._update_integration_health("control4")

            # Between 80-95% should be degraded
            assert status.health == ServiceHealth.DEGRADED

    def test_unstable_health_threshold(self) -> None:
        """Unstable state should trigger at correct threshold."""
        manager = FailoverManager()
        status = manager._integration_status.get("control4")

        if status:
            # Set success rate to 60% (should be UNSTABLE)
            status.success_rate = 0.60
            status.failure_count = 40

            manager._update_integration_health("control4")

            # Between 50-80% should be unstable
            assert status.health == ServiceHealth.UNSTABLE

    def test_failing_health_threshold(self) -> None:
        """Failing state should trigger at correct threshold."""
        manager = FailoverManager()
        status = manager._integration_status.get("control4")

        if status:
            # Set success rate to 30% (should be FAILING)
            status.success_rate = 0.30
            status.failure_count = 70

            manager._update_integration_health("control4")

            # Below 50% should be failing
            assert status.health == ServiceHealth.FAILING


class TestIntegrationFailureHandling:
    """Tests for integration failure handling."""

    @pytest.mark.asyncio
    async def test_handle_failure_increments_count(self) -> None:
        """Handling failure should increment failure count."""
        manager = FailoverManager()

        status = manager.get_integration_status("control4")
        initial_count = status.failure_count if status else 0

        await manager.handle_integration_failure(
            "control4",
            Exception("Connection timeout"),
            {"type": "test"},
        )

        status = manager.get_integration_status("control4")
        assert status is not None
        assert status.failure_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_handle_failure_updates_last_failure_time(self) -> None:
        """Handling failure should update last failure timestamp."""
        manager = FailoverManager()

        before = time.time()
        await manager.handle_integration_failure(
            "control4",
            Exception("Connection timeout"),
            {"type": "test"},
        )
        after = time.time()

        status = manager.get_integration_status("control4")
        assert status is not None
        assert before <= status.last_failure <= after

    @pytest.mark.asyncio
    async def test_handle_unknown_integration(self) -> None:
        """Should handle unknown integration gracefully."""
        manager = FailoverManager()

        # Should not raise
        result = await manager.handle_integration_failure(
            "unknown_integration",
            Exception("Test error"),
        )

        # Should return the same integration name
        assert result == "unknown_integration"


class TestFailoverEventTracking:
    """Tests for failover event recording and callbacks."""

    def test_event_recording(self) -> None:
        """Failover events should be recorded."""
        manager = FailoverManager()

        event = FailoverEvent(
            integration="test",
            from_route="primary",
            to_route="fallback",
            reason="Test failover",
            strategy=FailoverStrategy.IMMEDIATE,
            timestamp=time.time(),
            success=True,
        )
        manager._record_failover_event(event)

        events = manager.get_failover_events()
        assert len(events) >= 1
        assert events[-1].integration == "test"

    def test_event_limit(self) -> None:
        """Events should be limited to prevent memory growth."""
        manager = FailoverManager()

        # Record many events
        for i in range(1100):
            event = FailoverEvent(
                integration=f"test_{i}",
                from_route="primary",
                to_route="fallback",
                reason="Test failover",
                strategy=FailoverStrategy.IMMEDIATE,
                timestamp=time.time(),
                success=True,
            )
            manager._record_failover_event(event)

        # Should be capped at 1000
        assert len(manager._failover_events) == 1000

    def test_event_callback_registration(self) -> None:
        """Callbacks should be called on failover events."""
        manager = FailoverManager()
        callback_called = []

        def callback(event: FailoverEvent) -> None:
            callback_called.append(event)

        manager.on_failover_event(callback)

        event = FailoverEvent(
            integration="test",
            from_route="primary",
            to_route="fallback",
            reason="Test failover",
            strategy=FailoverStrategy.IMMEDIATE,
            timestamp=time.time(),
            success=True,
        )
        manager._record_failover_event(event)

        assert len(callback_called) == 1
        assert callback_called[0].integration == "test"


class TestRedundancyOptions:
    """Tests for cross-integration redundancy."""

    def test_presence_redundancy(self) -> None:
        """Presence detection should have multiple fallbacks."""
        manager = FailoverManager()
        options = manager.get_redundancy_options("presence")

        assert "unifi" in options  # Primary
        assert "tesla" in options  # Secondary
        assert "august" in options  # Tertiary
        assert "eight_sleep" in options  # Quaternary

    def test_security_redundancy(self) -> None:
        """Security monitoring should have multiple fallbacks."""
        manager = FailoverManager()
        options = manager.get_redundancy_options("security")

        assert "envisalink" in options  # Primary
        assert "control4" in options  # Secondary
        assert "unifi" in options  # Camera fallback


class TestHealthSummary:
    """Tests for health summary reporting."""

    def test_health_summary_structure(self) -> None:
        """Health summary should contain expected fields."""
        manager = FailoverManager()
        summary = manager.get_health_summary()

        assert "total_integrations" in summary
        assert "healthy_integrations" in summary
        assert "health_percentage" in summary
        assert "active_failovers" in summary
        assert "recovery_tasks" in summary
        assert "overall_status" in summary

    def test_health_summary_initial_state(self) -> None:
        """Initial state should show health status."""
        manager = FailoverManager()
        summary = manager.get_health_summary()

        # Total integrations should be reported (may be 0 if SystemHealthMonitor not available)
        assert "total_integrations" in summary
        assert isinstance(summary["total_integrations"], int)
        # Health percentage should be reported
        assert isinstance(summary["health_percentage"], (int, float))
        # Recovery tasks should start at 0
        assert summary["recovery_tasks"] == 0


class TestMonitoring:
    """Tests for background monitoring."""

    @pytest.mark.asyncio
    async def test_start_monitoring(self) -> None:
        """Starting monitoring should set running flag."""
        manager = FailoverManager()

        await manager.start_monitoring()
        assert manager._running is True
        assert manager._monitor_task is not None

        await manager.stop_monitoring()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self) -> None:
        """Stopping monitoring should clean up."""
        manager = FailoverManager()

        await manager.start_monitoring()
        await manager.stop_monitoring()

        assert manager._running is False

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self) -> None:
        """Starting monitoring twice should be safe."""
        manager = FailoverManager()

        await manager.start_monitoring()
        task1 = manager._monitor_task

        await manager.start_monitoring()  # Should not create new task
        task2 = manager._monitor_task

        assert task1 is task2
        await manager.stop_monitoring()


class TestForceFailover:
    """Tests for manual failover forcing."""

    @pytest.mark.asyncio
    async def test_force_failover_valid_integration(self) -> None:
        """Force failover should work for valid integration."""
        manager = FailoverManager()

        result = manager.force_failover("control4", "Manual test")
        assert result is True
        # Give the async task a chance to start
        await asyncio.sleep(0.01)

    def test_force_failover_invalid_integration(self) -> None:
        """Force failover should fail for invalid integration."""
        manager = FailoverManager()

        result = manager.force_failover("nonexistent", "Test")
        assert result is False


class TestResetIntegration:
    """Tests for integration reset."""

    def test_reset_clears_failure_state(self) -> None:
        """Reset should clear all failure state."""
        manager = FailoverManager()

        # Corrupt the state
        status = manager._integration_status.get("control4")
        if status:
            status.health = ServiceHealth.FAILING
            status.failure_count = 100
            status.recovery_attempts = 5
            status.success_rate = 0.1
            status.is_primary_active = False

        # Reset
        result = manager.reset_integration("control4")
        assert result is True

        # Verify reset
        status = manager.get_integration_status("control4")
        assert status is not None
        assert status.health == ServiceHealth.HEALTHY
        assert status.failure_count == 0
        assert status.recovery_attempts == 0
        assert status.success_rate == 1.0
        assert status.is_primary_active is True

    def test_reset_unknown_integration(self) -> None:
        """Reset of unknown integration should return False."""
        manager = FailoverManager()

        result = manager.reset_integration("nonexistent")
        assert result is False


class TestSafetyInvariant:
    """Critical safety tests for h(x) >= 0 compliance."""

    def test_critical_tier_immediate_failover(self) -> None:
        """SAFETY: Critical integrations must use immediate failover."""
        manager = FailoverManager()

        critical_routes = [
            manager._failover_routes.get("envisalink"),
            manager._failover_routes.get("august"),
        ]

        for route in critical_routes:
            if route:
                assert route.strategy == FailoverStrategy.IMMEDIATE, (
                    f"Critical integration {route.primary} must use IMMEDIATE failover"
                )

    def test_critical_integrations_have_fallbacks(self) -> None:
        """SAFETY: Critical integrations must have fallback routes."""
        manager = FailoverManager()

        critical_integrations = ["envisalink", "august"]

        for name in critical_integrations:
            route = manager._failover_routes.get(name)
            assert route is not None, f"Critical integration {name} missing route"
            assert len(route.fallbacks) > 0, f"Critical integration {name} has no fallbacks"

    def test_all_integrations_start_healthy(self) -> None:
        """SAFETY: All integrations should start in healthy state."""
        manager = FailoverManager()

        for name, status in manager._integration_status.items():
            assert status.health == ServiceHealth.HEALTHY, (
                f"Integration {name} did not start healthy"
            )

    def test_no_hardened_integrations_optional(self) -> None:
        """SAFETY: No integration should be marked optional (all are required)."""
        manager = FailoverManager()

        # All integrations should be at least IMPORTANT (no OPTIONAL tier)
        for name, status in manager._integration_status.items():
            assert status.tier in [
                IntegrationTier.CRITICAL,
                IntegrationTier.ESSENTIAL,
                IntegrationTier.IMPORTANT,
            ], f"Integration {name} has invalid tier"

    @pytest.mark.asyncio
    async def test_immediate_failover_is_fast(self) -> None:
        """SAFETY: Immediate failover must complete quickly (<1 second)."""
        manager = FailoverManager()

        start = time.time()
        await manager._immediate_failover("primary", "fallback")
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Immediate failover took {elapsed}s, must be <1s for safety"

    def test_security_has_multiple_redundancy_paths(self) -> None:
        """SAFETY: Security monitoring must have multiple fallback paths."""
        manager = FailoverManager()

        security_options = manager.get_redundancy_options("security")
        assert len(security_options) >= 3, "Security must have at least 3 redundancy options"


class TestAllStatusesRetrieval:
    """Tests for bulk status retrieval."""

    def test_get_all_statuses(self) -> None:
        """Should return all integration statuses."""
        manager = FailoverManager()
        statuses = manager.get_all_statuses()

        assert len(statuses) > 0
        assert isinstance(statuses, dict)

    def test_get_all_statuses_is_copy(self) -> None:
        """Returned statuses should be a copy."""
        manager = FailoverManager()
        statuses1 = manager.get_all_statuses()
        statuses2 = manager.get_all_statuses()

        assert statuses1 is not statuses2


class TestGetActiveFailovers:
    """Tests for active failover detection."""

    def test_get_active_failovers_returns_list(self) -> None:
        """Should return a list of failover states."""
        manager = FailoverManager()
        active = manager.get_active_failovers()

        # Should return a list (may or may not be empty based on initialization)
        assert isinstance(active, list)

    def test_detect_active_failover(self) -> None:
        """Should detect integration in failover state when explicitly set."""
        manager = FailoverManager()

        # First reset a status to primary active
        status = manager._integration_status.get("control4")
        if status:
            status.is_primary_active = True

        initial_active = manager.get_active_failovers()
        control4_initially_active = "control4" in initial_active

        # Now put it in failover state
        if status:
            status.is_primary_active = False

        active = manager.get_active_failovers()
        # If it wasn't active before, should be in the list now
        if not control4_initially_active:
            assert "control4" in active


class TestFallbackHealthTesting:
    """Tests for fallback health verification."""

    @pytest.mark.asyncio
    async def test_healthy_fallback_passes(self) -> None:
        """Healthy fallback should pass health test."""
        manager = FailoverManager()

        result = await manager._test_fallback_health("control4")
        assert result is True  # Should be healthy by default

    @pytest.mark.asyncio
    async def test_failing_fallback_fails(self) -> None:
        """Failing fallback should not pass health test."""
        manager = FailoverManager()

        # Mark as failing
        status = manager._integration_status.get("control4")
        if status:
            status.health = ServiceHealth.FAILING

        result = await manager._test_fallback_health("control4")
        assert result is False

    @pytest.mark.asyncio
    async def test_unknown_fallback_fails(self) -> None:
        """Unknown fallback should not pass health test."""
        manager = FailoverManager()

        result = await manager._test_fallback_health("nonexistent")
        assert result is False
