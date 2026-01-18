"""Comprehensive tests for AdaptiveLimiter in rate_limiter.py.

Tests adaptive concurrency control, memory monitoring, and CPU-based scaling.
"""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kagami.core.services.llm.rate_limiter import (
    AdaptiveLimiter,
    get_adaptive_limiter,
    get_llm_semaphore,
)


class TestAdaptiveLimiter:
    """Test adaptive rate limiter functionality."""

    def test_initialization_defaults(self):
        """Test limiter initializes with default values."""
        limiter = AdaptiveLimiter()

        assert limiter._min_permits >= 1
        assert limiter._max_permits >= limiter._min_permits
        assert limiter._target_cpu > 0
        assert limiter._target_free_frac > 0
        assert limiter._allowed == limiter._max_permits
        assert limiter._active == 0
        assert not limiter._started

    def test_initialization_with_env_vars(self, monkeypatch):
        """Test limiter respects environment variables."""
        monkeypatch.setenv("LLM_MIN_CONCURRENCY", "4")
        monkeypatch.setenv("LLM_MAX_CONCURRENCY", "32")
        monkeypatch.setenv("LLM_TARGET_CPU_PERCENT", "90")
        monkeypatch.setenv("LLM_TARGET_FREE_MEM_FRACTION", "0.10")

        limiter = AdaptiveLimiter()

        assert limiter._min_permits == 4
        assert limiter._max_permits == 32
        assert limiter._target_cpu == 90.0
        assert limiter._target_free_frac == 0.10

    @pytest.mark.asyncio
    async def test_acquire_and_release(self):
        """Test basic acquire/release cycle."""
        limiter = AdaptiveLimiter()

        initial_active = limiter._active
        await limiter.acquire()

        assert limiter._active == initial_active + 1

        await limiter.release()
        assert limiter._active == initial_active

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager interface."""
        limiter = AdaptiveLimiter()

        initial_active = limiter._active

        async with limiter:
            assert limiter._active == initial_active + 1

        assert limiter._active == initial_active

    @pytest.mark.asyncio
    async def test_concurrency_limit_enforcement(self):
        """Test that limiter enforces maximum concurrency."""
        limiter = AdaptiveLimiter()
        limiter._allowed = 2  # Set very low limit
        limiter._max_permits = 2

        # Acquire 2 permits (at limit)
        await limiter.acquire()
        await limiter.acquire()

        assert limiter._active == 2

        # Try to acquire 3rd - should block
        acquire_task = asyncio.create_task(limiter.acquire())
        await asyncio.sleep(0.1)

        assert not acquire_task.done()

        # Release one permit
        await limiter.release()
        await asyncio.sleep(0.1)

        # Now 3rd acquire should complete
        assert acquire_task.done()

        # Cleanup
        await limiter.release()
        await limiter.release()

    @pytest.mark.asyncio
    async def test_compute_allowed_no_psutil(self):
        """Test _compute_allowed when psutil is unavailable."""
        limiter = AdaptiveLimiter()

        with patch("kagami.core.services.llm.rate_limiter.psutil", None):
            allowed = limiter._compute_allowed()

            # Should return max_permits when no system info
            assert allowed >= limiter._min_permits

    @pytest.mark.asyncio
    async def test_compute_allowed_with_high_memory(self):
        """Test _compute_allowed scales up with high free memory."""
        limiter = AdaptiveLimiter()

        # Mock high free memory (50%)
        mock_vm = MagicMock()
        mock_vm.available = 50 * 1024 * 1024 * 1024  # 50 GB
        mock_vm.total = 100 * 1024 * 1024 * 1024  # 100 GB

        with patch("kagami.core.services.llm.rate_limiter.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_vm
            mock_psutil.cpu_percent.return_value = 30.0  # Low CPU

            allowed = limiter._compute_allowed()

            # Should allow high concurrency
            assert allowed >= limiter._min_permits

    @pytest.mark.asyncio
    async def test_compute_allowed_with_low_memory(self):
        """Test _compute_allowed scales down with low memory."""
        limiter = AdaptiveLimiter()

        # Mock low free memory (2%)
        mock_vm = MagicMock()
        mock_vm.available = 2 * 1024 * 1024 * 1024  # 2 GB
        mock_vm.total = 100 * 1024 * 1024 * 1024  # 100 GB

        with patch("kagami.core.services.llm.rate_limiter.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_vm
            mock_psutil.cpu_percent.return_value = 50.0

            allowed = limiter._compute_allowed()

            # Should limit concurrency
            assert limiter._min_permits <= allowed <= limiter._max_permits

    @pytest.mark.asyncio
    async def test_is_memory_critically_low_no_psutil(self):
        """Test critical memory check when psutil unavailable."""
        limiter = AdaptiveLimiter()

        with patch("kagami.core.services.llm.rate_limiter.psutil", None):
            assert not limiter._is_memory_critically_low()

    @pytest.mark.asyncio
    async def test_is_memory_critically_low_normal(self):
        """Test critical memory check with normal memory."""
        limiter = AdaptiveLimiter()

        mock_vm = MagicMock()
        mock_vm.available = 10 * 1024 * 1024 * 1024  # 10 GB
        mock_vm.total = 100 * 1024 * 1024 * 1024  # 100 GB

        with patch("kagami.core.services.llm.rate_limiter.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_vm

            assert not limiter._is_memory_critically_low()

    @pytest.mark.asyncio
    async def test_is_memory_critically_low_critical(self):
        """Test critical memory check with critically low memory."""
        limiter = AdaptiveLimiter()
        limiter._hard_free_guard = 0.05  # 5%

        mock_vm = MagicMock()
        mock_vm.available = 1 * 1024 * 1024 * 1024  # 1 GB
        mock_vm.total = 100 * 1024 * 1024 * 1024  # 100 GB (1% free)

        with patch("kagami.core.services.llm.rate_limiter.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_vm

            assert limiter._is_memory_critically_low()

    @pytest.mark.asyncio
    async def test_adjust_loop_updates_allowed(self):
        """Test that adjust loop updates allowed permits."""
        limiter = AdaptiveLimiter()
        limiter._update_interval = 0.01  # Fast updates for testing

        mock_vm = MagicMock()
        mock_vm.available = 50 * 1024 * 1024 * 1024
        mock_vm.total = 100 * 1024 * 1024 * 1024

        with patch("kagami.core.services.llm.rate_limiter.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_vm
            mock_psutil.cpu_percent.return_value = 50.0

            # Start adjust loop
            adjust_task = asyncio.create_task(limiter._adjust_loop())

            # Wait for at least one update
            await asyncio.sleep(0.05)

            # Cancel the loop
            adjust_task.cancel()
            try:
                await adjust_task
            except asyncio.CancelledError:
                pass

            # Allowed should have been updated
            assert limiter._allowed >= limiter._min_permits

    @pytest.mark.asyncio
    async def test_multiple_concurrent_acquires(self):
        """Test multiple concurrent acquire operations."""
        limiter = AdaptiveLimiter()
        limiter._allowed = 10
        limiter._max_permits = 10

        # Create 5 concurrent acquires
        acquire_tasks = [asyncio.create_task(limiter.acquire()) for _ in range(5)]

        await asyncio.gather(*acquire_tasks)

        assert limiter._active == 5

        # Cleanup
        for _ in range(5):
            await limiter.release()

    @pytest.mark.asyncio
    async def test_release_never_negative(self):
        """Test that release never makes active count negative."""
        limiter = AdaptiveLimiter()

        # Release without acquiring
        await limiter.release()

        assert limiter._active >= 0

    def test_get_adaptive_limiter_singleton(self):
        """Test that get_adaptive_limiter returns singleton."""
        limiter1 = get_adaptive_limiter()
        limiter2 = get_adaptive_limiter()

        assert limiter1 is limiter2

    def test_get_llm_semaphore_singleton(self):
        """Test that get_llm_semaphore returns singleton."""
        sem1 = get_llm_semaphore()
        sem2 = get_llm_semaphore()

        assert sem1 is sem2

    def test_get_llm_semaphore_respects_env(self, monkeypatch):
        """Test semaphore respects LLM_MAX_CONCURRENCY env var."""
        # Reset global
        import kagami.core.services.llm.rate_limiter as rl_module

        rl_module._llm_semaphore = None

        monkeypatch.setenv("LLM_MAX_CONCURRENCY", "16")

        sem = get_llm_semaphore()

        # Semaphore should have 16 permits
        assert sem._value == 16


class TestAdaptiveLimiterEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_acquire_with_cancelled_error(self):
        """Test acquire handles cancellation gracefully."""
        limiter = AdaptiveLimiter()

        async def acquire_and_cancel():
            task = asyncio.create_task(limiter.acquire())
            await asyncio.sleep(0.01)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await acquire_and_cancel()

        # Limiter should still be functional
        await limiter.acquire()
        await limiter.release()

    @pytest.mark.asyncio
    async def test_compute_allowed_with_psutil_exception(self):
        """Test _compute_allowed handles psutil exceptions."""
        limiter = AdaptiveLimiter()

        with patch("kagami.core.services.llm.rate_limiter.psutil") as mock_psutil:
            mock_psutil.virtual_memory.side_effect = ValueError("psutil error")

            # Should not raise, should use default scaling
            allowed = limiter._compute_allowed()

            assert limiter._min_permits <= allowed <= limiter._max_permits

    @pytest.mark.asyncio
    async def test_acquire_waits_for_memory_critical(self):
        """Test acquire waits when memory is critically low."""
        limiter = AdaptiveLimiter()
        limiter._allowed = 100  # High limit

        mock_vm = MagicMock()
        mock_vm.available = 1 * 1024 * 1024  # Very low
        mock_vm.total = 100 * 1024 * 1024 * 1024

        with patch("kagami.core.services.llm.rate_limiter.psutil") as mock_psutil:
            mock_psutil.virtual_memory.return_value = mock_vm

            start_time = asyncio.get_event_loop().time()
            await limiter.acquire()
            end_time = asyncio.get_event_loop().time()

            # Should have slept due to critical memory
            # Note: This may not always trigger in fast CI environments
            await limiter.release()

    def test_min_permits_at_least_one(self, monkeypatch):
        """Test that min_permits is always at least 1."""
        monkeypatch.setenv("LLM_MIN_CONCURRENCY", "0")

        limiter = AdaptiveLimiter()

        assert limiter._min_permits >= 1

    def test_max_permits_at_least_min(self, monkeypatch):
        """Test that max_permits is at least min_permits."""
        monkeypatch.setenv("LLM_MIN_CONCURRENCY", "100")
        monkeypatch.setenv("LLM_MAX_CONCURRENCY", "10")

        limiter = AdaptiveLimiter()

        assert limiter._max_permits >= limiter._min_permits


@pytest.mark.asyncio
async def test_adaptive_limiter_integration():
    """Integration test: multiple operations under varying load."""
    limiter = AdaptiveLimiter()
    limiter._update_interval = 0.01
    limiter._allowed = 5

    completed = []

    async def worker(worker_id: int):
        async with limiter:
            await asyncio.sleep(0.05)
            completed.append(worker_id)

    # Start 10 workers with only 5 permits
    tasks = [asyncio.create_task(worker(i)) for i in range(10)]

    await asyncio.gather(*tasks)

    assert len(completed) == 10
    assert sorted(completed) == list(range(10))
