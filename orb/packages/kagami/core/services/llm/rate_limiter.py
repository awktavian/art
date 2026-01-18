"""Adaptive Rate Limiter for LLM Requests.

Extracted from service.py to reduce god module complexity.
Centrality goal: <0.001
"""

import asyncio
import logging
import os
from typing import Any

try:
    import psutil
except Exception:
    psutil = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class AdaptiveLimiter:
    """Adaptive concurrency limiter: adjusts permits using system load signals."""

    def __init__(self) -> None:
        self._min_permits = max(1, int(os.getenv("LLM_MIN_CONCURRENCY", "8")))
        self._max_permits = max(self._min_permits, int(os.getenv("LLM_MAX_CONCURRENCY", "64")))
        self._target_cpu = float(os.getenv("LLM_TARGET_CPU_PERCENT", "95"))
        self._target_free_frac = float(os.getenv("LLM_TARGET_FREE_MEM_FRACTION", "0.05"))
        self._hard_free_guard = float(os.getenv("KAGAMI_MEMORY_GUARD_FRACTION", "0.02"))
        self._update_interval = float(os.getenv("LLM_ADAPTIVE_UPDATE_SECONDS", "1.0"))
        self._allowed = self._max_permits
        self._active = 0
        self._cond = asyncio.Condition()
        self._started = False

    async def __aenter__(self) -> "AdaptiveLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        await self.release()

    async def acquire(self) -> None:
        if not self._started:
            self._maybe_start_background_task()
        async with self._cond:
            while self._active >= max(1, self._allowed):
                await self._cond.wait()
            if self._is_memory_critically_low():
                await asyncio.sleep(0.05)
            self._active += 1

    async def release(self) -> None:
        async with self._cond:
            self._active = max(0, self._active - 1)
            self._cond.notify_all()

    def _maybe_start_background_task(self) -> None:
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._adjust_loop())
            self._started = True
        except (TimeoutError, asyncio.CancelledError):
            self._started = True

    async def _adjust_loop(self) -> None:
        while True:
            try:
                allowed = self._compute_allowed()
                async with self._cond:
                    self._allowed = max(self._min_permits, min(self._max_permits, allowed))
                    self._cond.notify_all()
            except (TimeoutError, asyncio.CancelledError):
                pass
            await asyncio.sleep(self._update_interval)

    def _compute_allowed(self) -> int:
        mem_scale = 1.0
        cpu_scale = 1.0
        if psutil is not None:
            try:
                vm = psutil.virtual_memory()
                free_frac = float(vm.available) / float(vm.total) if vm.total else 0.5
                target_free = max(0.001, self._target_free_frac)
                mem_scale = max(0.0, min(1.0, free_frac / target_free))
            except (ValueError, TypeError):
                mem_scale = 1.0
            try:
                cpu = psutil.cpu_percent(interval=0.05)
                cpu_scale = max(
                    0.0, min(1.0, (self._target_cpu - float(cpu)) / max(1.0, self._target_cpu))
                )
            except (ValueError, TypeError):
                cpu_scale = 1.0
        scale = max(0.0, min(1.0, min(mem_scale, cpu_scale)))
        permitted = int(self._min_permits + (self._max_permits - self._min_permits) * scale)
        return max(self._min_permits, permitted)

    def _is_memory_critically_low(self) -> bool:
        if not psutil:
            return False
        try:
            vm = psutil.virtual_memory()
            free_frac = float(vm.available) / float(vm.total) if vm.total else 1.0
            return free_frac <= self._hard_free_guard
        except (ValueError, TypeError):
            return False


# Global limiter instances
_adaptive_limiter: AdaptiveLimiter | None = None
_llm_semaphore: asyncio.Semaphore | None = None


def get_adaptive_limiter() -> AdaptiveLimiter:
    """Get or create the global adaptive limiter instance."""
    global _adaptive_limiter
    if _adaptive_limiter is None:
        _adaptive_limiter = AdaptiveLimiter()
    return _adaptive_limiter


def get_llm_semaphore() -> asyncio.Semaphore:
    """Get or create the global LLM semaphore for basic rate limiting."""
    global _llm_semaphore
    if _llm_semaphore is None:
        max_concurrency = int(os.getenv("LLM_MAX_CONCURRENCY", "64"))
        _llm_semaphore = asyncio.Semaphore(max(1, max_concurrency))
        logger.info(f"✅ LLM concurrency limit: {max_concurrency}")
    return _llm_semaphore
