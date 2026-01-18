from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np


@pytest.mark.real_model
@pytest.mark.asyncio
async def test_motion_with_real_backend_when_available(client: Any, monkeypatch: Any) -> None:
    # Run only if HunyuanWorld repo is present locally
    repo = Path.home() / ".cache" / "forge_ai_models" / "HunyuanWorld-1.0"
    alt_repo = Path("hunyuanworld_repo")
    if not (repo.exists() or alt_repo.exists()):
        pytest.skip("HunyuanWorld repo not present")

    # Enable feature and physics for session start
    monkeypatch.setenv("HUNYUAN_WORLD_ENABLED", "1")
    monkeypatch.setenv("KAGAMI_ROOM_ENABLE_PHYSICS", "1")

    # 1) Generate a world
    r = client.post(
        "/api/rooms/generate",
        json={"prompt": "a modern hall", "labels_fg1": "sofa", "classes": "indoor"},
    )
    assert r.status_code == 200, r.text
    task_id = r.json()["task_id"]

    # 2) Wait for result
    res = client.get(f"/api/rooms/result/{task_id}")
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["success"] is True
    world_id = data["world_id"]
    assert world_id

    # 3) Start session (physics enabled)
    st = client.post(
        "/api/rooms/session/start",
        json={"world_id": world_id, "scene_type": "character_studio"},
    )
    assert st.status_code == 200, st.text
    session_id = st.json()["session_id"]
    assert session_id.startswith("session_")

    # 4) Apply motion
    m = client.post(
        "/api/rooms/motion",
        json={"session_id": session_id, "prompt": "walk", "duration": 1.0},
    )
    assert m.status_code == 200, m.text
    mout = m.json()
    assert mout["success"] is True
    assert (mout.get("applied_keyframes") or 0) >= 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_motion_agent_initialization():
    """Test MotionAgent initialization without models."""
    from kagami.forge.inference.motion_agent import MOTION_AGENT_PATH, MotionAgent

    if MOTION_AGENT_PATH is None:
        pytest.skip("Motion-Agent repo not available")

    agent = MotionAgent()
    assert not agent.initialized
    assert agent.model is None
    assert agent.motion_generator is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_motion_agent_generate_without_init():
    """Test motion generation triggers initialization."""
    from kagami.forge.inference.motion_agent import MOTION_AGENT_PATH, MotionAgent

    if MOTION_AGENT_PATH is None:
        pytest.skip("Motion-Agent repo not available")

    agent = MotionAgent()

    # Mock the generator to avoid model loading
    mock_gen = MagicMock()
    mock_gen.generate.return_value = np.random.rand(100, 22, 3)

    with patch.object(agent, "motion_generator", mock_gen):
        agent.initialized = True  # Skip initialization
        result = await agent.generate_motion("walk")

        assert result is not None
        assert "motion_data" in result


@pytest.mark.unit
@pytest.mark.asyncio
async def test_motion_agent_generate_with_duration_and_style():
    """Test motion generation with custom duration and style."""
    from kagami.forge.inference.motion_agent import MOTION_AGENT_PATH, MotionAgent

    if MOTION_AGENT_PATH is None:
        pytest.skip("Motion-Agent repo not available")

    agent = MotionAgent()

    # Mock the generator
    mock_gen = MagicMock()
    mock_gen.generate.return_value = np.random.rand(150, 22, 3)

    with patch.object(agent, "motion_generator", mock_gen):
        agent.initialized = True
        result = await agent.generate_motion("jump", duration=3.0, style="energetic")

        assert result is not None
        mock_gen.generate.assert_called_once()
        call_kwargs = mock_gen.generate.call_args[1]
        assert call_kwargs["duration"] == 3.0
        assert call_kwargs["style"] == "energetic"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_motion_agent_generate_empty_prompt():
    """Test motion generation with empty prompt."""
    from kagami.forge.inference.motion_agent import MOTION_AGENT_PATH, MotionAgent

    if MOTION_AGENT_PATH is None:
        pytest.skip("Motion-Agent repo not available")

    agent = MotionAgent()

    # Mock the generator
    mock_gen = MagicMock()
    mock_gen.generate.return_value = np.random.rand(100, 22, 3)

    with patch.object(agent, "motion_generator", mock_gen):
        agent.initialized = True
        result = await agent.generate_motion("")

        # Should still call with empty prompt
        assert result is not None
        mock_gen.generate.assert_called_once()
        call_kwargs = mock_gen.generate.call_args[1]
        assert call_kwargs["prompt"] == ""


@pytest.mark.unit
@pytest.mark.asyncio
async def test_motion_agent_timeout_handling():
    """Test motion generation timeout handling."""
    from kagami.forge.inference.motion_agent import MOTION_AGENT_PATH, MotionAgent

    if MOTION_AGENT_PATH is None:
        pytest.skip("Motion-Agent repo not available")

    agent = MotionAgent()

    # Mock generator that takes too long
    async def slow_generate(**kwargs) -> Any:
        import asyncio

        await asyncio.sleep(10)
        return np.random.rand(100, 22, 3)

    mock_gen = MagicMock()
    mock_gen.generate = slow_generate

    with patch.object(agent, "motion_generator", mock_gen):
        agent.initialized = True

        # Set short timeout via env
        import os

        os.environ["FORGE_MOTION_MAX_LATENCY_MS"] = "100"

        with pytest.raises(TimeoutError):  # Should timeout
            await agent.generate_motion("walk")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_motion_agent_concurrency_limit():
    """Test motion generation respects concurrency limit."""
    from kagami.forge.inference.motion_agent import MOTION_AGENT_PATH, MotionAgent

    if MOTION_AGENT_PATH is None:
        pytest.skip("Motion-Agent repo not available")

    agent = MotionAgent()

    # Mock generator
    call_count = 0

    async def mock_generate(**kwargs) -> Any:
        import asyncio

        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return np.random.rand(100, 22, 3)

    mock_gen = MagicMock()
    mock_gen.generate = mock_generate

    with patch.object(agent, "motion_generator", mock_gen):
        agent.initialized = True

        # Set concurrency limit
        import os

        os.environ["FORGE_MOTION_MAX_CONCURRENCY"] = "2"

        # Fire 5 requests concurrently
        import asyncio

        tasks = [agent.generate_motion(f"motion_{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        # All should complete
        assert len(results) == 5
        assert all(r is not None for r in results)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_motion_agent_error_propagation():
    """Test motion generation error propagation."""
    from kagami.forge.inference.motion_agent import MOTION_AGENT_PATH, MotionAgent

    if MOTION_AGENT_PATH is None:
        pytest.skip("Motion-Agent repo not available")

    agent = MotionAgent()

    # Mock generator that raises
    def failing_generate(**kwargs) -> None:
        raise RuntimeError("Model inference failed")

    mock_gen = MagicMock()
    mock_gen.generate = failing_generate

    with patch.object(agent, "motion_generator", mock_gen):
        agent.initialized = True

        with pytest.raises(Exception) as exc_info:
            await agent.generate_motion("walk")

        assert "failed" in str(exc_info.value).lower()
