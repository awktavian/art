from typing import Any

"""Chaos Monkey (Core).

Moved from scripts/testing/chaos_monkey.py to core library for better integration.
"""

import asyncio
import logging
import random
import subprocess
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ChaosEvent:
    """Record of a chaos event."""

    timestamp: float
    target: str
    action: str
    duration_s: float
    recovered: bool


class ChaosMonkey:
    """Inject controlled failures for resilience testing."""

    def __init__(self, targets: list[str], failure_rate: float):
        self.targets = targets
        self.failure_rate = failure_rate
        self.events: list[ChaosEvent] = []
        self.running = True

    async def kill_redis(self, duration: int = 30) -> None:
        """Temporarily stop Redis."""
        logger.info(f"💀 Killing Redis for {duration}s...")
        start_time = time.time()

        try:
            # Pause Redis container
            subprocess.run(["docker-compose", "pause", "redis"], check=True)

            await asyncio.sleep(duration)

            # Unpause Redis
            subprocess.run(["docker-compose", "unpause", "redis"], check=True)

            elapsed = time.time() - start_time
            recovered = True
            logger.info(f"✅ Redis recovered after {elapsed:.1f}s")

        except Exception as e:
            logger.error(f"❌ Redis chaos failed: {e}")
            elapsed = time.time() - start_time
            recovered = False

        self.events.append(
            ChaosEvent(
                timestamp=start_time,
                target="redis",
                action="pause",
                duration_s=elapsed,
                recovered=recovered,
            )
        )

    async def kill_database(self, duration: int = 30) -> None:
        """Temporarily stop database."""
        logger.info(f"💀 Killing database for {duration}s...")
        start_time = time.time()

        try:
            # Pause database container
            subprocess.run(["docker-compose", "pause", "cockroach"], check=True)

            await asyncio.sleep(duration)

            # Unpause database
            subprocess.run(["docker-compose", "unpause", "cockroach"], check=True)

            # Wait for healthy
            await asyncio.sleep(10)

            elapsed = time.time() - start_time
            recovered = True
            logger.info(f"✅ Database recovered after {elapsed:.1f}s")

        except Exception as e:
            logger.error(f"❌ Database chaos failed: {e}")
            elapsed = time.time() - start_time
            recovered = False

        self.events.append(
            ChaosEvent(
                timestamp=start_time,
                target="database",
                action="pause",
                duration_s=elapsed,
                recovered=recovered,
            )
        )

    async def inject_network_latency(self, latency_ms: int = 100, duration: int = 30) -> None:
        """Simulate network latency for resilience testing.

        NOTE: This is a portable placeholder. Real netem/tc integration is
        platform-specific and intentionally not enabled by default.
        """
        logger.warning(
            "🌐 Simulating %sms network latency for %ss (placeholder; no tc/netem applied)",
            latency_ms,
            duration,
        )
        start_time = time.time()
        try:
            await asyncio.sleep(duration)
            elapsed = time.time() - start_time
            recovered = True
        except Exception as e:
            logger.error(f"❌ Network latency chaos failed: {e}")
            elapsed = time.time() - start_time
            recovered = False

        self.events.append(
            ChaosEvent(
                timestamp=start_time,
                target="network",
                action=f"latency_{latency_ms}ms",
                duration_s=elapsed,
                recovered=recovered,
            )
        )

    async def run_chaos(self, duration: int) -> None:
        """Run chaos for specified duration."""
        logger.info(f"🐵 Chaos Monkey starting for {duration}s...")

        start_time = time.time()
        check_interval = 30

        while time.time() - start_time < duration and self.running:
            if random.random() < self.failure_rate:
                target = random.choice(self.targets)
                failure_duration = random.randint(10, 60)

                if target == "redis":
                    await self.kill_redis(failure_duration)
                elif target == "database":
                    await self.kill_database(failure_duration)
                elif target == "network":
                    await self.inject_network_latency(100, failure_duration)

            await asyncio.sleep(check_interval)

        logger.info(f"✅ Chaos Monkey complete: {len(self.events)} events injected")

    def report(self) -> dict[str, Any]:
        """Generate chaos report."""
        if not self.events:
            return {"events": 0}

        recovered = sum(1 for e in self.events if e.recovered)

        return {
            "total_events": len(self.events),
            "recovered_events": recovered,
            "recovery_rate": recovered / len(self.events),
            "events_by_target": {
                target: sum(1 for e in self.events if e.target == target)
                for target in {e.target for e in self.events}
            },
            "avg_duration_s": sum(e.duration_s for e in self.events) / len(self.events),
        }
