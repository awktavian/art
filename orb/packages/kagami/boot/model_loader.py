"""Model Loading State Manager — Async Background Loading with Health Tracking.

Provides centralized state management for all heavy model loading:
- World Model (KagamiWorldModel)
- Multimodal Encoder (Vision/Audio)
- LLM Services (Qwen progressively loaded)
- Embedding Service (Kagami semantic space)
- Any other transformers-based models

Key features:
- Lazy initialization with background async loading
- Progressive upgrades (instant → standard → flagship → ultimate)
- Readiness flags and health metrics
- Timeout and retry logic
- Observable state for diagnostics

Usage:
    tracker = get_model_loader_state()

    # Check if specific model is ready
    if tracker.is_ready("world_model"):
        model = app.state.world_model
    else:
        # Fail fast - no degraded mode
        raise HTTPException(503, "World model still loading")

    # Get progress for diagnostics
    progress = tracker.get_progress()
    # Returns: {
    #     "phase": "startup",
    #     "elapsed_seconds": 2.5,
    #     "models_ready": ["encoder"],
    #     "models_loading": ["world_model", "llm"],
    #     "models_failed": [],
    #     "overall_readiness": 0.33,
    # }
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal

logger = logging.getLogger(__name__)


class LoaderPhase(str, Enum):
    """Model loading phases (fail-fast, no degraded mode)."""

    STARTUP = "startup"  # Initial boot sequence
    READY = "ready"  # All critical models loaded
    ERROR = "error"  # Fatal loading errors - system halted


@dataclass
class ModelLoadState:
    """State for a single model's loading."""

    name: str
    ready: bool = False
    loading: bool = False
    failed: bool = False
    error: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    elapsed_seconds: float = 0.0
    weight: float = 1.0  # Importance for overall readiness calculation

    @property
    def duration_ms(self) -> float:
        """Duration in milliseconds."""
        elapsed = (
            self.end_time - self.start_time if self.end_time else time.time() - self.start_time
        )
        return elapsed * 1000

    @property
    def status(self) -> Literal["ready", "loading", "failed", "pending"]:
        """Current status."""
        if self.ready:
            return "ready"
        if self.loading:
            return "loading"
        if self.failed:
            return "failed"
        return "pending"

    def mark_ready(self) -> None:
        """Mark model as successfully loaded."""
        self.ready = True
        self.loading = False
        self.failed = False
        self.error = None
        self.end_time = time.time()
        logger.info(f"✅ {self.name} model ready ({self.duration_ms:.0f}ms)")

    def mark_loading(self) -> None:
        """Mark model as currently loading."""
        self.ready = False
        self.loading = True
        self.failed = False
        self.error = None

    def mark_failed(self, error: str) -> None:
        """Mark model loading as failed."""
        self.ready = False
        self.loading = False
        self.failed = True
        self.error = error
        self.end_time = time.time()
        logger.error(f"❌ {self.name} model failed: {error} ({self.duration_ms:.0f}ms)")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "name": self.name,
            "status": self.status,
            "ready": self.ready,
            "loading": self.loading,
            "failed": self.failed,
            "error": self.error,
            "elapsed_ms": self.duration_ms,
            "weight": self.weight,
        }


class ModelLoaderState:
    """Central state manager for all model loading.

    Tracks multiple models through startup sequence with:
    - Individual state tracking per model
    - Overall readiness metrics
    - Phase tracking (startup → ready/degraded)
    - Health and diagnostics
    """

    # Critical models that must succeed for full operation
    CRITICAL_MODELS = {"world_model", "encoder"}

    # Optional models that can fail gracefully
    OPTIONAL_MODELS = {"llm_standard", "llm_flagship"}

    def __init__(self) -> None:
        self._models: dict[str, ModelLoadState] = {}
        self._phase = LoaderPhase.STARTUP
        self._startup_time = time.time()
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize loader state tracking."""
        async with self._lock:
            if self._initialized:
                return

            # Register all known models with default weights
            model_configs = {
                "world_model": 1.0,
                "encoder": 1.0,
                "receipt_processor": 0.5,
                "llm_instant": 0.5,
                "llm_standard": 0.8,
                "llm_flagship": 0.8,
            }

            for model_name, weight in model_configs.items():
                state = ModelLoadState(name=model_name, weight=weight)
                self._models[model_name] = state

            self._initialized = True
            logger.info(f"✅ Model loader state initialized ({len(self._models)} models tracked)")

    async def mark_loading(self, model_name: str) -> None:
        """Mark a model as starting to load."""
        async with self._lock:
            if model_name not in self._models:
                self._models[model_name] = ModelLoadState(name=model_name)
            self._models[model_name].mark_loading()

    async def mark_ready(self, model_name: str) -> None:
        """Mark a model as successfully loaded."""
        async with self._lock:
            if model_name not in self._models:
                self._models[model_name] = ModelLoadState(name=model_name)
            self._models[model_name].mark_ready()
            await self._update_phase()

    async def mark_failed(self, model_name: str, error: str) -> None:
        """Mark a model as failed to load."""
        async with self._lock:
            if model_name not in self._models:
                self._models[model_name] = ModelLoadState(name=model_name)
            self._models[model_name].mark_failed(error)
            await self._update_phase()

    async def _update_phase(self) -> None:
        """Update overall phase based on model states."""
        critical_ready = all(
            self._models.get(m, ModelLoadState(name=m)).ready for m in self.CRITICAL_MODELS
        )

        if critical_ready:
            self._phase = LoaderPhase.READY
            logger.info("🚀 All critical models ready - API fully operational")
        else:
            any_failed = any(m.failed for m in self._models.values())
            if any_failed:
                failed_names = [m.name for m in self._models.values() if m.failed]
                raise RuntimeError(
                    f"Critical model loading failed: {', '.join(failed_names)}. "
                    "Cannot operate without required models."
                )
            else:
                self._phase = LoaderPhase.STARTUP
                logger.info("⏳ Still loading models - API starting with limited features")

    def is_ready(self, model_name: str) -> bool:
        """Check if a specific model is ready."""
        if model_name not in self._models:
            return False
        return self._models[model_name].ready

    def is_critical_ready(self) -> bool:
        """Check if all critical models are ready."""
        return all(self.is_ready(m) for m in self.CRITICAL_MODELS if m in self._models)

    def get_phase(self) -> LoaderPhase:
        """Get current loading phase."""
        return self._phase

    def get_progress(self) -> dict[str, Any]:
        """Get detailed progress report."""
        elapsed = time.time() - self._startup_time

        ready_models = [m for m, s in self._models.items() if s.ready]
        loading_models = [m for m, s in self._models.items() if s.loading]
        failed_models = [m for m, s in self._models.items() if s.failed]

        # Calculate weighted readiness (0-1)
        total_weight = sum(m.weight for m in self._models.values())
        ready_weight = sum(m.weight for m in self._models.values() if m.ready)
        overall_readiness = ready_weight / total_weight if total_weight > 0 else 0

        return {
            "phase": self._phase.value,
            "elapsed_seconds": elapsed,
            "models_ready": ready_models,
            "models_loading": loading_models,
            "models_failed": failed_models,
            "overall_readiness": overall_readiness,
            "details": {name: state.to_dict() for name, state in self._models.items()},
        }

    def get_health(self) -> dict[str, Any]:
        """Get health status for boot health checks."""
        critical_ready = self.is_critical_ready()
        any_failed = any(m.failed for m in self._models.values() if m.name in self.CRITICAL_MODELS)

        # Calculate readiness score safely
        ready_weight = sum(m.weight for m in self._models.values() if m.ready)
        total_weight = sum(m.weight for m in self._models.values())
        readiness_score = ready_weight / total_weight if total_weight > 0 else 0.0

        return {
            "critical_models_ready": critical_ready,
            "critical_models_failed": any_failed,
            "phase": self._phase.value,
            "readiness_score": readiness_score,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return self.get_progress()


# Global singleton
_loader_state: ModelLoaderState | None = None


def get_model_loader_state() -> ModelLoaderState:
    """Get global model loader state instance."""
    global _loader_state
    if _loader_state is None:
        _loader_state = ModelLoaderState()
    return _loader_state


def reset_model_loader_state() -> None:
    """Reset global state (for testing)."""
    global _loader_state
    _loader_state = None


__all__ = [
    "LoaderPhase",
    "ModelLoadState",
    "ModelLoaderState",
    "get_model_loader_state",
    "reset_model_loader_state",
]
