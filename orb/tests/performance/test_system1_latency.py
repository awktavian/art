"""
Performance tests for System 1 (fast instincts) latency.

System 1 instincts must respond in <5ms to meet design targets.
Tests actual timing with multiple iterations to get reliable measurements.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_e2e


import asyncio
import time
from statistics import mean

import numpy as np


class TestSystem1LatencySLOs:
    """Test System 1 instinct latency meets <5ms SLO."""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_prediction_instinct_latency(self):
        """Prediction instinct must respond in <5ms p95."""
        from kagami.core.instincts.prediction_instinct import PredictionInstinct

        instinct = PredictionInstinct()
        action = {"action": "read", "target": "file"}

        # Warm up (10 iterations)
        for _ in range(10):
            await instinct.predict(action)

        # Measure (100 iterations)
        durations = []
        for _ in range(100):
            start = time.perf_counter()
            await instinct.predict(action)
            durations.append((time.perf_counter() - start) * 1000)  # Convert to ms

        # Calculate statistics
        p50 = np.percentile(durations, 50)
        p95 = np.percentile(durations, 95)
        p99 = np.percentile(durations, 99)
        avg = mean(durations)

        print("\nPrediction Instinct Latency:")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")
        print(f"  avg: {avg:.2f}ms")

        # SLO assertions
        assert p95 < 5.0, f"p95 latency {p95:.2f}ms exceeds 5ms SLO"
        assert p99 < 10.0, f"p99 latency {p99:.2f}ms exceeds 10ms ceiling"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_threat_instinct_latency(self):
        """Threat instinct must respond in <5ms p95."""
        from kagami.core.instincts.threat_instinct import ThreatInstinct

        instinct = ThreatInstinct()
        action = {"action": "read", "target": "public_data"}

        # Warm up
        for _ in range(10):
            await instinct.assess(action)

        # Measure
        durations = []
        for _ in range(100):
            start = time.perf_counter()
            await instinct.assess(action)
            durations.append((time.perf_counter() - start) * 1000)

        p50 = np.percentile(durations, 50)
        p95 = np.percentile(durations, 95)
        p99 = np.percentile(durations, 99)

        print("\nThreat Instinct Latency:")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        assert p95 < 5.0, f"p95 latency {p95:.2f}ms exceeds 5ms SLO"
        assert p99 < 10.0, f"p99 latency {p99:.2f}ms exceeds 10ms ceiling"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_ethical_instinct_latency(self):
        """Ethical instinct must respond in <5ms p95."""
        from kagami.core.instincts.ethical_instinct import EthicalInstinct

        instinct = EthicalInstinct()
        action = {"action": "help", "target": "user"}

        # Warm up
        for _ in range(10):
            await instinct.evaluate(action)

        # Measure
        durations = []
        for _ in range(100):
            start = time.perf_counter()
            await instinct.evaluate(action)
            durations.append((time.perf_counter() - start) * 1000)

        p50 = np.percentile(durations, 50)
        p95 = np.percentile(durations, 95)
        p99 = np.percentile(durations, 99)

        print("\nEthical Instinct Latency:")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        assert p95 < 5.0, f"p95 latency {p95:.2f}ms exceeds 5ms SLO"
        assert p99 < 10.0, f"p99 latency {p99:.2f}ms exceeds 10ms ceiling"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_learning_instinct_latency(self):
        """Learning instinct memory operations must be fast (<5ms p95)."""
        from kagami.core.instincts.learning_instinct import LearningInstinct

        instinct = LearningInstinct()
        context = {"action": "test_task"}
        outcome = {"status": "success", "duration_ms": 100}

        # Warm up
        for _ in range(10):
            await instinct.remember(context, outcome, valence=0.8)

        # Measure
        durations = []
        for _ in range(100):
            start = time.perf_counter()
            await instinct.remember(context, outcome, valence=0.8)
            durations.append((time.perf_counter() - start) * 1000)

        p50 = np.percentile(durations, 50)
        p95 = np.percentile(durations, 95)
        p99 = np.percentile(durations, 99)

        print("\nLearning Instinct Latency:")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        assert p95 < 5.0, f"p95 latency {p95:.2f}ms exceeds 5ms SLO"
        assert p99 < 10.0, f"p99 latency {p99:.2f}ms exceeds 10ms ceiling"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_all_instincts_parallel_latency(self):
        """All 4 instincts running in parallel must complete in <10ms p95."""
        from kagami.core.instincts.ethical_instinct import EthicalInstinct
        from kagami.core.instincts.learning_instinct import LearningInstinct
        from kagami.core.instincts.prediction_instinct import PredictionInstinct
        from kagami.core.instincts.threat_instinct import ThreatInstinct

        prediction = PredictionInstinct()
        threat = ThreatInstinct()
        ethical = EthicalInstinct()
        learning = LearningInstinct()

        action = {"action": "test", "target": "data"}

        # Warm up
        for _ in range(10):
            await asyncio.gather(
                prediction.predict(action),
                threat.assess(action),
                ethical.evaluate(action),
                learning.remember(action, {"status": "ok"}, valence=0.5),
            )

        # Measure parallel execution
        durations = []
        for _ in range(100):
            start = time.perf_counter()
            await asyncio.gather(
                prediction.predict(action),
                threat.assess(action),
                ethical.evaluate(action),
                learning.remember(action, {"status": "ok"}, valence=0.5),
            )
            durations.append((time.perf_counter() - start) * 1000)

        p50 = np.percentile(durations, 50)
        p95 = np.percentile(durations, 95)
        p99 = np.percentile(durations, 99)

        print("\nAll Instincts Parallel Latency:")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")
        print(f"  p99: {p99:.2f}ms")

        # Parallel should be faster than sequential (benefit of async)
        assert p95 < 10.0, f"p95 parallel latency {p95:.2f}ms exceeds 10ms SLO"
        assert p99 < 20.0, f"p99 parallel latency {p99:.2f}ms exceeds 20ms ceiling"


class TestWearableLatencySLOs:
    """Test wearable layer meets <50ms p95 latency SLO."""

    @pytest.mark.performance
    def test_reflex_layer_latency(self) -> None:
        """Reflex layer must respond in <1ms for cache hits."""
        from kagami.core.wearable import ReflexLayer

        reflex = ReflexLayer()

        # Warm up and prime cache
        for _ in range(10):
            reflex.try_reflex("health")

        # Measure cache hits
        durations = []
        for _ in range(1000):  # More iterations for sub-ms timing
            start = time.perf_counter()
            reflex.try_reflex("health")
            durations.append((time.perf_counter() - start) * 1000)

        p50 = np.percentile(durations, 50)
        p95 = np.percentile(durations, 95)
        p99 = np.percentile(durations, 99)

        print("\nReflex Layer Cache Hit Latency:")
        print(f"  p50: {p50:.3f}ms")
        print(f"  p95: {p95:.3f}ms")
        print(f"  p99: {p99:.3f}ms")

        assert p95 < 1.0, f"p95 reflex latency {p95:.3f}ms exceeds 1ms SLO"
        assert p99 < 5.0, f"p99 reflex latency {p99:.3f}ms exceeds 5ms ceiling"

    @pytest.mark.performance
    def test_operation_router_latency(self) -> None:
        """Operation router decision must complete in <10ms."""
        from kagami.core.execution.operation_router import OperationRouter

        router = OperationRouter()
        intent = {"action": "read", "app": "test"}

        # Warm up
        for _ in range(10):
            router.classify_operation(intent, threat_score=0.3)

        # Measure
        durations = []
        for _ in range(100):
            start = time.perf_counter()
            router.classify_operation(intent, threat_score=0.3)
            durations.append((time.perf_counter() - start) * 1000)

        p50 = np.percentile(durations, 50)
        p95 = np.percentile(durations, 95)

        print("\nOperation Router Latency:")
        print(f"  p50: {p50:.2f}ms")
        print(f"  p95: {p95:.2f}ms")

        assert p95 < 10.0, f"p95 router latency {p95:.2f}ms exceeds 10ms SLO"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s", "-m", "performance"])
