"""Tests for physics integration into consciousness."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from kagami.core.embodiment.physics_integration import PhysicsGroundedReasoning


@pytest.mark.asyncio
class TestPhysicsGroundedReasoning:
    """Test physics-grounded reasoning system."""

    async def test_initialization(self):
        """Test physics grounding initializes."""
        pgr = PhysicsGroundedReasoning()
        await pgr.initialize()

        # Should initialize without crashing
        assert pgr is not None

    async def test_ground_concept(self):
        """Test grounding abstract concept."""
        pgr = PhysicsGroundedReasoning()
        await pgr.initialize()

        result = await pgr.ground_concept("heavy")

        assert "grounded" in result
        assert "properties" in result
        assert "confidence" in result
        assert isinstance(result["properties"], list)

    async def test_predict_outcome(self):
        """Test predicting physical outcomes."""
        pgr = PhysicsGroundedReasoning()
        await pgr.initialize()

        result = await pgr.predict_physical_outcome("drop ball from height")

        assert "predicted_outcome" in result
        assert "confidence" in result
        assert "based_on" in result


@pytest.mark.asyncio
async def test_singleton():
    """Test singleton pattern."""
    from kagami.core.embodiment.physics_integration import get_physics_grounded

    pgr1 = await get_physics_grounded()
    pgr2 = await get_physics_grounded()

    assert pgr1 is pgr2
