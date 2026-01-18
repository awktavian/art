"""Voice Profile API Routes.

Provides voice profile management for speaker identification:
- Create/update voice profile with audio embedding
- List household voice profiles
- Delete voice profile
- Identify speaker from audio

Per plan: Add voice profile storage and speaker identification endpoints.

Created: January 1, 2026
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from kagami_api.auth import User, get_current_user
from kagami_api.response_schemas import get_error_responses

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/users/voice-profiles", tags=["user", "voice"])

    # =============================================================================
    # SCHEMAS
    # =============================================================================

    class VoiceProfileCreate(BaseModel):
        """Request to create/update a voice profile."""

        name: str = Field(max_length=100, description="Display name for this profile")
        embedding: list[float] = Field(
            description="Voice embedding vector (typically 192-512 dimensions)"
        )
        threshold: float = Field(
            default=0.7, ge=0.0, le=1.0, description="Confidence threshold for matching"
        )

    class VoiceProfileOut(BaseModel):
        """Voice profile information (output)."""

        id: str = Field(description="Profile unique identifier")
        user_id: str = Field(description="Associated user ID")
        name: str = Field(description="Display name")
        embedding: list[float] = Field(description="Voice embedding vector")
        threshold: float = Field(description="Confidence threshold")
        created_at: datetime = Field(description="Creation timestamp")
        updated_at: datetime | None = Field(None, description="Last update timestamp")
        sample_count: int = Field(default=1, description="Number of audio samples used")

    class VoiceProfilesResponse(BaseModel):
        """Response containing voice profiles."""

        profiles: list[VoiceProfileOut]
        total: int

    class IdentifyRequest(BaseModel):
        """Request to identify speaker from embedding."""

        embedding: list[float] = Field(
            description="Voice embedding vector to match against profiles"
        )

    class IdentifyResponse(BaseModel):
        """Speaker identification result."""

        identified: bool = Field(description="Whether speaker was identified")
        user_id: str | None = Field(None, description="Identified user's ID")
        name: str | None = Field(None, description="Identified user's name")
        confidence: float = Field(description="Match confidence (0.0-1.0)")

    # =============================================================================
    # STORAGE HELPERS (Redis-backed)
    # =============================================================================

    async def _get_redis_client() -> Any:
        """Get async Redis client."""
        try:
            from kagami.core.caching.redis import RedisClientFactory

            return RedisClientFactory.get_client(
                purpose="default", async_mode=True, decode_responses=True
            )
        except Exception:
            return None

    async def _get_voice_profile(profile_id: str) -> dict[str, Any] | None:
        """Get voice profile by ID."""
        client = await _get_redis_client()
        if not client:
            return None

        key = f"voice_profile:{profile_id}"
        data = await client.get(key)
        if data:
            return json.loads(data)
        return None

    async def _get_user_voice_profile(user_id: str) -> dict[str, Any] | None:
        """Get voice profile for a user."""
        client = await _get_redis_client()
        if not client:
            return None

        # Look up profile ID by user
        profile_id = await client.get(f"user:voice_profile:{user_id}")
        if profile_id:
            return await _get_voice_profile(profile_id)
        return None

    async def _set_voice_profile(profile_id: str, profile: dict[str, Any]) -> bool:
        """Store voice profile data."""
        client = await _get_redis_client()
        if not client:
            return False

        key = f"voice_profile:{profile_id}"
        await client.set(key, json.dumps(profile, default=str))

        # Also index by user_id
        user_id = profile.get("user_id")
        if user_id:
            await client.set(f"user:voice_profile:{user_id}", profile_id)

        return True

    async def _delete_voice_profile(profile_id: str) -> bool:
        """Delete voice profile."""
        client = await _get_redis_client()
        if not client:
            return False

        profile = await _get_voice_profile(profile_id)
        if profile:
            user_id = profile.get("user_id")
            if user_id:
                await client.delete(f"user:voice_profile:{user_id}")

        await client.delete(f"voice_profile:{profile_id}")
        return True

    async def _get_household_voice_profiles(
        household_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get all voice profiles, optionally filtered by household."""
        client = await _get_redis_client()
        if not client:
            return []

        profiles = []
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor=cursor, match="voice_profile:*")
            for key in keys:
                data = await client.get(key)
                if data:
                    profile = json.loads(data)
                    # TODO: Filter by household when household info is available
                    profiles.append(profile)
            if cursor == 0:
                break

        return profiles

    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b) or len(a) == 0:
            return 0.0

        dot = sum(ai * bi for ai, bi in zip(a, b, strict=False))
        norm_a = sum(ai * ai for ai in a) ** 0.5
        norm_b = sum(bi * bi for bi in b) ** 0.5

        if norm_a == 0 or norm_b == 0:
            return 0.0

        return dot / (norm_a * norm_b)

    # =============================================================================
    # ROUTES
    # =============================================================================

    @router.post(
        "",
        response_model=VoiceProfileOut,
        responses=get_error_responses(400, 401, 422, 500),
        summary="Create/update voice profile",
        description="""
        Create or update your voice profile for speaker identification.

        The embedding should be generated by a speaker recognition model
        (e.g., SpeechBrain, Resemblyzer, or similar).
        """,
    )
    async def create_or_update_voice_profile(
        request: VoiceProfileCreate,
        current_user: User = Depends(get_current_user),
    ) -> VoiceProfileOut:
        """Create or update voice profile."""
        now = datetime.utcnow()

        # Check for existing profile
        existing = await _get_user_voice_profile(current_user.id)

        if existing:
            # Update existing profile
            profile_id = existing["id"]
            existing["name"] = request.name
            existing["embedding"] = request.embedding
            existing["threshold"] = request.threshold
            existing["updated_at"] = now.isoformat()
            existing["sample_count"] = existing.get("sample_count", 1) + 1
            profile = existing
        else:
            # Create new profile
            profile_id = str(uuid.uuid4())
            profile = {
                "id": profile_id,
                "user_id": current_user.id,
                "name": request.name,
                "embedding": request.embedding,
                "threshold": request.threshold,
                "created_at": now.isoformat(),
                "updated_at": None,
                "sample_count": 1,
            }

        if not await _set_voice_profile(profile_id, profile):
            raise HTTPException(status_code=500, detail="Failed to save voice profile")

        logger.info(
            f"Voice profile {'updated' if existing else 'created'}: {profile_id} "
            f"for user {current_user.id}"
        )

        return VoiceProfileOut(
            id=profile_id,
            user_id=current_user.id,
            name=request.name,
            embedding=request.embedding,
            threshold=request.threshold,
            created_at=datetime.fromisoformat(profile["created_at"]),
            updated_at=(
                datetime.fromisoformat(profile["updated_at"]) if profile.get("updated_at") else None
            ),
            sample_count=profile.get("sample_count", 1),
        )

    @router.get(
        "",
        response_model=VoiceProfilesResponse,
        responses=get_error_responses(401, 500),
        summary="List voice profiles",
        description="Returns all voice profiles for the household (for Hub speaker ID).",
    )
    async def list_voice_profiles(
        current_user: User = Depends(get_current_user),
    ) -> VoiceProfilesResponse:
        """List all voice profiles."""
        profiles_data = await _get_household_voice_profiles()

        profiles = []
        for p in profiles_data:
            profiles.append(
                VoiceProfileOut(
                    id=p["id"],
                    user_id=p["user_id"],
                    name=p["name"],
                    embedding=p["embedding"],
                    threshold=p["threshold"],
                    created_at=datetime.fromisoformat(p["created_at"]),
                    updated_at=(
                        datetime.fromisoformat(p["updated_at"]) if p.get("updated_at") else None
                    ),
                    sample_count=p.get("sample_count", 1),
                )
            )

        return VoiceProfilesResponse(profiles=profiles, total=len(profiles))

    @router.get(
        "/me",
        response_model=VoiceProfileOut,
        responses=get_error_responses(401, 404, 500),
        summary="Get my voice profile",
        description="Returns the current user's voice profile.",
    )
    async def get_my_voice_profile(
        current_user: User = Depends(get_current_user),
    ) -> VoiceProfileOut:
        """Get current user's voice profile."""
        profile = await _get_user_voice_profile(current_user.id)
        if not profile:
            raise HTTPException(status_code=404, detail="Voice profile not found")

        return VoiceProfileOut(
            id=profile["id"],
            user_id=profile["user_id"],
            name=profile["name"],
            embedding=profile["embedding"],
            threshold=profile["threshold"],
            created_at=datetime.fromisoformat(profile["created_at"]),
            updated_at=(
                datetime.fromisoformat(profile["updated_at"]) if profile.get("updated_at") else None
            ),
            sample_count=profile.get("sample_count", 1),
        )

    @router.delete(
        "/me",
        responses=get_error_responses(401, 404, 500),
        summary="Delete my voice profile",
        description="Delete the current user's voice profile.",
    )
    async def delete_my_voice_profile(
        current_user: User = Depends(get_current_user),
    ) -> dict[str, Any]:
        """Delete current user's voice profile."""
        profile = await _get_user_voice_profile(current_user.id)
        if not profile:
            raise HTTPException(status_code=404, detail="Voice profile not found")

        await _delete_voice_profile(profile["id"])

        logger.info(f"Voice profile deleted for user {current_user.id}")

        return {
            "success": True,
            "message": "Voice profile deleted",
        }

    @router.post(
        "/identify",
        response_model=IdentifyResponse,
        responses=get_error_responses(400, 401, 500),
        summary="Identify speaker",
        description="""
        Identify speaker from voice embedding.

        Used by the Hub to determine which household member is speaking.
        Returns the best matching profile if confidence exceeds threshold.
        """,
    )
    async def identify_speaker(
        request: IdentifyRequest,
        current_user: User = Depends(get_current_user),
    ) -> IdentifyResponse:
        """Identify speaker from embedding."""
        profiles = await _get_household_voice_profiles()

        if not profiles:
            return IdentifyResponse(
                identified=False,
                user_id=None,
                name=None,
                confidence=0.0,
            )

        best_match = None
        best_confidence = 0.0

        for profile in profiles:
            similarity = _cosine_similarity(request.embedding, profile["embedding"])
            threshold = profile.get("threshold", 0.7)

            logger.debug(
                f"Speaker {profile['name']} similarity: {similarity:.3f} "
                f"(threshold: {threshold:.3f})"
            )

            if similarity >= threshold and similarity > best_confidence:
                best_match = profile
                best_confidence = similarity

        if best_match:
            logger.info(
                f"Speaker identified: {best_match['name']} (confidence: {best_confidence:.2f})"
            )
            return IdentifyResponse(
                identified=True,
                user_id=best_match["user_id"],
                name=best_match["name"],
                confidence=best_confidence,
            )

        return IdentifyResponse(
            identified=False,
            user_id=None,
            name=None,
            confidence=best_confidence,
        )

    return router


__all__ = ["get_router"]
