"""World Model Initializer for WorldModelService.

CREATED: December 21, 2025

Extracted from WorldModelService to reduce god class complexity.
This module provides initialization logic for KagamiWorldModel, including:
- Environment-based configuration loading
- Device selection
- Checkpoint restoration
- Strange Loop wiring
- SemanticState ↔ CoreState conversion

RESPONSIBILITIES:
=================
1. Check if world model loading is allowed (KAGAMI_LOAD_WORLD_MODEL)
2. Select appropriate device (CUDA, MPS, CPU)
3. Load from checkpoint or create new model
4. Wire Strange Loop to EgoModel and Planner
5. Convert SemanticState to CoreState for compatibility

USAGE:
======
```python
from kagami.core.world_model.initializer import WorldModelInitializer

initializer = WorldModelInitializer()

# Async initialization
model = await initializer.ensure_initialized_async()

# Sync initialization (backward compatibility)
model = initializer.ensure_initialized()

# Strange Loop wiring
initializer.wire_strange_loop(model)
```
"""

from __future__ import annotations

import logging
import os
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.world_model.kagami_world_model import (
        KagamiWorldModel,
    )

logger = logging.getLogger(__name__)


def _lazy_import_torch() -> Any:
    """Lazy import torch to avoid blocking module import.

    OPTIMIZATION (Dec 16, 2025): torch import adds 200-1000ms delay.
    Only import when actually needed for world model operations.
    """
    import torch

    return torch


class WorldModelInitializer:
    """Initialization logic for KagamiWorldModel.

    Handles:
    - Environment-based configuration
    - Device selection (CUDA, MPS, CPU)
    - Checkpoint loading
    - Strange Loop wiring
    - SemanticState → CoreState conversion
    """

    @staticmethod
    def should_load_world_model() -> bool:
        """Return True if world model loading is allowed.

        Tests and constrained environments disable heavyweight model loading via
        `KAGAMI_LOAD_WORLD_MODEL=0`. The service respects this flag.

        Returns:
            True if loading is allowed, False otherwise
        """
        flag = (os.getenv("KAGAMI_LOAD_WORLD_MODEL") or "1").strip().lower()
        if flag in {"0", "false", "off", "no"}:
            return False
        return True

    @staticmethod
    def select_device() -> Any:  # torch.device
        """Pick a reasonable default device for the world model.

        Priority:
        1. KAGAMI_WORLD_MODEL_DEVICE environment variable
        2. CUDA if available
        3. MPS if available (Apple Silicon)
        4. CPU (fallback)

        Returns:
            torch.device instance
        """
        torch = _lazy_import_torch()
        explicit = (os.getenv("KAGAMI_WORLD_MODEL_DEVICE") or "").strip().lower()
        if explicit:
            return torch.device(explicit)
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    async def ensure_initialized_async(
        self,
    ) -> tuple[KagamiWorldModel | None, Any]:  # (model, device)
        """Ensure world model is initialized (ASYNC VERSION).

        Returns:
            (model, device) tuple[Any, ...] where model can be None if loading disabled
        """
        torch = _lazy_import_torch()

        # Respect environment-level guardrails (tests disable external model loading).
        if not self.should_load_world_model():
            logger.info("🌍 WorldModelService: model load disabled (KAGAMI_LOAD_WORLD_MODEL=0)")
            return None, torch.device("cpu")

        # Build/load the model via the refactored factory/checkpoint helpers.
        from kagami.core.world_model.model_factory import (
            KagamiWorldModelFactory,
            load_model_from_checkpoint,
        )

        device = self.select_device()

        # Optional checkpoint loading (preferred in production).
        ckpt = (os.getenv("KAGAMI_WORLD_MODEL_CHECKPOINT") or "").strip()
        candidate_paths: list[str] = []
        if ckpt:
            candidate_paths.append(ckpt)
        # Common default locations used across scripts and schedulers.
        candidate_paths.extend(
            [
                "var/checkpoints/world_model/latest.pt",
                "checkpoints/kagami/latest.pt",
            ]
        )

        model: KagamiWorldModel | None = None

        # OPTIMIZATION: Run model loading in thread pool to avoid blocking event loop
        import asyncio

        loop = asyncio.get_running_loop()

        for p in candidate_paths:
            try:
                if p and os.path.exists(p):
                    # Run model loading in thread pool
                    model = await loop.run_in_executor(
                        None, lambda: load_model_from_checkpoint(p, device=device.type)
                    )
                    logger.info("🌍 Loaded KagamiWorldModel from checkpoint: %s", p)
                    break
            except Exception as e:
                logger.warning("World model checkpoint load failed (%s): %s", p, e)

        if model is None:
            # Fresh init (no checkpoint present).
            bulk_dim_env = os.getenv("KAGAMI_BULK_DIM") or os.getenv("KAGAMI_WORLD_MODEL_BULK_DIM")
            bulk_dim: int | None = None
            if bulk_dim_env:
                try:
                    bulk_dim = int(bulk_dim_env)
                except Exception:
                    bulk_dim = None

            preset = (os.getenv("KAGAMI_WORLD_MODEL_PRESET") or "").strip().lower() or None

            # OPTIMIZATION: Create model in thread pool for fresh init too
            model = await loop.run_in_executor(
                None,
                lambda: KagamiWorldModelFactory.create(
                    preset=preset,
                    bulk_dim=bulk_dim,
                    device=device.type,
                ),
            )
            logger.info(
                "🌍 Created new KagamiWorldModel (preset=%s bulk_dim=%s device=%s)",
                preset,
                bulk_dim or getattr(getattr(model, "config", None), "bulk_dim", None),
                device,
            )

        # Get actual device from model parameters
        if model is not None:
            try:
                device = next(model.parameters()).device
            except StopIteration:
                device = torch.device("cpu")

        return model, device

    def ensure_initialized(self) -> tuple[KagamiWorldModel | None, Any]:
        """Ensure world model is initialized (SYNC wrapper for async).

        Returns:
            (model, device) tuple[Any, ...] where model can be None if loading disabled
        """
        import asyncio

        try:
            # Try to get current event loop
            asyncio.get_running_loop()
            # We're in async context, create task
            return (None, _lazy_import_torch().device("cpu"))  # Can't block in async
        except RuntimeError:
            # No event loop, run synchronously
            return asyncio.run(self.ensure_initialized_async())

    def wire_strange_loop(self, model: KagamiWorldModel) -> bool:
        """Wire Strange Loop to EgoModel and LatentMultimodalPlanner.

        MOVED FROM UnifiedOrchestrator (Dec 6, 2025).

        This enables self-aware prediction and planning:
        - EgoModel gets mu_self for self-prediction
        - LatentMultimodalPlanner gets mu_self for self-aware planning

        Args:
            model: KagamiWorldModel instance

        Returns:
            True if wiring succeeded, False otherwise
        """
        if model is None:
            return False

        # Get Strange Loop from OrganismRSSM (Dec 25, 2025: fixed deprecated rssm attribute)
        rssm = getattr(model, "organism_rssm", None)
        strange_loop = getattr(rssm, "strange_loop", None) if rssm else None

        if strange_loop is None:
            logger.debug("No Strange Loop found in world model - skipping wiring")
            return False

        # Wire EgoModel (if exists on model)
        ego_model = getattr(model, "ego_model", None)
        if ego_model and hasattr(ego_model, "connect_strange_loop"):
            ego_model.connect_strange_loop(strange_loop)
            logger.info("🔗 Wired EgoModel to Strange Loop (mu_self)")

        # Wire LatentMultimodalPlanner via Active Inference
        ai_engine = getattr(model, "_active_inference_engine", None)
        if ai_engine:
            planner = getattr(ai_engine, "planner", None)
            if planner and hasattr(planner, "connect_strange_loop"):
                planner.connect_strange_loop(strange_loop)
                logger.info("🔗 Wired LatentMultimodalPlanner to Strange Loop (mu_self)")

        return True

    def semantic_to_core_state(self, semantic_state: Any, model: KagamiWorldModel) -> Any:
        """Convert SemanticState to CoreState.

        Args:
            semantic_state: SemanticState with embedding
            model: KagamiWorldModel for CoreState construction

        Returns:
            CoreState if successful, None otherwise
        """
        try:
            import numpy as np

            from kagami.core.world_model.kagami_world_model import CoreState

            torch = _lazy_import_torch()

            embedding = semantic_state.embedding
            if isinstance(embedding, np.ndarray):
                embedding = torch.from_numpy(embedding).float()

            if embedding.dim() == 1:
                embedding = embedding.unsqueeze(0).unsqueeze(0)
            elif embedding.dim() == 2:
                embedding = embedding.unsqueeze(1)

            # Canonical semantics:
            # - e8_code: [*, 8] E8 bottleneck code
            # - s7_phase: [*, 7] intrinsic S⁷ phase
            # If the semantic embedding doesn't contain these explicitly, we fall back safely.
            e8 = (
                embedding[..., :8]
                if embedding.shape[-1] >= 8
                else torch.nn.functional.pad(embedding, (0, 8 - embedding.shape[-1]))
            )
            s7 = (
                embedding[..., 8:15]
                if embedding.shape[-1] >= 15
                else torch.zeros(
                    *embedding.shape[:-1], 7, device=embedding.device, dtype=embedding.dtype
                )
            )

            return CoreState(
                e8_code=e8,
                s7_phase=torch.nn.functional.normalize(s7, dim=-1),
                shell_residual=e8,  # 8D E8 shell (consistent with KagamiWorldModel)
                timestamp=time.time(),
                context_hash=getattr(semantic_state, "context_hash", ""),
            )

        except Exception as e:
            logger.debug(f"SemanticState→CoreState conversion failed: {e}")
            return None


__all__ = ["WorldModelInitializer"]
