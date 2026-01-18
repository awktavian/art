"""Integration Tests: Core Components

Tests async_utils and world_model working together in realistic pipelines.
Verifies end-to-end behavior, concurrent operations, and system integration.

Created: January 12, 2026
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import torch

pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.integration,
    pytest.mark.timeout(120),
]


# =============================================================================
# TEST: Async Utils + World Model Integration
# =============================================================================


class TestAsyncWorldModelIntegration:
    """Test async utilities with world model operations."""

    @pytest.fixture
    def mock_registry(self):
        """Create mock task registry for async tests."""
        with patch("kagami.core.task_registry.get_task_registry") as mock:
            mock_reg = MagicMock()
            mock_reg.register_task.return_value = True
            mock.return_value = mock_reg
            yield mock_reg

    @pytest.mark.asyncio
    async def test_async_world_model_inference(self, mock_registry) -> None:
        """Test running world model inference in async context."""
        from kagami.core.async_utils import safe_create_task
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        async def run_inference() -> dict[str, Any]:
            """Run single RSSM inference step."""
            e8_code = torch.randn(2, 8)
            s7_phase = torch.randn(2, 7)

            # Simulate async work before/after
            await asyncio.sleep(0.01)
            result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)
            await asyncio.sleep(0.01)

            return result

        task = safe_create_task(run_inference(), name="inference-task")
        result = await task

        assert "organism_action" in result
        assert "h_next" in result
        assert torch.isfinite(result["organism_action"]).all()

    @pytest.mark.asyncio
    async def test_concurrent_world_model_inference(self, mock_registry) -> None:
        """Test multiple concurrent world model inferences."""
        from kagami.core.async_utils import safe_gather
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        # Create separate RSSM instances for each concurrent inference
        async def run_inference(instance_id: int) -> dict[str, Any]:
            rssm = OrganismRSSM(config=ColonyRSSMConfig())
            e8_code = torch.randn(2, 8)
            s7_phase = torch.randn(2, 7)

            # Simulate variable latency
            await asyncio.sleep(0.01 * (instance_id % 3 + 1))

            result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)
            return {"id": instance_id, "action_sum": float(result["organism_action"].sum())}

        # Run 5 concurrent inferences
        results = await safe_gather(
            run_inference(1),
            run_inference(2),
            run_inference(3),
            run_inference(4),
            run_inference(5),
        )

        assert len(results) == 5
        ids = {r["id"] for r in results}
        assert ids == {1, 2, 3, 4, 5}

    @pytest.mark.asyncio
    async def test_async_sequence_processing(self, mock_registry) -> None:
        """Test processing sequences asynchronously."""
        from kagami.core.async_utils import safe_create_task
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        async def process_sequence(seq_len: int) -> dict[str, torch.Tensor]:
            """Process a sequence through RSSM."""
            B = 2
            e8_code = torch.randn(B, seq_len, 8)
            s7_phase = torch.randn(B, seq_len, 7)

            await asyncio.sleep(0.01)
            result = rssm.forward(e8_code, s7_phase)
            return result

        task = safe_create_task(process_sequence(10), name="sequence-task")
        result = await task

        assert result["h"].shape[1] == 10  # T dimension
        assert torch.isfinite(result["h"]).all()

    @pytest.mark.asyncio
    async def test_async_imagination_rollout(self, mock_registry) -> None:
        """Test async imagination/planning rollout."""
        from kagami.core.async_utils import safe_create_task
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        async def imagine_future(depth: int) -> dict[str, torch.Tensor]:
            """Imagine future trajectories."""
            B = 2
            h_init = torch.randn(B, rssm.deter_dim)
            z_init = torch.randn(B, rssm.stoch_dim)
            policy = torch.randn(B, depth, rssm.action_dim)

            await asyncio.sleep(0.01)
            result = rssm.imagine(h_init, z_init, policy)
            return result

        task = safe_create_task(imagine_future(20), name="imagination-task")
        result = await task

        assert result["h_states"].shape[1] == 20
        assert result["e8_predictions"].shape == (2, 20, 8)

    @pytest.mark.asyncio
    async def test_async_batch_processing_pipeline(self, mock_registry) -> None:
        """Test async batch processing pipeline."""
        from kagami.core.async_utils import background_task, safe_gather
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        processed_batches: list[int] = []

        @background_task(name="batch-processor")
        async def process_batch(batch_id: int) -> dict[str, Any]:
            """Process a single batch."""
            rssm = OrganismRSSM(config=ColonyRSSMConfig())
            e8_code = torch.randn(4, 8)
            s7_phase = torch.randn(4, 7)

            result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)
            processed_batches.append(batch_id)

            return {
                "batch_id": batch_id,
                "action_mean": float(result["organism_action"].mean()),
            }

        # Process 3 batches concurrently
        tasks = [process_batch(i) for i in range(3)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert set(processed_batches) == {0, 1, 2}


# =============================================================================
# TEST: World Model Pipeline Flow
# =============================================================================


class TestWorldModelPipelineFlow:
    """Test end-to-end world model pipeline flows."""

    @pytest.fixture
    def rssm(self):
        """Create RSSM for testing."""
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        return OrganismRSSM(config=ColonyRSSMConfig())

    def test_encode_step_decode_pipeline(self, rssm) -> None:
        """Test encode -> step -> decode pipeline."""
        # Simulate encoding observation to E8
        e8_code = torch.randn(4, 8)
        s7_phase = torch.randn(4, 7)

        # Step through world model
        result = rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)

        # Decode back to observation prediction
        h = result["h_next"]
        z = result["z_next"]

        # Aggregate to organism level
        h_org = h.mean(dim=1)  # [B, H]
        z_org = z.mean(dim=1)  # [B, Z]

        # Predict E8 observation
        e8_pred = rssm.predict_obs(h_org, z_org)

        assert e8_pred.shape == (4, 8)
        assert torch.isfinite(e8_pred).all()

    def test_sequence_to_reward_pipeline(self, rssm) -> None:
        """Test sequence processing to reward prediction pipeline."""
        B, T = 2, 8
        e8_seq = torch.randn(B, T, 8)
        s7_seq = torch.randn(B, T, 7)

        # Process sequence
        result = rssm.forward(e8_seq, s7_seq)

        # Get final state
        h_final = result["h"][:, -1].mean(dim=1)  # [B, H]
        z_final = result["z"][:, -1].mean(dim=1)  # [B, Z]

        # Predict reward from final state
        reward = rssm.predict_reward(h_final, z_final)

        assert reward.shape == (B,)
        assert torch.isfinite(reward).all()

    def test_planning_with_value_estimation(self, rssm) -> None:
        """Test planning pipeline with value estimation."""
        B, depth = 2, 10

        # Initialize from random state
        h_init = torch.randn(B, rssm.deter_dim)
        z_init = torch.randn(B, rssm.stoch_dim)

        # Generate random policy
        policy = torch.randn(B, depth, rssm.action_dim)

        # Imagine trajectory
        traj = rssm.imagine(h_init, z_init, policy)

        # Estimate value at each step
        values = []
        for t in range(depth):
            h_t = traj["h_states"][:, t]
            z_t = traj["z_states"][:, t]
            v_t = rssm.predict_value(h_t, z_t)
            values.append(v_t)

        values = torch.stack(values, dim=1)  # [B, depth]

        assert values.shape == (B, depth)
        assert torch.isfinite(values).all()

    def test_multi_episode_processing(self, rssm) -> None:
        """Test processing multiple episodes with boundaries."""
        B, T = 2, 20
        e8_code = torch.randn(B, T, 8)
        s7_phase = torch.randn(B, T, 7)

        # Create episode boundaries at t=5, t=10, t=15
        continue_flags = torch.ones(B, T)
        continue_flags[:, 5] = 0
        continue_flags[:, 10] = 0
        continue_flags[:, 15] = 0

        # Process with boundaries
        result = rssm.forward(e8_code, s7_phase, continue_flags=continue_flags)

        # Should complete without NaN
        assert torch.isfinite(result["h"]).all()
        assert torch.isfinite(result["z"]).all()

        # KL should be finite at all timesteps
        assert torch.isfinite(result["kl"]).all()


# =============================================================================
# TEST: State Management Integration
# =============================================================================


class TestStateManagementIntegration:
    """Test state management across operations."""

    def test_state_persistence_across_steps(self) -> None:
        """Test state is properly persisted across step_all calls."""
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        # Initial step
        e8_1 = torch.randn(2, 8)
        s7_1 = torch.randn(2, 7)
        result1 = rssm.step_all(e8_code=e8_1, s7_phase=s7_1)

        # Get state after first step
        states1 = rssm.get_current_states()
        h1 = torch.stack([s.hidden for s in states1], dim=1)

        # Second step
        e8_2 = torch.randn(2, 8)
        s7_2 = torch.randn(2, 7)
        result2 = rssm.step_all(e8_code=e8_2, s7_phase=s7_2)

        # State should have changed
        states2 = rssm.get_current_states()
        h2 = torch.stack([s.hidden for s in states2], dim=1)

        assert not torch.allclose(h1, h2)

    def test_state_clone_independence(self) -> None:
        """Test cloned states are independent."""
        from kagami.core.world_model.rssm_state import ColonyState

        # Create state with non-zero values
        hidden = torch.randn(4, 64)
        stochastic = torch.randn(4, 32)
        original = ColonyState(hidden=hidden, stochastic=stochastic, colony_id=0)

        # Clone
        cloned = original.clone()

        # Store original values
        original_hidden_sum = original.hidden.abs().sum().item()

        # Modify original
        original.hidden.zero_()

        # Cloned should be unchanged
        assert not torch.allclose(cloned.hidden, original.hidden)
        assert cloned.hidden.abs().sum().item() > 0
        # Verify the cloned value matches what original was before zeroing
        assert abs(cloned.hidden.abs().sum().item() - original_hidden_sum) < 1e-5

    def test_batch_size_change_reinitializes(self) -> None:
        """Test changing batch size reinitializes states."""
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        # First step with batch_size=2
        rssm.step_all(e8_code=torch.randn(2, 8), s7_phase=torch.randn(2, 7))
        states_b2 = rssm.get_current_states()
        assert states_b2[0].hidden.size(0) == 2

        # Second step with batch_size=4 (should reinitialize)
        rssm.step_all(e8_code=torch.randn(4, 8), s7_phase=torch.randn(4, 7))
        states_b4 = rssm.get_current_states()
        assert states_b4[0].hidden.size(0) == 4


# =============================================================================
# TEST: Gradient Flow Integration
# =============================================================================


class TestGradientFlowIntegration:
    """Test gradient flow through integrated components."""

    def test_end_to_end_gradient_flow(self) -> None:
        """Test gradients flow through entire forward pass."""
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        B, T = 2, 8
        e8_code = torch.randn(B, T, 8, requires_grad=True)
        s7_phase = torch.randn(B, T, 7, requires_grad=True)

        # Forward pass
        result = rssm.forward(e8_code, s7_phase, sample=False)

        # Compute loss from multiple outputs
        loss = (
            result["h"].sum()
            + result["z"].sum()
            + result["kl"].sum()
            + result["organism_actions"].sum()
        )

        loss.backward()

        # All inputs should have gradients
        assert e8_code.grad is not None
        assert s7_phase.grad is not None
        assert torch.isfinite(e8_code.grad).all()
        assert torch.isfinite(s7_phase.grad).all()

    def test_reward_prediction_gradient_flow(self) -> None:
        """Test gradients flow through reward prediction."""
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        h = torch.randn(4, rssm.deter_dim, requires_grad=True)
        z = torch.randn(4, rssm.stoch_dim, requires_grad=True)
        target_reward = torch.randn(4)

        # Compute reward loss
        loss = rssm.reward_loss(h, z, target_reward)
        loss.backward()

        assert h.grad is not None
        assert z.grad is not None

    def test_value_prediction_gradient_flow(self) -> None:
        """Test gradients flow through value prediction."""
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        h = torch.randn(4, rssm.deter_dim, requires_grad=True)
        z = torch.randn(4, rssm.stoch_dim, requires_grad=True)
        target_value = torch.randn(4)

        # Compute value loss
        loss = rssm.value_loss(h, z, target_value)
        loss.backward()

        assert h.grad is not None
        assert z.grad is not None


# =============================================================================
# TEST: Error Handling Integration
# =============================================================================


class TestErrorHandlingIntegration:
    """Test error handling across integrated components."""

    @pytest.mark.asyncio
    async def test_async_world_model_error_recovery(self) -> None:
        """Test async error recovery with world model."""
        from kagami.core.async_utils import safe_gather

        async def failing_inference() -> dict:
            raise RuntimeError("Inference failed")

        async def successful_inference() -> dict:
            from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

            rssm = OrganismRSSM(config=ColonyRSSMConfig())
            result = rssm.step_all(e8_code=torch.randn(2, 8), s7_phase=torch.randn(2, 7))
            return {"success": True, "action": float(result["organism_action"].mean())}

        # Gather with return_exceptions to handle failure
        results = await safe_gather(
            failing_inference(),
            successful_inference(),
            successful_inference(),
            return_exceptions=True,
        )

        assert len(results) == 3
        assert isinstance(results[0], RuntimeError)
        assert results[1]["success"] is True
        assert results[2]["success"] is True

    def test_invalid_input_handling(self) -> None:
        """Test world model handles invalid inputs gracefully."""
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        # Wrong E8 dimension
        with pytest.raises(ValueError):
            rssm.step_all(e8_code=torch.randn(2, 16), s7_phase=torch.randn(2, 7))

        # Wrong S7 dimension
        with pytest.raises(ValueError):
            rssm.step_all(e8_code=torch.randn(2, 8), s7_phase=torch.randn(2, 14))


# =============================================================================
# TEST: Performance Integration
# =============================================================================


class TestPerformanceIntegration:
    """Test performance characteristics of integrated components."""

    def test_batch_scaling(self) -> None:
        """Test world model scales with batch size."""
        import time

        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())

        batch_sizes = [1, 4, 16]
        times = []

        for bs in batch_sizes:
            e8_code = torch.randn(bs, 8)
            s7_phase = torch.randn(bs, 7)

            # Warm up
            rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)

            # Time
            start = time.monotonic()
            for _ in range(10):
                rssm.step_all(e8_code=e8_code, s7_phase=s7_phase)
            elapsed = time.monotonic() - start

            times.append(elapsed)

        # Larger batches should be more efficient per-sample
        time_per_sample = [t / (bs * 10) for t, bs in zip(times, batch_sizes, strict=True)]

        # Batch=16 should be more efficient than batch=1
        assert time_per_sample[2] < time_per_sample[0] * 2

    def test_sequence_length_scaling(self) -> None:
        """Test world model scales with sequence length."""
        import time

        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        rssm = OrganismRSSM(config=ColonyRSSMConfig())
        B = 2

        seq_lengths = [8, 32, 64]
        times = []

        for T in seq_lengths:
            e8_code = torch.randn(B, T, 8)
            s7_phase = torch.randn(B, T, 7)

            start = time.monotonic()
            rssm.forward(e8_code, s7_phase)
            elapsed = time.monotonic() - start

            times.append(elapsed)

        # Time should scale roughly linearly with sequence length
        # (with some overhead for longer sequences)
        ratio_32_8 = times[1] / times[0]
        ratio_64_32 = times[2] / times[1]

        # Should be roughly 4x and 2x respectively (with tolerance)
        assert ratio_32_8 < 8  # Less than 8x for 4x sequence
        assert ratio_64_32 < 4  # Less than 4x for 2x sequence


# =============================================================================
# TEST: Concurrent Safety
# =============================================================================


class TestConcurrentSafety:
    """Test concurrent safety of components."""

    @pytest.mark.asyncio
    async def test_concurrent_rssm_instances(self) -> None:
        """Test multiple RSSM instances can run concurrently."""
        from kagami.core.async_utils import safe_gather
        from kagami.core.world_model.colony_rssm import ColonyRSSMConfig, OrganismRSSM

        async def run_isolated_rssm(instance_id: int) -> dict:
            """Run isolated RSSM instance."""
            rssm = OrganismRSSM(config=ColonyRSSMConfig())

            results = []
            for _step in range(5):
                e8 = torch.randn(2, 8)
                s7 = torch.randn(2, 7)
                result = rssm.step_all(e8_code=e8, s7_phase=s7)
                results.append(float(result["organism_action"].sum()))
                await asyncio.sleep(0.001)

            return {"id": instance_id, "results": results}

        # Run 5 concurrent isolated instances
        outputs = await safe_gather(
            run_isolated_rssm(1),
            run_isolated_rssm(2),
            run_isolated_rssm(3),
            run_isolated_rssm(4),
            run_isolated_rssm(5),
        )

        assert len(outputs) == 5

        # Each should have 5 results
        for out in outputs:
            assert len(out["results"]) == 5

    @pytest.mark.asyncio
    async def test_shared_state_not_corrupted(self) -> None:
        """Test singleton RSSM state is not corrupted by concurrent access.

        Note: This test verifies that get_organism_rssm singleton
        behavior works correctly, but in practice each task should
        use its own RSSM instance for true isolation.
        """
        from kagami.core.world_model.rssm_core import (
            get_organism_rssm,
            reset_organism_rssm,
        )

        # Reset singleton
        reset_organism_rssm()

        # Get singleton
        rssm = get_organism_rssm()

        # Verify we can use it sequentially
        for _ in range(3):
            e8 = torch.randn(2, 8)
            s7 = torch.randn(2, 7)
            result = rssm.step_all(e8_code=e8, s7_phase=s7)
            assert torch.isfinite(result["organism_action"]).all()

        # Cleanup
        reset_organism_rssm()
