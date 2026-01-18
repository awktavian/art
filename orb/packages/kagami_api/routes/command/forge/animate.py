"""Forge Animation Routes.

Animation generation endpoints using FacialAnimator and GestureEngine.

Integration Points:
- FacialAnimator: Facial expression and emotion animation
- GestureEngine: Body gesture and motion generation
- MotionRetargeting: Motion transfer between character rigs

Routes:
- POST /api/command/forge/animate - Generate animation
- POST /api/command/forge/animate/facial - Generate facial animation
- POST /api/command/forge/animate/gesture - Generate gesture animation
- GET /api/command/forge/animate/status/{job_id} - Check animation status
"""

import logging
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from kagami_api.auth import User, get_current_user_optional
from kagami_api.services.redis_job_storage import get_job_storage

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/animate", tags=["forge-animate"])

    # Redis-backed job storage (replaces unbounded dict)
    _job_storage = get_job_storage("animation")

    class AnimateRequest(BaseModel):
        """Animation generation request."""

        character_id: str = Field(..., description="Character to animate")
        animation_type: str = Field(
            default="idle",
            description="Animation type: idle, walk, run, gesture, facial, full",
        )
        duration_seconds: float = Field(default=2.0, ge=0.1, le=60.0)
        emotion: str | None = Field(default=None, description="Emotion for facial animation")
        gesture_prompt: str | None = Field(
            default=None, description="Natural language gesture description"
        )
        intensity: float = Field(default=0.7, ge=0.0, le=1.0)
        fps: int = Field(default=30, ge=1, le=120)

    class FacialAnimateRequest(BaseModel):
        """Facial animation request."""

        character_id: str = Field(..., description="Character to animate")
        emotion: str = Field(
            ..., description="Target emotion: happy, sad, angry, surprised, neutral, etc."
        )
        intensity: float = Field(default=0.8, ge=0.0, le=1.0)
        duration_seconds: float = Field(default=1.0, ge=0.1, le=10.0)
        blend_in: float = Field(default=0.2, ge=0.0, le=1.0, description="Blend in duration ratio")
        blend_out: float = Field(
            default=0.2, ge=0.0, le=1.0, description="Blend out duration ratio"
        )

    class GestureAnimateRequest(BaseModel):
        """Gesture animation request."""

        character_id: str = Field(..., description="Character to animate")
        prompt: str = Field(..., description="Natural language gesture description")
        duration_seconds: float = Field(default=2.0, ge=0.1, le=30.0)
        style: str = Field(
            default="natural", description="Animation style: natural, exaggerated, subtle"
        )

    class AnimateResponse(BaseModel):
        """Animation generation response."""

        job_id: str
        status: str
        message: str
        estimated_time_seconds: float | None = None
        preview_url: str | None = None

    class AnimationResult(BaseModel):
        """Animation result with motion data."""

        job_id: str
        status: str
        character_id: str
        animation_type: str
        duration_seconds: float
        frame_count: int
        fps: int
        motion_data_url: str | None = None
        blendshape_data: dict[str, Any] | None = None
        bone_transforms: list[dict[str, Any]] | None = None

    async def _run_animation_job(job_id: str, request: AnimateRequest) -> None:
        """Background task to generate animation."""
        try:
            # Update status to processing
            await _job_storage.update_job(job_id, status="processing")

            # Use canonical device detection
            from kagami.core.utils.device import get_device

            device = get_device()

            # Import animation modules
            from kagami.forge.modules.motion import (
                FacialAnimator,
                GestureEngine,
            )

            # Store animation data as JSON strings
            facial_data = None
            gesture_data = None

            # Initialize components based on animation type
            if request.animation_type in ("facial", "full"):
                facial_animator = FacialAnimator(device=device)
                await facial_animator.initialize()

                if request.emotion:
                    # Generate facial animation
                    result = await facial_animator.animate_character(  # type: ignore[attr-defined]
                        character_id=request.character_id,
                        emotion=request.emotion,
                        intensity=request.intensity,
                        duration=request.duration_seconds,
                    )
                    facial_data = result

            if request.animation_type in ("gesture", "full"):
                gesture_engine = GestureEngine(device=device)  # type: ignore[call-arg]
                await gesture_engine.initialize()

                if request.gesture_prompt:
                    # Generate gesture from prompt
                    result = await gesture_engine.generate_gesture(  # type: ignore[attr-defined]
                        prompt=request.gesture_prompt,
                        duration=request.duration_seconds,
                        style={"intensity": request.intensity},
                    )
                    gesture_data = result

            # Calculate frame count
            frame_count = int(request.duration_seconds * request.fps)

            # Update job with results
            await _job_storage.update_job(
                job_id,
                status="completed",
                frame_count=str(frame_count),
                fps=str(request.fps),
                facial_data=facial_data,
                gesture_data=gesture_data,
            )

            logger.info(f"Animation job {job_id} completed: {frame_count} frames")

        except Exception as e:
            logger.error(f"Animation job {job_id} failed: {e}")
            await _job_storage.update_job(job_id, status="failed", error=str(e))

    @router.post("", response_model=AnimateResponse)
    async def generate_animation(
        request: AnimateRequest,
        background_tasks: BackgroundTasks,
        current_user: User | None = Depends(get_current_user_optional),
    ) -> AnimateResponse:
        """Generate animation for a character.

        Supports multiple animation types:
        - idle: Basic idle animation loop
        - walk/run: Locomotion animations
        - gesture: LLM-driven gesture from prompt
        - facial: Emotion-based facial animation
        - full: Combined body and facial animation
        """
        job_id = f"anim-{uuid.uuid4().hex[:12]}"

        # Estimate processing time based on complexity
        estimated_time = request.duration_seconds * 2.0
        if request.animation_type == "full":
            estimated_time *= 1.5

        # Create job in Redis storage
        metadata = {
            "character_id": request.character_id,
            "animation_type": request.animation_type,
            "duration_seconds": request.duration_seconds,
            "fps": request.fps,
            "emotion": request.emotion,
            "gesture_prompt": request.gesture_prompt,
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

        # Queue background task
        background_tasks.add_task(_run_animation_job, job_id, request)

        logger.info(f"Animation job queued: {job_id} ({request.animation_type})")

        return AnimateResponse(
            job_id=job_id,
            status="queued",
            message=f"Animation job queued: {request.animation_type} for {request.duration_seconds}s",
            estimated_time_seconds=estimated_time,
        )

    @router.post("/facial", response_model=AnimateResponse)
    async def generate_facial_animation(
        request: FacialAnimateRequest,
        background_tasks: BackgroundTasks,
        current_user: User | None = Depends(get_current_user_optional),
    ) -> AnimateResponse:
        """Generate facial animation with emotion blending.

        Uses FacialAnimator with DECA and Audio2Face integration for
        high-quality facial expressions.
        """
        job_id = f"facial-{uuid.uuid4().hex[:12]}"

        # Create job in Redis storage
        metadata = {
            "character_id": request.character_id,
            "animation_type": "facial",
            "duration_seconds": request.duration_seconds,
            "emotion": request.emotion,
            "intensity": request.intensity,
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

        # Convert to standard AnimateRequest for processing
        anim_request = AnimateRequest(
            character_id=request.character_id,
            animation_type="facial",
            duration_seconds=request.duration_seconds,
            emotion=request.emotion,
            intensity=request.intensity,
        )

        background_tasks.add_task(_run_animation_job, job_id, anim_request)

        return AnimateResponse(
            job_id=job_id,
            status="queued",
            message=f"Facial animation queued: {request.emotion} @ {request.intensity:.1f}",
            estimated_time_seconds=request.duration_seconds * 1.5,
        )

    @router.post("/gesture", response_model=AnimateResponse)
    async def generate_gesture_animation(
        request: GestureAnimateRequest,
        background_tasks: BackgroundTasks,
        current_user: User | None = Depends(get_current_user_optional),
    ) -> AnimateResponse:
        """Generate gesture animation from natural language prompt.

        Uses GestureEngine with LLM integration to interpret prompts
        and generate appropriate body movements.
        """
        job_id = f"gesture-{uuid.uuid4().hex[:12]}"

        # Create job in Redis storage
        metadata = {
            "character_id": request.character_id,
            "animation_type": "gesture",
            "duration_seconds": request.duration_seconds,
            "gesture_prompt": request.prompt,
            "style": request.style,
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

        anim_request = AnimateRequest(
            character_id=request.character_id,
            animation_type="gesture",
            duration_seconds=request.duration_seconds,
            gesture_prompt=request.prompt,
        )

        background_tasks.add_task(_run_animation_job, job_id, anim_request)

        return AnimateResponse(
            job_id=job_id,
            status="queued",
            message=f"Gesture animation queued: '{request.prompt[:50]}...'",
            estimated_time_seconds=request.duration_seconds * 2.0,
        )

    @router.get("/status/{job_id}", response_model=AnimationResult)
    async def get_animation_status(job_id: str) -> AnimationResult:
        """Get animation job status and results."""
        job = await _job_storage.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Animation job not found: {job_id}")

        # Extract metadata
        metadata = job.get("metadata", {})
        character_id = metadata.get("character_id", "")
        animation_type = metadata.get("animation_type", "")
        duration_seconds = metadata.get("duration_seconds", 0.0)

        # Parse numeric fields from storage
        try:
            frame_count = int(job.get("frame_count", 0))
        except (ValueError, TypeError):
            frame_count = 0

        try:
            fps = int(job.get("fps", 30))
        except (ValueError, TypeError):
            fps = 30

        return AnimationResult(
            job_id=job_id,
            status=job.get("status", "unknown"),
            character_id=character_id,
            animation_type=animation_type,
            duration_seconds=duration_seconds,
            frame_count=frame_count,
            fps=fps,
            blendshape_data=job.get("facial_data"),
            bone_transforms=job.get("gesture_data"),
        )

    @router.delete("/job/{job_id}")
    async def cancel_animation_job(job_id: str) -> dict[str, str]:
        """Cancel a queued or processing animation job."""
        job = await _job_storage.get_job(job_id)

        if not job:
            raise HTTPException(status_code=404, detail=f"Animation job not found: {job_id}")

        if job["status"] == "completed":
            raise HTTPException(status_code=400, detail="Cannot cancel completed job")

        await _job_storage.update_job(job_id, status="cancelled")
        logger.info(f"Animation job cancelled: {job_id}")

        return {"status": "cancelled", "job_id": job_id}

    return router
