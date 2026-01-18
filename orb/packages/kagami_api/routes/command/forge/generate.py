"""Forge character generation API endpoint.

This module implements the `/api/forge/generate` endpoint for creating
AI-generated characters using the ForgeService unified interface.

Features:
- Multi-format export (FBX, GLTF, USD, etc.)
- Quality profiles (preview, draft, final)
- Semantic caching for cost reduction
- Real-time progress via WebSocket
- Idempotency-protected operations
- Standardized response format
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from kagami.core.di import try_resolve
from kagami.core.interfaces import ForgeCapability as InterfaceForgeCapability
from kagami.core.interfaces import ForgeProvider, PrivacyProvider
from kagami.forge.service import (
    ForgeOperation,
    ForgeRequest,
    ForgeService,
    get_forge_service,
)

from kagami_api.forge_room_events import finalize_forge_generation
from kagami_api.rbac import Permission, require_permission
from kagami_api.routes.forge_common import build_forge_metadata
from kagami_api.schemas.forge_dtos import ForgeGenerateRequest

from .decorators import forge_route


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/command/forge", tags=["command", "forge"])
    logger = logging.getLogger(__name__)

    @router.post(
        "/generate",
        dependencies=[Depends(require_permission(Permission.TOOL_EXECUTE))],  # type: ignore[func-returns-value]
        response_model=None,
    )
    @forge_route("forge.generate", require_confirmation_for=["final"], idempotency_ttl=600)
    async def generate_character(
        request: Request,
        payload: ForgeGenerateRequest,
        service: ForgeService = Depends(get_forge_service),
    ) -> dict[str, Any]:
        """Generate a character from text concept.

        Uses ForgeService for unified processing with automatic:
        - Idempotency enforcement
        - Metric recording
        - Receipt emission
        - Error handling

        Args:
            payload: Character generation request with concept, quality, exports

        Returns:
            Generated character data with 3D model and metadata
        """
        # Build metadata
        forge_meta = build_forge_metadata(request, payload.model_dump())
        correlation_id = forge_meta["correlation_id"]

        concept = payload.concept
        quality_mode = payload.quality_mode
        export_formats = [ef.value for ef in payload.export_format_enums()]
        room_id = (payload.room_id or "").strip() if isinstance(payload.room_id, str) else None

        # Try ForgeProvider first (for external providers)
        forge_provider = try_resolve(ForgeProvider)
        privacy_provider = try_resolve(PrivacyProvider)

        if forge_provider and isinstance(forge_provider, ForgeProvider):
            try:
                req = payload.to_character_request(
                    request_id=correlation_id, extra_metadata=dict(forge_meta)
                )
                result = await forge_provider.generate(
                    InterfaceForgeCapability.TEXT_GENERATION,
                    {"request": req, "room_id": room_id, "correlation_id": correlation_id},
                )
                if result:
                    return await finalize_forge_generation(
                        result=result,
                        correlation_id=correlation_id,
                        concept=concept,
                        room_id=room_id,
                        auto_insert=payload.auto_insert,
                        privacy_provider=privacy_provider,
                    )
            except Exception as exc:
                logger.warning("ForgeProvider failed, using ForgeService: %s", exc)

        # Use ForgeService for generation
        forge_request = ForgeRequest(
            capability=ForgeOperation.CHARACTER_GENERATION,
            params={
                "concept": concept,
                "personality_brief": payload.personality_brief,
                "backstory_brief": payload.backstory_brief,
            },
            quality_mode=quality_mode,
            export_formats=export_formats,
            metadata=dict(forge_meta),
            correlation_id=correlation_id,
        )

        response = await service.execute(forge_request)

        if not response.success:
            raise HTTPException(
                status_code=501 if "module" in (response.error_code or "") else 500,
                detail=response.error,
            )

        # Build result from ForgeResponse
        result = {
            **response.data,
            "correlation_id": correlation_id,
            "cached": response.cached,
            "duration_ms": response.duration_ms,
        }

        # Add validation hints if requested
        if payload.validate_after:
            try:
                char_data = response.data.get("character", response.data)
                result["validation_hint"] = {
                    "stats": {
                        "vertices": int(char_data.get("vertices", 0)),
                        "faces": int(char_data.get("faces", 0)),
                        "has_texture": bool(char_data.get("has_texture", False)),
                    }
                }
            except Exception:
                pass

        return await finalize_forge_generation(
            result=result,
            correlation_id=correlation_id,
            concept=concept,
            room_id=room_id,
            auto_insert=payload.auto_insert,
            privacy_provider=privacy_provider,
        )

    return router
