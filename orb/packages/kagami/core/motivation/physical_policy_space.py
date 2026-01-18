"""Physical Policy Space — SmartHome Action Execution with CBF Safety.

Maps abstract physical intents to concrete SmartHome controller methods.
This is the effector bridge between cognitive decision-making and physical embodiment.

ARCHITECTURE (Dec 30, 2025 — HARDENED):
========================================
IntelligentActionMapper routes goals to (app, action) pairs.
When app="smarthome", PhysicalPolicySpace executes the physical action.

SAFETY (CRITICAL):
- ALL physical actions pass through CBF safety check before execution
- Rate limiting prevents rapid-fire commands
- Room validation ensures target exists
- Security actions require elevated CBF threshold

Action Namespace:
- climate.* — HVAC, temperature control
- lights.* — Lighting control
- scene.* — Pre-defined scenes
- audio.* — Audio/announcements
- security.* — Locks, alarms (elevated safety threshold)
- tesla.* — Vehicle control
- shades.* — Motorized shades

The physical policy space is the actuator boundary of the Markov blanket.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from kagami.core.safety.cbf_integration import check_cbf_for_operation

if TYPE_CHECKING:
    from kagami_smarthome import SmartHomeController

logger = logging.getLogger(__name__)


# Valid rooms in the house (from home-layout.mdc)
VALID_ROOMS = frozenset(
    {
        "Living Room",
        "Kitchen",
        "Dining",
        "Entry",
        "Mudroom",
        "Garage",
        "Deck",
        "Porch",
        "Powder Room",
        "Stairway",
        "Primary Bedroom",
        "Primary Bath",
        "Primary Closet",
        "Primary Hall",
        "Office",
        "Office Bath",
        "Bed 3",
        "Bath 3",
        "Loft",
        "Laundry",
        "Game Room",
        "Bed 4",
        "Bath 4",
        "Gym",
        "Rack Room",
        "Patio",
    }
)

# Security-critical actions requiring elevated CBF threshold
SECURITY_ACTIONS = frozenset(
    {
        "security.lock_all",
        "security.unlock",
        "security.arm",
        "security.disarm",
        "scene.goodnight",  # Involves locks
    }
)

# Rate limit: max actions per window
RATE_LIMIT_WINDOW_SECONDS = 10.0
RATE_LIMIT_MAX_ACTIONS = 20


@dataclass
class PhysicalActionResult:
    """Result of a physical action execution."""

    success: bool
    action: str
    details: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    h_x: float | None = None  # CBF barrier value for audit


@dataclass
class RateLimitState:
    """Track action rate for rate limiting."""

    timestamps: list[float] = field(default_factory=list)

    def record(self) -> None:
        """Record an action timestamp."""
        now = time.time()
        # Remove old timestamps outside window
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        self.timestamps = [t for t in self.timestamps if t > cutoff]
        self.timestamps.append(now)

    def is_rate_limited(self) -> bool:
        """Check if rate limited."""
        now = time.time()
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        recent = [t for t in self.timestamps if t > cutoff]
        return len(recent) >= RATE_LIMIT_MAX_ACTIONS


class PhysicalPolicySpace:
    """Execute physical actions via SmartHome controller with CBF safety.

    This is the effector boundary — where cognitive decisions become physical reality.
    ALL actions pass through CBF safety check before execution.

    Usage:
        policy_space = PhysicalPolicySpace()
        result = await policy_space.execute("smarthome", "scene.movie", {"room": "Living Room"})
    """

    def __init__(self) -> None:
        self._controller: SmartHomeController | None = None
        self._execution_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._cbf_blocked_count = 0
        self._rate_limit_state = RateLimitState()
        self._semantic_matcher: Any = None

    async def _ensure_controller(self) -> SmartHomeController | None:
        """Lazy-load SmartHome controller."""
        if self._controller is None:
            try:
                from kagami_smarthome import get_smart_home

                self._controller = await get_smart_home()
                logger.info("✅ PhysicalPolicySpace connected to SmartHome")
            except Exception as e:
                logger.warning(f"SmartHome unavailable: {e}")
                return None
        return self._controller

    async def _ensure_semantic_matcher(self) -> Any | None:
        """Lazy-load SemanticMatcher for room validation."""
        if self._semantic_matcher is None:
            try:
                from kagami.core.integrations.semantic_matcher import get_semantic_matcher

                self._semantic_matcher = get_semantic_matcher()
            except Exception as e:
                logger.debug(f"SemanticMatcher unavailable: {e}")
                return None
        return self._semantic_matcher

    def _validate_rooms(self, rooms: list[str]) -> tuple[list[str], list[str]]:
        """Validate room names against known rooms.

        Returns:
            Tuple of (valid_rooms, invalid_rooms)
        """
        valid = []
        invalid = []
        for room in rooms:
            if room in VALID_ROOMS:
                valid.append(room)
            else:
                # Try fuzzy matching
                room_lower = room.lower()
                matched = False
                for valid_room in VALID_ROOMS:
                    if valid_room.lower() == room_lower:
                        valid.append(valid_room)
                        matched = True
                        break
                if not matched:
                    invalid.append(room)
        return valid, invalid

    async def _check_cbf_safety(
        self,
        action: str,
        context: dict[str, Any],
    ) -> tuple[bool, float, str | None]:
        """Check CBF safety for physical action.

        Security actions use elevated threshold (h(x) > 0.2 instead of h(x) > 0).

        Returns:
            Tuple of (is_safe, h_x_value, reason_if_blocked)
        """
        # Build operation description for CBF
        operation = f"physical.{action}"
        target = context.get("room") or context.get("rooms") or "all"

        # Security actions need elevated threshold
        is_security = action in SECURITY_ACTIONS

        result = await check_cbf_for_operation(
            operation=operation,
            action=action,
            target=str(target),
            params=context,
            metadata={
                "physical": True,
                "security_action": is_security,
            },
            source="physical_policy_space",
        )

        # Security actions require h(x) > 0.2 (20% margin)
        if is_security and result.safe and result.h_x is not None:
            if result.h_x < 0.2:
                logger.warning(
                    f"🔐 Security action {action} blocked: h(x)={result.h_x:.3f} < 0.2 threshold"
                )
                return (
                    False,
                    result.h_x,
                    f"Security action requires h(x) > 0.2, got {result.h_x:.3f}",
                )

        return result.safe, result.h_x or 0.0, result.reason if not result.safe else None

    async def execute(
        self,
        app: str,
        action: str,
        context: dict[str, Any] | None = None,
    ) -> PhysicalActionResult:
        """Execute a physical action with CBF safety check.

        Args:
            app: Must be "smarthome"
            action: The action namespace (e.g., "scene.movie", "climate.comfort")
            context: Optional context (room, temperature, message, etc.)

        Returns:
            PhysicalActionResult with success status, details, and CBF h(x) value
        """
        context = context or {}

        # Validate app
        if app != "smarthome":
            return PhysicalActionResult(
                success=False,
                action=action,
                details={"app": app, "supported_apps": ["smarthome"]},
                error=f"Physical policy space only handles 'smarthome' app, got: {app}",
            )

        # Rate limiting check
        if self._rate_limit_state.is_rate_limited():
            logger.warning(
                f"🚫 Rate limited: {action} (>{RATE_LIMIT_MAX_ACTIONS} actions in {RATE_LIMIT_WINDOW_SECONDS}s)"
            )
            return PhysicalActionResult(
                success=False,
                action=action,
                details={"rate_limit": True},
                error=f"Rate limited: max {RATE_LIMIT_MAX_ACTIONS} actions per {RATE_LIMIT_WINDOW_SECONDS}s",
            )

        # Room validation
        room = context.get("room")
        rooms = context.get("rooms", [room] if room else [])
        if rooms:
            valid_rooms, invalid_rooms = self._validate_rooms(rooms)
            if invalid_rooms:
                logger.warning(f"⚠️ Invalid rooms: {invalid_rooms}")
                # Continue with valid rooms only, or fail if all invalid
                if not valid_rooms:
                    return PhysicalActionResult(
                        success=False,
                        action=action,
                        details={"invalid_rooms": invalid_rooms, "valid_rooms": list(VALID_ROOMS)},
                        error=f"No valid rooms: {invalid_rooms}",
                    )
                # Update context with valid rooms only
                context = {**context, "rooms": valid_rooms}
                if room and room not in valid_rooms:
                    context["room"] = valid_rooms[0] if valid_rooms else None

        # CBF SAFETY CHECK (CRITICAL)
        is_safe, h_x, block_reason = await self._check_cbf_safety(action, context)

        if not is_safe:
            self._cbf_blocked_count += 1
            logger.error(
                f"🛑 CBF BLOCKED physical action: {action} — h(x)={h_x:.3f}, reason={block_reason}"
            )
            return PhysicalActionResult(
                success=False,
                action=action,
                details={"cbf_blocked": True, "h_x": h_x},
                error=f"CBF safety check failed: {block_reason}",
                h_x=h_x,
            )

        self._execution_count += 1
        self._rate_limit_state.record()

        # Get controller
        controller = await self._ensure_controller()
        if not controller:
            self._failure_count += 1
            return PhysicalActionResult(
                success=False,
                action=action,
                details={},
                error="SmartHome controller unavailable",
                h_x=h_x,
            )

        try:
            result = await self._dispatch_action(controller, action, context)
            result.h_x = h_x  # Add CBF value to result
            self._success_count += 1
            logger.info(f"🏠 Physical action executed: {action} (h(x)={h_x:.3f})")
            return result
        except Exception as e:
            self._failure_count += 1
            logger.error(f"Physical action failed: {action} — {e}")
            return PhysicalActionResult(
                success=False,
                action=action,
                details={},
                error=str(e),
                h_x=h_x,
            )

    async def _dispatch_action(
        self,
        controller: SmartHomeController,
        action: str,
        context: dict[str, Any],
    ) -> PhysicalActionResult:
        """Dispatch action to appropriate controller method."""
        room = context.get("room")
        rooms = context.get("rooms", [room] if room else [])

        # Climate actions
        if action == "climate.comfort":
            temp = context.get("temperature", 72)
            if room:
                await controller.set_room_temp(room, temp)
            else:
                await controller.set_all_temps(temp)
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"temperature": temp, "rooms": rooms or "all"},
            )

        if action == "climate.heat":
            temp = context.get("temperature", 74)
            if room:
                await controller.set_room_temp(room, temp)
            else:
                await controller.set_all_temps(temp)
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"temperature": temp, "mode": "heat"},
            )

        if action == "climate.cool":
            temp = context.get("temperature", 70)
            if room:
                await controller.set_room_temp(room, temp)
            else:
                await controller.set_all_temps(temp)
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"temperature": temp, "mode": "cool"},
            )

        # Lighting actions
        if action == "lights.focus":
            level = context.get("level", 70)
            await controller.set_lights(level, rooms=rooms or ["Office"])
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"level": level, "rooms": rooms or ["Office"]},
            )

        if action == "lights.relax":
            level = context.get("level", 30)
            await controller.set_lights(level, rooms=rooms or None)
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"level": level, "rooms": rooms or "all"},
            )

        if action == "lights.bright":
            await controller.set_lights(100, rooms=rooms or None)
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"level": 100, "rooms": rooms or "all"},
            )

        if action == "lights.dim":
            level = context.get("level", 20)
            await controller.set_lights(level, rooms=rooms or None)
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"level": level, "rooms": rooms or "all"},
            )

        # Scene actions
        if action == "scene.movie":
            await controller.enter_movie_mode()
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"scene": "movie"},
            )

        if action == "scene.goodnight":
            await controller.goodnight()
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"scene": "goodnight"},
            )

        # Audio actions
        if action == "audio.play":
            playlist = context.get("playlist", "focus")
            await controller.spotify_play_playlist(playlist)
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"playlist": playlist},
            )

        if action == "audio.announce":
            message = context.get("message", "")
            if rooms:
                await controller.announce(message, rooms=rooms)
            else:
                await controller.announce_all(message)
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"message": message, "rooms": rooms or "all"},
            )

        # Security actions
        if action == "security.lock_all":
            await controller.lock_all()
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"locks": "all"},
            )

        # Tesla actions
        if action == "tesla.precondition":
            temp = context.get("temperature")
            if temp:
                await controller.precondition_car(temp_c=temp)
            else:
                await controller.precondition_car()
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"vehicle": "Tesla", "temperature": temp},
            )

        # Shade actions
        if action == "shades.open":
            await controller.open_shades(rooms=rooms or None)
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"shades": "open", "rooms": rooms or "all"},
            )

        if action == "shades.close":
            await controller.close_shades(rooms=rooms or None)
            return PhysicalActionResult(
                success=True,
                action=action,
                details={"shades": "close", "rooms": rooms or "all"},
            )

        # Unknown action
        return PhysicalActionResult(
            success=False,
            action=action,
            details={},
            error=f"Unknown physical action: {action}",
        )

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics including CBF blocks."""
        total = self._execution_count or 1
        return {
            "execution_count": self._execution_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "cbf_blocked_count": self._cbf_blocked_count,
            "success_rate": self._success_count / total,
            "cbf_block_rate": self._cbf_blocked_count
            / (self._execution_count + self._cbf_blocked_count + 1),
            "controller_connected": self._controller is not None,
            "rate_limit_window_seconds": RATE_LIMIT_WINDOW_SECONDS,
            "rate_limit_max_actions": RATE_LIMIT_MAX_ACTIONS,
        }


# Singleton
_physical_policy_space: PhysicalPolicySpace | None = None


def get_physical_policy_space() -> PhysicalPolicySpace:
    """Get global PhysicalPolicySpace instance."""
    global _physical_policy_space
    if _physical_policy_space is None:
        _physical_policy_space = PhysicalPolicySpace()
    return _physical_policy_space


def reset_physical_policy_space() -> None:
    """Reset singleton (for testing)."""
    global _physical_policy_space
    _physical_policy_space = None


__all__ = [
    "SECURITY_ACTIONS",
    "VALID_ROOMS",
    "PhysicalActionResult",
    "PhysicalPolicySpace",
    "get_physical_policy_space",
    "reset_physical_policy_space",
]
