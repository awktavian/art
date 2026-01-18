"""Batch Processing System for Gaussian Splatting and Character Generation.

Implements parallel batch processing to optimize GPU utilization and reduce
sequential generation bottlenecks.

Target: 50%+ speedup through parallelization
Memory overhead: <20%

Colony: Forge (e₂)
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


class BatchStrategy(str, Enum):
    """Batch processing strategy."""

    PARALLEL = "parallel"  # Process all in parallel
    SEQUENTIAL = "sequential"  # Process one at a time
    CHUNKED = "chunked"  # Process in chunks based on GPU memory
    ADAPTIVE = "adaptive"  # Adapt based on system resources


class Priority(int, Enum):
    """Task priority for queue management."""

    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


@dataclass
class BatchConfig:
    """Configuration for batch processing."""

    # Batch behavior
    max_batch_size: int = 8
    strategy: BatchStrategy = BatchStrategy.ADAPTIVE
    timeout: float = 300.0  # 5 minutes per batch

    # GPU configuration
    gpu_memory_limit_gb: float = 8.0
    estimated_memory_per_item_gb: float = 0.5
    enable_gpu_monitoring: bool = True

    # Queue management
    queue_size: int = 100
    enable_priority_queue: bool = True

    # Performance tuning
    prefetch_count: int = 2
    enable_pipelining: bool = True
    pipeline_stages: int = 3

    # Error handling
    max_retries: int = 3
    retry_delay: float = 1.0
    fail_fast: bool = False


@dataclass
class BatchTask(Generic[T, R]):
    """Single task in a batch."""

    id: str
    input_data: T
    priority: Priority = Priority.NORMAL
    created_at: float = field(default_factory=time.time)
    result: R | None = None
    error: Exception | None = None
    completed: bool = False


@dataclass
class BatchResult(Generic[R]):
    """Result from batch processing."""

    success: bool
    results: list[R]
    errors: list[Exception]
    execution_time: float
    throughput: float  # items per second
    memory_used_gb: float


class BatchQueue(Generic[T, R]):
    """Queue for managing batch tasks."""

    def __init__(self, config: BatchConfig):
        self.config = config
        self._queue: asyncio.Queue[BatchTask[T, R]] = asyncio.Queue(maxsize=config.queue_size)
        self._priority_queue: list[BatchTask[T, R]] = []
        self._lock = asyncio.Lock()

    async def enqueue(self, task: BatchTask[T, R]) -> None:
        """Add task to queue."""
        if self.config.enable_priority_queue and task.priority != Priority.NORMAL:
            async with self._lock:
                self._priority_queue.append(task)
                self._priority_queue.sort(key=lambda t: (-t.priority.value, t.created_at))
        else:
            await self._queue.put(task)

    async def dequeue(self) -> BatchTask[T, R] | None:
        """Get next task from queue."""
        # Check priority queue first
        if self.config.enable_priority_queue and self._priority_queue:
            async with self._lock:
                if self._priority_queue:
                    return self._priority_queue.pop(0)

        # Get from regular queue
        try:
            return await asyncio.wait_for(self._queue.get(), timeout=0.1)
        except TimeoutError:
            return None

    async def dequeue_batch(self, max_size: int | None = None) -> list[BatchTask[T, R]]:
        """Get a batch of tasks from queue."""
        max_size = max_size or self.config.max_batch_size
        batch: list[BatchTask[T, R]] = []

        # Get high-priority tasks first
        if self.config.enable_priority_queue:
            async with self._lock:
                while self._priority_queue and len(batch) < max_size:
                    batch.append(self._priority_queue.pop(0))

        # Fill remaining slots from regular queue
        while len(batch) < max_size:
            task = await self.dequeue()
            if task is None:
                break
            batch.append(task)

        return batch

    async def size(self) -> int:
        """Get total queue size."""
        return self._queue.qsize() + len(self._priority_queue)


class GaussianSplattingBatchProcessor:
    """Batch processor for Gaussian Splatting generation."""

    def __init__(self, config: BatchConfig | None = None):
        self.config = config or BatchConfig()
        self._queue: BatchQueue[dict[str, Any], dict[str, Any]] = BatchQueue(self.config)
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._stats = {
            "total_processed": 0,
            "total_failed": 0,
            "total_time": 0.0,
            "avg_throughput": 0.0,
        }

    async def start(self) -> None:
        """Start batch processing worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._process_batches())
        logger.info("Gaussian Splatting batch processor started")

    async def stop(self) -> None:
        """Stop batch processing worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Gaussian Splatting batch processor stopped")

    async def submit(
        self,
        prompt: str,
        config: dict[str, Any] | None = None,
        priority: Priority = Priority.NORMAL,
    ) -> str:
        """Submit a generation task.

        Args:
            prompt: Text prompt for generation
            config: Generation configuration
            priority: Task priority

        Returns:
            Task ID for tracking
        """
        task_id = f"gs_{int(time.time() * 1000)}"
        task = BatchTask(
            id=task_id,
            input_data={"prompt": prompt, "config": config or {}},
            priority=priority,
        )

        await self._queue.enqueue(task)
        logger.debug(f"Submitted Gaussian Splatting task: {task_id}")
        return task_id

    async def _process_batches(self) -> None:
        """Main worker loop to process batches."""
        while self._running:
            try:
                # Get next batch
                batch = await self._queue.dequeue_batch()

                if not batch:
                    await asyncio.sleep(0.1)
                    continue

                # Determine optimal batch size based on strategy
                batch_size = self._determine_batch_size(len(batch))
                if batch_size < len(batch):
                    # Process in chunks
                    for i in range(0, len(batch), batch_size):
                        chunk = batch[i : i + batch_size]
                        await self._process_batch(chunk)
                else:
                    await self._process_batch(batch)

            except Exception as e:
                logger.error(f"Error in batch processing loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    def _determine_batch_size(self, requested_size: int) -> int:
        """Determine optimal batch size based on strategy and resources."""
        if self.config.strategy == BatchStrategy.SEQUENTIAL:
            return 1

        if self.config.strategy == BatchStrategy.PARALLEL:
            return min(requested_size, self.config.max_batch_size)

        if self.config.strategy == BatchStrategy.CHUNKED:
            # Calculate based on GPU memory
            available_memory = self._get_available_gpu_memory()
            max_items = int(available_memory / self.config.estimated_memory_per_item_gb)
            return min(max_items, requested_size, self.config.max_batch_size)

        # ADAPTIVE
        available_memory = self._get_available_gpu_memory()
        max_items = int(available_memory / self.config.estimated_memory_per_item_gb)

        # Scale based on system load
        import psutil

        cpu_percent = psutil.cpu_percent(interval=0.1)
        if cpu_percent > 80:
            max_items = max(1, max_items // 2)

        return min(max_items, requested_size, self.config.max_batch_size)

    def _get_available_gpu_memory(self) -> float:
        """Get available GPU memory in GB."""
        if not self.config.enable_gpu_monitoring:
            return self.config.gpu_memory_limit_gb

        try:
            import torch

            if torch.cuda.is_available():
                device = torch.cuda.current_device()
                total = torch.cuda.get_device_properties(device).total_memory
                allocated = torch.cuda.memory_allocated(device)
                available = (total - allocated) / (1024**3)
                return min(available * 0.8, self.config.gpu_memory_limit_gb)  # 80% safety margin
        except Exception:
            pass

        return self.config.gpu_memory_limit_gb

    async def _process_batch(
        self, batch: list[BatchTask[dict[str, Any], dict[str, Any]]]
    ) -> BatchResult[dict[str, Any]]:
        """Process a batch of Gaussian Splatting tasks."""
        start_time = time.time()
        results: list[dict[str, Any]] = []
        errors: list[Exception] = []

        logger.info(f"Processing batch of {len(batch)} Gaussian Splatting tasks")

        try:
            if self.config.strategy == BatchStrategy.SEQUENTIAL:
                # Process sequentially
                for task in batch:
                    try:
                        result = await self._generate_single(task.input_data)
                        task.result = result
                        task.completed = True
                        results.append(result)
                    except Exception as e:
                        task.error = e
                        task.completed = True
                        errors.append(e)
                        if self.config.fail_fast:
                            break

            else:
                # Process in parallel
                tasks_to_run = [self._generate_single(task.input_data) for task in batch]

                completed_results = await asyncio.gather(*tasks_to_run, return_exceptions=True)

                for task, result in zip(batch, completed_results, strict=False):
                    if isinstance(result, Exception):
                        task.error = result
                        errors.append(result)
                    else:
                        task.result = result
                        results.append(result)
                    task.completed = True

            execution_time = time.time() - start_time
            throughput = len(results) / execution_time if execution_time > 0 else 0

            # Update stats
            self._stats["total_processed"] += len(results)
            self._stats["total_failed"] += len(errors)
            self._stats["total_time"] += execution_time
            self._stats["avg_throughput"] = (
                self._stats["total_processed"] / self._stats["total_time"]
                if self._stats["total_time"] > 0
                else 0
            )

            # Get memory usage
            memory_used = self._get_current_memory_usage()

            logger.info(
                f"Batch completed: {len(results)} success, {len(errors)} errors, "
                f"{execution_time:.2f}s, {throughput:.2f} items/s, {memory_used:.2f} GB"
            )

            return BatchResult(
                success=len(errors) == 0,
                results=results,
                errors=errors,
                execution_time=execution_time,
                throughput=throughput,
                memory_used_gb=memory_used,
            )

        except Exception as e:
            logger.error(f"Batch processing failed: {e}", exc_info=True)
            return BatchResult(
                success=False,
                results=results,
                errors=[e],
                execution_time=time.time() - start_time,
                throughput=0.0,
                memory_used_gb=0.0,
            )

    async def _generate_single(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate single Gaussian Splatting result.

        This is a wrapper that calls the actual Gaussian Splatting generation.
        """
        # Import here to avoid circular dependency
        from kagami.forge.modules.generation.gaussian_splatting import (
            GaussianSplattingConfig,
            GaussianSplattingGenerator,
            GenerationMode,
        )

        prompt = input_data["prompt"]
        config_dict = input_data.get("config", {})

        # Create config
        config = GaussianSplattingConfig(
            mode=GenerationMode(config_dict.get("mode", "text_to_3d")),
            num_gaussians=config_dict.get("num_gaussians", 100_000),
            num_iterations=config_dict.get("num_iterations", 3000),
        )

        # Create generator
        generator = GaussianSplattingGenerator(config)

        # Generate
        result = await generator.generate(prompt)

        return {
            "success": result.success,
            "output_path": result.output_path,
            "generation_time": result.generation_time,
            "num_gaussians": result.cloud.num_gaussians if result.cloud else 0,
        }

    def _get_current_memory_usage(self) -> float:
        """Get current memory usage in GB."""
        try:
            import torch

            if torch.cuda.is_available():
                device = torch.cuda.current_device()
                return torch.cuda.memory_allocated(device) / (1024**3)
        except Exception:
            pass

        return 0.0

    async def get_stats(self) -> dict[str, Any]:
        """Get processor statistics."""
        return {
            **self._stats,
            "queue_size": await self._queue.size(),
            "running": self._running,
        }


class CharacterGenerationBatchProcessor:
    """Batch processor for character generation."""

    def __init__(self, config: BatchConfig | None = None):
        self.config = config or BatchConfig()
        self._queue: BatchQueue[dict[str, Any], dict[str, Any]] = BatchQueue(self.config)
        self._running = False
        self._worker_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start batch processing worker."""
        if self._running:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._process_batches())
        logger.info("Character generation batch processor started")

    async def stop(self) -> None:
        """Stop batch processing worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("Character generation batch processor stopped")

    async def submit(
        self,
        concept: str,
        style: str | None = None,
        priority: Priority = Priority.NORMAL,
    ) -> str:
        """Submit a character generation task."""
        task_id = f"char_{int(time.time() * 1000)}"
        task = BatchTask(
            id=task_id,
            input_data={"concept": concept, "style": style},
            priority=priority,
        )

        await self._queue.enqueue(task)
        return task_id

    async def _process_batches(self) -> None:
        """Main worker loop to process batches."""
        while self._running:
            try:
                batch = await self._queue.dequeue_batch()

                if not batch:
                    await asyncio.sleep(0.1)
                    continue

                await self._process_batch(batch)

            except Exception as e:
                logger.error(f"Error in character batch processing: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _process_batch(
        self, batch: list[BatchTask[dict[str, Any], dict[str, Any]]]
    ) -> BatchResult[dict[str, Any]]:
        """Process a batch of character generation tasks."""
        start_time = time.time()
        results: list[dict[str, Any]] = []
        errors: list[Exception] = []

        logger.info(f"Processing batch of {len(batch)} character generation tasks")

        # Process in parallel with pipeline
        if self.config.enable_pipelining:
            # Stage 1: Generate concepts
            concepts_tasks = [self._generate_concept(task.input_data["concept"]) for task in batch]
            concepts = await asyncio.gather(*concepts_tasks, return_exceptions=True)

            # Stage 2: Generate 3D models
            models_tasks = []
            for concept in concepts:
                if not isinstance(concept, Exception):
                    models_tasks.append(self._generate_3d_model(concept))
                else:
                    models_tasks.append(asyncio.sleep(0))  # Skip failed concepts

            models = await asyncio.gather(*models_tasks, return_exceptions=True)

            # Stage 3: Generate textures and finalize
            final_tasks = []
            for model in models:
                if not isinstance(model, Exception) and model:
                    final_tasks.append(self._finalize_character(model))
                else:
                    final_tasks.append(asyncio.sleep(0))

            finals = await asyncio.gather(*final_tasks, return_exceptions=True)

            # Collect results
            for task, final in zip(batch, finals, strict=False):
                if isinstance(final, Exception):
                    task.error = final
                    errors.append(final)
                elif final:
                    task.result = final
                    results.append(final)
                task.completed = True

        else:
            # Sequential processing
            for task in batch:
                try:
                    concept = await self._generate_concept(task.input_data["concept"])
                    model = await self._generate_3d_model(concept)
                    final = await self._finalize_character(model)
                    task.result = final
                    results.append(final)
                except Exception as e:
                    task.error = e
                    errors.append(e)
                task.completed = True

        execution_time = time.time() - start_time
        throughput = len(results) / execution_time if execution_time > 0 else 0

        return BatchResult(
            success=len(errors) == 0,
            results=results,
            errors=errors,
            execution_time=execution_time,
            throughput=throughput,
            memory_used_gb=0.0,
        )

    async def _generate_concept(self, concept: str) -> dict[str, Any]:
        """Generate character concept."""
        # Simulate concept generation
        await asyncio.sleep(0.5)
        return {
            "concept": concept,
            "description": f"Generated concept for {concept}",
            "attributes": {},
        }

    async def _generate_3d_model(self, concept: dict[str, Any]) -> dict[str, Any]:
        """Generate 3D model from concept."""
        # Simulate 3D model generation
        await asyncio.sleep(1.0)
        return {
            **concept,
            "model_path": f"/tmp/{concept['concept']}.ply",
            "mesh_generated": True,
        }

    async def _finalize_character(self, model: dict[str, Any]) -> dict[str, Any]:
        """Finalize character with textures."""
        # Simulate texture generation
        await asyncio.sleep(0.8)
        return {
            **model,
            "textured": True,
            "ready": True,
        }


# Global processor instances
_gaussian_processor: GaussianSplattingBatchProcessor | None = None
_character_processor: CharacterGenerationBatchProcessor | None = None


async def get_gaussian_processor() -> GaussianSplattingBatchProcessor:
    """Get or create global Gaussian Splatting processor."""
    global _gaussian_processor

    if _gaussian_processor is None:
        _gaussian_processor = GaussianSplattingBatchProcessor()
        await _gaussian_processor.start()

    return _gaussian_processor


async def get_character_processor() -> CharacterGenerationBatchProcessor:
    """Get or create global character generation processor."""
    global _character_processor

    if _character_processor is None:
        _character_processor = CharacterGenerationBatchProcessor()
        await _character_processor.start()

    return _character_processor
