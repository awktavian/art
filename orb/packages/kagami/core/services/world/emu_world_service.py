from __future__ import annotations

"""Emu3.5 world generation service - native multimodal world learner.

Emu3.5 is a 34B unified vision-language model that:
- Generates interleaved vision-language sequences (visual narrative/guidance)
- Performs Any-to-Image (X2I) editing with high quality
- Supports world exploration with temporal consistency
- Handles text-rich image generation (English + Chinese)
- Uses DiDA for 20× faster visual generation

Architecture:
- Local inference via Emu3.5 repo (requires GPU)
- Supports T2I, X2I, interleaved generation
- Outputs: panorama frames + narrative JSON
- Full receipts/idempotency/metrics

References:
- Model: https://huggingface.co/BAAI/Emu3.5
- Paper: https://arxiv.org/abs/2510.26583
- Project: https://emu.world
"""

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from kagami.core.config import Config, get_bool_config, get_config
from kagami.core.tasks.background_task_manager import get_task_manager

logger = logging.getLogger(__name__)


@dataclass
class EmuWorldJobResult:
    """Result from Emu3.5 world generation."""

    success: bool
    panorama_path: str | None
    world_output_dir: str | None
    narrative_data: dict[str, Any] | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class EmuWorldService:
    """Emu3.5 world generation orchestrator.

    Modes:
    - Local: Direct inference via Emu3.5 Python API
    - Cloud: HTTP to remote Emu server (future)
    - Dry-run: Fast placeholder for testing

    Outputs:
    - panorama.png: Representative first frame
    - frames/: Sequence of generated images
    - narrative.json: Interleaved text descriptions
    """

    def __init__(self) -> None:
        self.enabled = get_bool_config("EMU_WORLD_ENABLED", True)

        # Emu3.5 repo path
        default_emu_repo = Path.home() / "dev" / "Emu3.5"
        emu_repo_env = get_config("EMU_REPO_PATH", "")
        self.emu_repo_path = Path(emu_repo_env or default_emu_repo)

        # Model cache for weights
        self.model_cache = Config.get_model_cache_path() / "emu3.5"
        self.model_cache.mkdir(parents=True, exist_ok=True)

        # Output root
        self.output_root = self.model_cache / "outputs"
        self.output_root.mkdir(parents=True, exist_ok=True)

        # Job tracking
        self._completed_jobs: dict[str, EmuWorldJobResult] = {}

        # Inference engine (lazy-loaded)
        self._engine = None
        self._initialized = False
        self._model_snapshot_path: Path | None = None
        self._vq_snapshot_path: Path | None = None

    async def initialize(self) -> None:
        """Initialize Emu3.5 model for local inference - PRODUCTION ONLY."""
        if self._initialized:
            return

        if not self.enabled:
            raise RuntimeError("EmuWorldService disabled - set[Any] EMU_WORLD_ENABLED=1")

        # Check repo exists
        if not self.emu_repo_path.exists():
            raise RuntimeError(
                f"Emu3.5 repo not found at {self.emu_repo_path}\n"
                "Setup: make forge-emu (or set[Any] EMU_REPO_PATH to an existing checkout)"
            )

        # Initialize real inference engine (NO TEST MODE)
        from kagami.core.services.world.emu_inference import Emu3InferenceEngine

        # Download required snapshots on first run
        (
            self._model_snapshot_path,
            self._vq_snapshot_path,
        ) = await self._ensure_models_downloaded()

        # Create engine
        self._engine = Emu3InferenceEngine(  # type: ignore[assignment]
            self.emu_repo_path,
            self.model_cache,
            self._model_snapshot_path,
            self._vq_snapshot_path,
        )
        try:
            # Initialize with timeout (10 minutes for large model load)
            await asyncio.wait_for(self._engine.initialize(), timeout=600.0)  # type: ignore[attr-defined]
        except TimeoutError:
            logger.error("Emu3.5 initialization timed out after 600s")
            raise RuntimeError("Emu3.5 initialization timed out - check GPU/Disk speed") from None

        logger.info("✅ EmuWorldService initialized with real Emu3.5 inference on MPS")
        self._initialized = True

    async def _ensure_models_downloaded(self) -> tuple[Path, Path]:
        """Download Emu3.5 base + VQ models and return their paths."""
        from huggingface_hub import snapshot_download

        cache_dir = self.model_cache / "models"
        cache_dir.mkdir(parents=True, exist_ok=True)

        loop = asyncio.get_running_loop()

        async def _download(model_id: str) -> Path:
            def _run() -> str:
                return snapshot_download(
                    model_id,
                    cache_dir=str(cache_dir),
                )

            path_str = await loop.run_in_executor(None, _run)
            logger.info(f"✅ Snapshot ready for {model_id}: {path_str}")
            return Path(path_str)

        model_snapshot = await _download("BAAI/Emu3.5")
        vq_snapshot = await _download("BAAI/Emu3.5-VisionTokenizer")
        return model_snapshot, vq_snapshot

    async def generate_world(
        self,
        *,
        prompt: str,
        image_path: str | None = None,
        mode: str = "world_exploration",  # world_exploration, visual_narrative, x2i
        num_steps: int = 5,
        resolution: int = 512,
        wait: bool = True,
        timeout: float | None = None,
        correlation_id: str | None = None,
    ) -> str:
        """Submit world generation job.

        Args:
            prompt: Text description of world to generate
            image_path: Optional reference image
            mode: Generation mode (world_exploration, visual_narrative, x2i)
            num_steps: Number of interleaved steps to generate
            resolution: Image resolution (512/720/1024)
            wait: Wait for completion
            timeout: Max wait time
            correlation_id: Optional correlation ID for receipts

        Returns:
            job_id for tracking
        """
        if not self._initialized:
            await self.initialize()

        job_id = str(uuid4().hex[:16])
        corr_id = correlation_id or job_id
        out_dir = self.output_root / job_id
        out_dir.mkdir(parents=True, exist_ok=True)

        # Emit PLAN receipt
        try:
            from kagami.core.receipts import UnifiedReceiptFacade as URF

            await URF.emit(  # type: ignore[misc]
                correlation_id=corr_id,
                action="plan",
                event_name="EMU_WORLD_GEN_PLAN",
                data={
                    "job_id": job_id,
                    "prompt": prompt[:200],  # Truncate for receipt
                    "mode": mode,
                    "resolution": resolution,
                    "num_steps": num_steps,
                    "has_reference": image_path is not None,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to emit PLAN receipt: {e}")

        # Submit background job
        task_name = await get_task_manager().create_task(
            name=f"emu_world_{job_id}",
            coro=self._run_generation(
                job_id=job_id,
                prompt=prompt,
                image_path=image_path,
                mode=mode,
                num_steps=num_steps,
                resolution=resolution,
                out_dir=out_dir,
                correlation_id=corr_id,
            ),
        )

        if wait:
            try:
                await get_task_manager().wait_for_task(task_name, timeout=timeout)
            except TimeoutError:
                logger.warning(f"Job {job_id} timed out after {timeout}s")

        return job_id

    async def get_result(self, job_id: str) -> EmuWorldJobResult | None:
        """Get job result if completed."""
        return self._completed_jobs.get(job_id)

    async def _run_generation(
        self,
        *,
        job_id: str,
        prompt: str,
        image_path: str | None,
        mode: str,
        num_steps: int,
        resolution: int,
        out_dir: Path,
        correlation_id: str,
    ) -> None:
        """Run Emu3.5 generation (background task)."""
        start_time = time.time()

        try:
            # Emit EXECUTE receipt
            try:
                from kagami.core.receipts import UnifiedReceiptFacade as URF

                await URF.emit(  # type: ignore[misc]
                    correlation_id=correlation_id,
                    action="execute",
                    event_name="EMU_WORLD_GEN_EXECUTE",
                    data={"job_id": job_id, "mode": mode, "started_at": start_time},
                )
            except Exception as e:
                logger.debug(f"Failed to emit EXECUTE receipt: {e}")

            # Ensure engine is initialized
            if self._engine is None:
                raise RuntimeError("Emu3.5 inference engine not initialized") from None

            # Real generation
            if mode == "world_exploration":  # type: ignore[unreachable]
                await self._run_world_exploration(
                    job_id, prompt, image_path, num_steps, resolution, out_dir, correlation_id
                )
            elif mode == "visual_narrative":
                await self._run_visual_narrative(
                    job_id, prompt, num_steps, resolution, out_dir, correlation_id
                )
            elif mode == "x2i":
                await self._run_x2i(job_id, prompt, image_path, resolution, out_dir, correlation_id)
            else:
                raise ValueError(f"Unknown mode: {mode}")

            # Emit metrics
            try:
                from kagami_observability.metrics.emu import (
                    EMU_WORLD_GENERATION_DURATION_SECONDS,
                    EMU_WORLD_GENERATIONS_TOTAL,
                )

                duration = time.time() - start_time
                EMU_WORLD_GENERATIONS_TOTAL.labels(mode=mode, status="success").inc()
                EMU_WORLD_GENERATION_DURATION_SECONDS.labels(mode=mode).observe(duration)
            except Exception as e:
                logger.debug(f"Failed to emit metrics: {e}")

        except Exception as e:
            logger.error(f"Generation failed for {job_id}: {e}")
            self._completed_jobs[job_id] = EmuWorldJobResult(
                success=False, panorama_path=None, world_output_dir=None, error=str(e)
            )

            # Emit failure metrics
            try:
                from kagami_observability.metrics.emu import EMU_WORLD_GENERATIONS_TOTAL

                EMU_WORLD_GENERATIONS_TOTAL.labels(mode=mode, status="error").inc()
            except Exception:
                pass

            # Emit VERIFY receipt (failure)
            try:
                from kagami.core.receipts import UnifiedReceiptFacade as URF

                await URF.emit(  # type: ignore[misc]
                    correlation_id=correlation_id,
                    action="verify",
                    event_name="EMU_WORLD_GEN_VERIFY",
                    data={
                        "job_id": job_id,
                        "success": False,
                        "error": str(e),
                        "duration_seconds": time.time() - start_time,
                    },
                )
            except Exception:
                pass

    async def _run_world_exploration(
        self,
        job_id: str,
        prompt: str,
        image_path: str | None,
        num_steps: int,
        resolution: int,
        out_dir: Path,
        correlation_id: str,
    ) -> None:
        """Run world exploration mode - generates sequence of exploration steps."""
        from PIL import Image as PILImage

        # Load reference image if provided
        reference_image = None
        if image_path:
            reference_image = PILImage.open(image_path).convert("RGB")

        # Generate using real Emu3.5
        results = await self._engine.generate(  # type: ignore[attr-defined]
            prompt=prompt,
            mode="world_exploration",
            reference_image=reference_image,
            num_steps=num_steps,
            guidance_scale=3.0,
        )

        # Save results
        await self._save_generation_results(
            job_id, prompt, results, out_dir, correlation_id, "world_exploration"
        )

    async def _run_visual_narrative(
        self,
        job_id: str,
        prompt: str,
        num_steps: int,
        resolution: int,
        out_dir: Path,
        correlation_id: str,
    ) -> None:
        """Run visual narrative mode - generates story with interleaved images."""
        results = await self._engine.generate(  # type: ignore[attr-defined]
            prompt=prompt,
            mode="visual_narrative",
            num_steps=num_steps,
            guidance_scale=3.0,
        )

        await self._save_generation_results(
            job_id, prompt, results, out_dir, correlation_id, "visual_narrative"
        )

    async def _run_x2i(
        self,
        job_id: str,
        prompt: str,
        image_path: str | None,
        resolution: int,
        out_dir: Path,
        correlation_id: str,
    ) -> None:
        """Run Any-to-Image mode - edits/generates based on reference."""
        from PIL import Image as PILImage

        if not image_path:
            raise ValueError("X2I mode requires reference image")

        reference_image = PILImage.open(image_path).convert("RGB")

        results = await self._engine.generate(  # type: ignore[attr-defined]
            prompt=prompt,
            mode="x2i",
            reference_image=reference_image,
            guidance_scale=2.0,  # Lower guidance for editing
        )

        await self._save_generation_results(job_id, prompt, results, out_dir, correlation_id, "x2i")

    async def _save_generation_results(
        self,
        job_id: str,
        prompt: str,
        results: list[dict[str, Any]],
        out_dir: Path,
        correlation_id: str,
        mode: str,
    ) -> None:
        """Save generation results to disk and update job status."""
        # Create frames directory
        frames_dir = out_dir / "frames"
        frames_dir.mkdir(exist_ok=True)

        # Process results
        narrative_steps = []
        frame_idx = 0
        panorama_path = None

        for item in results:
            if item["type"] == "image":
                # Save image
                frame_path = frames_dir / f"frame_{frame_idx:03d}.png"
                item["content"].save(frame_path)

                if panorama_path is None:
                    # First frame is panorama
                    panorama_path = out_dir / "panorama.png"
                    item["content"].save(panorama_path)

                narrative_steps.append(
                    {
                        "step": frame_idx,
                        "type": "image",
                        "frame": f"frames/frame_{frame_idx:03d}.png",
                    }
                )
                frame_idx += 1

            elif item["type"] == "text":
                narrative_steps.append(
                    {
                        "step": len(narrative_steps),
                        "type": "text",
                        "content": item["content"],
                    }
                )

        # Save narrative JSON
        narrative = {
            "prompt": prompt,
            "mode": mode,
            "steps": narrative_steps,
            "num_frames": frame_idx,
        }

        with open(out_dir / "narrative.json", "w") as f:
            json.dump(narrative, f, indent=2)

        # Update job result
        self._completed_jobs[job_id] = EmuWorldJobResult(
            success=True,
            panorama_path=str(panorama_path) if panorama_path else None,
            world_output_dir=str(out_dir),
            narrative_data=narrative,
            metadata={"mode": mode, "num_frames": frame_idx},
        )

        # Emit VERIFY receipt (success)
        try:
            from kagami.core.receipts import UnifiedReceiptFacade as URF

            await URF.emit(  # type: ignore[misc]
                correlation_id=correlation_id,
                action="verify",
                event_name="EMU_WORLD_GEN_VERIFY",
                data={
                    "job_id": job_id,
                    "success": True,
                    "output_files": ["panorama.png", "narrative.json"],
                    "num_frames": frame_idx,
                    "mode": mode,
                },
            )
        except Exception as e:
            logger.debug(f"Failed to emit VERIFY receipt: {e}")


# Singleton
_emu_world_service: EmuWorldService | None = None


def get_emu_world_service() -> EmuWorldService:
    """Get global EmuWorldService instance."""
    global _emu_world_service
    if _emu_world_service is None:
        _emu_world_service = EmuWorldService()
    return _emu_world_service
