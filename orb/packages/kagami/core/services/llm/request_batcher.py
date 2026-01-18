"""LLM Request Batcher with Deduplication and Coalescing.

Optimizes LLM API calls by:
1. Batching multiple requests together
2. Deduplicating identical requests
3. Coalescing similar requests
4. Parallel execution where possible

Target: 50%+ reduction in API latency for concurrent requests.

Colony: Nexus (e₄) - Integration
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BatchingStrategy(str, Enum):
    """Strategy for batching LLM requests."""

    TIME_BASED = "time_based"  # Batch within time window
    SIZE_BASED = "size_based"  # Batch when reaching size
    ADAPTIVE = "adaptive"  # Adapt based on load


@dataclass
class LLMRequest:
    """Single LLM request."""

    id: str
    prompt: str
    model: str
    temperature: float = 0.7
    max_tokens: int = 1000
    system_prompt: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    created_at: float = field(default_factory=time.time)

    def cache_key(self) -> str:
        """Generate cache key for deduplication."""
        data = {
            "prompt": self.prompt,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "system_prompt": self.system_prompt,
        }
        content = str(sorted(data.items()))
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass
class LLMResponse:
    """LLM response."""

    request_id: str
    content: str
    model: str
    usage: dict[str, int] | None = None
    latency: float = 0.0
    cached: bool = False
    error: Exception | None = None


@dataclass
class BatchConfig:
    """Configuration for LLM request batching."""

    # Batching strategy
    strategy: BatchingStrategy = BatchingStrategy.ADAPTIVE
    max_batch_size: int = 10
    batch_timeout_ms: int = 100  # Max time to wait for batch
    min_batch_size: int = 2

    # Deduplication
    enable_deduplication: bool = True
    dedup_cache_ttl: int = 300  # 5 minutes

    # Coalescing
    enable_coalescing: bool = True
    similarity_threshold: float = 0.85  # Cosine similarity threshold

    # Parallel execution
    max_parallel_requests: int = 5
    enable_parallel: bool = True

    # Rate limiting
    requests_per_second: float = 10.0
    burst_size: int = 20

    # Retry logic
    max_retries: int = 3
    retry_delay: float = 1.0
    exponential_backoff: bool = True


@dataclass
class BatchStats:
    """Statistics for batch processing."""

    total_requests: int = 0
    deduplicated: int = 0
    coalesced: int = 0
    batches_processed: int = 0
    total_latency: float = 0.0
    cache_hits: int = 0
    errors: int = 0

    @property
    def avg_latency(self) -> float:
        """Average request latency."""
        return self.total_latency / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def dedup_rate(self) -> float:
        """Deduplication rate."""
        return self.deduplicated / self.total_requests if self.total_requests > 0 else 0.0

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate."""
        return self.cache_hits / self.total_requests if self.total_requests > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_requests": self.total_requests,
            "deduplicated": self.deduplicated,
            "coalesced": self.coalesced,
            "batches_processed": self.batches_processed,
            "avg_latency_ms": self.avg_latency * 1000,
            "dedup_rate": self.dedup_rate,
            "cache_hit_rate": self.cache_hit_rate,
            "errors": self.errors,
        }


class RequestBatcher:
    """Batches and optimizes LLM requests."""

    def __init__(self, config: BatchConfig | None = None):
        """Initialize request batcher.

        Args:
            config: Batch configuration
        """
        self.config = config or BatchConfig()
        self._pending_requests: dict[str, LLMRequest] = {}
        self._pending_futures: dict[str, asyncio.Future[LLMResponse]] = {}
        self._dedup_cache: dict[str, LLMResponse] = {}
        self._stats = BatchStats()
        self._lock = asyncio.Lock()
        self._batch_timer: asyncio.Task | None = None
        self._rate_limiter: asyncio.Semaphore | None = None
        self._last_batch_time = 0.0

    async def request(
        self,
        prompt: str,
        model: str = "gpt-4",
        temperature: float = 0.7,
        max_tokens: int = 1000,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Submit LLM request for batched processing.

        Args:
            prompt: User prompt
            model: Model name
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            system_prompt: Optional system prompt
            **kwargs: Additional metadata

        Returns:
            LLM response
        """
        request_id = f"req_{int(time.time() * 1000000)}"

        request = LLMRequest(
            id=request_id,
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            metadata=kwargs,
        )

        self._stats.total_requests += 1

        # Check deduplication cache
        if self.config.enable_deduplication:
            cache_key = request.cache_key()
            if cache_key in self._dedup_cache:
                cached_response = self._dedup_cache[cache_key]
                self._stats.deduplicated += 1
                self._stats.cache_hits += 1
                logger.debug(f"Request deduplicated: {request_id}")
                return LLMResponse(
                    request_id=request_id,
                    content=cached_response.content,
                    model=cached_response.model,
                    usage=cached_response.usage,
                    cached=True,
                )

        # Create future for response
        future: asyncio.Future[LLMResponse] = asyncio.Future()

        async with self._lock:
            self._pending_requests[request_id] = request
            self._pending_futures[request_id] = future

            # Start batch timer if not running
            if self._batch_timer is None or self._batch_timer.done():
                self._batch_timer = asyncio.create_task(self._batch_timeout())

            # Check if we should process batch immediately
            if len(self._pending_requests) >= self.config.max_batch_size:
                asyncio.create_task(self._process_batch())

        # Wait for response
        try:
            response = await asyncio.wait_for(
                future, timeout=self.config.batch_timeout_ms / 1000 * 10
            )
            return response
        except TimeoutError:
            logger.error(f"Request timed out: {request_id}")
            return LLMResponse(
                request_id=request_id,
                content="",
                model=model,
                error=TimeoutError("Request timed out"),
            )

    async def _batch_timeout(self) -> None:
        """Timer to trigger batch processing."""
        await asyncio.sleep(self.config.batch_timeout_ms / 1000)
        await self._process_batch()

    async def _process_batch(self) -> None:
        """Process pending requests as a batch."""
        async with self._lock:
            if not self._pending_requests:
                return

            # Get pending requests
            batch_requests = list(self._pending_requests.values())
            batch_futures = dict(self._pending_futures)

            # Clear pending
            self._pending_requests.clear()
            self._pending_futures.clear()

        logger.info(f"Processing batch of {len(batch_requests)} requests")

        # Apply coalescing if enabled
        if self.config.enable_coalescing:
            batch_requests = await self._coalesce_requests(batch_requests)

        # Process requests
        start_time = time.time()

        if self.config.enable_parallel and len(batch_requests) > 1:
            # Parallel execution
            tasks = []
            for request in batch_requests:
                tasks.append(self._execute_request(request))

            # Limit parallelism
            semaphore = asyncio.Semaphore(self.config.max_parallel_requests)

            async def bounded_execute(req: LLMRequest) -> LLMResponse:
                async with semaphore:
                    return await self._execute_request(req)

            responses = await asyncio.gather(
                *[bounded_execute(req) for req in batch_requests], return_exceptions=True
            )
        else:
            # Sequential execution
            responses = []
            for request in batch_requests:
                response = await self._execute_request(request)
                responses.append(response)

        # Set futures
        for request, response in zip(batch_requests, responses, strict=False):
            if isinstance(response, Exception):
                response_obj = LLMResponse(
                    request_id=request.id,
                    content="",
                    model=request.model,
                    error=response,
                )
                self._stats.errors += 1
            else:
                response_obj = response

            # Cache response if deduplication enabled
            if self.config.enable_deduplication and not response_obj.error:
                cache_key = request.cache_key()
                self._dedup_cache[cache_key] = response_obj
                # Clean old cache entries
                asyncio.create_task(self._cleanup_cache(cache_key))

            # Set future
            future = batch_futures.get(request.id)
            if future and not future.done():
                future.set_result(response_obj)

        batch_time = time.time() - start_time
        self._stats.batches_processed += 1
        self._stats.total_latency += batch_time
        self._last_batch_time = batch_time

        logger.info(
            f"Batch completed: {len(batch_requests)} requests in {batch_time:.2f}s "
            f"({len(batch_requests) / batch_time:.2f} req/s)"
        )

    async def _coalesce_requests(self, requests: list[LLMRequest]) -> list[LLMRequest]:
        """Coalesce similar requests.

        Groups similar requests together and returns representative requests.
        """
        if len(requests) <= 1:
            return requests

        # Simple coalescing: group by exact match first
        groups: dict[str, list[LLMRequest]] = {}
        for request in requests:
            key = f"{request.model}:{request.prompt[:100]}"
            if key not in groups:
                groups[key] = []
            groups[key].append(request)

        # If multiple requests in a group, mark as coalesced
        coalesced_count = sum(len(group) - 1 for group in groups.values() if len(group) > 1)
        self._stats.coalesced += coalesced_count

        # Return one request per group
        return [group[0] for group in groups.values()]

    async def _execute_request(self, request: LLMRequest) -> LLMResponse:
        """Execute single LLM request.

        This should be overridden to call actual LLM service.
        """
        start_time = time.time()

        try:
            # Import here to avoid circular dependency
            from kagami.core.services.llm.service import LLMService

            llm_service = LLMService()

            # Execute request
            response_text = await llm_service.generate(
                prompt=request.prompt,
                model=request.model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                system_prompt=request.system_prompt,
            )

            latency = time.time() - start_time

            return LLMResponse(
                request_id=request.id,
                content=response_text,
                model=request.model,
                latency=latency,
            )

        except Exception as e:
            logger.error(f"Failed to execute LLM request {request.id}: {e}")
            return LLMResponse(
                request_id=request.id,
                content="",
                model=request.model,
                error=e,
                latency=time.time() - start_time,
            )

    async def _cleanup_cache(self, cache_key: str) -> None:
        """Remove cache entry after TTL."""
        await asyncio.sleep(self.config.dedup_cache_ttl)
        self._dedup_cache.pop(cache_key, None)

    async def get_stats(self) -> dict[str, Any]:
        """Get batcher statistics."""
        return {
            **self._stats.to_dict(),
            "pending_requests": len(self._pending_requests),
            "cache_size": len(self._dedup_cache),
            "last_batch_time_ms": self._last_batch_time * 1000,
        }

    async def clear_cache(self) -> None:
        """Clear deduplication cache."""
        self._dedup_cache.clear()


class MultiModelBatcher:
    """Batches requests across multiple LLM providers/models."""

    def __init__(self, config: BatchConfig | None = None):
        """Initialize multi-model batcher."""
        self.config = config or BatchConfig()
        self._batchers: dict[str, RequestBatcher] = {}
        self._lock = asyncio.Lock()

    async def request(
        self,
        prompt: str,
        model: str = "gpt-4",
        **kwargs: Any,
    ) -> LLMResponse:
        """Submit request for batched processing.

        Automatically routes to appropriate batcher based on model.
        """
        # Get or create batcher for model
        async with self._lock:
            if model not in self._batchers:
                self._batchers[model] = RequestBatcher(self.config)

        batcher = self._batchers[model]
        return await batcher.request(prompt, model, **kwargs)

    async def get_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all batchers."""
        stats = {}
        for model, batcher in self._batchers.items():
            stats[model] = await batcher.get_stats()
        return stats


# Global batcher instance
_global_batcher: MultiModelBatcher | None = None


async def get_global_batcher() -> MultiModelBatcher:
    """Get or create global batcher instance."""
    global _global_batcher

    if _global_batcher is None:
        _global_batcher = MultiModelBatcher()

    return _global_batcher


# Convenience function for batched LLM calls


async def batched_llm_request(
    prompt: str,
    model: str = "gpt-4",
    temperature: float = 0.7,
    max_tokens: int = 1000,
    system_prompt: str | None = None,
    **kwargs: Any,
) -> str:
    """Make batched LLM request.

    This is a drop-in replacement for direct LLM calls that automatically
    batches requests for better performance.

    Args:
        prompt: User prompt
        model: Model name
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        system_prompt: Optional system prompt
        **kwargs: Additional parameters

    Returns:
        Generated text

    Example:
        # Instead of:
        response = await llm_service.generate(prompt)

        # Use:
        response = await batched_llm_request(prompt)
    """
    batcher = await get_global_batcher()
    response = await batcher.request(
        prompt=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
        **kwargs,
    )

    if response.error:
        raise response.error

    return response.content


# Decorator for automatic batching


def batch_llm_calls(
    model: str = "gpt-4",
    temperature: float = 0.7,
) -> Callable[[Callable[..., Awaitable[str]]], Callable[..., Awaitable[str]]]:
    """Decorator to automatically batch LLM calls.

    Example:
        @batch_llm_calls(model="gpt-4")
        async def generate_summary(text: str) -> str:
            prompt = f"Summarize: {text}"
            return await llm_service.generate(prompt)

        # Multiple calls will be automatically batched
        summaries = await asyncio.gather(
            generate_summary(text1),
            generate_summary(text2),
            generate_summary(text3),
        )
    """

    def decorator(func: Callable[..., Awaitable[str]]) -> Callable[..., Awaitable[str]]:
        async def wrapper(*args: Any, **kwargs: Any) -> str:
            # Extract prompt from function call
            result = await func(*args, **kwargs)

            # If result is a prompt, batch it
            if isinstance(result, str):
                return await batched_llm_request(
                    prompt=result,
                    model=model,
                    temperature=temperature,
                )

            return result

        return wrapper

    return decorator
