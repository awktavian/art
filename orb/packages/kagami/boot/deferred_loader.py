"""Deferred Model Loading — Non-Blocking Boot with Request Queueing.

CREATED: December 30, 2025

Simple non-blocking model loading:
1. API starts INSTANTLY (no blocking on models)
2. Models load in background
3. Requests queue until model ready
4. Hot-swap to new models at runtime

No tiers. No complexity. Just: loading → ready.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelSlot:
    """A slot holding a model."""

    name: str
    model: Any = None
    ready: bool = False
    loading: bool = False
    error: str | None = None
    load_start: float | None = None
    load_end: float | None = None

    @property
    def load_duration_ms(self) -> float | None:
        if self.load_start and self.load_end:
            return (self.load_end - self.load_start) * 1000
        return None


@dataclass
class QueuedRequest:
    """A request waiting for model."""

    request_id: str
    model_name: str
    handler: Callable[..., Awaitable[Any]]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]
    future: asyncio.Future[Any] = field(
        default_factory=lambda: asyncio.get_event_loop().create_future()
    )
    created_at: float = field(default_factory=time.time)
    timeout: float = 30.0

    @property
    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.timeout


class DeferredModelLoader:
    """Non-blocking model loader with request queueing.

    Simple:
    - Models load in background
    - Requests queue until ready
    - Hot-swap supported
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        self.max_queue_size = max_queue_size
        self._slots: dict[str, ModelSlot] = {}
        self._queues: dict[str, asyncio.Queue[QueuedRequest]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._processors: dict[str, asyncio.Task[None]] = {}
        self._shutting_down = False
        self._initialized = False

    async def register_model(self, name: str) -> None:
        """Register a model slot."""
        if name not in self._slots:
            self._slots[name] = ModelSlot(name=name)
            self._queues[name] = asyncio.Queue(maxsize=self.max_queue_size)
            self._locks[name] = asyncio.Lock()

            # Start queue processor
            self._processors[name] = asyncio.create_task(
                self._process_queue(name),
                name=f"queue_{name}",
            )

    async def load_model(
        self,
        name: str,
        loader: Callable[[], Awaitable[Any]],
    ) -> bool:
        """Load a model in background.

        Args:
            name: Model name
            loader: Async function that returns the model

        Returns:
            True if loaded successfully
        """
        await self.register_model(name)
        slot = self._slots[name]

        async with self._locks[name]:
            slot.loading = True
            slot.load_start = time.time()

        try:
            logger.info(f"📦 Loading {name}...")
            model = await loader()

            async with self._locks[name]:
                slot.model = model
                slot.ready = True
                slot.loading = False
                slot.load_end = time.time()
                slot.error = None

            logger.info(f"✅ {name} ready ({slot.load_duration_ms:.0f}ms)")
            return True

        except Exception as e:
            logger.error(f"❌ {name} failed: {e}")
            async with self._locks[name]:
                slot.loading = False
                slot.error = str(e)
            return False

    async def hot_swap(
        self,
        name: str,
        loader: Callable[[], Awaitable[Any]],
    ) -> bool:
        """Hot-swap a model to a new version.

        Args:
            name: Model name
            loader: Async function that returns the new model

        Returns:
            True if swapped successfully
        """
        if name not in self._slots:
            return False

        slot = self._slots[name]

        try:
            logger.info(f"🔄 Hot-swapping {name}...")
            new_model = await loader()

            async with self._locks[name]:
                old_model = slot.model
                slot.model = new_model

            # Clean up old model
            if old_model is not None:
                del old_model
                gc.collect()
                try:
                    import torch

                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except ImportError:
                    pass

            logger.info(f"✅ {name} hot-swapped")
            return True

        except Exception as e:
            logger.error(f"❌ Hot-swap failed for {name}: {e}")
            return False

    def is_ready(self, name: str) -> bool:
        """Check if model is ready."""
        slot = self._slots.get(name)
        return slot is not None and slot.ready

    def get_model(self, name: str) -> Any | None:
        """Get model if ready, None otherwise."""
        slot = self._slots.get(name)
        if slot and slot.ready:
            return slot.model
        return None

    async def call_when_ready(
        self,
        name: str,
        handler: Callable[..., Awaitable[Any]],
        *args: Any,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> Any:
        """Call handler when model is ready.

        If model ready: calls immediately
        If model loading: queues and waits

        Args:
            name: Model name
            handler: Async function(model, *args, **kwargs)
            timeout: Max wait time

        Returns:
            Handler result
        """
        await self.register_model(name)

        # Fast path: model ready
        slot = self._slots.get(name)
        if slot and slot.ready:
            return await handler(slot.model, *args, **kwargs)

        # Queue the request
        request = QueuedRequest(
            request_id=f"{name}_{time.time()}",
            model_name=name,
            handler=handler,
            args=args,
            kwargs=kwargs,
            timeout=timeout,
        )

        queue = self._queues.get(name)
        if not queue:
            raise RuntimeError(f"No queue for {name}")

        try:
            queue.put_nowait(request)
        except asyncio.QueueFull:
            raise RuntimeError(f"Queue full for {name}") from None

        return await asyncio.wait_for(request.future, timeout=timeout)

    async def _process_queue(self, name: str) -> None:
        """Process queued requests for a model."""
        queue = self._queues[name]

        while not self._shutting_down:
            try:
                request = await asyncio.wait_for(queue.get(), timeout=1.0)
            except TimeoutError:
                continue

            # Check expiration
            if request.is_expired:
                if not request.future.done():
                    request.future.set_exception(TimeoutError("Request expired in queue"))
                continue

            # Check if model ready
            slot = self._slots.get(name)
            if slot and slot.ready:
                try:
                    result = await request.handler(
                        slot.model,
                        *request.args,
                        **request.kwargs,
                    )
                    if not request.future.done():
                        request.future.set_result(result)
                except Exception as e:
                    if not request.future.done():
                        request.future.set_exception(e)
            else:
                # Re-queue
                if not request.is_expired:
                    await queue.put(request)
                    await asyncio.sleep(0.1)

    def get_status(self) -> dict[str, Any]:
        """Get loader status."""
        return {
            "models": {
                name: {
                    "ready": slot.ready,
                    "loading": slot.loading,
                    "error": slot.error,
                    "load_duration_ms": slot.load_duration_ms,
                }
                for name, slot in self._slots.items()
            },
            "queues": {name: queue.qsize() for name, queue in self._queues.items()},
        }

    async def shutdown(self) -> None:
        """Shutdown loader."""
        self._shutting_down = True
        for task in self._processors.values():
            task.cancel()
        await asyncio.gather(*self._processors.values(), return_exceptions=True)


# Singleton
_loader: DeferredModelLoader | None = None


def get_deferred_loader() -> DeferredModelLoader:
    """Get singleton loader."""
    global _loader
    if _loader is None:
        _loader = DeferredModelLoader()
    return _loader


def reset_deferred_loader() -> None:
    """Reset singleton (for testing)."""
    global _loader
    _loader = None


__all__ = [
    "DeferredModelLoader",
    "ModelSlot",
    "get_deferred_loader",
    "reset_deferred_loader",
]
