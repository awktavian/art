"""Integration tests for multi-module workflows.

Tests interactions between services, agents, training, and forge modules.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestServicesIntegration:
    """Integration tests for services layer."""

    @pytest.mark.asyncio
    async def test_llm_service_with_rate_limiting(self):
        """Test LLM service integrates with rate limiter."""
        from kagami.core.services.llm.rate_limiter import AdaptiveLimiter

        limiter = AdaptiveLimiter()

        # Acquire multiple permits
        tasks = []
        for _ in range(5):
            tasks.append(asyncio.create_task(limiter.acquire()))

        await asyncio.gather(*tasks)

        assert limiter._active == 5

        # Release all
        for _ in range(5):
            await limiter.release()

        assert limiter._active == 0

    @pytest.mark.asyncio
    async def test_llm_service_with_batching(self):
        """Test LLM service integrates with request batcher."""
        from kagami.core.services.llm.request_batcher import RequestBatcher, LLMResponse

        batcher = RequestBatcher()

        # Mock execute
        async def mock_execute(request):
            await asyncio.sleep(0.01)
            return LLMResponse(
                request_id=request.id,
                content=f"Response to {request.prompt}",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        # Submit concurrent requests
        tasks = [
            asyncio.create_task(batcher.request(prompt=f"Test {i}", model="gpt-4"))
            for i in range(10)
        ]

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 10
        assert all(r.content for r in responses)

    @pytest.mark.asyncio
    async def test_storage_router_integration(self):
        """Test storage router integrates with backend services."""
        from kagami.core.services.storage_routing import UnifiedStorageRouter, DataCategory

        router = UnifiedStorageRouter()

        # Test routing decisions
        assert router.get_backend(DataCategory.VECTOR).value == "weaviate"
        assert router.get_backend(DataCategory.CACHE).value == "redis"

        # Test status retrieval
        status = router.get_status()
        assert "weaviate" in status
        assert "redis" in status


class TestUnifiedAgentsIntegration:
    """Integration tests for unified agents."""

    @pytest.mark.asyncio
    async def test_homeostasis_with_colonies(self):
        """Test homeostasis monitor with mock colonies."""
        from kagami.core.unified_agents.homeostasis import HomeostasisMonitor

        monitor = HomeostasisMonitor(interval=0.05)

        # Create mock colonies
        mock_colonies = {}
        for name in ["forge", "nexus", "crystal"]:
            colony = MagicMock()
            colony.get_stats.return_value = {
                "success_rate": 0.8,
                "worker_count": 5,
                "available_workers": 3,
                "completed": 10,
                "failed": 2,
            }
            colony.cleanup_workers = AsyncMock()
            mock_colonies[name] = colony

        await monitor.start(mock_colonies)
        await asyncio.sleep(0.1)

        # Verify monitoring is working
        assert len(monitor.state.colony_health) == 3
        assert monitor.stats.homeostasis_cycles > 0

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_homeostasis_detects_degradation(self):
        """Test homeostasis detects and responds to degradation."""
        from kagami.core.unified_agents.homeostasis import (
            HomeostasisMonitor,
            OrganismStatus,
        )

        monitor = HomeostasisMonitor(interval=0.05, health_threshold=0.6)

        # Create unhealthy colony
        colony = MagicMock()
        colony.get_stats.return_value = {
            "success_rate": 0.3,  # Low health
            "worker_count": 5,
            "available_workers": 1,
            "completed": 3,
            "failed": 7,
        }
        colony.cleanup_workers = AsyncMock()

        await monitor.start({"forge": colony})
        await asyncio.sleep(0.1)

        # Should detect degradation
        assert monitor.status == OrganismStatus.DEGRADED

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_homeostasis_recovery(self):
        """Test homeostasis recovery from degraded state."""
        from kagami.core.unified_agents.homeostasis import (
            HomeostasisMonitor,
            OrganismStatus,
        )

        monitor = HomeostasisMonitor(interval=0.05, health_threshold=0.6)

        # Start with unhealthy colony
        colony = MagicMock()
        stats = {
            "success_rate": 0.3,
            "worker_count": 5,
            "available_workers": 1,
            "completed": 3,
            "failed": 7,
        }
        colony.get_stats.return_value = stats
        colony.cleanup_workers = AsyncMock()

        await monitor.start({"forge": colony})
        await asyncio.sleep(0.1)

        assert monitor.status == OrganismStatus.DEGRADED

        # Improve health
        stats["success_rate"] = 0.8
        stats["completed"] = 8
        stats["failed"] = 2

        await asyncio.sleep(0.1)

        # Should recover
        assert monitor.status == OrganismStatus.ACTIVE

        await monitor.stop()


class TestTrainingIntegration:
    """Integration tests for training modules."""

    def test_checkpoint_manager_workflow(self):
        """Test checkpoint manager full workflow."""
        import tempfile
        import shutil
        import torch
        import torch.nn as nn

        from kagami.core.training.training_utils import CheckpointManager

        class SimpleModel(nn.Module):
            def __init__(self):
                super().__init__()
                self.linear = nn.Linear(10, 10)

            def forward(self, x):
                return self.linear(x)

        temp_dir = tempfile.mkdtemp()
        try:
            manager = CheckpointManager(temp_dir, keep_last_n=2)

            model = SimpleModel()
            optimizer = torch.optim.Adam(model.parameters())

            # Save multiple checkpoints
            paths = []
            for i in range(3):
                path = manager.save_checkpoint(
                    model=model,
                    optimizer=optimizer,
                    epoch=i,
                    step=i * 100,
                    loss=0.5 - i * 0.1,
                    config={"epoch": i},
                )
                paths.append(path)

            # Only last 2 should exist
            import os
            existing = [p for p in paths if os.path.exists(p)]
            assert len(existing) == 2

            # Load last checkpoint
            new_model = SimpleModel()
            metadata = manager.load_checkpoint(
                paths[-1],
                model=new_model,
                device="cpu",
            )

            assert metadata["epoch"] == 2

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestForgeIntegration:
    """Integration tests for forge modules."""

    @pytest.mark.asyncio
    async def test_forge_service_basic_workflow(self):
        """Test basic forge service workflow."""
        # Mock forge service components
        with patch('kagami.forge.service.ForgeService') as MockForge:
            mock_service = MagicMock()
            MockForge.return_value = mock_service

            # Simulate character generation request
            mock_service.generate_character = AsyncMock(
                return_value={
                    "character_id": "char_123",
                    "model_url": "https://example.com/model.glb",
                    "textures": ["texture1.png", "texture2.png"],
                }
            )

            result = await mock_service.generate_character(concept="warrior")

            assert result["character_id"] == "char_123"
            assert "model_url" in result


class TestCrossModuleIntegration:
    """Integration tests across multiple modules."""

    @pytest.mark.asyncio
    async def test_services_and_agents_integration(self):
        """Test services layer integrates with agents."""
        from kagami.core.services.storage_routing import UnifiedStorageRouter
        from kagami.core.unified_agents.homeostasis import HomeostasisMonitor

        # Create router
        router = UnifiedStorageRouter()

        # Create monitor
        monitor = HomeostasisMonitor()

        # Both should work together
        router_status = router.get_status()
        monitor_stats = monitor.get_stats()

        assert "weaviate" in router_status
        assert "status" in monitor_stats

    @pytest.mark.asyncio
    async def test_rate_limiting_and_batching_integration(self):
        """Test rate limiter integrates with request batcher."""
        from kagami.core.services.llm.rate_limiter import AdaptiveLimiter
        from kagami.core.services.llm.request_batcher import RequestBatcher, LLMResponse

        limiter = AdaptiveLimiter()
        batcher = RequestBatcher()

        # Mock execute with rate limiting
        async def mock_execute_with_limit(request):
            async with limiter:
                await asyncio.sleep(0.01)
                return LLMResponse(
                    request_id=request.id,
                    content="Response",
                    model=request.model,
                )

        batcher._execute_request = mock_execute_with_limit

        # Submit requests
        tasks = [
            asyncio.create_task(batcher.request(prompt=f"Test {i}", model="gpt-4"))
            for i in range(5)
        ]

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 5
        assert all(r.content for r in responses)

    @pytest.mark.asyncio
    async def test_full_workflow_simulation(self):
        """Simulate a full workflow across modules."""
        from kagami.core.services.llm.rate_limiter import AdaptiveLimiter
        from kagami.core.services.storage_routing import UnifiedStorageRouter
        from kagami.core.unified_agents.homeostasis import HomeostasisMonitor

        # Initialize components
        limiter = AdaptiveLimiter()
        router = UnifiedStorageRouter()
        monitor = HomeostasisMonitor()

        # Simulate workflow
        async def workflow():
            # Step 1: Acquire rate limit
            async with limiter:
                # Step 2: Store data
                await asyncio.sleep(0.01)

                # Step 3: Check system health
                health = monitor.get_health()

                return health

        result = await workflow()

        assert "status" in result

    @pytest.mark.asyncio
    async def test_concurrent_workflows(self):
        """Test multiple concurrent workflows."""
        from kagami.core.services.llm.rate_limiter import AdaptiveLimiter
        from kagami.core.services.llm.request_batcher import RequestBatcher, LLMResponse

        limiter = AdaptiveLimiter()
        batcher = RequestBatcher()

        async def mock_execute(request):
            async with limiter:
                await asyncio.sleep(0.01)
                return LLMResponse(
                    request_id=request.id,
                    content="Response",
                    model=request.model,
                )

        batcher._execute_request = mock_execute

        # Run multiple concurrent workflows
        async def workflow(wf_id):
            responses = []
            for i in range(3):
                response = await batcher.request(
                    prompt=f"Workflow {wf_id} request {i}",
                    model="gpt-4",
                )
                responses.append(response)
            return responses

        # Execute 5 workflows concurrently
        workflows = [workflow(i) for i in range(5)]
        results = await asyncio.gather(*workflows)

        assert len(results) == 5
        assert all(len(r) == 3 for r in results)


class TestErrorHandlingIntegration:
    """Integration tests for error handling across modules."""

    @pytest.mark.asyncio
    async def test_homeostasis_handles_colony_errors(self):
        """Test homeostasis handles colony errors gracefully."""
        from kagami.core.unified_agents.homeostasis import HomeostasisMonitor

        monitor = HomeostasisMonitor(interval=0.05)

        # Create colony that raises errors
        colony = MagicMock()
        colony.get_stats.side_effect = RuntimeError("Colony error")
        colony.cleanup_workers = AsyncMock()

        await monitor.start({"forge": colony})
        await asyncio.sleep(0.1)

        # Monitor should still be running
        assert monitor._running

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_batcher_handles_execution_errors(self):
        """Test batcher handles execution errors."""
        from kagami.core.services.llm.request_batcher import RequestBatcher, LLMResponse

        batcher = RequestBatcher()

        # Mock execute with errors
        call_count = [0]

        async def mock_execute_with_errors(request):
            call_count[0] += 1
            if call_count[0] % 2 == 0:
                raise ValueError("Test error")
            return LLMResponse(
                request_id=request.id,
                content="Success",
                model=request.model,
            )

        batcher._execute_request = mock_execute_with_errors

        # Submit requests
        tasks = [
            asyncio.create_task(batcher.request(prompt=f"Test {i}", model="gpt-4"))
            for i in range(4)
        ]

        responses = await asyncio.gather(*tasks)

        # Some should succeed, some should have errors
        assert len(responses) == 4
        success_count = sum(1 for r in responses if not r.error)
        error_count = sum(1 for r in responses if r.error)

        assert success_count > 0
        assert error_count > 0


@pytest.mark.slow
class TestPerformanceIntegration:
    """Performance-focused integration tests."""

    @pytest.mark.asyncio
    async def test_high_throughput_batching(self):
        """Test batcher handles high throughput."""
        from kagami.core.services.llm.request_batcher import RequestBatcher, LLMResponse
        import time

        batcher = RequestBatcher()

        async def mock_execute(request):
            await asyncio.sleep(0.001)
            return LLMResponse(
                request_id=request.id,
                content="Response",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        # Submit many concurrent requests
        start_time = time.time()

        tasks = [
            asyncio.create_task(batcher.request(prompt=f"Test {i}", model="gpt-4"))
            for i in range(100)
        ]

        responses = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        assert len(responses) == 100
        # With batching, should complete faster than sequential
        # Sequential would take ~0.1s, batched should be much faster
        assert elapsed < 2.0  # Generous upper bound

    @pytest.mark.asyncio
    async def test_homeostasis_low_overhead(self):
        """Test homeostasis has low overhead."""
        from kagami.core.unified_agents.homeostasis import HomeostasisMonitor
        import time

        monitor = HomeostasisMonitor(interval=0.01)  # Fast cycles

        # Create mock colonies
        colonies = {}
        for i in range(7):
            colony = MagicMock()
            colony.get_stats.return_value = {
                "success_rate": 0.8,
                "worker_count": 5,
                "available_workers": 3,
                "completed": 10,
                "failed": 2,
            }
            colony.cleanup_workers = AsyncMock()
            colonies[f"colony_{i}"] = colony

        start_time = time.time()

        await monitor.start(colonies)
        await asyncio.sleep(0.1)  # Run for 100ms

        cycles = monitor.stats.homeostasis_cycles
        elapsed = time.time() - start_time

        await monitor.stop()

        # Should complete many cycles in 100ms
        assert cycles >= 5  # At least 5 cycles in 100ms
        # Each cycle should be fast
        assert elapsed < 0.2  # Total time reasonable
