"""Tests for forge observability metrics module."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration


from kagami.forge.observability.metrics import (
    CACHE_HITS_TOTAL,
    CACHE_MISSES_TOTAL,
    ERRORS_TOTAL,
    ETHICAL_BLOCKS_TOTAL,
    GENERATION_DURATION,
    GENERATION_TOTAL,
    GPU_USAGE_PERCENT,
    IDEMPOTENCY_CHECKS_TOTAL,
    MEMORY_USAGE_MB,
    QUALITY_SCORE,
    THREAT_SCORE,
    VALIDATION_FAILURES_TOTAL,
)


class TestForgeMetrics:
    """Tests for Forge Prometheus metrics."""

    def test_generation_duration_exists(self) -> None:
        """Test GENERATION_DURATION metric exists."""
        assert GENERATION_DURATION is not None

    def test_generation_duration_labels(self) -> None:
        """Test GENERATION_DURATION has expected labels."""
        # Should be able to call with labels
        GENERATION_DURATION.labels("test_module", "high").observe(0.5)

    def test_generation_total_exists(self) -> None:
        """Test GENERATION_TOTAL metric exists."""
        assert GENERATION_TOTAL is not None

    def test_generation_total_labels(self) -> None:
        """Test GENERATION_TOTAL has expected labels."""
        GENERATION_TOTAL.labels("test_module", "success").inc()

    def test_cache_hits_exists(self) -> None:
        """Test CACHE_HITS_TOTAL metric exists."""
        assert CACHE_HITS_TOTAL is not None

    def test_cache_hits_labels(self) -> None:
        """Test CACHE_HITS_TOTAL has expected labels."""
        CACHE_HITS_TOTAL.labels("test_module").inc()

    def test_cache_misses_exists(self) -> None:
        """Test CACHE_MISSES_TOTAL metric exists."""
        assert CACHE_MISSES_TOTAL is not None

    def test_cache_misses_labels(self) -> None:
        """Test CACHE_MISSES_TOTAL has expected labels."""
        CACHE_MISSES_TOTAL.labels("test_module").inc()

    def test_quality_score_exists(self) -> None:
        """Test QUALITY_SCORE metric exists."""
        assert QUALITY_SCORE is not None

    def test_quality_score_labels(self) -> None:
        """Test QUALITY_SCORE has expected labels."""
        QUALITY_SCORE.labels("test_module", "test_aspect").observe(0.85)

    def test_validation_failures_exists(self) -> None:
        """Test VALIDATION_FAILURES_TOTAL metric exists."""
        assert VALIDATION_FAILURES_TOTAL is not None

    def test_validation_failures_labels(self) -> None:
        """Test VALIDATION_FAILURES_TOTAL has expected labels."""
        VALIDATION_FAILURES_TOTAL.labels("test_module", "test_reason").inc()

    def test_memory_usage_exists(self) -> None:
        """Test MEMORY_USAGE_MB metric exists."""
        assert MEMORY_USAGE_MB is not None

    def test_memory_usage_labels(self) -> None:
        """Test MEMORY_USAGE_MB has expected labels."""
        MEMORY_USAGE_MB.labels("test_module").set(100.5)

    def test_gpu_usage_exists(self) -> None:
        """Test GPU_USAGE_PERCENT metric exists."""
        assert GPU_USAGE_PERCENT is not None

    def test_gpu_usage_labels(self) -> None:
        """Test GPU_USAGE_PERCENT has expected labels."""
        GPU_USAGE_PERCENT.labels("test_module").set(45.0)

    def test_errors_total_exists(self) -> None:
        """Test ERRORS_TOTAL metric exists."""
        assert ERRORS_TOTAL is not None

    def test_errors_total_labels(self) -> None:
        """Test ERRORS_TOTAL has expected labels."""
        ERRORS_TOTAL.labels("test_module", "ValueError").inc()

    def test_ethical_blocks_exists(self) -> None:
        """Test ETHICAL_BLOCKS_TOTAL metric exists."""
        assert ETHICAL_BLOCKS_TOTAL is not None

    def test_ethical_blocks_labels(self) -> None:
        """Test ETHICAL_BLOCKS_TOTAL has expected labels."""
        ETHICAL_BLOCKS_TOTAL.labels("test_reason").inc()

    def test_threat_score_exists(self) -> None:
        """Test THREAT_SCORE metric exists."""
        assert THREAT_SCORE is not None

    def test_threat_score_labels(self) -> None:
        """Test THREAT_SCORE has expected labels."""
        THREAT_SCORE.labels("test_module").observe(0.3)

    def test_idempotency_checks_exists(self) -> None:
        """Test IDEMPOTENCY_CHECKS_TOTAL metric exists."""
        assert IDEMPOTENCY_CHECKS_TOTAL is not None

    def test_idempotency_checks_labels(self) -> None:
        """Test IDEMPOTENCY_CHECKS_TOTAL has expected labels."""
        IDEMPOTENCY_CHECKS_TOTAL.labels("new").inc()
        IDEMPOTENCY_CHECKS_TOTAL.labels("duplicate").inc()
