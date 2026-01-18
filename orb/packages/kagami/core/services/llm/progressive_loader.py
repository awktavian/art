"""Progressive Model Loading - Start Fast, Upgrade Smart

Loads models progressively to optimize startup time and memory usage:
- Instant: 0.5B model (1s load, 500MB) - for health checks, routing, simple tasks
- Standard: 1.5B model (3s load, 1.5GB) - for API responses, structured output
- Flagship: 7B model (8s load, 7GB) - for complex reasoning, code generation
- Ultimate: 72B model (60s load, 72GB) - for research-grade quality

Strategy: Load instant immediately, upgrade to standard in background,
load flagship/ultimate only on explicit demand.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any, Literal

logger = logging.getLogger(__name__)

ModelSize = Literal["instant", "standard", "flagship", "ultimate"]


class ProgressiveModelLoader:
    """Load models progressively: instant → standard → flagship → ultimate"""

    # Model configurations - Using Qwen2.5 (transformers-compatible)
    # Qwen3 not yet supported in stable transformers release
    # Run: huggingface-cli download <model> to cache models
    MODELS = {
        "instant": {
            # Qwen2.5-0.5B is transformers-compatible
            "name": "Qwen/Qwen2.5-0.5B-Instruct",
            "size_gb": 0.5,
            "load_time_s": 1,
            "use_cases": ["health_checks", "simple_classification", "routing", "fast_responses"],
        },
        "standard": {
            # Qwen2.5-7B is transformers-compatible
            "name": "Qwen/Qwen2.5-7B-Instruct",
            "size_gb": 7,
            "load_time_s": 3,
            "use_cases": ["api_responses", "structured_output", "chat", "general_tasks"],
        },
        "flagship": {
            # Qwen2.5-14B is transformers-compatible
            "name": "Qwen/Qwen2.5-14B-Instruct",
            "size_gb": 14,
            "load_time_s": 8,
            "use_cases": ["complex_reasoning", "code_generation", "analysis", "research"],
        },
        "ultimate": {
            # Qwen2.5-72B for maximum capability
            "name": "Qwen/Qwen2.5-72B-Instruct",
            "size_gb": 72,
            "load_time_s": 60,
            "use_cases": [
                "research_grade",
                "architecture",
                "world_class_quality",
                "production_critical",
            ],
        },
    }

    def __init__(self) -> None:
        self._models: dict[ModelSize, Any] = {}
        self._loading_tasks: dict[ModelSize, asyncio.Task] = {}
        self._current_level: ModelSize = "instant"
        self._callbacks: list[Callable] = []
        self._initialized = False

    async def initialize(self) -> None:
        """Start progressive loading entirely in background (non-blocking)

        OPTIMIZATION: All model loading happens asynchronously to prevent startup blocking.
        API serves immediately, models load in background.

        This method returns immediately after spawning background tasks.
        No environment variables needed - always non-blocking by design.
        """
        if self._initialized:
            return

        logger.info("🚀 Progressive model loading starting in background...")

        # Mark as initialized immediately - no blocking during boot
        self._initialized = True

        # Load instant model in background (non-blocking)
        # API can serve with fallback/stub responses until ready
        self._loading_tasks["instant"] = asyncio.create_task(self._load_model_background("instant"))

        # Start background upgrade to standard after instant loads
        # Chain tasks: instant → standard (automatic upgrade)
        async def _load_standard_after_instant() -> None:
            """Wait for instant, then load standard"""
            try:
                # Wait for instant to complete
                if "instant" in self._loading_tasks:
                    await self._loading_tasks["instant"]
                # Then load standard
                await self._load_model_background("standard")
            except Exception as e:
                logger.error(f"Background standard loading failed: {e}")

        self._loading_tasks["standard"] = asyncio.create_task(_load_standard_after_instant())

        logger.info("✅ Progressive loader initialized (instant + standard loading in background)")

    async def _load_model(self, size: ModelSize) -> Any:
        """Load model synchronously

        Args:
            size: Model size to load

        Returns:
            Loaded StructuredOutputClient
        """
        if size in self._models:
            return self._models[size]

        config = self.MODELS[size]
        model_name = config["name"]
        assert isinstance(model_name, str), f"Model name must be str, got {type(model_name)}"

        logger.info(
            f"⏳ Loading {size} model: {model_name} "
            f"(~{config['load_time_s']}s, {config['size_gb']}GB)"
        )

        start = time.time()

        try:
            # Import here to avoid circular dependency
            from kagami.core.services.llm.structured_client import StructuredOutputClient

            # Create client
            client = StructuredOutputClient(
                model_name=model_name,
                device="auto",
                load_in_4bit=(size == "ultimate"),  # Only quantize ultimate
                load_in_8bit=False,
            )

            # Initialize (loads model weights)
            # Note: In tests, StructuredOutputClient should be mocked at the class level if needed
            await client.initialize()

            # Cache loaded model
            self._models[size] = client
            duration = time.time() - start

            logger.info(
                f"✅ {size.capitalize()} model loaded in {duration:.1f}s "
                f"(target: {config['load_time_s']}s)"
            )

            # Notify callbacks
            for callback in self._callbacks:
                try:
                    await self._safe_callback(callback, size, client)
                except Exception as e:
                    logger.error(f"Callback error: {e}")

            return client

        except Exception as e:
            logger.error(f"Failed to load {size} model: {e}")
            raise

    async def _safe_callback(self, callback: Callable, size: ModelSize, client: Any) -> None:
        """Safely execute callback (handles both sync and async)"""
        if asyncio.iscoroutinefunction(callback):
            await callback(size, client)
        else:
            callback(size, client)

    async def _load_model_background(self, size: ModelSize) -> None:
        """Load model in background without blocking API"""
        try:
            await self._load_model(size)
            self._current_level = size
            logger.info(f"🔄 Upgraded to {size} model (background load complete)")
        except Exception as e:
            logger.error(f"Background load failed for {size}: {e}")
            # Don't raise - continue serving with current model

    def get_model(self, requested_size: ModelSize | None = None) -> Any:
        """Get best available model

        Args:
            requested_size: Specific size needed (None = use best available)

        Returns:
            Loaded model (may be smaller than requested if not loaded yet)
            Returns None if no models loaded yet (caller should use stub/fallback)

        Raises:
            RuntimeError: Only if progressive loader not initialized at all
        """
        # If specific size requested and available, return it
        if requested_size and requested_size in self._models:
            return self._models[requested_size]

        # Return best available (prefer larger models)
        size_priority: list[ModelSize] = ["ultimate", "flagship", "standard", "instant"]
        for size in size_priority:
            if size in self._models:
                if requested_size and requested_size != size:
                    logger.debug(
                        f"Requested {requested_size} model not loaded, using {size} instead"
                    )
                return self._models[size]

        # No models loaded yet - return None to signal caller to use fallback
        # This is expected during boot when models are loading in background
        if not self._initialized:
            raise RuntimeError("Progressive loader not initialized")

        logger.debug("No models loaded yet - background loading in progress")
        return None

    async def upgrade_to(self, size: ModelSize) -> Any:
        """Upgrade to larger model (load if needed)

        Args:
            size: Target model size

        Returns:
            Loaded model

        Raises:
            RuntimeError: If load fails
        """
        if size in self._models:
            return self._models[size]

        # Check if already loading
        if size in self._loading_tasks:
            task = self._loading_tasks[size]
            if not task.done():
                logger.info(f"Waiting for {size} model to finish loading...")
                await task
                return self._models[size]

        # Load now (will block until complete)
        logger.info(f"🔼 Upgrading to {size} model on-demand...")
        return await self._load_model(size)

    def on_model_loaded(self, callback: Callable) -> None:
        """Register callback for when models finish loading

        Callback signature:
            async def callback(size: ModelSize, model: StructuredOutputClient)
            or
            def callback(size: ModelSize, model: StructuredOutputClient)
        """
        self._callbacks.append(callback)

    def get_status(self) -> dict[str, Any]:
        """Get loading status and available models"""
        models_loaded = list(self._models.keys())
        models_loading = [size for size, task in self._loading_tasks.items() if not task.done()]

        return {
            "current_level": self._current_level,
            "models_loaded": models_loaded,
            "models_loading": models_loading,
            "instant_ready": "instant" in self._models,
            "standard_ready": "standard" in self._models,
            "flagship_ready": "flagship" in self._models,
            "ultimate_ready": "ultimate" in self._models,
            "use_cases": {
                size: config["use_cases"]
                for size, config in self.MODELS.items()
                if size in self._models
            },
        }

    def get_model_info(self, size: ModelSize) -> dict[str, Any]:
        """Get information about a specific model size"""
        if size not in self.MODELS:
            raise ValueError(f"Unknown model size: {size}")

        config = self.MODELS[size]
        is_loaded = size in self._models
        is_loading = size in self._loading_tasks and not self._loading_tasks[size].done()

        return {
            "size": size,
            "name": config["name"],
            "size_gb": config["size_gb"],
            "load_time_s": config["load_time_s"],
            "use_cases": config["use_cases"],
            "loaded": is_loaded,
            "loading": is_loading,
        }


# Global instance
_progressive_loader: ProgressiveModelLoader | None = None


def get_progressive_loader() -> ProgressiveModelLoader:
    """Get global progressive loader instance"""
    global _progressive_loader
    if _progressive_loader is None:
        _progressive_loader = ProgressiveModelLoader()
    return _progressive_loader


def reset_progressive_loader() -> None:
    """Reset global loader (for testing)"""
    global _progressive_loader
    _progressive_loader = None


__all__ = [
    "ModelSize",
    "ProgressiveModelLoader",
    "get_progressive_loader",
    "reset_progressive_loader",
]
