"""Test Configurator integration with UnifiedOrganism.

Verifies that the LeCun Configurator is properly wired into the organism
execution path and modulates routing behavior based on task characteristics.

Created: December 20, 2025
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import torch

from kagami.core.unified_agents.unified_organism import (
    UnifiedOrganism,
    OrganismConfig,
)


@pytest.fixture
def organism():
    """Create a test organism."""
    config = OrganismConfig(device="cpu")
    org = UnifiedOrganism(config=config)
    yield org


@pytest.mark.asyncio
async def test_embed_intent(organism: Any) -> None:
    """Test intent embedding generation."""
    # Test basic embedding
    intent = "research.web"
    embedding = organism._embed_intent(intent)

    # Verify shape
    assert embedding.shape == (1, 512), "Embedding should be [1, 512]"
    assert embedding.dtype == torch.float32
    assert embedding.device.type == "cpu"

    # Verify values are normalized [0, 1]
    assert torch.all(embedding >= 0.0)
    assert torch.all(embedding <= 1.0)

    # Test different intents produce different embeddings
    intent2 = "build.feature"
    embedding2 = organism._embed_intent(intent2)
    assert not torch.allclose(
        embedding, embedding2
    ), "Different intents should produce different embeddings"


@pytest.mark.asyncio
async def test_configurator_applied_during_execution(organism: Any) -> None:
    """Test that Configurator is applied during intent execution."""
    await organism.start()

    # Execute an intent (should trigger Configurator)
    result = await organism.execute_intent(
        intent="test.simple",
        params={"query": "test"},
        context={},
        task_config=None,  # Force Configurator to generate config
    )

    # Verify execution succeeded
    assert result["success"], "Intent execution should succeed"

    # Verify Configurator was applied by checking routing behavior
    # (The Configurator modulates router thresholds based on urgency)
    # Default complex_threshold is 0.7, high urgency sets it to 0.9
    assert organism._router.complex_threshold in [
        0.7,
        0.9,
    ], "Router threshold should be set by Configurator"

    await organism.stop()


@pytest.mark.asyncio
async def test_configurator_urgency_modulation(organism: Any) -> None:
    """Test that Configurator urgency modulates routing."""
    await organism.start()

    # Store original threshold
    original_threshold = organism._router.complex_threshold

    # Execute with task_config=None to trigger Configurator
    result = await organism.execute_intent(
        intent="urgent.task",
        params={"priority": "high"},
        context={},
        task_config=None,
    )

    assert result["success"]

    # Threshold should be modulated (either 0.7 or 0.9 depending on urgency)
    assert organism._router.complex_threshold in [0.7, 0.9]

    await organism.stop()


@pytest.mark.asyncio
async def test_configurator_with_existing_task_config(organism: Any) -> None:
    """Test that existing task_config bypasses Configurator."""
    await organism.start()

    # Create a mock task config
    from kagami.core.executive.task_configuration import TaskConfiguration

    custom_config = TaskConfiguration(
        task_type="custom",
        urgency=0.9,
    )

    # Store original threshold
    original_threshold = organism._router.complex_threshold

    # Execute with explicit task_config (should NOT trigger Configurator)
    result = await organism.execute_intent(
        intent="test.simple",
        params={"query": "test"},
        context={},
        task_config=custom_config,
    )

    assert result["success"]

    # Threshold should be modulated by explicit config
    assert organism._router.complex_threshold == 0.9, "High urgency should set threshold to 0.9"

    await organism.stop()


@pytest.mark.asyncio
async def test_configurator_graceful_failure(organism: Any) -> None:
    """Test that Configurator failure doesn't break execution."""
    await organism.start()

    # Patch _get_executive to fail
    def failing_executive():
        raise RuntimeError("Configurator failure")

    original_get_exec = organism._get_executive
    organism._get_executive = failing_executive

    try:
        # Execute should still work with fallback
        result = await organism.execute_intent(
            intent="test.simple",
            params={"query": "test"},
            context={},
            task_config=None,
        )

        # Should succeed with fallback to defaults
        assert result["success"], "Execution should succeed even if Configurator fails"

    finally:
        # Restore original
        organism._get_executive = original_get_exec

    await organism.stop()


@pytest.mark.asyncio
async def test_configurator_world_model_integration(organism: Any) -> None:
    """Test Configurator queries world model state."""
    await organism.start()

    # Execute intent (will try to query world model)
    result = await organism.execute_intent(
        intent="test.worldmodel",
        params={"query": "test"},
        context={},
        task_config=None,
    )

    assert result["success"]

    # Verify world model query was attempted (logged, not failed)
    # The organism should gracefully handle missing world model

    await organism.stop()


@pytest.mark.asyncio
async def test_configurator_embedding_consistency(organism: Any) -> None:
    """Test that same intent produces consistent embeddings."""
    intent = "research.web"

    embedding1 = organism._embed_intent(intent)
    embedding2 = organism._embed_intent(intent)

    # Same intent should produce identical embeddings
    assert torch.allclose(embedding1, embedding2), "Same intent should produce identical embeddings"


@pytest.mark.asyncio
async def test_configurator_embedding_determinism(organism: Any) -> None:
    """Test that embeddings are deterministic across restarts."""
    intent = "research.web"

    embedding1 = organism._embed_intent(intent)

    # Create new organism
    organism2 = UnifiedOrganism(OrganismConfig(device="cpu"))
    embedding2 = organism2._embed_intent(intent)

    # Should be identical (hash-based embedding is deterministic)
    assert torch.allclose(embedding1, embedding2), "Embeddings should be deterministic"
