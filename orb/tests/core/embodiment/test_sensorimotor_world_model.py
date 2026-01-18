"""Test Sensorimotor World Model Integration.

Verifies:
1. Canonical dimensions (512 -> 14)
2. KagamiWorldModel integration (RSSM removed Dec 2025)
3. Action-conditioned prediction flow
"""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



import torch
from kagami.core.embodiment.sensorimotor_world_model import create_sensorimotor_world_model


@pytest.mark.asyncio
async def test_sensorimotor_integration():
    # 1. Instantiate (disable compile to avoid dynamo tracing issues in test)
    model = create_sensorimotor_world_model(device="cpu", compile_model=False)

    # 2. Verify dimensions
    expected_dims = [512, 248, 133, 78, 52, 21, 14]
    assert model.matryoshka_dims == expected_dims
    assert model.brain.dimensions == expected_dims

    # 3. Verify local RSSM removed (Dec 2025: RSSM now handled by OrganismRSSM separately)
    # NOTE: KagamiWorldModel no longer has .rssm attribute - dynamics handled via OrganismRSSM
    assert not hasattr(model, "rssm"), "Local RSSM attribute should be removed"
    # Brain uses S7AugmentedHierarchy + StrangeLoopS7Tracker for strange loop dynamics

    # 4. Test predict_with_action
    # Mock inputs
    B = 2
    vision_emb = torch.randn(B, 512)
    action = torch.randn(B, 8)  # Default action dim

    inputs = {"vision_emb": vision_emb}

    # Run prediction
    result = model.predict_with_action(inputs, action)  # type: ignore[arg-type]

    # Check outputs
    assert "predicted_manifold_state" in result
    assert "rssm_kl_divergence" in result
    assert "predicted_z" in result
    assert "predicted_o" in result

    # Check shapes
    z_pred = result["predicted_z"]
    assert z_pred.shape[-1] == 14  # H14

    o_pred = result["predicted_o"]
    assert o_pred.shape[-1] == 8  # S7 embedded in R8
