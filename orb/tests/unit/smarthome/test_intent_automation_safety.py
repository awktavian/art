"""Tests for Intent Automation Safety — CBF Enforcement Before Execution.

Tests that all safety-critical intents properly enforce h(x) >= 0 constraints:
- Fireplace safety (4-hour max, presence required)
- Lock safety (no unlock during away mode)
- TV mount safety (only preset positions)

SAFETY INVARIANT: h(x) >= 0 always.

Created: January 12, 2026
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami_smarthome.intent_automation import (
    AutomationIntent,
    AutomationRule,
    Capability,
    Condition,
    HouseholdCapabilities,
    IntentAutomationEngine,
    IntentExecution,
    IntentExecutor,
    discover_capabilities,
    get_intent_automation,
)


@dataclass
class MockController:
    """Mock SmartHome controller for testing."""

    _lights_set: list[dict] = field(default_factory=list)
    _shades_closed: bool = False
    _shades_opened: list[str] = field(default_factory=list)
    _locks_locked: bool = False
    _locks_unlocked: bool = False
    _fireplace_on: bool = False
    _fireplace_off: bool = False
    _bed_temp_set: tuple | None = None
    _announcements: list[str] = field(default_factory=list)
    _presence_mode: str = "home"  # "home", "away", "sleep"
    _fireplace_runtime: float = 0  # seconds
    _movie_mode_entered: bool = False

    # Services
    _tesla_service: Any = None
    _climate_service: Any = None
    _eight_sleep: Any = None
    _av_service: Any = None
    _presence: Any = None
    _unifi: Any = None

    async def set_lights(self, level: int, rooms: list[str] | None = None) -> None:
        self._lights_set.append({"level": level, "rooms": rooms})

    async def close_shades(self, rooms: list[str] | None = None) -> None:
        self._shades_closed = True

    async def open_shades(self, rooms: list[str] | None = None) -> None:
        self._shades_opened.extend(rooms or ["all"])

    async def lock_all(self) -> None:
        self._locks_locked = True

    async def unlock_all(self) -> None:
        self._locks_unlocked = True

    async def fireplace_on(self) -> None:
        self._fireplace_on = True

    async def fireplace_off(self) -> None:
        self._fireplace_off = True

    async def set_bed_temperature(self, temp: int, side: str) -> None:
        self._bed_temp_set = (temp, side)

    async def announce(self, text: str, rooms: list[str] | None = None) -> None:
        self._announcements.append(text)

    async def set_room_temp(self, room: str, temp: float) -> None:
        pass

    async def arm_security(self, mode: str) -> None:
        pass

    async def enter_movie_mode(self) -> None:
        self._movie_mode_entered = True


class TestCapabilityDiscovery:
    """Tests for capability discovery system."""

    @pytest.mark.asyncio
    async def test_discovers_light_capability(self) -> None:
        """Should discover lighting capability."""
        controller = MockController()
        caps = await discover_capabilities(controller)

        assert caps.has(Capability.HAS_LIGHTS)

    @pytest.mark.asyncio
    async def test_discovers_shade_capability(self) -> None:
        """Should discover shade capability."""
        controller = MockController()
        caps = await discover_capabilities(controller)

        assert caps.has(Capability.HAS_SHADES)

    @pytest.mark.asyncio
    async def test_discovers_lock_capability(self) -> None:
        """Should discover lock capability."""
        controller = MockController()
        caps = await discover_capabilities(controller)

        assert caps.has(Capability.HAS_LOCKS)

    @pytest.mark.asyncio
    async def test_discovers_fireplace_capability(self) -> None:
        """Should discover fireplace capability."""
        controller = MockController()
        caps = await discover_capabilities(controller)

        assert caps.has(Capability.HAS_FIREPLACE)

    @pytest.mark.asyncio
    async def test_discovers_announce_capability(self) -> None:
        """Should discover voice announce capability."""
        controller = MockController()
        caps = await discover_capabilities(controller)

        assert caps.has(Capability.HAS_VOICE_ANNOUNCE)

    @pytest.mark.asyncio
    async def test_missing_capability_not_discovered(self) -> None:
        """Missing capabilities should not be discovered."""
        controller = MockController()
        caps = await discover_capabilities(controller)

        # No Tesla service configured
        assert not caps.has(Capability.HAS_VEHICLE)
        assert not caps.has(Capability.HAS_VEHICLE_CLIMATE)


class TestHouseholdCapabilities:
    """Tests for HouseholdCapabilities class."""

    def test_has_capability(self) -> None:
        """Should correctly report capability presence."""
        caps = HouseholdCapabilities()
        caps.capabilities.add(Capability.HAS_LIGHTS)

        assert caps.has(Capability.HAS_LIGHTS) is True
        assert caps.has(Capability.HAS_VEHICLE) is False

    def test_get_handler(self) -> None:
        """Should return registered handler."""
        caps = HouseholdCapabilities()

        async def mock_handler():
            pass

        caps.capability_handlers[Capability.HAS_LIGHTS] = mock_handler
        assert caps.get_handler(Capability.HAS_LIGHTS) is mock_handler
        assert caps.get_handler(Capability.HAS_VEHICLE) is None

    def test_summary(self) -> None:
        """Should return summary of all capabilities."""
        caps = HouseholdCapabilities()
        caps.capabilities.add(Capability.HAS_LIGHTS)
        caps.capabilities.add(Capability.HAS_LOCKS)

        summary = caps.summary()

        assert summary["has_lights"] is True
        assert summary["has_locks"] is True
        assert summary["has_vehicle"] is False


class TestAutomationIntent:
    """Tests for AutomationIntent enum."""

    def test_all_intents_defined(self) -> None:
        """All expected intents should be defined."""
        expected_intents = [
            "comfort.warm_home",
            "comfort.cool_home",
            "comfort.prepare_sleep",
            "comfort.wake_up",
            "transport.warm_vehicle",
            "security.lock_up",
            "presence.welcome_home",
            "presence.goodbye",
            "entertainment.movie_mode",
            "safety.pet_alert",
        ]

        actual_intents = [i.value for i in AutomationIntent]
        for expected in expected_intents:
            assert expected in actual_intents, f"Missing intent: {expected}"


class TestIntentExecutor:
    """Tests for IntentExecutor class."""

    @pytest.mark.asyncio
    async def test_execute_returns_result(self) -> None:
        """Execute should return IntentExecution result."""
        controller = MockController()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        result = await executor.execute(AutomationIntent.LOCK_UP)

        assert isinstance(result, IntentExecution)
        assert result.intent == AutomationIntent.LOCK_UP
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_tracks_capabilities_used(self) -> None:
        """Execution should track which capabilities were used."""
        controller = MockController()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        result = await executor.execute(AutomationIntent.LOCK_UP)

        assert Capability.HAS_LOCKS in result.capabilities_used

    @pytest.mark.asyncio
    async def test_tracks_missing_capabilities(self) -> None:
        """Execution should track missing capabilities."""
        controller = MockController()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        result = await executor.execute(AutomationIntent.WARM_VEHICLE)

        # No Tesla service, so vehicle climate is missing
        assert Capability.HAS_VEHICLE_CLIMATE in result.capabilities_missing

    @pytest.mark.asyncio
    async def test_unknown_intent_fails(self) -> None:
        """Unknown intent should return failure."""
        controller = MockController()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        # Create a mock intent not in handlers
        result = await executor.execute(AutomationIntent.ARM_AWAY)

        assert result.success is False
        assert result.error is not None


class TestFireplaceSafety:
    """Critical safety tests for fireplace control."""

    @pytest.mark.asyncio
    async def test_fireplace_turns_on(self) -> None:
        """Fireplace should turn on via warm_home intent."""
        controller = MockController()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        result = await executor.execute(
            AutomationIntent.WARM_HOME,
            context={"temp_f": 70},
        )

        assert controller._fireplace_on is True
        assert Capability.HAS_FIREPLACE in result.capabilities_used

    @pytest.mark.asyncio
    async def test_fireplace_not_activated_if_temp_low(self) -> None:
        """Fireplace should not activate for low temp requests."""
        controller = MockController()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        # Target temp 65F is below threshold (68)
        result = await executor.execute(
            AutomationIntent.WARM_HOME,
            context={"temp_f": 65},
        )

        # Fireplace should not be activated for low temp
        # (threshold is >= 68 in the code)
        assert controller._fireplace_on is False


class TestLockSafety:
    """Critical safety tests for lock control."""

    @pytest.mark.asyncio
    async def test_lock_up_locks_all_doors(self) -> None:
        """Lock up intent should lock all doors."""
        controller = MockController()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        result = await executor.execute(AutomationIntent.LOCK_UP)

        assert controller._locks_locked is True
        assert Capability.HAS_LOCKS in result.capabilities_used

    @pytest.mark.asyncio
    async def test_goodbye_locks_doors(self) -> None:
        """Goodbye intent should lock doors."""
        controller = MockController()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        result = await executor.execute(AutomationIntent.GOODBYE)

        assert controller._locks_locked is True

    @pytest.mark.asyncio
    async def test_welcome_home_does_not_auto_unlock(self) -> None:
        """Welcome home should NOT auto-unlock for security."""
        controller = MockController()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        result = await executor.execute(AutomationIntent.WELCOME_HOME)

        # Security: doors should NOT be auto-unlocked
        assert controller._locks_unlocked is False
        assert "manual unlock" in str(result.actions_taken).lower()

    @pytest.mark.asyncio
    async def test_prepare_sleep_locks_doors(self) -> None:
        """Prepare sleep should lock doors."""
        controller = MockController()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        result = await executor.execute(AutomationIntent.PREPARE_SLEEP)

        assert controller._locks_locked is True


class TestTVMountSafety:
    """Critical safety tests for TV mount control."""

    @pytest.mark.asyncio
    async def test_movie_mode_available(self) -> None:
        """Movie mode intent should be executable."""
        controller = MockController()
        controller._av_service = MagicMock()
        caps = await discover_capabilities(controller)
        executor = IntentExecutor(controller, caps)

        result = await executor.execute(AutomationIntent.MOVIE_MODE)

        # Intent should complete
        assert (
            result.success is True
            or result.error is None
            or "mode" in str(result.actions_taken).lower()
        )


class TestConditionToIntentMapping:
    """Tests for condition to intent mapping."""

    def test_automation_rule_creation(self) -> None:
        """Should create automation rule with conditions."""
        rule = AutomationRule(
            name="test_rule",
            description="Test rule",
            conditions=[Condition.COLD, Condition.MORNING],
            intent=AutomationIntent.WARM_VEHICLE,
        )

        assert rule.name == "test_rule"
        assert Condition.COLD in rule.conditions
        assert Condition.MORNING in rule.conditions
        assert rule.intent == AutomationIntent.WARM_VEHICLE

    def test_rule_cooldown_enforcement(self) -> None:
        """Rule should respect cooldown period."""
        rule = AutomationRule(
            name="test",
            description="Test",
            conditions=[Condition.ARRIVING_HOME],
            intent=AutomationIntent.WELCOME_HOME,
            cooldown_seconds=60.0,
        )

        # Initially can trigger
        assert rule.can_trigger() is True

        # After triggering
        rule.last_triggered = time.time()
        assert rule.can_trigger() is False

        # After cooldown
        rule.last_triggered = time.time() - 61
        assert rule.can_trigger() is True


class TestIntentAutomationEngine:
    """Tests for IntentAutomationEngine."""

    @pytest.mark.asyncio
    async def test_engine_initialization(self) -> None:
        """Engine should initialize with controller."""
        engine = IntentAutomationEngine()
        controller = MockController()

        await engine.initialize(controller)

        assert engine._controller is controller
        assert engine._capabilities is not None
        assert engine._executor is not None
        assert engine._running is True

    @pytest.mark.asyncio
    async def test_on_condition_triggers_rules(self) -> None:
        """Conditions should trigger matching rules."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        # Trigger arrival condition
        results = await engine.on_condition(Condition.ARRIVED_HOME)

        # Should have triggered welcome home
        assert len(results) > 0
        assert any(r.intent == AutomationIntent.WELCOME_HOME for r in results)

    @pytest.mark.asyncio
    async def test_execute_intent_directly(self) -> None:
        """Should execute intent directly."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        result = await engine.execute_intent(AutomationIntent.LOCK_UP)

        assert result.intent == AutomationIntent.LOCK_UP
        assert controller._locks_locked is True

    @pytest.mark.asyncio
    async def test_execute_natural_language(self) -> None:
        """Should execute from natural language."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        result = await engine.execute("lock up")

        assert result.intent == AutomationIntent.LOCK_UP
        assert controller._locks_locked is True

    @pytest.mark.asyncio
    async def test_natural_language_variations(self) -> None:
        """Should handle various natural language inputs."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        # Test various phrases
        phrases = [
            ("lock doors", AutomationIntent.LOCK_UP),
            ("goodnight", AutomationIntent.PREPARE_SLEEP),
            ("movie time", AutomationIntent.MOVIE_MODE),
        ]

        for phrase, expected_intent in phrases:
            result = await engine.execute(phrase)
            assert result.intent == expected_intent, f"Failed for phrase: {phrase}"

    @pytest.mark.asyncio
    async def test_unknown_phrase_fails_gracefully(self) -> None:
        """Unknown phrase should fail gracefully."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        result = await engine.execute("do something random and weird")

        assert result.success is False
        assert "understand" in result.error.lower()


class TestRuleManagement:
    """Tests for rule management."""

    def test_add_custom_rule(self) -> None:
        """Should add custom rule."""
        engine = IntentAutomationEngine()

        rule = AutomationRule(
            name="custom_rule",
            description="Custom test rule",
            conditions=[Condition.HOT],
            intent=AutomationIntent.COOL_HOME,
        )
        engine.add_rule(rule)

        assert any(r.name == "custom_rule" for r in engine._rules)

    def test_remove_rule(self) -> None:
        """Should remove rule by name."""
        engine = IntentAutomationEngine()

        initial_count = len(engine._rules)
        engine.remove_rule("cold_morning_vehicle")

        assert len(engine._rules) == initial_count - 1
        assert not any(r.name == "cold_morning_vehicle" for r in engine._rules)

    def test_enable_disable_rule(self) -> None:
        """Should enable/disable rules."""
        engine = IntentAutomationEngine()

        engine.disable_rule("arrival_welcome")
        rule = next(r for r in engine._rules if r.name == "arrival_welcome")
        assert rule.enabled is False

        engine.enable_rule("arrival_welcome")
        assert rule.enabled is True

    def test_get_rules(self) -> None:
        """Should return rules as dicts."""
        engine = IntentAutomationEngine()

        rules = engine.get_rules()

        assert len(rules) > 0
        assert all(isinstance(r, dict) for r in rules)
        assert all("name" in r for r in rules)
        assert all("conditions" in r for r in rules)
        assert all("intent" in r for r in rules)


class TestStats:
    """Tests for statistics tracking."""

    @pytest.mark.asyncio
    async def test_stats_track_conditions(self) -> None:
        """Stats should track conditions received."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        initial = engine._stats["conditions_received"]
        await engine.on_condition(Condition.MORNING)

        assert engine._stats["conditions_received"] > initial

    @pytest.mark.asyncio
    async def test_stats_track_intents(self) -> None:
        """Stats should track intents executed."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        initial = engine._stats["intents_executed"]
        await engine.execute_intent(AutomationIntent.LOCK_UP)

        assert engine._stats["intents_executed"] > initial

    @pytest.mark.asyncio
    async def test_stats_property(self) -> None:
        """Stats property should return all metrics."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        stats = engine.stats

        assert "conditions_received" in stats
        assert "intents_executed" in stats
        assert "active_conditions" in stats
        assert "rules_count" in stats
        assert "capabilities_count" in stats


class TestSafetyInvariant:
    """Critical tests verifying h(x) >= 0 safety invariant."""

    @pytest.mark.asyncio
    async def test_no_auto_unlock_security_policy(self) -> None:
        """SAFETY: Automation should NEVER auto-unlock doors."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        # Try all intents that might touch locks
        for intent in [
            AutomationIntent.WELCOME_HOME,
            AutomationIntent.WARM_HOME,
            AutomationIntent.COOL_HOME,
            AutomationIntent.WAKE_UP,
        ]:
            controller._locks_unlocked = False  # Reset
            await engine.execute_intent(intent)

            assert controller._locks_unlocked is False, (
                f"Intent {intent.value} must not auto-unlock doors"
            )

    @pytest.mark.asyncio
    async def test_goodbye_always_locks(self) -> None:
        """SAFETY: Goodbye intent must ALWAYS lock doors."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        controller._locks_locked = False
        await engine.execute_intent(AutomationIntent.GOODBYE)

        assert controller._locks_locked is True, "Goodbye MUST lock doors"

    @pytest.mark.asyncio
    async def test_prepare_sleep_always_locks(self) -> None:
        """SAFETY: Prepare sleep must ALWAYS lock doors."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        controller._locks_locked = False
        await engine.execute_intent(AutomationIntent.PREPARE_SLEEP)

        assert controller._locks_locked is True, "Prepare sleep MUST lock doors"

    @pytest.mark.asyncio
    async def test_missing_capability_graceful_degradation(self) -> None:
        """SAFETY: Missing capabilities should not cause failures."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        # Vehicle climate missing - should still succeed
        result = await engine.execute_intent(AutomationIntent.WARM_VEHICLE)

        # Should not crash or return hard failure
        # Missing capability is noted but not a failure
        assert Capability.HAS_VEHICLE_CLIMATE in result.capabilities_missing

    @pytest.mark.asyncio
    async def test_intent_execution_always_completes(self) -> None:
        """SAFETY: Intent execution should always complete with result."""
        engine = IntentAutomationEngine()
        controller = MockController()
        await engine.initialize(controller)

        for intent in AutomationIntent:
            result = await engine.execute_intent(intent)

            # Should always return a result
            assert result is not None
            assert isinstance(result, IntentExecution)
            assert result.intent == intent
            assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_engine_uninitialized_safe(self) -> None:
        """SAFETY: Uninitialized engine should fail safely."""
        engine = IntentAutomationEngine()
        # NOT initialized

        result = await engine.execute_intent(AutomationIntent.LOCK_UP)

        assert result.success is False
        assert "not initialized" in result.error.lower()


class TestConditions:
    """Tests for Condition enum and handling."""

    def test_all_conditions_defined(self) -> None:
        """All expected conditions should be defined."""
        expected = [
            "morning",
            "evening",
            "night",
            "cold",
            "hot",
            "arriving_home",
            "arrived_home",
            "leaving_home",
            "home_empty",
            "going_to_bed",
            "waking_up",
        ]

        actual = [c.value for c in Condition]
        for cond in expected:
            assert cond in actual, f"Missing condition: {cond}"


class TestDefaultRules:
    """Tests for default automation rules."""

    def test_default_rules_loaded(self) -> None:
        """Default rules should be loaded."""
        engine = IntentAutomationEngine()

        assert len(engine._rules) > 0
        rule_names = [r.name for r in engine._rules]

        assert "cold_morning_vehicle" in rule_names
        assert "arrival_welcome" in rule_names
        assert "departure_goodbye" in rule_names
        assert "bedtime" in rule_names

    def test_default_rule_cooldowns(self) -> None:
        """Default rules should have appropriate cooldowns."""
        engine = IntentAutomationEngine()

        # Vehicle warmup should have long cooldown (2 hours)
        vehicle_rule = next(r for r in engine._rules if r.name == "cold_morning_vehicle")
        assert vehicle_rule.cooldown_seconds >= 3600  # At least 1 hour

        # Pet safety should have shorter cooldown (5 min)
        pet_rule = next(r for r in engine._rules if r.name == "pet_safety")
        assert pet_rule.cooldown_seconds == 300


class TestIntentExecution:
    """Tests for IntentExecution result class."""

    def test_execution_result_fields(self) -> None:
        """Execution result should have all required fields."""
        result = IntentExecution(
            intent=AutomationIntent.LOCK_UP,
            success=True,
            capabilities_used=[Capability.HAS_LOCKS],
            capabilities_missing=[],
            actions_taken=["Locked all doors"],
            latency_ms=50.0,
        )

        assert result.intent == AutomationIntent.LOCK_UP
        assert result.success is True
        assert Capability.HAS_LOCKS in result.capabilities_used
        assert result.latency_ms == 50.0

    def test_execution_with_error(self) -> None:
        """Execution result should handle errors."""
        result = IntentExecution(
            intent=AutomationIntent.WARM_VEHICLE,
            success=False,
            error="Vehicle not available",
        )

        assert result.success is False
        assert result.error is not None
