from __future__ import annotations

"""Gameplay Motion Primitives - Physics-Based Movement Library.

Defines core motion types for autonomous gameplay generation.
Integrated with Genesis physics for realistic character movement.

Based on PROJECT GENESIS-KAGAMI plan (2025-10-05).
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MotionType(Enum):
    """Core movement primitives for gameplay."""

    # Locomotion
    JUMP = "jump"
    DASH = "dash"
    ROLL = "roll"
    WALK = "walk"
    RUN = "run"

    # Combat
    PUNCH = "punch"
    KICK = "kick"
    BLOCK = "block"

    # Interactions
    GRAB = "grab"
    THROW = "throw"
    PUSH = "push"
    PULL = "pull"

    # Special
    DODGE = "dodge"
    SLIDE = "slide"
    CROUCH = "crouch"


@dataclass
class MotionPrimitive:
    """A physics-based motion that can be executed."""

    motion_type: MotionType
    duration: float  # seconds
    physics_params: dict[str, Any]
    cooldown: float = 0.0  # seconds before can use again
    energy_cost: float = 1.0  # gameplay resource cost

    # Physics properties
    force_magnitude: float = 0.0
    impulse: bool = False  # True for instant force, False for continuous

    # Collision properties
    damage_on_contact: float = 0.0
    knockback_force: float = 0.0

    # Animation hints
    animation_name: str | None = None
    animation_speed: float = 1.0


# ============================================================================
# LOCOMOTION PRIMITIVES
# ============================================================================

JUMP = MotionPrimitive(
    motion_type=MotionType.JUMP,
    duration=0.8,
    physics_params={
        "vertical_impulse": 8.0,
        "allow_air_control": True,
        "air_control_factor": 0.3,
    },
    cooldown=0.5,
    energy_cost=1.5,
    force_magnitude=8.0,
    impulse=True,
    animation_name="jump",
)

DASH = MotionPrimitive(
    motion_type=MotionType.DASH,
    duration=0.3,
    physics_params={
        "forward_impulse": 12.0,
        "ignore_friction": True,
        "invulnerable_frames": 5,  # Brief invincibility
    },
    cooldown=2.0,
    energy_cost=2.0,
    force_magnitude=12.0,
    impulse=True,
    animation_name="dash",
    animation_speed=2.0,
)

ROLL = MotionPrimitive(
    motion_type=MotionType.ROLL,
    duration=0.6,
    physics_params={
        "forward_impulse": 6.0,
        "reduce_hitbox": True,
        "hitbox_scale": 0.5,
        "invulnerable_frames": 10,
    },
    cooldown=1.5,
    energy_cost=1.0,
    force_magnitude=6.0,
    impulse=True,
    animation_name="roll",
)

WALK = MotionPrimitive(
    motion_type=MotionType.WALK,
    duration=1.0,  # Continuous
    physics_params={
        "speed": 2.0,
        "acceleration": 8.0,
        "deceleration": 10.0,
    },
    cooldown=0.0,
    energy_cost=0.1,
    force_magnitude=2.0,
    impulse=False,
    animation_name="walk",
)

RUN = MotionPrimitive(
    motion_type=MotionType.RUN,
    duration=1.0,  # Continuous
    physics_params={
        "speed": 5.0,
        "acceleration": 10.0,
        "deceleration": 12.0,
    },
    cooldown=0.0,
    energy_cost=0.3,
    force_magnitude=5.0,
    impulse=False,
    animation_name="run",
)

# ============================================================================
# COMBAT PRIMITIVES
# ============================================================================

PUNCH = MotionPrimitive(
    motion_type=MotionType.PUNCH,
    duration=0.4,
    physics_params={
        "attack_range": 1.5,
        "attack_arc": 60.0,  # degrees
        "startup_frames": 3,
        "active_frames": 5,
        "recovery_frames": 8,
    },
    cooldown=0.5,
    energy_cost=0.5,
    damage_on_contact=10.0,
    knockback_force=3.0,
    animation_name="punch",
    animation_speed=1.5,
)

KICK = MotionPrimitive(
    motion_type=MotionType.KICK,
    duration=0.6,
    physics_params={
        "attack_range": 2.0,
        "attack_arc": 90.0,
        "startup_frames": 5,
        "active_frames": 6,
        "recovery_frames": 10,
    },
    cooldown=0.8,
    energy_cost=1.0,
    damage_on_contact=15.0,
    knockback_force=5.0,
    animation_name="kick",
    animation_speed=1.2,
)

BLOCK = MotionPrimitive(
    motion_type=MotionType.BLOCK,
    duration=1.0,  # Continuous while held
    physics_params={
        "damage_reduction": 0.8,  # 80% damage reduction
        "stamina_drain": 0.5,  # per second
        "movement_speed_modifier": 0.3,  # 30% speed while blocking
    },
    cooldown=0.2,
    energy_cost=0.5,
    animation_name="block",
)

# ============================================================================
# INTERACTION PRIMITIVES
# ============================================================================

GRAB = MotionPrimitive(
    motion_type=MotionType.GRAB,
    duration=0.5,
    physics_params={
        "grab_range": 1.5,
        "grab_strength": 10.0,
        "can_grab_players": True,
        "can_grab_objects": True,
    },
    cooldown=0.5,
    energy_cost=0.5,
    animation_name="grab",
)

THROW = MotionPrimitive(
    motion_type=MotionType.THROW,
    duration=0.4,
    physics_params={
        "throw_force": 15.0,
        "throw_angle": 30.0,  # degrees upward
        "requires_grabbed_object": True,
    },
    cooldown=0.0,  # No cooldown (limited by grab)
    energy_cost=1.0,
    force_magnitude=15.0,
    impulse=True,
    damage_on_contact=20.0,  # If thrown object hits
    animation_name="throw",
    animation_speed=1.5,
)

PUSH = MotionPrimitive(
    motion_type=MotionType.PUSH,
    duration=0.5,
    physics_params={
        "push_force": 8.0,
        "push_range": 2.0,
        "affects_objects": True,
        "affects_players": True,
    },
    cooldown=1.0,
    energy_cost=1.0,
    force_magnitude=8.0,
    knockback_force=4.0,
    animation_name="push",
)

PULL = MotionPrimitive(
    motion_type=MotionType.PULL,
    duration=0.6,
    physics_params={
        "pull_force": 6.0,
        "pull_range": 3.0,
        "affects_objects": True,
        "affects_players": False,  # Can't pull players
    },
    cooldown=1.0,
    energy_cost=1.0,
    force_magnitude=6.0,
    animation_name="pull",
)

# ============================================================================
# SPECIAL PRIMITIVES
# ============================================================================

DODGE = MotionPrimitive(
    motion_type=MotionType.DODGE,
    duration=0.4,
    physics_params={
        "sideways_impulse": 8.0,
        "invulnerable_frames": 8,
        "direction": "perpendicular",  # 90° from facing
    },
    cooldown=1.5,
    energy_cost=1.5,
    force_magnitude=8.0,
    impulse=True,
    animation_name="dodge",
    animation_speed=1.8,
)

SLIDE = MotionPrimitive(
    motion_type=MotionType.SLIDE,
    duration=0.8,
    physics_params={
        "forward_impulse": 10.0,
        "friction_multiplier": 0.1,  # Very low friction
        "reduce_hitbox": True,
        "hitbox_scale": 0.6,
    },
    cooldown=2.0,
    energy_cost=1.5,
    force_magnitude=10.0,
    impulse=True,
    animation_name="slide",
)

CROUCH = MotionPrimitive(
    motion_type=MotionType.CROUCH,
    duration=1.0,  # Continuous
    physics_params={
        "height_scale": 0.5,
        "movement_speed_modifier": 0.4,
        "harder_to_hit": True,
        "hitbox_scale": 0.7,
    },
    cooldown=0.0,
    energy_cost=0.0,
    animation_name="crouch",
)

# ============================================================================
# PRIMITIVE REGISTRY
# ============================================================================

PRIMITIVE_REGISTRY: dict[MotionType, MotionPrimitive] = {
    # Locomotion
    MotionType.JUMP: JUMP,
    MotionType.DASH: DASH,
    MotionType.ROLL: ROLL,
    MotionType.WALK: WALK,
    MotionType.RUN: RUN,
    # Combat
    MotionType.PUNCH: PUNCH,
    MotionType.KICK: KICK,
    MotionType.BLOCK: BLOCK,
    # Interaction
    MotionType.GRAB: GRAB,
    MotionType.THROW: THROW,
    MotionType.PUSH: PUSH,
    MotionType.PULL: PULL,
    # Special
    MotionType.DODGE: DODGE,
    MotionType.SLIDE: SLIDE,
    MotionType.CROUCH: CROUCH,
}


def get_primitive(motion_type: MotionType) -> MotionPrimitive:
    """Get a motion primitive by type."""
    return PRIMITIVE_REGISTRY[motion_type]


def get_all_primitives() -> list[MotionPrimitive]:
    """Get all motion primitives."""
    return list(PRIMITIVE_REGISTRY.values())


def get_locomotion_primitives() -> list[MotionPrimitive]:
    """Get locomotion primitives only."""
    return [JUMP, DASH, ROLL, WALK, RUN]


def get_combat_primitives() -> list[MotionPrimitive]:
    """Get combat primitives only."""
    return [PUNCH, KICK, BLOCK]


def get_interaction_primitives() -> list[MotionPrimitive]:
    """Get interaction primitives only."""
    return [GRAB, THROW, PUSH, PULL]


def get_special_primitives() -> list[MotionPrimitive]:
    """Get special movement primitives only."""
    return [DODGE, SLIDE, CROUCH]


# ============================================================================
# COMBINATION DETECTION (Emergent Gameplay)
# ============================================================================


@dataclass
class MotionCombo:
    """A discovered combination of primitives that creates emergent gameplay."""

    name: str
    primitives: list[MotionType]
    timing_window: float  # Max time between moves (seconds)
    effect: str
    discovered_by: str = "autonomous"  # "player" or "autonomous"
    usage_count: int = 0


# Common combos that might be discovered
POTENTIAL_COMBOS = [
    MotionCombo(
        name="Dash Jump",
        primitives=[MotionType.DASH, MotionType.JUMP],
        timing_window=0.2,
        effect="Extra distance jump with momentum",
    ),
    MotionCombo(
        name="Roll Attack",
        primitives=[MotionType.ROLL, MotionType.KICK],
        timing_window=0.3,
        effect="Rising kick out of roll with bonus damage",
    ),
    MotionCombo(
        name="Grab Throw Combo",
        primitives=[MotionType.GRAB, MotionType.THROW],
        timing_window=2.0,
        effect="Throw grabbed object for projectile attack",
    ),
    MotionCombo(
        name="Dodge Counter",
        primitives=[MotionType.DODGE, MotionType.PUNCH],
        timing_window=0.4,
        effect="Counter-attack with bonus damage if dodged successfully",
    ),
]

# ============================================================================
# GENESIS PHYSICS INTEGRATION
# ============================================================================


async def execute_primitive_with_physics(
    primitive: MotionPrimitive,
    character_id: str,
    room_id: str,
    direction: tuple[float, float, float] = (0, 0, 1),
) -> dict[str, Any]:
    """Execute a motion primitive using Genesis physics simulation.

    Args:
        primitive: The motion primitive to execute
        character_id: ID of character performing the motion
        room_id: Room where motion occurs
        direction: Direction vector (normalized)

    Returns:
        Result dict[str, Any] with simulation data
    """
    try:
        from kagami.forge.modules.genesis_physics_wrapper import get_or_create_physics

        # Get or create physics instance for this room
        physics = await get_or_create_physics(room_id)

        # Map motion type to Genesis simulation type
        motion_mapping = {
            MotionType.JUMP: "jump",
            MotionType.DASH: "dash",
            MotionType.ROLL: "roll",
            MotionType.WALK: "walk",
            MotionType.RUN: "run",
            MotionType.PUNCH: "punch",
            MotionType.KICK: "kick",
        }

        genesis_motion = motion_mapping.get(
            primitive.motion_type,
            "walk",  # Default fallback
        )

        # Execute simulation
        result = await physics.simulate_character_motion(  # type: ignore[call-arg]
            motion_type=genesis_motion,
            duration=primitive.duration,
            capture_rate=30,
            record_data=True,
        )

        # Add gameplay metadata
        result["primitive"] = {
            "type": primitive.motion_type.value,
            "cooldown": primitive.cooldown,
            "energy_cost": primitive.energy_cost,
            "damage": primitive.damage_on_contact,
            "knockback": primitive.knockback_force,
        }

        return result

    except Exception as e:
        logger.error(f"Failed to execute primitive {primitive.motion_type}: {e}")
        return {
            "success": False,
            "error": str(e),
            "primitive": primitive.motion_type.value,
        }


logger.info(f"✅ Motion primitives library loaded: {len(PRIMITIVE_REGISTRY)} primitives available")
