"""Progressive Rendering Pipeline for Forge.

Implements draft → final rendering pipeline with:
1. Quick draft previews (low quality, fast)
2. Progressive refinement stages
3. User feedback integration
4. Quality scaling based on resources

Target: Reduce perceived latency by 70% through progressive rendering.

Colony: Forge (e₂)
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class RenderQuality(str, Enum):
    """Rendering quality levels."""

    DRAFT = "draft"  # Quick preview, low quality (5-10s)
    PREVIEW = "preview"  # Medium quality (15-30s)
    PRODUCTION = "production"  # High quality (30-60s)
    FINAL = "final"  # Maximum quality (60-120s)


class RenderStage(str, Enum):
    """Stages in progressive rendering pipeline."""

    CONCEPT = "concept"  # Initial concept generation
    GEOMETRY = "geometry"  # 3D geometry generation
    TEXTURE = "texture"  # Texture generation
    LIGHTING = "lighting"  # Lighting setup
    REFINEMENT = "refinement"  # Quality refinement
    FINALIZATION = "finalization"  # Final touches


@dataclass
class RenderConfig:
    """Configuration for progressive rendering."""

    # Quality settings
    target_quality: RenderQuality = RenderQuality.PRODUCTION
    enable_progressive: bool = True
    skip_to_final: bool = False

    # Stage timing (seconds)
    draft_timeout: float = 10.0
    preview_timeout: float = 30.0
    production_timeout: float = 60.0
    final_timeout: float = 120.0

    # Progressive settings
    stages_to_render: list[RenderStage] = field(
        default_factory=lambda: [
            RenderStage.CONCEPT,
            RenderStage.GEOMETRY,
            RenderStage.TEXTURE,
            RenderStage.LIGHTING,
            RenderStage.REFINEMENT,
        ]
    )

    # Gaussian Splatting settings per quality
    gaussians_per_quality: dict[RenderQuality, int] = field(
        default_factory=lambda: {
            RenderQuality.DRAFT: 10_000,
            RenderQuality.PREVIEW: 50_000,
            RenderQuality.PRODUCTION: 100_000,
            RenderQuality.FINAL: 200_000,
        }
    )

    iterations_per_quality: dict[RenderQuality, int] = field(
        default_factory=lambda: {
            RenderQuality.DRAFT: 500,
            RenderQuality.PREVIEW: 1500,
            RenderQuality.PRODUCTION: 3000,
            RenderQuality.FINAL: 5000,
        }
    )

    # Feedback integration
    enable_user_feedback: bool = True
    feedback_callback: Callable[[str, Any], Awaitable[dict[str, Any]]] | None = None

    # Resource adaptation
    enable_adaptive_quality: bool = True
    gpu_memory_threshold_gb: float = 6.0
    cpu_usage_threshold: float = 80.0


@dataclass
class RenderResult:
    """Result from a rendering stage."""

    stage: RenderStage
    quality: RenderQuality
    output_path: str | None = None
    preview_data: bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    render_time: float = 0.0
    success: bool = False
    error: Exception | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "stage": self.stage.value,
            "quality": self.quality.value,
            "output_path": self.output_path,
            "has_preview": self.preview_data is not None,
            "metadata": self.metadata,
            "render_time": self.render_time,
            "success": self.success,
            "error": str(self.error) if self.error else None,
        }


@dataclass
class ProgressiveRenderState:
    """State tracking for progressive rendering."""

    request_id: str
    prompt: str
    current_stage: RenderStage = RenderStage.CONCEPT
    current_quality: RenderQuality = RenderQuality.DRAFT
    results: dict[RenderStage, RenderResult] = field(default_factory=dict[str, Any])
    start_time: float = field(default_factory=time.time)
    user_feedback: dict[str, Any] = field(default_factory=dict[str, Any])
    canceled: bool = False

    @property
    def elapsed_time(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        stages = list(RenderStage)
        completed = len(self.results)
        return (completed / len(stages)) * 100 if stages else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_id": self.request_id,
            "prompt": self.prompt,
            "current_stage": self.current_stage.value,
            "current_quality": self.current_quality.value,
            "progress_percent": self.progress_percent,
            "elapsed_time": self.elapsed_time,
            "completed_stages": len(self.results),
            "canceled": self.canceled,
        }


class ProgressiveRenderer:
    """Progressive rendering pipeline."""

    def __init__(self, config: RenderConfig | None = None):
        """Initialize progressive renderer.

        Args:
            config: Render configuration
        """
        self.config = config or RenderConfig()
        self._active_renders: dict[str, ProgressiveRenderState] = {}
        self._lock = asyncio.Lock()

    async def render(
        self,
        prompt: str,
        callback: Callable[[RenderResult], Awaitable[None]] | None = None,
    ) -> ProgressiveRenderState:
        """Start progressive rendering.

        Args:
            prompt: Text prompt for generation
            callback: Optional callback for intermediate results

        Returns:
            Final render state with all results
        """
        request_id = f"render_{int(time.time() * 1000)}"

        # Create render state
        state = ProgressiveRenderState(
            request_id=request_id,
            prompt=prompt,
        )

        async with self._lock:
            self._active_renders[request_id] = state

        logger.info(f"Starting progressive render: {request_id}")

        try:
            if self.config.skip_to_final:
                # Skip to final quality
                result = await self._render_stage(
                    state,
                    RenderStage.FINALIZATION,
                    self.config.target_quality,
                )
                state.results[RenderStage.FINALIZATION] = result

                if callback:
                    await callback(result)

            elif self.config.enable_progressive:
                # Progressive rendering through stages
                for stage in self.config.stages_to_render:
                    if state.canceled:
                        logger.info(f"Render canceled: {request_id}")
                        break

                    state.current_stage = stage

                    # Determine quality for this stage
                    quality = self._determine_quality_for_stage(stage)
                    state.current_quality = quality

                    # Render stage
                    result = await self._render_stage(state, stage, quality)
                    state.results[stage] = result

                    # Notify callback with intermediate result
                    if callback:
                        await callback(result)

                    # Check for user feedback
                    if self.config.enable_user_feedback and self.config.feedback_callback:
                        feedback = await self.config.feedback_callback(request_id, result.to_dict())
                        state.user_feedback.update(feedback)

                        # Apply feedback adjustments
                        if feedback.get("cancel"):
                            state.canceled = True
                        elif feedback.get("adjust_quality"):
                            self.config.target_quality = RenderQuality(feedback["adjust_quality"])

            else:
                # Direct rendering at target quality
                result = await self._render_stage(
                    state,
                    RenderStage.FINALIZATION,
                    self.config.target_quality,
                )
                state.results[RenderStage.FINALIZATION] = result

                if callback:
                    await callback(result)

            logger.info(
                f"Progressive render completed: {request_id} "
                f"({state.elapsed_time:.2f}s, {len(state.results)} stages)"
            )

        except Exception as e:
            logger.error(f"Progressive render failed: {request_id}: {e}", exc_info=True)
            state.results[RenderStage.FINALIZATION] = RenderResult(
                stage=RenderStage.FINALIZATION,
                quality=self.config.target_quality,
                success=False,
                error=e,
            )

        finally:
            async with self._lock:
                self._active_renders.pop(request_id, None)

        return state

    def _determine_quality_for_stage(self, stage: RenderStage) -> RenderQuality:
        """Determine quality level for a stage."""
        # Early stages use lower quality
        if stage in [RenderStage.CONCEPT, RenderStage.GEOMETRY]:
            return RenderQuality.DRAFT
        elif stage in [RenderStage.TEXTURE, RenderStage.LIGHTING]:
            return RenderQuality.PREVIEW
        elif stage == RenderStage.REFINEMENT:
            return RenderQuality.PRODUCTION
        else:
            return self.config.target_quality

    async def _render_stage(
        self,
        state: ProgressiveRenderState,
        stage: RenderStage,
        quality: RenderQuality,
    ) -> RenderResult:
        """Render a single stage.

        Args:
            state: Render state
            stage: Stage to render
            quality: Quality level

        Returns:
            Render result
        """
        start_time = time.time()

        logger.info(f"Rendering stage {stage.value} at {quality.value} quality")

        try:
            # Adapt quality based on system resources
            if self.config.enable_adaptive_quality:
                quality = await self._adapt_quality(quality)

            # Route to appropriate renderer
            if stage == RenderStage.CONCEPT:
                result = await self._render_concept(state, quality)
            elif stage == RenderStage.GEOMETRY:
                result = await self._render_geometry(state, quality)
            elif stage == RenderStage.TEXTURE:
                result = await self._render_texture(state, quality)
            elif stage == RenderStage.LIGHTING:
                result = await self._render_lighting(state, quality)
            elif stage == RenderStage.REFINEMENT:
                result = await self._render_refinement(state, quality)
            else:
                result = await self._render_finalization(state, quality)

            result.render_time = time.time() - start_time
            result.success = True

            logger.info(f"Stage {stage.value} completed in {result.render_time:.2f}s")

            return result

        except Exception as e:
            logger.error(f"Stage {stage.value} failed: {e}", exc_info=True)
            return RenderResult(
                stage=stage,
                quality=quality,
                render_time=time.time() - start_time,
                success=False,
                error=e,
            )

    async def _adapt_quality(self, quality: RenderQuality) -> RenderQuality:
        """Adapt quality based on system resources."""
        try:
            import psutil
            import torch

            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if cpu_percent > self.config.cpu_usage_threshold:
                logger.info(f"High CPU usage ({cpu_percent}%), reducing quality")
                quality_levels = list(RenderQuality)
                current_idx = quality_levels.index(quality)
                if current_idx > 0:
                    quality = quality_levels[current_idx - 1]

            # Check GPU memory
            if torch.cuda.is_available():
                device = torch.cuda.current_device()
                total = torch.cuda.get_device_properties(device).total_memory
                allocated = torch.cuda.memory_allocated(device)
                available_gb = (total - allocated) / (1024**3)

                if available_gb < self.config.gpu_memory_threshold_gb:
                    logger.info(f"Low GPU memory ({available_gb:.1f}GB), reducing quality")
                    quality_levels = list(RenderQuality)
                    current_idx = quality_levels.index(quality)
                    if current_idx > 0:
                        quality = quality_levels[current_idx - 1]

        except Exception as e:
            logger.warning(f"Failed to adapt quality: {e}")

        return quality

    async def _render_concept(
        self, state: ProgressiveRenderState, quality: RenderQuality
    ) -> RenderResult:
        """Render concept stage (LLM-based concept generation)."""
        # Use LLM to generate detailed concept
        from kagami.core.services.llm.request_batcher import batched_llm_request

        concept_prompt = f"""Generate a detailed 3D character concept based on: {state.prompt}

Include:
- Physical appearance
- Proportions and measurements
- Color palette
- Style and aesthetic
- Key features

Be specific and detailed."""

        concept = await batched_llm_request(
            prompt=concept_prompt,
            temperature=0.7,
            max_tokens=500,
        )

        return RenderResult(
            stage=RenderStage.CONCEPT,
            quality=quality,
            metadata={"concept": concept, "prompt": state.prompt},
        )

    async def _render_geometry(
        self, state: ProgressiveRenderState, quality: RenderQuality
    ) -> RenderResult:
        """Render geometry stage (Gaussian Splatting)."""
        from kagami.forge.modules.generation.gaussian_splatting import (
            GaussianSplattingConfig,
            GaussianSplattingGenerator,
            GenerationMode,
        )

        # Get concept from previous stage
        concept_result = state.results.get(RenderStage.CONCEPT)
        prompt = concept_result.metadata["concept"] if concept_result else state.prompt

        # Configure based on quality
        config = GaussianSplattingConfig(
            mode=GenerationMode.TEXT_TO_3D,
            num_gaussians=self.config.gaussians_per_quality[quality],
            num_iterations=self.config.iterations_per_quality[quality],
        )

        generator = GaussianSplattingGenerator(config)
        result = await generator.generate(prompt)

        return RenderResult(
            stage=RenderStage.GEOMETRY,
            quality=quality,
            output_path=result.output_path,
            metadata={
                "num_gaussians": result.cloud.num_gaussians if result.cloud else 0,
                "generation_time": result.generation_time,
            },
        )

    async def _render_texture(
        self, state: ProgressiveRenderState, quality: RenderQuality
    ) -> RenderResult:
        """Render texture stage."""
        # Simulate texture generation
        await asyncio.sleep(2.0 if quality == RenderQuality.DRAFT else 5.0)

        return RenderResult(
            stage=RenderStage.TEXTURE,
            quality=quality,
            metadata={"texture_resolution": 1024 if quality == RenderQuality.DRAFT else 2048},
        )

    async def _render_lighting(
        self, state: ProgressiveRenderState, quality: RenderQuality
    ) -> RenderResult:
        """Render lighting stage."""
        # Simulate lighting setup
        await asyncio.sleep(1.0 if quality == RenderQuality.DRAFT else 3.0)

        return RenderResult(
            stage=RenderStage.LIGHTING,
            quality=quality,
            metadata={"light_sources": 2 if quality == RenderQuality.DRAFT else 5},
        )

    async def _render_refinement(
        self, state: ProgressiveRenderState, quality: RenderQuality
    ) -> RenderResult:
        """Render refinement stage."""
        # Simulate refinement
        await asyncio.sleep(3.0 if quality == RenderQuality.PRODUCTION else 8.0)

        return RenderResult(
            stage=RenderStage.REFINEMENT,
            quality=quality,
            metadata={"refinement_passes": 3 if quality == RenderQuality.PRODUCTION else 10},
        )

    async def _render_finalization(
        self, state: ProgressiveRenderState, quality: RenderQuality
    ) -> RenderResult:
        """Render finalization stage."""
        # Combine all previous stages
        await asyncio.sleep(2.0)

        # Collect outputs from previous stages
        outputs = {
            stage.value: result.output_path
            for stage, result in state.results.items()
            if result.output_path
        }

        return RenderResult(
            stage=RenderStage.FINALIZATION,
            quality=quality,
            metadata={"combined_outputs": outputs},
        )

    async def cancel_render(self, request_id: str) -> bool:
        """Cancel an active render.

        Args:
            request_id: Render request ID

        Returns:
            True if canceled successfully
        """
        async with self._lock:
            if request_id in self._active_renders:
                self._active_renders[request_id].canceled = True
                logger.info(f"Canceling render: {request_id}")
                return True
        return False

    async def get_render_state(self, request_id: str) -> dict[str, Any] | None:
        """Get state of an active render.

        Args:
            request_id: Render request ID

        Returns:
            Render state dictionary or None if not found
        """
        async with self._lock:
            state = self._active_renders.get(request_id)
            return state.to_dict() if state else None

    async def get_active_renders(self) -> list[dict[str, Any]]:
        """Get all active renders.

        Returns:
            List of render state dictionaries
        """
        async with self._lock:
            return [state.to_dict() for state in self._active_renders.values()]


# Global renderer instance
_global_renderer: ProgressiveRenderer | None = None


def get_global_renderer() -> ProgressiveRenderer:
    """Get or create global progressive renderer."""
    global _global_renderer

    if _global_renderer is None:
        _global_renderer = ProgressiveRenderer()

    return _global_renderer


# Convenience function for progressive rendering


async def progressive_render(
    prompt: str,
    quality: RenderQuality = RenderQuality.PRODUCTION,
    callback: Callable[[RenderResult], Awaitable[None]] | None = None,
) -> ProgressiveRenderState:
    """Render with progressive quality.

    Args:
        prompt: Text prompt for generation
        quality: Target quality level
        callback: Optional callback for intermediate results

    Returns:
        Final render state

    Example:
        async def on_result(result: RenderResult):
            print(f"Stage {result.stage} completed")

        state = await progressive_render(
            "fantasy warrior character",
            quality=RenderQuality.PRODUCTION,
            callback=on_result,
        )
    """
    renderer = get_global_renderer()
    renderer.config.target_quality = quality

    return await renderer.render(prompt, callback)
