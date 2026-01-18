from __future__ import annotations

"""
Registers concrete service providers for K os interfaces.

This module wires real implementations into the DI container so that
core components can depend on abstractions (DatabaseProvider,
PrivacyProvider, ForgeProvider) without importing API layers directly.
"""

import logging
import uuid
from typing import Any

from kagami.core.database.async_connection import get_async_db_session
from kagami.core.di import has_service, register_instance
from kagami.core.interfaces import (
    ConfigDict,
    ConsentType,
    DatabaseProvider,
    ForgeCapability,
    ForgeMetadata,
    ForgeProvider,
    ForgeStatus,
    ParamsDict,
    PrivacyLevel,
    PrivacyProvider,
)
from kagami.core.security.privacy import TokenScrubber
from kagami.forge.matrix import ForgeMatrix, get_forge_matrix
from kagami.forge.schema import CharacterRequest
from sqlalchemy import text

logger = logging.getLogger(__name__)


class AsyncDatabaseProvider(DatabaseProvider):
    """Async SQLAlchemy-backed DatabaseProvider."""

    async def execute(self, query: str, params: dict[str, Any] | None = None) -> Any:
        async with get_async_db_session() as session:
            result = await session.execute(text(query), params or {})
            return result.rowcount  # type: ignore[attr-defined]

    async def fetch_one(
        self, query: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        async with get_async_db_session() as session:
            result = await session.execute(text(query), params or {})
            row = result.mappings().first()
            return dict(row) if row is not None else None

    async def fetch_all(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        async with get_async_db_session() as session:
            result = await session.execute(text(query), params or {})
            return [dict(row) for row in result.mappings().all()]

    async def transaction(self) -> Any:
        """Expose DB session context manager for transactional callers."""
        return get_async_db_session()


class DefaultPrivacyProvider(PrivacyProvider):
    """Privacy provider that relies on the TokenScrubber."""

    def __init__(self) -> None:
        self._scrubber = TokenScrubber()

    async def classify_data(self, data: dict[str, Any]) -> PrivacyLevel:
        violations = self._scrubber.detect_violations(data)
        return PrivacyLevel.RESTRICTED if violations else PrivacyLevel.INTERNAL

    async def anonymize(self, data: dict[str, Any], fields: list[str]) -> dict[str, Any]:
        scrubbed = dict(data)
        for field in fields:
            if field in scrubbed:
                scrubbed[field] = self._scrubber.scrub(scrubbed[field])
        return scrubbed

    async def check_consent(self, user_id: str, _consent_type: ConsentType) -> bool:
        # SAFE DEFAULT: Deny by default.
        # The previous "True" default was a security risk (Allow-All).
        logger.warning(f"DefaultPrivacyProvider denying consent for user {user_id} (Default=Deny)")
        return False

    async def audit_access(self, user_id: str, resource: str, action: str) -> None:
        logger.debug("Privacy audit: user_id=%s resource=%s action=%s", user_id, resource, action)


class ForgeMatrixProvider(ForgeProvider):
    """ForgeProvider adapter that wraps ForgeMatrix and routes to capability-specific handlers."""

    def __init__(self) -> None:
        try:
            self._forge = get_forge_matrix()
        except Exception:
            self._forge = ForgeMatrix()
        self._jobs: dict[str, ForgeMetadata] = {}

    async def generate(
        self, capability: ForgeCapability, params: ParamsDict, config: ConfigDict | None = None
    ) -> dict[str, Any]:
        if capability not in self.get_supported_capabilities():
            raise ValueError(
                f"Capability {capability} not supported. "
                f"Supported: {[c.value for c in self.get_supported_capabilities()]}"
            ) from None

        request_payload = params.get("request")
        if request_payload is None:
            raise ValueError("Forge request missing 'request' payload") from None

        if not isinstance(request_payload, CharacterRequest):
            request_payload = CharacterRequest(**request_payload)

        correlation_id = getattr(request_payload, "request_id", None) or str(uuid.uuid4())
        room_hint = params.get("room_id")
        if room_hint:
            try:
                self._forge.set_room_hint_for_correlation(correlation_id, str(room_hint))  # type: ignore[attr-defined]
            except Exception:
                pass

        try:
            await self._forge.initialize()
        except Exception:
            pass

        # Route based on capability
        if capability == ForgeCapability.TEXT_GENERATION:
            result = await self._forge.generate_character(request_payload)
        elif capability == ForgeCapability.IMAGE_GENERATION:
            result = await self._generate_image(request_payload, params)
        elif capability == ForgeCapability.VIDEO_GENERATION:
            result = await self._generate_video(request_payload, params)
        elif capability == ForgeCapability.AUDIO_GENERATION:
            result = await self._generate_audio(request_payload, params)
        elif capability == ForgeCapability.CODE_GENERATION:
            result = await self._generate_code(request_payload, params)
        elif capability == ForgeCapability.MOTION_GENERATION:
            result = await self._generate_motion(request_payload, params)
        elif capability == ForgeCapability.PHYSICS_SIMULATION:
            result = await self._simulate_physics(request_payload, params)
        else:
            raise ValueError(f"Unhandled capability: {capability}") from None

        self._jobs[correlation_id] = ForgeMetadata(
            job_id=correlation_id,
            capability=capability,
            status=ForgeStatus.COMPLETED,
            cost=float(result.get("overall_quality") or 0.0),
            duration_seconds=float(result.get("duration_ms") or 0.0) / 1000.0,
            metadata={"request_id": correlation_id},
        )
        if room_hint:
            try:
                self._forge.clear_room_hint_for_correlation(correlation_id)  # type: ignore[attr-defined]
            except Exception:
                pass
        return result  # type: ignore[no-any-return]

    async def _generate_image(
        self, request: CharacterRequest, params: ParamsDict
    ) -> dict[str, Any]:
        """Generate image using OptimizedImageGenerator."""
        from kagami.forge.optimized_image_generator import OptimizedImageGenerator

        generator = OptimizedImageGenerator()  # type: ignore[call-arg]
        prompt = getattr(request, "concept", "") or getattr(request, "style_prompt", "")
        if not prompt:
            raise ValueError("Image generation requires concept or style_prompt") from None

        image_result = await generator.generate_image(
            prompt=prompt,
            width=params.get("width", 512),
            height=params.get("height", 512),
        )
        return {
            "request_id": getattr(request, "request_id", "unknown"),
            "success": True,
            "image": image_result.get("image_path") or image_result.get("image_url"),  # type: ignore[attr-defined]
            "metadata": image_result,
        }

    async def _generate_video(
        self, request: CharacterRequest, params: ParamsDict
    ) -> dict[str, Any]:
        """Generate video using genesis video system."""
        from kagami.forge.creator_api import generate_genesis_video

        video_params = {
            "prompt": getattr(request, "concept", ""),
            "duration": params.get("duration", 5.0),
            "fps": params.get("fps", 30),
        }
        result = await generate_genesis_video(video_params)
        return {
            "request_id": getattr(request, "request_id", "unknown"),
            "success": True,
            "video": result,
        }

    async def _generate_audio(
        self, request: CharacterRequest, params: ParamsDict
    ) -> dict[str, Any]:
        """Generate audio using unified media pipeline."""
        from kagami.core.media import get_media_pipeline

        pipeline = await get_media_pipeline()
        text = params.get("text") or getattr(request, "concept", "")
        if not text:
            raise ValueError("Audio generation requires text parameter") from None

        result = await pipeline.speak(text)
        return {
            "request_id": getattr(request, "request_id", "unknown"),
            "success": result.success,
            "audio_path": str(result.audio_path) if result.audio_path else None,
            "duration_ms": result.duration_ms,
            "error": result.error,
        }

    async def _generate_code(self, request: CharacterRequest, params: ParamsDict) -> dict[str, Any]:
        """Generate code using LLM service."""
        from kagami.forge.llm_service_adapter import get_llm_service

        llm_service = get_llm_service()
        prompt = params.get("prompt") or getattr(request, "concept", "")
        if not prompt:
            raise ValueError("Code generation requires prompt parameter") from None

        code = await llm_service.generate_text(  # type: ignore[attr-defined]
            prompt=f"Generate code for: {prompt}",
            max_tokens=params.get("max_tokens", 2000),
        )
        return {
            "request_id": getattr(request, "request_id", "unknown"),
            "success": True,
            "code": code,
            "language": params.get("language", "python"),
        }

    async def _generate_motion(
        self, request: CharacterRequest, params: ParamsDict
    ) -> dict[str, Any]:
        """Generate motion using motion synthesis."""
        from kagami.forge.inference.motion_agent import MotionAgent

        motion_agent = MotionAgent()
        prompt = params.get("motion_prompt") or getattr(request, "concept", "")
        if not prompt:
            raise ValueError("Motion generation requires motion_prompt parameter") from None

        motion_result = await motion_agent.generate_motion(
            prompt=prompt,
            duration=params.get("duration", 3.0),
        )
        return {
            "request_id": getattr(request, "request_id", "unknown"),
            "success": True,
            "motion": motion_result,
        }

    async def _simulate_physics(
        self, request: CharacterRequest, params: ParamsDict
    ) -> dict[str, Any]:
        """Run physics simulation using genesis wrapper."""
        from kagami.forge.modules.genesis_physics_wrapper import GenesisPhysicsWrapper

        physics = GenesisPhysicsWrapper()
        scene_config = params.get("scene") or {}
        if not scene_config:
            raise ValueError("Physics simulation requires scene configuration") from None

        await physics.initialize()
        await physics.create_physics_scene(scene_config)  # type: ignore[arg-type]

        # Run simulation steps
        steps = params.get("steps", 100)
        physics.step(num_steps=steps)

        # Get final state
        sim_result = physics.get_entity_states()
        return {
            "request_id": getattr(request, "request_id", "unknown"),
            "success": True,
            "simulation": sim_result,
        }

    async def get_status(self, job_id: str) -> ForgeStatus:
        meta = self._jobs.get(job_id)
        return meta.status if meta else ForgeStatus.COMPLETED

    async def cancel(self, job_id: str) -> bool:
        self._jobs.pop(job_id, None)
        return False

    def get_supported_capabilities(self) -> list[ForgeCapability]:
        """Return all supported Forge capabilities.

        All capabilities are supported through various backend modules:
        - TEXT_GENERATION: ForgeMatrix character generation
        - IMAGE_GENERATION: OptimizedImageGenerator
        - VIDEO_GENERATION: Genesis video system
        - AUDIO_GENERATION: EmoVoice synthesizer
        - CODE_GENERATION: LLM service adapter
        - MOTION_GENERATION: Motion synthesis agent
        - PHYSICS_SIMULATION: Genesis physics wrapper
        """
        return [
            ForgeCapability.TEXT_GENERATION,
            ForgeCapability.IMAGE_GENERATION,
            ForgeCapability.VIDEO_GENERATION,
            ForgeCapability.AUDIO_GENERATION,
            ForgeCapability.CODE_GENERATION,
            ForgeCapability.MOTION_GENERATION,
            ForgeCapability.PHYSICS_SIMULATION,
        ]


def register_api_providers() -> None:
    """Register default provider implementations if not already configured."""
    if not has_service(DatabaseProvider):
        register_instance(DatabaseProvider, AsyncDatabaseProvider())
        logger.info("Registered AsyncDatabaseProvider")

    if not has_service(PrivacyProvider):
        register_instance(PrivacyProvider, DefaultPrivacyProvider())
        logger.info("Registered DefaultPrivacyProvider")

    if not has_service(ForgeProvider):
        register_instance(ForgeProvider, ForgeMatrixProvider())
        logger.info("Registered ForgeMatrixProvider")
