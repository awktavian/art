"""Tests for physics API resource limits.

Tests comprehensive resource limiting for physics simulations:
- Duration bounds (0.1 - 60.0 seconds)
- Rate limiting (10 simulations/minute)
- Concurrent execution limit (3 simultaneous)
- GPU budget (300 GPU-seconds/hour)
- Status endpoint
"""

from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import asyncio
import time

from kagami_api.routes.physics import (
    MAX_CONCURRENT_SIMULATIONS_PER_USER,
    MAX_DURATION_SECONDS,
    MAX_GPU_SECONDS_PER_HOUR,
    MAX_SIMULATIONS_PER_MINUTE,
    MIN_DURATION_SECONDS,
    ResourceTracker,
)


@pytest.fixture
def tracker():
    """Create a fresh ResourceTracker for each test."""
    return ResourceTracker()


class TestResourceTracker:
    """Test ResourceTracker isolation and correctness."""

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self, tracker: Any) -> None:
        """Test rate limiting: max 10 simulations per minute."""
        user_id = "test_user_1"

        # First 10 should succeed
        for i in range(MAX_SIMULATIONS_PER_MINUTE):
            allowed, remaining = await tracker.check_rate_limit(user_id)
            assert allowed, f"Simulation {i + 1} should be allowed"
            assert remaining == MAX_SIMULATIONS_PER_MINUTE - i
            await tracker.record_simulation_start(user_id)
            await tracker.record_simulation_end(user_id, 1.0)

        # 11th should fail
        allowed, remaining = await tracker.check_rate_limit(user_id)
        assert not allowed, "11th simulation should be blocked"
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_rate_limit_window_expiry(self, tracker: Any) -> None:
        """Test rate limit window expiry after 60 seconds."""
        user_id = "test_user_2"

        # Fill quota
        for _ in range(MAX_SIMULATIONS_PER_MINUTE):
            await tracker.record_simulation_start(user_id)
            await tracker.record_simulation_end(user_id, 1.0)

        # Should be blocked
        allowed, _ = await tracker.check_rate_limit(user_id)
        assert not allowed

        # Manually expire old entries by manipulating timestamps
        now = time.time()
        tracker._simulation_counts[user_id] = [now - 61.0] * MAX_SIMULATIONS_PER_MINUTE

        # Should be allowed after window expires
        allowed, remaining = await tracker.check_rate_limit(user_id)
        assert allowed, "Should be allowed after window expires"
        assert remaining == MAX_SIMULATIONS_PER_MINUTE

    @pytest.mark.asyncio
    async def test_concurrent_limit_enforcement(self, tracker: Any) -> None:
        """Test concurrent simulation limit: max 3 simultaneous."""
        user_id = "test_user_3"

        # Start 3 simulations without ending them
        for i in range(MAX_CONCURRENT_SIMULATIONS_PER_USER):
            allowed, active = await tracker.check_concurrent_limit(user_id)
            assert allowed, f"Concurrent simulation {i + 1} should be allowed"
            assert active == i
            await tracker.record_simulation_start(user_id)

        # 4th should fail
        allowed, active = await tracker.check_concurrent_limit(user_id)
        assert not allowed, "4th concurrent simulation should be blocked"
        assert active == MAX_CONCURRENT_SIMULATIONS_PER_USER

        # End one simulation
        await tracker.record_simulation_end(user_id, 1.0)

        # Should allow another
        allowed, active = await tracker.check_concurrent_limit(user_id)
        assert allowed, "Should allow new simulation after one completes"
        assert active == MAX_CONCURRENT_SIMULATIONS_PER_USER - 1

    @pytest.mark.asyncio
    async def test_gpu_budget_enforcement(self, tracker: Any) -> None:
        """Test GPU budget: max 300 GPU-seconds per hour."""
        user_id = "test_user_4"

        # Use up most of the budget
        budget_used = 250.0
        await tracker.record_simulation_start(user_id)
        await tracker.record_simulation_end(user_id, budget_used)

        # Should allow small simulation
        allowed, used, remaining = await tracker.check_gpu_budget(user_id, 30.0)
        assert allowed, "Should allow simulation within budget"
        assert used == budget_used
        assert remaining == MAX_GPU_SECONDS_PER_HOUR - budget_used

        # Should block large simulation
        allowed, used, remaining = await tracker.check_gpu_budget(user_id, 100.0)
        assert not allowed, "Should block simulation exceeding budget"
        assert used == budget_used

    @pytest.mark.asyncio
    async def test_gpu_budget_window_expiry(self, tracker: Any) -> None:
        """Test GPU budget window expiry after 1 hour."""
        user_id = "test_user_5"

        # Use full budget
        await tracker.record_simulation_start(user_id)
        await tracker.record_simulation_end(user_id, MAX_GPU_SECONDS_PER_HOUR)

        # Should be blocked
        allowed, used, _ = await tracker.check_gpu_budget(user_id, 1.0)
        assert not allowed
        assert used == MAX_GPU_SECONDS_PER_HOUR

        # Manually expire old entries
        now = time.time()
        tracker._gpu_usage[user_id] = [(now - 3601.0, MAX_GPU_SECONDS_PER_HOUR)]

        # Should be allowed after window expires
        allowed, used, remaining = await tracker.check_gpu_budget(user_id, 1.0)
        assert allowed, "Should be allowed after window expires"
        assert used == 0.0
        assert remaining == MAX_GPU_SECONDS_PER_HOUR

    @pytest.mark.asyncio
    async def test_user_isolation(self, tracker: Any) -> None:
        """Test that different users have separate quotas."""
        user1 = "test_user_6"
        user2 = "test_user_7"

        # Fill user1's rate limit
        for _ in range(MAX_SIMULATIONS_PER_MINUTE):
            await tracker.record_simulation_start(user1)
            await tracker.record_simulation_end(user1, 1.0)

        # User1 should be blocked
        allowed, _ = await tracker.check_rate_limit(user1)
        assert not allowed

        # User2 should still have full quota
        allowed, remaining = await tracker.check_rate_limit(user2)
        assert allowed, "User2 should have separate quota from User1"
        assert remaining == MAX_SIMULATIONS_PER_MINUTE

    @pytest.mark.asyncio
    async def test_get_user_status(self, tracker: Any) -> None:
        """Test status reporting."""
        user_id = "test_user_8"

        # Initial status: all resources available
        status = await tracker.get_user_status(user_id)
        assert status["rate_limit"]["remaining"] == MAX_SIMULATIONS_PER_MINUTE
        assert status["concurrent_limit"]["active"] == 0
        assert status["gpu_budget"]["used_seconds"] == 0.0
        assert status["gpu_budget"]["remaining_seconds"] == MAX_GPU_SECONDS_PER_HOUR

        # Use some resources
        await tracker.record_simulation_start(user_id)
        await tracker.record_simulation_end(user_id, 10.0)

        # Check updated status
        status = await tracker.get_user_status(user_id)
        assert status["rate_limit"]["remaining"] == MAX_SIMULATIONS_PER_MINUTE - 1
        assert status["concurrent_limit"]["active"] == 0  # Simulation ended
        assert status["gpu_budget"]["used_seconds"] == 10.0
        assert status["gpu_budget"]["remaining_seconds"] == MAX_GPU_SECONDS_PER_HOUR - 10.0

    @pytest.mark.asyncio
    async def test_concurrent_access_safety(self, tracker: Any) -> None:
        """Test thread-safety with concurrent operations."""
        user_id = "test_user_9"

        # Run 20 concurrent rate limit checks
        async def check_and_record():
            allowed, _ = await tracker.check_rate_limit(user_id)
            if allowed:
                await tracker.record_simulation_start(user_id)
                await tracker.record_simulation_end(user_id, 1.0)
            return allowed

        results = await asyncio.gather(*[check_and_record() for _ in range(20)])

        # Exactly MAX_SIMULATIONS_PER_MINUTE should succeed
        assert sum(results) == MAX_SIMULATIONS_PER_MINUTE, "Should allow exactly 10 simulations"


class TestRequestValidation:
    """Test Pydantic validation for SimulateMotionRequest."""

    def test_duration_bounds(self) -> None:
        """Test duration parameter validation."""
        from pydantic import ValidationError

        from kagami_api.routes.physics import SimulateMotionRequest

        # Valid durations
        valid_request = SimulateMotionRequest(
            room_id="test_room", motion_type="walk", duration=30.0
        )
        assert valid_request.duration == 30.0

        # Min bound
        min_request = SimulateMotionRequest(
            room_id="test_room", motion_type="walk", duration=MIN_DURATION_SECONDS
        )
        assert min_request.duration == MIN_DURATION_SECONDS

        # Max bound
        max_request = SimulateMotionRequest(
            room_id="test_room", motion_type="walk", duration=MAX_DURATION_SECONDS
        )
        assert max_request.duration == MAX_DURATION_SECONDS

        # Below min should fail
        with pytest.raises(ValidationError) as exc_info:
            SimulateMotionRequest(room_id="test_room", motion_type="walk", duration=0.05)
        assert "greater than or equal to" in str(exc_info.value).lower()

        # Above max should fail
        with pytest.raises(ValidationError) as exc_info:
            SimulateMotionRequest(room_id="test_room", motion_type="walk", duration=120.0)
        assert "less than or equal to" in str(exc_info.value).lower()

    def test_default_duration(self) -> None:
        """Test default duration value."""
        from kagami_api.routes.physics import SimulateMotionRequest

        request = SimulateMotionRequest(room_id="test_room", motion_type="walk")
        assert request.duration == 3.0


class TestResourceConstants:
    """Test that resource limit constants are sensible."""

    def test_duration_bounds(self) -> None:
        """Test duration bounds are reasonable."""
        assert MIN_DURATION_SECONDS > 0, "Min duration must be positive"
        assert MAX_DURATION_SECONDS > MIN_DURATION_SECONDS, "Max > Min"
        assert MIN_DURATION_SECONDS >= 0.1, "Min should be at least 0.1s"
        assert MAX_DURATION_SECONDS <= 300, "Max should not exceed 5 minutes"

    def test_rate_limit(self) -> None:
        """Test rate limit is reasonable."""
        assert MAX_SIMULATIONS_PER_MINUTE > 0, "Must allow at least 1 simulation"
        assert MAX_SIMULATIONS_PER_MINUTE <= 100, "Rate limit seems too high"

    def test_concurrent_limit(self) -> None:
        """Test concurrent limit is reasonable."""
        assert MAX_CONCURRENT_SIMULATIONS_PER_USER > 0, "Must allow at least 1 concurrent"
        assert MAX_CONCURRENT_SIMULATIONS_PER_USER <= 10, "Concurrent limit seems too high"

    def test_gpu_budget(self) -> None:
        """Test GPU budget is reasonable."""
        assert MAX_GPU_SECONDS_PER_HOUR > 0, "Must allow some GPU usage"
        assert MAX_GPU_SECONDS_PER_HOUR <= 3600, "Budget should not exceed 1 hour"

    def test_quota_relationships(self) -> None:
        """Test relationships between quotas are sane."""
        # If you run max concurrent at max duration, you shouldn't instantly hit rate limit
        max_usage_per_batch = MAX_CONCURRENT_SIMULATIONS_PER_USER * MAX_DURATION_SECONDS
        # This is a loose check, just ensuring quotas are somewhat balanced
        assert max_usage_per_batch < MAX_GPU_SECONDS_PER_HOUR * 10, "Quotas seem imbalanced"
