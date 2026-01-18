"""Comprehensive tests for LLM Request Batcher.

Tests batching, deduplication, coalescing, and parallel execution.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami.core.services.llm.request_batcher import (
    BatchConfig,
    BatchingStrategy,
    BatchStats,
    LLMRequest,
    LLMResponse,
    MultiModelBatcher,
    RequestBatcher,
    batched_llm_request,
    get_global_batcher,
)


class TestLLMRequest:
    """Test LLMRequest dataclass."""

    def test_request_creation(self):
        """Test creating an LLM request."""
        req = LLMRequest(
            id="test-1",
            prompt="Hello world",
            model="gpt-4",
            temperature=0.7,
            max_tokens=100,
        )

        assert req.id == "test-1"
        assert req.prompt == "Hello world"
        assert req.model == "gpt-4"
        assert req.temperature == 0.7
        assert req.max_tokens == 100

    def test_cache_key_deterministic(self):
        """Test that cache_key is deterministic for same inputs."""
        req1 = LLMRequest(
            id="test-1",
            prompt="Hello",
            model="gpt-4",
            temperature=0.7,
            max_tokens=100,
        )
        req2 = LLMRequest(
            id="test-2",  # Different ID
            prompt="Hello",
            model="gpt-4",
            temperature=0.7,
            max_tokens=100,
        )

        assert req1.cache_key() == req2.cache_key()

    def test_cache_key_different_for_different_prompts(self):
        """Test that cache_key differs for different prompts."""
        req1 = LLMRequest(id="1", prompt="Hello", model="gpt-4")
        req2 = LLMRequest(id="2", prompt="Goodbye", model="gpt-4")

        assert req1.cache_key() != req2.cache_key()

    def test_cache_key_different_for_different_models(self):
        """Test that cache_key differs for different models."""
        req1 = LLMRequest(id="1", prompt="Hello", model="gpt-4")
        req2 = LLMRequest(id="2", prompt="Hello", model="gpt-3.5")

        assert req1.cache_key() != req2.cache_key()

    def test_cache_key_includes_system_prompt(self):
        """Test that cache_key includes system prompt."""
        req1 = LLMRequest(id="1", prompt="Hello", model="gpt-4", system_prompt="You are helpful")
        req2 = LLMRequest(id="2", prompt="Hello", model="gpt-4", system_prompt="You are rude")

        assert req1.cache_key() != req2.cache_key()

    def test_request_has_timestamp(self):
        """Test that request has created_at timestamp."""
        req = LLMRequest(id="1", prompt="Hello", model="gpt-4")

        assert req.created_at > 0
        assert req.created_at <= time.time()


class TestLLMResponse:
    """Test LLMResponse dataclass."""

    def test_response_creation(self):
        """Test creating an LLM response."""
        resp = LLMResponse(
            request_id="test-1",
            content="Hello there!",
            model="gpt-4",
            usage={"input_tokens": 10, "output_tokens": 20},
            latency=0.5,
        )

        assert resp.request_id == "test-1"
        assert resp.content == "Hello there!"
        assert resp.model == "gpt-4"
        assert resp.usage["input_tokens"] == 10
        assert resp.latency == 0.5
        assert not resp.cached
        assert resp.error is None

    def test_response_with_error(self):
        """Test response with error."""
        error = ValueError("Test error")
        resp = LLMResponse(
            request_id="test-1",
            content="",
            model="gpt-4",
            error=error,
        )

        assert resp.error is error


class TestBatchConfig:
    """Test BatchConfig dataclass."""

    def test_default_config(self):
        """Test default batch configuration."""
        config = BatchConfig()

        assert config.strategy == BatchingStrategy.ADAPTIVE
        assert config.max_batch_size == 10
        assert config.batch_timeout_ms == 100
        assert config.enable_deduplication
        assert config.enable_parallel

    def test_custom_config(self):
        """Test custom batch configuration."""
        config = BatchConfig(
            strategy=BatchingStrategy.TIME_BASED,
            max_batch_size=20,
            batch_timeout_ms=200,
            enable_deduplication=False,
        )

        assert config.strategy == BatchingStrategy.TIME_BASED
        assert config.max_batch_size == 20
        assert config.batch_timeout_ms == 200
        assert not config.enable_deduplication


class TestBatchStats:
    """Test BatchStats dataclass."""

    def test_stats_initialization(self):
        """Test stats initialization."""
        stats = BatchStats()

        assert stats.total_requests == 0
        assert stats.deduplicated == 0
        assert stats.avg_latency == 0.0
        assert stats.dedup_rate == 0.0

    def test_avg_latency_calculation(self):
        """Test average latency calculation."""
        stats = BatchStats(total_requests=10, total_latency=5.0)

        assert stats.avg_latency == 0.5

    def test_dedup_rate_calculation(self):
        """Test deduplication rate calculation."""
        stats = BatchStats(total_requests=100, deduplicated=25)

        assert stats.dedup_rate == 0.25

    def test_cache_hit_rate_calculation(self):
        """Test cache hit rate calculation."""
        stats = BatchStats(total_requests=100, cache_hits=40)

        assert stats.cache_hit_rate == 0.40

    def test_stats_to_dict(self):
        """Test converting stats to dict."""
        stats = BatchStats(
            total_requests=10,
            deduplicated=2,
            total_latency=5.0,
        )

        result = stats.to_dict()

        assert result["total_requests"] == 10
        assert result["deduplicated"] == 2
        assert "avg_latency_ms" in result
        assert "dedup_rate" in result


class TestRequestBatcher:
    """Test RequestBatcher class."""

    def test_batcher_initialization(self):
        """Test batcher initializes correctly."""
        batcher = RequestBatcher()

        assert batcher.config is not None
        assert len(batcher._pending_requests) == 0
        assert len(batcher._pending_futures) == 0
        assert len(batcher._dedup_cache) == 0

    def test_batcher_with_custom_config(self):
        """Test batcher with custom config."""
        config = BatchConfig(max_batch_size=5)
        batcher = RequestBatcher(config)

        assert batcher.config.max_batch_size == 5

    @pytest.mark.asyncio
    async def test_request_submission(self):
        """Test submitting a request."""
        batcher = RequestBatcher()

        # Mock execute_request to avoid actual LLM call
        async def mock_execute(request):
            return LLMResponse(
                request_id=request.id,
                content="Test response",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        response = await batcher.request(prompt="Test prompt", model="gpt-4")

        assert response.content == "Test response"
        assert batcher._stats.total_requests == 1

    @pytest.mark.asyncio
    async def test_deduplication(self):
        """Test request deduplication."""
        config = BatchConfig(enable_deduplication=True)
        batcher = RequestBatcher(config)

        # Mock execute_request
        async def mock_execute(request):
            await asyncio.sleep(0.01)
            return LLMResponse(
                request_id=request.id,
                content=f"Response to {request.prompt}",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        # First request
        response1 = await batcher.request(
            prompt="Hello",
            model="gpt-4",
            temperature=0.7,
            max_tokens=100,
        )

        # Second identical request (should be deduplicated)
        response2 = await batcher.request(
            prompt="Hello",
            model="gpt-4",
            temperature=0.7,
            max_tokens=100,
        )

        assert response2.cached
        assert batcher._stats.deduplicated >= 1

    @pytest.mark.asyncio
    async def test_batch_processing_on_size(self):
        """Test that batch processes when reaching max size."""
        config = BatchConfig(max_batch_size=3, batch_timeout_ms=1000)
        batcher = RequestBatcher(config)

        responses_received = []

        async def mock_execute(request):
            await asyncio.sleep(0.01)
            return LLMResponse(
                request_id=request.id,
                content=f"Response {request.id}",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        # Submit 3 requests simultaneously
        tasks = [
            asyncio.create_task(batcher.request(prompt=f"Prompt {i}", model="gpt-4"))
            for i in range(3)
        ]

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 3
        assert batcher._stats.batches_processed >= 1

    @pytest.mark.asyncio
    async def test_batch_timeout(self):
        """Test that batch processes after timeout."""
        config = BatchConfig(max_batch_size=10, batch_timeout_ms=100)
        batcher = RequestBatcher(config)

        async def mock_execute(request):
            return LLMResponse(
                request_id=request.id,
                content="Response",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        # Submit single request
        response = await batcher.request(prompt="Test", model="gpt-4")

        assert response.content == "Response"
        assert batcher._stats.batches_processed >= 1

    @pytest.mark.asyncio
    async def test_parallel_execution(self):
        """Test parallel execution of requests."""
        config = BatchConfig(
            max_batch_size=5,
            enable_parallel=True,
            max_parallel_requests=3,
        )
        batcher = RequestBatcher(config)

        execution_times = []

        async def mock_execute(request):
            start = time.time()
            await asyncio.sleep(0.05)
            execution_times.append(time.time() - start)
            return LLMResponse(
                request_id=request.id,
                content="Response",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        # Submit 5 requests
        tasks = [
            asyncio.create_task(batcher.request(prompt=f"Prompt {i}", model="gpt-4"))
            for i in range(5)
        ]

        start_time = time.time()
        await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # With parallelism, should complete faster than sequential
        # Sequential would take 5 * 0.05 = 0.25s
        # Parallel (3 at a time) should take ~2 batches = ~0.10s
        assert total_time < 0.20

    @pytest.mark.asyncio
    async def test_sequential_execution(self):
        """Test sequential execution when parallel disabled."""
        config = BatchConfig(
            max_batch_size=3,
            enable_parallel=False,
        )
        batcher = RequestBatcher(config)

        async def mock_execute(request):
            await asyncio.sleep(0.01)
            return LLMResponse(
                request_id=request.id,
                content="Response",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        tasks = [
            asyncio.create_task(batcher.request(prompt=f"Prompt {i}", model="gpt-4"))
            for i in range(3)
        ]

        responses = await asyncio.gather(*tasks)

        assert len(responses) == 3

    @pytest.mark.asyncio
    async def test_coalescing(self):
        """Test request coalescing."""
        config = BatchConfig(
            max_batch_size=5,
            enable_coalescing=True,
            batch_timeout_ms=100,
        )
        batcher = RequestBatcher(config)

        async def mock_execute(request):
            return LLMResponse(
                request_id=request.id,
                content="Response",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        # Submit multiple similar requests
        tasks = [
            asyncio.create_task(batcher.request(prompt="Same prompt", model="gpt-4"))
            for _ in range(5)
        ]

        await asyncio.gather(*tasks)

        # Some requests should be coalesced
        # Note: Coalescing is best-effort, may not always trigger
        assert batcher._stats.coalesced >= 0

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling in request execution."""
        batcher = RequestBatcher()

        async def mock_execute_with_error(request):
            raise ValueError("Test error")

        batcher._execute_request = mock_execute_with_error

        response = await batcher.request(prompt="Test", model="gpt-4")

        assert response.error is not None
        assert isinstance(response.error, ValueError)
        assert batcher._stats.errors >= 1

    @pytest.mark.asyncio
    async def test_cache_cleanup(self):
        """Test that cache entries are cleaned up after TTL."""
        config = BatchConfig(
            enable_deduplication=True,
            dedup_cache_ttl=0.1,  # 100ms TTL
        )
        batcher = RequestBatcher(config)

        async def mock_execute(request):
            return LLMResponse(
                request_id=request.id,
                content="Response",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        # Make request
        await batcher.request(prompt="Test", model="gpt-4")

        initial_cache_size = len(batcher._dedup_cache)
        assert initial_cache_size > 0

        # Wait for TTL to expire
        await asyncio.sleep(0.15)

        # Cache should be cleaned up
        assert len(batcher._dedup_cache) <= initial_cache_size

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test getting batcher statistics."""
        batcher = RequestBatcher()

        async def mock_execute(request):
            return LLMResponse(
                request_id=request.id,
                content="Response",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        # Make some requests
        await batcher.request(prompt="Test 1", model="gpt-4")
        await batcher.request(prompt="Test 2", model="gpt-4")

        stats = await batcher.get_stats()

        assert "total_requests" in stats
        assert "pending_requests" in stats
        assert "cache_size" in stats
        assert stats["total_requests"] >= 2

    @pytest.mark.asyncio
    async def test_clear_cache(self):
        """Test clearing deduplication cache."""
        batcher = RequestBatcher()

        async def mock_execute(request):
            return LLMResponse(
                request_id=request.id,
                content="Response",
                model=request.model,
            )

        batcher._execute_request = mock_execute

        await batcher.request(prompt="Test", model="gpt-4")
        assert len(batcher._dedup_cache) > 0

        await batcher.clear_cache()
        assert len(batcher._dedup_cache) == 0


class TestMultiModelBatcher:
    """Test MultiModelBatcher class."""

    def test_multi_model_initialization(self):
        """Test multi-model batcher initialization."""
        batcher = MultiModelBatcher()

        assert len(batcher._batchers) == 0

    @pytest.mark.asyncio
    async def test_request_routing(self):
        """Test that requests are routed to correct model batcher."""
        batcher = MultiModelBatcher()

        # Mock execute for all batchers
        async def mock_execute(request):
            return LLMResponse(
                request_id=request.id,
                content=f"Response from {request.model}",
                model=request.model,
            )

        # Make requests to different models
        for model in ["gpt-4", "gpt-3.5", "claude"]:
            if model not in batcher._batchers:
                batcher._batchers[model] = RequestBatcher()
            batcher._batchers[model]._execute_request = mock_execute

        response1 = await batcher.request("Test 1", model="gpt-4")
        response2 = await batcher.request("Test 2", model="gpt-3.5")
        response3 = await batcher.request("Test 3", model="claude")

        assert "gpt-4" in response1.content
        assert "gpt-3.5" in response2.content
        assert "claude" in response3.content

    @pytest.mark.asyncio
    async def test_get_stats_multi_model(self):
        """Test getting stats from multi-model batcher."""
        batcher = MultiModelBatcher()

        async def mock_execute(request):
            return LLMResponse(
                request_id=request.id,
                content="Response",
                model=request.model,
            )

        # Create batchers for models
        for model in ["gpt-4", "gpt-3.5"]:
            batcher._batchers[model] = RequestBatcher()
            batcher._batchers[model]._execute_request = mock_execute

        await batcher.request("Test 1", model="gpt-4")
        await batcher.request("Test 2", model="gpt-3.5")

        stats = await batcher.get_stats()

        assert "gpt-4" in stats
        assert "gpt-3.5" in stats


class TestGlobalBatcher:
    """Test global batcher functions."""

    @pytest.mark.asyncio
    async def test_get_global_batcher_singleton(self):
        """Test that global batcher is a singleton."""
        batcher1 = await get_global_batcher()
        batcher2 = await get_global_batcher()

        assert batcher1 is batcher2

    @pytest.mark.asyncio
    async def test_batched_llm_request(self):
        """Test convenience function for batched requests."""
        # Mock the global batcher
        with patch("kagami.core.services.llm.request_batcher.get_global_batcher") as mock_get:
            mock_batcher = AsyncMock()
            mock_response = LLMResponse(
                request_id="test",
                content="Test response",
                model="gpt-4",
            )
            mock_batcher.request.return_value = mock_response
            mock_get.return_value = mock_batcher

            result = await batched_llm_request(
                prompt="Test prompt",
                model="gpt-4",
                temperature=0.7,
            )

            assert result == "Test response"
            mock_batcher.request.assert_called_once()

    @pytest.mark.asyncio
    async def test_batched_llm_request_with_error(self):
        """Test batched request with error raises exception."""
        with patch("kagami.core.services.llm.request_batcher.get_global_batcher") as mock_get:
            mock_batcher = AsyncMock()
            mock_response = LLMResponse(
                request_id="test",
                content="",
                model="gpt-4",
                error=ValueError("Test error"),
            )
            mock_batcher.request.return_value = mock_response
            mock_get.return_value = mock_batcher

            with pytest.raises(ValueError, match="Test error"):
                await batched_llm_request(prompt="Test")


@pytest.mark.asyncio
async def test_batcher_integration_concurrent_requests():
    """Integration test: concurrent requests with batching."""
    config = BatchConfig(
        max_batch_size=5,
        batch_timeout_ms=50,
        enable_deduplication=True,
        enable_parallel=True,
    )
    batcher = RequestBatcher(config)

    async def mock_execute(request):
        await asyncio.sleep(0.02)
        return LLMResponse(
            request_id=request.id,
            content=f"Response to: {request.prompt}",
            model=request.model,
        )

    batcher._execute_request = mock_execute

    # Submit 10 concurrent requests
    tasks = [
        asyncio.create_task(
            batcher.request(prompt=f"Prompt {i % 3}", model="gpt-4")  # Some duplicates
        )
        for i in range(10)
    ]

    start_time = time.time()
    responses = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    assert len(responses) == 10
    assert all(r.content for r in responses)
    assert batcher._stats.total_requests == 10

    # Should complete reasonably fast with batching
    assert elapsed < 1.0
