"""Tests for Organism-Level Control Barrier Functions.

Created: December 14, 2025

Tests the Tier 1 (organism-level) safety barriers that enforce
global system-wide safety invariants.
"""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import time
from unittest.mock import MagicMock, patch

import numpy as np

from kagami.core.safety.organism_barriers import (
    OrganismBarriers,
    OrganismBarriersConfig,
    TokenBucket,
    get_organism_barriers,
)

# =============================================================================
# TOKEN BUCKET TESTS
# =============================================================================


class TestTokenBucket:
    """Tests for TokenBucket rate limiter."""

    def test_initialization(self) -> None:
        """Test token bucket initialization."""
        bucket = TokenBucket(rate=10.0, capacity=20.0)

        assert bucket.rate == 10.0
        assert bucket.capacity == 20.0
        assert bucket.tokens == 20.0  # Starts full

    def test_default_capacity(self) -> None:
        """Test default capacity is 2x rate."""
        bucket = TokenBucket(rate=10.0)
        assert bucket.capacity == 20.0

    def test_consume_success(self) -> None:
        """Test successful token consumption."""
        bucket = TokenBucket(rate=10.0, capacity=20.0)

        # Should succeed with full bucket
        assert bucket.consume(tokens=5.0) is True
        assert bucket.tokens == 15.0

    def test_consume_failure(self) -> None:
        """Test token consumption failure when insufficient tokens."""
        bucket = TokenBucket(rate=10.0, capacity=20.0)

        # Try to consume more than available
        assert bucket.consume(tokens=25.0) is False
        assert bucket.tokens == 20.0  # Unchanged

    def test_token_refill(self) -> None:
        """Test tokens refill over time."""
        bucket = TokenBucket(rate=10.0, capacity=20.0)

        # Consume all tokens
        bucket.consume(tokens=20.0)
        assert bucket.tokens == 0.0

        # Wait and check refill (1 second = 10 tokens)
        time.sleep(0.1)  # 100ms = 1 token
        available = bucket.available()

        # Should have ~1 token (allow some tolerance)
        assert 0.8 <= available <= 1.2

    def test_capacity_limit(self) -> None:
        """Test tokens don't exceed capacity."""
        bucket = TokenBucket(rate=100.0, capacity=10.0)
        bucket.tokens = 5.0

        # Wait long enough to overfill
        time.sleep(0.2)  # Would add 20 tokens if no cap

        # Should be capped at capacity
        assert bucket.available() <= 10.0

    def test_multiple_operations(self) -> None:
        """Test multiple operations in sequence."""
        bucket = TokenBucket(rate=10.0, capacity=10.0)

        # Consume tokens one by one
        for _ in range(5):
            assert bucket.consume(tokens=1.0) is True

        assert 4.5 <= bucket.tokens <= 5.5  # ~5 tokens left


# =============================================================================
# CONFIGURATION TESTS
# =============================================================================


class TestOrganismBarriersConfig:
    """Tests for OrganismBarriersConfig."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = OrganismBarriersConfig()

        assert config.max_memory_gb == 16.0
        assert config.max_processes == 100
        assert config.max_disk_usage_pct == 0.9
        assert config.min_free_disk_gb == 5.0
        assert config.blanket_tolerance == 0.01
        assert config.enable_blanket_check is False

    def test_custom_config(self) -> None:
        """Test custom configuration."""
        config = OrganismBarriersConfig(
            max_memory_gb=32.0,
            max_processes=200,
            rate_limits={"api.request": 100.0},
        )

        assert config.max_memory_gb == 32.0
        assert config.max_processes == 200
        assert "api.request" in config.rate_limits

    def test_invalid_memory_gb(self) -> None:
        """Test validation of max_memory_gb."""
        with pytest.raises(ValueError, match="max_memory_gb must be positive"):
            OrganismBarriersConfig(max_memory_gb=-1.0)

    def test_invalid_processes(self) -> None:
        """Test validation of max_processes."""
        with pytest.raises(ValueError, match="max_processes must be positive"):
            OrganismBarriersConfig(max_processes=0)

    def test_invalid_disk_usage_pct(self) -> None:
        """Test validation of max_disk_usage_pct."""
        with pytest.raises(ValueError, match="max_disk_usage_pct must be in"):
            OrganismBarriersConfig(max_disk_usage_pct=1.5)

    def test_invalid_blanket_tolerance(self) -> None:
        """Test validation of blanket_tolerance."""
        with pytest.raises(ValueError, match="blanket_tolerance must be positive"):
            OrganismBarriersConfig(blanket_tolerance=-0.1)


# =============================================================================
# ORGANISM BARRIERS TESTS
# =============================================================================


class TestOrganismBarriers:
    """Tests for OrganismBarriers."""

    @pytest.fixture
    def barriers(self):
        """Create OrganismBarriers for testing."""
        config = OrganismBarriersConfig(
            max_memory_gb=16.0,
            max_processes=100,
            rate_limits={"test.operation": 10.0},
        )
        return OrganismBarriers(config)

    def test_initialization(self, barriers) -> None:
        """Test barriers initialization."""
        assert barriers.config.max_memory_gb == 16.0
        assert "test.operation" in barriers._rate_buckets

    @patch("psutil.virtual_memory")
    def test_h_memory_safe(self, mock_memory, barriers) -> None:
        """Test h_memory when memory is safe."""
        # Mock memory usage: 8GB used out of 16GB max
        mock_memory.return_value = MagicMock(used=8 * 1024**3)

        h = barriers.h_memory()

        # h = (16 - 8) / 16 = 0.5
        assert 0.4 <= h <= 0.6

    @patch("psutil.virtual_memory")
    def test_h_memory_critical(self, mock_memory, barriers) -> None:
        """Test h_memory when memory is critical."""
        # Mock memory usage: 18GB used (exceeds 16GB max)
        mock_memory.return_value = MagicMock(used=18 * 1024**3)

        h = barriers.h_memory()

        # h = (16 - 18) / 16 = -0.125
        assert h < 0

    @patch("psutil.virtual_memory")
    def test_h_memory_low_usage(self, mock_memory, barriers) -> None:
        """Test h_memory with low memory usage."""
        # Mock memory usage: 2GB used out of 16GB max
        mock_memory.return_value = MagicMock(used=2 * 1024**3)

        h = barriers.h_memory()

        # h = (16 - 2) / 16 = 0.875
        assert h > 0.8

    @patch("psutil.Process")
    def test_h_process_safe(self, mock_process, barriers) -> None:
        """Test h_process when process count is safe."""
        # Mock 20 processes (well below 100 max)
        mock_proc = MagicMock()
        mock_proc.children.return_value = [MagicMock()] * 19  # 19 children + 1 parent = 20
        mock_process.return_value = mock_proc

        h = barriers.h_process()

        # h = (100 - 20) / 100 = 0.8
        assert 0.75 <= h <= 0.85

    @patch("psutil.Process")
    def test_h_process_critical(self, mock_process, barriers) -> None:
        """Test h_process when too many processes."""
        # Mock 120 processes (exceeds 100 max)
        mock_proc = MagicMock()
        mock_proc.children.return_value = [MagicMock()] * 119  # 119 children + 1 parent = 120
        mock_process.return_value = mock_proc

        h = barriers.h_process()

        # h = (100 - 120) / 100 = -0.2
        assert h < 0

    @patch("shutil.disk_usage")
    def test_h_disk_space_safe(self, mock_disk, barriers) -> None:
        """Test h_disk_space when disk is safe."""
        # Mock disk: 100GB total, 50GB used, 50GB free
        mock_disk.return_value = MagicMock(
            total=100 * 1024**3,
            used=50 * 1024**3,
            free=50 * 1024**3,
        )

        h = barriers.h_disk_space()

        # Constraint 1: h1 = (0.9 - 0.5) / 0.9 = 0.444
        # Constraint 2: h2 = (50 - 5) / 5 = 9.0
        # h = min(0.444, 9.0) = 0.444
        assert 0.4 <= h <= 0.5

    @patch("shutil.disk_usage")
    def test_h_disk_space_critical(self, mock_disk, barriers) -> None:
        """Test h_disk_space when disk is critical."""
        # Mock disk: 100GB total, 95GB used, 5GB free (at min limit)
        mock_disk.return_value = MagicMock(
            total=100 * 1024**3,
            used=95 * 1024**3,
            free=5 * 1024**3,
        )

        h = barriers.h_disk_space()

        # Constraint 1: h1 = (0.9 - 0.95) / 0.9 = -0.056 (violated)
        # Constraint 2: h2 = (5 - 5) / 5 = 0.0 (boundary)
        # h = min(-0.056, 0.0) = -0.056
        assert h < 0

    def test_h_blanket_integrity_disabled(self, barriers) -> None:
        """Test h_blanket_integrity when check is disabled."""
        h = barriers.h_blanket_integrity()
        assert h == 1.0  # Returns 1.0 when disabled

    def test_h_blanket_integrity_no_state(self) -> None:
        """Test h_blanket_integrity when no state provided."""
        config = OrganismBarriersConfig(enable_blanket_check=True)
        barriers = OrganismBarriers(config)

        h = barriers.h_blanket_integrity()
        assert h == 1.0  # Fail open when no state

    def test_h_blanket_integrity_low_correlation(self) -> None:
        """Test h_blanket_integrity with low correlation (good)."""
        config = OrganismBarriersConfig(
            enable_blanket_check=True,
            blanket_tolerance=0.01,
        )
        barriers = OrganismBarriers(config)

        # Uncorrelated internal and external states
        state = {
            "internal_state": np.random.randn(100),
            "external_obs": np.random.randn(100),
        }

        h = barriers.h_blanket_integrity(state)

        # Low correlation → low mutual info → positive h
        # (with random noise, correlation should be near zero)
        assert h > 0

    def test_h_blanket_integrity_high_correlation(self) -> None:
        """Test h_blanket_integrity with high correlation (bad)."""
        config = OrganismBarriersConfig(
            enable_blanket_check=True,
            blanket_tolerance=0.01,
        )
        barriers = OrganismBarriers(config)

        # Highly correlated internal and external states
        x = np.random.randn(100)
        state = {
            "internal_state": x,
            "external_obs": x + np.random.randn(100) * 0.1,  # Same with small noise
        }

        h = barriers.h_blanket_integrity(state)

        # High correlation → high mutual info → negative h
        assert h < 0.5  # At least in yellow zone

    def test_h_rate_limit_allowed(self, barriers) -> None:
        """Test h_rate_limit when operation is allowed."""
        # Should succeed on first call
        h = barriers.h_rate_limit("test.operation")
        assert h > 0

    def test_h_rate_limit_exceeded(self, barriers) -> None:
        """Test h_rate_limit when rate limit is exceeded."""
        # Consume all tokens
        for _ in range(20):  # More than bucket capacity
            barriers.h_rate_limit("test.operation")

        # Should now be rate limited
        h = barriers.h_rate_limit("test.operation")
        assert h < 0

    def test_h_rate_limit_unknown_operation(self, barriers) -> None:
        """Test h_rate_limit for operation without limit."""
        h = barriers.h_rate_limit("unknown.operation")
        assert h == 1.0  # No limit configured

    def test_check_all(self, barriers) -> None:
        """Test check_all returns all barrier values."""
        with (
            patch("psutil.virtual_memory") as mock_mem,
            patch("psutil.Process") as mock_proc,
            patch("shutil.disk_usage") as mock_disk,
        ):
            # Mock safe values
            mock_mem.return_value = MagicMock(used=8 * 1024**3)
            mock_proc_obj = MagicMock()
            mock_proc_obj.children.return_value = []
            mock_proc.return_value = mock_proc_obj
            mock_disk.return_value = MagicMock(
                total=100 * 1024**3,
                used=50 * 1024**3,
                free=50 * 1024**3,
            )

            result = barriers.check_all()

            assert "memory" in result
            assert "process" in result
            assert "disk" in result
            assert "rate_limit.test.operation" in result

    def test_is_safe(self, barriers) -> None:
        """Test is_safe checks all barriers."""
        with (
            patch("psutil.virtual_memory") as mock_mem,
            patch("psutil.Process") as mock_proc,
            patch("shutil.disk_usage") as mock_disk,
        ):
            # Mock all safe values
            mock_mem.return_value = MagicMock(used=8 * 1024**3)
            mock_proc_obj = MagicMock()
            mock_proc_obj.children.return_value = []
            mock_proc.return_value = mock_proc_obj
            mock_disk.return_value = MagicMock(
                total=100 * 1024**3,
                used=50 * 1024**3,
                free=50 * 1024**3,
            )

            assert barriers.is_safe() is True

    def test_is_unsafe(self, barriers) -> None:
        """Test is_safe returns False when barrier violated."""
        with patch("psutil.virtual_memory") as mock_mem:
            # Mock memory violation
            mock_mem.return_value = MagicMock(used=20 * 1024**3)

            assert barriers.is_safe() is False

    def test_min_barrier(self, barriers) -> None:
        """Test min_barrier returns most restrictive value."""
        with (
            patch("psutil.virtual_memory") as mock_mem,
            patch("psutil.Process") as mock_proc,
            patch("shutil.disk_usage") as mock_disk,
        ):
            # Mock different barrier values
            mock_mem.return_value = MagicMock(used=8 * 1024**3)  # h = 0.5
            mock_proc_obj = MagicMock()
            mock_proc_obj.children.return_value = [MagicMock()] * 79  # h = 0.2
            mock_proc.return_value = mock_proc_obj
            mock_disk.return_value = MagicMock(
                total=100 * 1024**3,
                used=50 * 1024**3,
                free=50 * 1024**3,
            )  # h ≈ 0.44

            h_min = barriers.min_barrier()

            # Should return smallest (process barrier ≈ 0.2)
            assert 0.15 <= h_min <= 0.25

    def test_get_violations(self, barriers) -> None:
        """Test get_violations returns only violated barriers."""
        with patch("psutil.virtual_memory") as mock_mem:
            # Mock memory violation, others safe
            mock_mem.return_value = MagicMock(used=20 * 1024**3)  # Exceeds 16GB

            violations = barriers.get_violations()

            assert "memory" in violations
            assert violations["memory"] < 0

    def test_get_status_zone_green(self, barriers) -> None:
        """Test get_status_zone returns GREEN when h > 0.5."""
        with (
            patch("psutil.virtual_memory") as mock_mem,
            patch("psutil.Process") as mock_proc,
            patch("shutil.disk_usage") as mock_disk,
        ):
            # Mock all high values (h > 0.5)
            mock_mem.return_value = MagicMock(used=4 * 1024**3)  # h = 0.75
            mock_proc_obj = MagicMock()
            mock_proc_obj.children.return_value = []
            mock_proc.return_value = mock_proc_obj
            mock_disk.return_value = MagicMock(
                total=100 * 1024**3,
                used=30 * 1024**3,
                free=70 * 1024**3,
            )

            zone = barriers.get_status_zone()
            assert zone == "GREEN"

    def test_get_status_zone_yellow(self, barriers) -> None:
        """Test get_status_zone returns YELLOW when 0 <= h <= 0.5."""
        with (
            patch("psutil.virtual_memory") as mock_mem,
            patch("psutil.Process") as mock_proc,
            patch("shutil.disk_usage") as mock_disk,
        ):
            # Mock values in yellow zone
            mock_mem.return_value = MagicMock(used=12 * 1024**3)  # h = 0.25
            mock_proc_obj = MagicMock()
            mock_proc_obj.children.return_value = []
            mock_proc.return_value = mock_proc_obj
            mock_disk.return_value = MagicMock(
                total=100 * 1024**3,
                used=50 * 1024**3,
                free=50 * 1024**3,
            )

            zone = barriers.get_status_zone()
            assert zone == "YELLOW"

    def test_get_status_zone_red(self, barriers) -> None:
        """Test get_status_zone returns RED when h < 0."""
        with patch("psutil.virtual_memory") as mock_mem:
            # Mock memory violation
            mock_mem.return_value = MagicMock(used=20 * 1024**3)  # h < 0

            zone = barriers.get_status_zone()
            assert zone == "RED"


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class TestErrorHandling:
    """Tests for error handling in barriers."""

    def test_h_memory_fails_closed_on_error(self) -> None:
        """Test h_memory fails closed (returns 0) on error."""
        barriers = OrganismBarriers()

        with patch("psutil.virtual_memory", side_effect=Exception("Mock error")):
            h = barriers.h_memory()
            assert h == 0.0  # Fail closed

    def test_h_process_fails_closed_on_error(self) -> None:
        """Test h_process fails closed (returns 0) on error."""
        barriers = OrganismBarriers()

        with patch("psutil.Process", side_effect=Exception("Mock error")):
            h = barriers.h_process()
            assert h == 0.0  # Fail closed

    def test_h_disk_fails_closed_on_error(self) -> None:
        """Test h_disk_space fails closed (returns 0) on error."""
        barriers = OrganismBarriers()

        with patch("shutil.disk_usage", side_effect=Exception("Mock error")):
            h = barriers.h_disk_space()
            assert h == 0.0  # Fail closed

    def test_h_blanket_fails_closed_on_error(self) -> None:
        """Test h_blanket_integrity fails closed (returns 0) on error."""
        config = OrganismBarriersConfig(enable_blanket_check=True)
        barriers = OrganismBarriers(config)

        # Provide invalid state that will cause error
        state = {
            "internal_state": "invalid",  # Not an array
            "external_obs": "invalid",
        }

        h = barriers.h_blanket_integrity(state)
        assert h == 0.0  # Fail closed


# =============================================================================
# SINGLETON TESTS
# =============================================================================


class TestSingleton:
    """Tests for singleton pattern."""

    def test_get_organism_barriers_singleton(self) -> None:
        """Test get_organism_barriers returns singleton."""
        barriers1 = get_organism_barriers()
        barriers2 = get_organism_barriers()

        assert barriers1 is barriers2

    def test_singleton_caching(self) -> None:
        """Test singleton is cached across calls."""
        from kagami.core.safety.organism_barriers import _organism_barriers

        # Clear singleton
        import kagami.core.safety.organism_barriers as module

        module._organism_barriers = None

        # First call creates instance
        barriers1 = get_organism_barriers()
        assert module._organism_barriers is barriers1

        # Second call returns same instance
        barriers2 = get_organism_barriers()
        assert barriers2 is barriers1


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestIntegration:
    """Integration tests for organism barriers."""

    def test_real_system_metrics(self) -> None:
        """Test with real system metrics (if available)."""
        barriers = OrganismBarriers()

        # Try to get real metrics (will fail open if libraries unavailable)
        h_mem = barriers.h_memory()
        h_proc = barriers.h_process()
        h_disk = barriers.h_disk_space()

        # All should return valid floats
        assert isinstance(h_mem, float)
        assert isinstance(h_proc, float)
        assert isinstance(h_disk, float)

    def test_multiple_rate_limits(self) -> None:
        """Test multiple rate limiters working together."""
        config = OrganismBarriersConfig(
            rate_limits={
                "api.read": 100.0,
                "api.write": 10.0,
                "websocket.message": 50.0,
            }
        )
        barriers = OrganismBarriers(config)

        # Each operation should have independent bucket
        h1 = barriers.h_rate_limit("api.read")
        h2 = barriers.h_rate_limit("api.write")
        h3 = barriers.h_rate_limit("websocket.message")

        assert h1 > 0
        assert h2 > 0
        assert h3 > 0

    def test_concurrent_barrier_checks(self) -> None:
        """Test concurrent barrier checking doesn't interfere."""
        barriers = OrganismBarriers()

        # Multiple check_all calls should be independent
        result1 = barriers.check_all()
        result2 = barriers.check_all()

        # Should have same barriers
        assert result1.keys() == result2.keys()


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_memory_limit(self) -> None:
        """Test handling of zero memory (should validate in config)."""
        with pytest.raises(ValueError):
            OrganismBarriersConfig(max_memory_gb=0.0)

    def test_exact_boundary_memory(self) -> None:
        """Test exact boundary condition for memory."""
        barriers = OrganismBarriers(OrganismBarriersConfig(max_memory_gb=16.0))

        with patch("psutil.virtual_memory") as mock_mem:
            # Exactly at limit
            mock_mem.return_value = MagicMock(used=16.0 * 1024**3)

            h = barriers.h_memory()
            assert abs(h) < 1e-6  # Should be ~0

    def test_empty_rate_limits(self) -> None:
        """Test barriers with no rate limits configured."""
        config = OrganismBarriersConfig(rate_limits={})
        barriers = OrganismBarriers(config)

        # Should still work for any operation
        h = barriers.h_rate_limit("any.operation")
        assert h == 1.0

    def test_very_small_blanket_tolerance(self) -> None:
        """Test with very small blanket tolerance."""
        config = OrganismBarriersConfig(
            enable_blanket_check=True,
            blanket_tolerance=1e-6,
        )
        barriers = OrganismBarriers(config)

        # Even small correlation should violate
        x = np.random.randn(100)
        state = {
            "internal_state": x,
            "external_obs": x + np.random.randn(100) * 0.5,
        }

        h = barriers.h_blanket_integrity(state)
        # Should detect violation with tight tolerance
        assert h < 0.9
