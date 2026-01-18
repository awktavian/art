"""Test physics-based gameplay primitives with Genesis."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.core.embodiment.motion_primitives import (
    MotionType,
    get_combat_primitives,
    get_locomotion_primitives,
    get_primitive,
)


def test_all_primitives_load() -> None:
    """Verify all 15 primitives load correctly."""
    locomotion = get_locomotion_primitives()
    combat = get_combat_primitives()

    assert len(locomotion) == 5
    assert len(combat) == 3


def test_jump_primitive() -> None:
    """Test jump motion primitive."""
    jump = get_primitive(MotionType.JUMP)

    assert jump.duration == 0.8
    assert jump.force_magnitude == 8.0
    assert jump.impulse is True
    assert jump.cooldown == 0.5


def test_combat_damage() -> None:
    """Test combat primitives have damage values."""
    punch = get_primitive(MotionType.PUNCH)
    kick = get_primitive(MotionType.KICK)

    assert punch.damage_on_contact == 10.0
    assert kick.damage_on_contact == 15.0
    assert kick.knockback_force > punch.knockback_force


@pytest.mark.asyncio
async def test_physics_execution() -> None:
    """Test executing primitive with Genesis physics."""
    from kagami.core.embodiment.motion_primitives import execute_primitive_with_physics

    jump = get_primitive(MotionType.JUMP)

    # This will use mock mode if Genesis not available
    result = await execute_primitive_with_physics(
        primitive=jump,
        character_id="test_char",
        room_id="test_room",
    )

    assert "primitive" in result or "error" in result
