"""Forge Image Generation Routes.

Image generation using OptimizedImageGenerator with Emu3.5/FLUX.

Integration Points:
- OptimizedImageGenerator: Primary image generation (Emu3.5)
- EmuImageGenerator: Direct Emu3.5 access for X2I editing
- OpenAI: gpt-image-1 fallback (explicit only)

Routes:
- POST /api/command/forge/image - Generate image from prompt
- POST /api/command/forge/image/edit - Edit existing image (X2I)
- GET /api/command/forge/image/status/{job_id} - Check generation status
- GET /api/command/forge/image/result/{job_id} - Get generated image
"""

import base64
import io
import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from kagami_api.auth import User, get_current_user_optional
from kagami_api.services.redis_job_storage import get_job_storage

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/image", tags=["forge-image"])

    # Redis-backed job storage (replaces unbounded dict)
    _job_storage = get_job_storage("image")

    # Temporary file directory for generated images
    _TEMP_DIR = Path(tempfile.gettempdir()) / "kagami_images"
    _TEMP_DIR.mkdir(parents=True, exist_ok=True)

    class ImageGenerationRequest(BaseModel):
        """Image generation request."""

        prompt: str = Field(
            ..., description="Text prompt for image generation", min_length=1, max_length=2000
        )
        negative_prompt: str = Field(default="", description="Negative prompt", max_length=1000)
        width: int = Field(default=1024, ge=256, le=2048)
        height: int = Field(default=1024, ge=256, le=2048)
        steps: int = Field(default=12, ge=1, le=50, description="Inference steps")
        guidance_scale: float = Field(default=0.5, ge=0.0, le=20.0)
        provider: str = Field(
            default="emu",
            description="Provider: emu (Emu3.5), flux (FLUX.1), openai (gpt-image-1)",
        )
        seed: int | None = Field(default=None, description="Random seed for reproducibility")

    class ImageEditRequest(BaseModel):
        """Image editing request (X2I)."""

        prompt: str = Field(..., description="Edit instruction")
        image_base64: str = Field(..., description="Base64-encoded source image")
        mask_base64: str | None = Field(default=None, description="Optional mask for inpainting")
        strength: float = Field(default=0.8, ge=0.0, le=1.0, description="Edit strength")
        width: int | None = Field(default=None, description="Output width (None = preserve)")
        height: int | None = Field(default=None, description="Output height (None = preserve)")

    class ImageGenerationResponse(BaseModel):
        """Image generation response."""

        job_id: str
        status: str
        message: str
        estimated_time_seconds: float | None = None

    class ImageResult(BaseModel):
        """Image generation result."""

        job_id: str
        status: str
        prompt: str
        width: int
        height: int
        provider: str
        generation_time_seconds: float | None = None
        image_base64: str | None = None
        image_url: str | None = None

    async def _run_generation_job(job_id: str, request: ImageGenerationRequest) -> None:
        """Background task to generate image."""
        try:
            # Update status to processing
            await _job_storage.update_job(job_id, status="processing")

            # Use canonical device detection
            from kagami.core.utils.device import get_device

            device = get_device()

            from kagami.forge.optimized_image_generator import (
                ImageGenConfig,
                OptimizedImageGenerator,
            )

            # Configure generator
            config = ImageGenConfig(
                guidance_scale=request.guidance_scale,
                num_inference_steps=request.steps,
                width=request.width,
                height=request.height,
                provider=request.provider,
            )

            generator = OptimizedImageGenerator(device=device, config=config)
            await generator.initialize()

            # Generate image
            use_local = request.provider != "openai"
            image = await generator.generate_image(
                prompt=request.prompt,
                width=request.width,
                height=request.height,
                use_local=use_local,
            )

            # Save image to temporary file (avoid base64 in Redis)
            image_path = _TEMP_DIR / f"{job_id}.png"
            image.save(image_path)

            # Update job with result path
            await _job_storage.update_job(
                job_id,
                status="completed",
                result_path=str(image_path),
            )

            logger.info(f"Image job {job_id} completed: {request.width}x{request.height}")

        except Exception as e:
            logger.error(f"Image job {job_id} failed: {e}")
            await _job_storage.update_job(job_id, status="failed", error=str(e))

    async def _run_edit_job(job_id: str, request: ImageEditRequest) -> None:
        """Background task to edit image."""
        try:
            # Update status to processing
            await _job_storage.update_job(job_id, status="processing")

            from PIL import Image

            # Decode source image
            image_bytes = base64.b64decode(request.image_base64)
            source_image = Image.open(io.BytesIO(image_bytes))

            # Get Emu generator for X2I editing
            from kagami.forge.emu_image_generator import get_emu_image_generator

            emu_gen = get_emu_image_generator()
            if not emu_gen._initialized:
                await emu_gen.initialize()

            # Determine output dimensions
            width = request.width or source_image.width
            height = request.height or source_image.height

            # Generate edited image
            result_image = await emu_gen.generate_image(
                prompt=request.prompt,
                width=width,
                height=height,
                reference_images=[source_image],
                mode="x2i",
            )

            # Save result to temporary file
            image_path = _TEMP_DIR / f"{job_id}.png"
            result_image.save(image_path)

            # Update job with result path
            await _job_storage.update_job(
                job_id,
                status="completed",
                result_path=str(image_path),
                width=str(width),
                height=str(height),
            )

            logger.info(f"Image edit job {job_id} completed")

        except Exception as e:
            logger.error(f"Image edit job {job_id} failed: {e}")
            await _job_storage.update_job(job_id, status="failed", error=str(e))

    @router.post("", response_model=ImageGenerationResponse)
    async def generate_image(
        request: ImageGenerationRequest,
        background_tasks: BackgroundTasks,
        current_user: User | None = Depends(get_current_user_optional),
    ) -> ImageGenerationResponse:
        """Generate image from text prompt.

        Providers:
        - emu (default): Emu3.5 - Best for text rendering, any-to-image
        - flux: FLUX.1-dev - High quality general images
        - openai: gpt-image-1 - OpenAI DALL-E (requires API key)
        """
        job_id = f"img-{uuid.uuid4().hex[:12]}"

        # Estimate time based on resolution and steps
        base_time = 5.0
        resolution_factor = (request.width * request.height) / (1024 * 1024)
        steps_factor = request.steps / 12
        estimated_time = base_time * resolution_factor * steps_factor

        # Create job in Redis storage
        metadata = {
            "prompt": request.prompt,
            "width": request.width,
            "height": request.height,
            "provider": request.provider,
            "steps": request.steps,
            "guidance_scale": request.guidance_scale,
        }

        # Extract user_id from authenticated user if available
        user_id = current_user.id if current_user else None

        created = await _job_storage.create_job(
            job_id=job_id,
            user_id=user_id,
            metadata=metadata,
        )

        if not created:
            raise HTTPException(
                status_code=429,
                detail="Job limit exceeded. Please wait for existing jobs to complete.",
            )

        background_tasks.add_task(_run_generation_job, job_id, request)

        logger.info(
            f"Image job queued: {job_id} ({request.provider}, {request.width}x{request.height})"
        )

        return ImageGenerationResponse(
            job_id=job_id,
            status="queued",
            message=f"Image generation queued: {request.width}x{request.height} via {request.provider}",
            estimated_time_seconds=estimated_time,
        )

    @router.post("/edit", response_model=ImageGenerationResponse)
    async def edit_image(
        request: ImageEditRequest,
        background_tasks: BackgroundTasks,
        current_user: User | None = Depends(get_current_user_optional),
    ) -> ImageGenerationResponse:
        """Edit existing image using X2I (any-to-image).

        Uses Emu3.5's X2I capability for image-guided generation.
        Supports inpainting with optional mask.
        """
        job_id = f"edit-{uuid.uuid4().hex[:12]}"

        # Create job in Redis storage
        metadata = {
            "prompt": request.prompt,
            "strength": request.strength,
            "provider": "emu_x2i",
        }

        # Extract user_id from authenticated user if available
        user_id = current_user.id if current_user else None

        created = await _job_storage.create_job(
            job_id=job_id,
            user_id=user_id,
            metadata=metadata,
        )

        if not created:
            raise HTTPException(
                status_code=429,
                detail="Job limit exceeded. Please wait for existing jobs to complete.",
            )

        background_tasks.add_task(_run_edit_job, job_id, request)

        return ImageGenerationResponse(
            job_id=job_id,
            status="queued",
            message="Image edit queued (X2I mode)",
            estimated_time_seconds=8.0,
        )

    @router.get("/status/{job_id}", response_model=ImageResult)
    async def get_image_status(job_id: str) -> ImageResult:
        """Get image generation job status."""
        job = await _job_storage.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Image job not found: {job_id}")

        # Extract metadata
        metadata = job.get("metadata", {})
        prompt = metadata.get("prompt", "")
        width = metadata.get("width", 0)
        height = metadata.get("height", 0)
        provider = metadata.get("provider", "unknown")

        # Calculate generation time
        generation_time = None
        if job.get("started_at") and job.get("completed_at"):
            generation_time = job["completed_at"] - job["started_at"]

        # Load image as base64 if completed (for backward compatibility)
        image_base64 = None
        if job.get("status") == "completed" and job.get("result_path"):
            try:
                image_path = Path(job["result_path"])
                if image_path.exists():
                    image_bytes = image_path.read_bytes()
                    image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            except Exception as e:
                logger.warning(f"Failed to load image for {job_id}: {e}")

        return ImageResult(
            job_id=job_id,
            status=job.get("status", "unknown"),
            prompt=prompt,
            width=width,
            height=height,
            provider=provider,
            generation_time_seconds=generation_time,
            image_base64=image_base64,
        )

    @router.get("/result/{job_id}")
    async def get_image_result(job_id: str) -> StreamingResponse:
        """Get generated image as PNG file.

        Returns the image directly for download/display.
        """
        job = await _job_storage.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Image job not found: {job_id}")

        if job.get("status") != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Image not ready. Status: {job.get('status')}",
            )

        result_path = job.get("result_path")
        if not result_path:
            raise HTTPException(status_code=500, detail="Image data not found")

        # Load image from file
        image_path = Path(result_path)
        if not image_path.exists():
            raise HTTPException(status_code=500, detail="Image file not found")

        try:
            image_bytes = image_path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to read image {job_id}: {e}")
            raise HTTPException(status_code=500, detail="Failed to read image file") from e

        return StreamingResponse(
            io.BytesIO(image_bytes),
            media_type="image/png",
            headers={"Content-Disposition": f"inline; filename={job_id}.png"},
        )

    @router.delete("/job/{job_id}")
    async def cancel_image_job(job_id: str) -> dict[str, str]:
        """Cancel a queued image generation job."""
        job = await _job_storage.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Image job not found: {job_id}")

        if job["status"] == "completed":
            raise HTTPException(status_code=400, detail="Cannot cancel completed job")

        await _job_storage.update_job(job_id, status="cancelled")
        logger.info(f"Image job cancelled: {job_id}")

        return {"status": "cancelled", "job_id": job_id}

    return router
