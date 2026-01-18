"""Biometric Authentication API Routes.

Provides endpoints for:
- Biometric authentication (face, voice)
- User-identity linking
- Entitlement verification
- Biometric enrollment

Endpoints:
- POST /api/user/biometric/auth - Authenticate via biometric
- POST /api/user/biometric/link - Link user to identity
- POST /api/user/biometric/unlink - Unlink identity
- POST /api/user/biometric/verify-link - Verify link
- GET /api/user/biometric/entitlements - Get user entitlements
- GET /api/user/biometric/status - Get biometric status

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Privacy IS safety.

Created: January 2026
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from kagami_api.auth import get_current_user
from kagami_api.response_schemas import get_error_responses

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/biometric", tags=["biometric"])


# =============================================================================
# Request/Response Models
# =============================================================================


class BiometricAuthRequest(BaseModel):
    """Biometric authentication request.

    Attributes:
        embedding: Biometric embedding vector (512 for face, 192 for voice).
        biometric_type: Type of biometric (face or voice).
        liveness_score: Liveness detection score (0-1).
        device_id: Device identifier for session binding.
    """

    embedding: list[float] = Field(..., description="Biometric embedding vector")
    biometric_type: str = Field("face", description="face or voice")
    liveness_score: float | None = Field(None, ge=0, le=1, description="Liveness score")
    device_id: str | None = Field(None, description="Device identifier")


class BiometricAuthResponse(BaseModel):
    """Biometric authentication response.

    Attributes:
        success: Whether authentication succeeded.
        access_token: JWT access token if success.
        token_type: Token type (bearer).
        expires_in: Token expiry in seconds.
        refresh_token: Refresh token if success.
        user_id: Authenticated user ID.
        identity_id: Matched identity ID.
        confidence: Match confidence score.
        error: Error message if failed.
    """

    success: bool
    access_token: str | None = None
    token_type: str = "bearer"
    expires_in: int = 3600
    refresh_token: str | None = None
    user_id: str | None = None
    identity_id: str | None = None
    confidence: float = 0.0
    error: str | None = None


class LinkIdentityRequest(BaseModel):
    """Request to link user to biometric identity.

    Attributes:
        identity_id: Biometric identity ID to link.
        method: How the link is being established.
    """

    identity_id: str = Field(..., description="Biometric identity ID")
    method: str = Field(
        "manual", description="Link method (manual, face_enrollment, voice_enrollment)"
    )


class LinkIdentityResponse(BaseModel):
    """Response from identity link operation.

    Attributes:
        success: Whether link was created.
        user_id: User account ID.
        identity_id: Biometric identity ID.
        verified: Whether link is verified.
        tier: User's subscription tier.
        error: Error message if failed.
    """

    success: bool
    user_id: str | None = None
    identity_id: str | None = None
    verified: bool = False
    tier: str = "free"
    error: str | None = None


class VerifyLinkRequest(BaseModel):
    """Request to verify identity link.

    Attributes:
        verification_code: Optional verification code.
    """

    verification_code: str | None = Field(None, description="Verification code")


class EntitlementsResponse(BaseModel):
    """User entitlements response.

    Attributes:
        tier: Subscription tier.
        entitlements: List of entitlement names.
        has_biometric_auth: Whether user has biometric auth.
        has_face_recognition: Whether user has face recognition.
        has_voice_recognition: Whether user has voice recognition.
    """

    tier: str
    entitlements: list[str]
    has_biometric_auth: bool = False
    has_face_recognition: bool = False
    has_voice_recognition: bool = False


class BiometricStatusResponse(BaseModel):
    """Biometric status for a user.

    Attributes:
        has_linked_identity: Whether user has linked identity.
        identity_id: Linked identity ID if any.
        verified: Whether link is verified.
        has_face: Whether identity has face embedding.
        has_voice: Whether identity has voice embedding.
        tier: Subscription tier.
    """

    has_linked_identity: bool
    identity_id: str | None = None
    verified: bool = False
    has_face: bool = False
    has_voice: bool = False
    tier: str = "free"


# =============================================================================
# Router Factory
# =============================================================================


def get_router() -> APIRouter:
    """Create and configure the biometric authentication router."""

    @router.post(
        "/auth",
        response_model=BiometricAuthResponse,
        responses=get_error_responses(400, 401, 403, 500),
    )
    async def biometric_auth(request: BiometricAuthRequest) -> BiometricAuthResponse:
        """Authenticate via biometric embedding.

        This endpoint does NOT require prior authentication.
        It authenticates the user based on their biometric data.

        Requirements:
        - User must have linked identity with biometric embeddings
        - User must have Pro or Enterprise subscription
        - Liveness verification is required

        Returns JWT tokens if authentication succeeds.
        """
        start_time = time.time()

        try:
            from kagami.core.identity import (
                BiometricType,
                get_unified_identity_service,
            )

            service = await get_unified_identity_service()

            # Parse biometric type
            biometric_type = BiometricType.FACE
            if request.biometric_type.lower() == "voice":
                biometric_type = BiometricType.VOICE

            # Authenticate
            result = await service.authenticate_biometric(
                embedding=request.embedding,
                biometric_type=biometric_type,
                liveness_score=request.liveness_score,
                device_id=request.device_id,
            )

            latency_ms = (time.time() - start_time) * 1000
            logger.info(f"Biometric auth: success={result.success}, latency={latency_ms:.1f}ms")

            return BiometricAuthResponse(
                success=result.success,
                access_token=result.access_token,
                refresh_token=result.refresh_token,
                expires_in=result.expires_in,
                user_id=result.user_id,
                identity_id=result.identity_id,
                confidence=result.confidence,
                error=result.error,
            )

        except Exception as e:
            logger.error(f"Biometric auth error: {e}")
            return BiometricAuthResponse(
                success=False,
                error=str(e),
            )

    @router.post(
        "/link",
        response_model=LinkIdentityResponse,
        responses=get_error_responses(400, 401, 403, 404, 409, 500),
    )
    async def link_identity(
        request: LinkIdentityRequest,
        user: Any = Depends(get_current_user),
    ) -> LinkIdentityResponse:
        """Link current user to a biometric identity.

        Creates a link between the authenticated user account and
        a biometric identity (face/voice embeddings).

        Requirements:
        - User must be authenticated
        - Identity must exist and not be linked to another user
        - User should verify the link afterwards
        """
        user_id = user.get("id") or user.get("user_id") or str(user.get("sub", ""))

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not determine user ID",
            )

        try:
            from kagami.core.identity import get_unified_identity_service

            service = await get_unified_identity_service()

            link = await service.link_identity(
                user_id=user_id,
                identity_id=request.identity_id,
                method=request.method,
            )

            return LinkIdentityResponse(
                success=True,
                user_id=link.user_id,
                identity_id=link.identity_id,
                verified=link.verified,
                tier=link.tier,
            )

        except PermissionError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            ) from e
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(e),
            ) from e
        except Exception as e:
            logger.error(f"Link identity error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            ) from e

    @router.post(
        "/unlink",
        response_model=LinkIdentityResponse,
        responses=get_error_responses(400, 401, 404, 500),
    )
    async def unlink_identity(
        user: Any = Depends(get_current_user),
    ) -> LinkIdentityResponse:
        """Unlink current user from their biometric identity.

        Removes the link between user account and biometric identity.
        The biometric data is preserved but no longer associated with
        the user account.
        """
        user_id = user.get("id") or user.get("user_id") or str(user.get("sub", ""))

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not determine user ID",
            )

        try:
            from kagami.core.identity import get_unified_identity_service

            service = await get_unified_identity_service()

            success = await service.unlink_identity(user_id)

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No linked identity found",
                )

            return LinkIdentityResponse(
                success=True,
                user_id=user_id,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unlink identity error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            ) from e

    @router.post(
        "/verify-link",
        response_model=LinkIdentityResponse,
        responses=get_error_responses(400, 401, 404, 500),
    )
    async def verify_link(
        request: VerifyLinkRequest,
        user: Any = Depends(get_current_user),
    ) -> LinkIdentityResponse:
        """Verify the user-identity link.

        Marks the link as verified, enabling biometric authentication.
        """
        user_id = user.get("id") or user.get("user_id") or str(user.get("sub", ""))

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not determine user ID",
            )

        try:
            from kagami.core.identity import get_unified_identity_service

            service = await get_unified_identity_service()

            success = await service.verify_link(
                user_id=user_id,
                verification_code=request.verification_code,
            )

            if not success:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No linked identity found",
                )

            return LinkIdentityResponse(
                success=True,
                user_id=user_id,
                verified=True,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Verify link error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            ) from e

    @router.get(
        "/entitlements",
        response_model=EntitlementsResponse,
        responses=get_error_responses(401, 500),
    )
    async def get_entitlements(
        user: Any = Depends(get_current_user),
    ) -> EntitlementsResponse:
        """Get current user's entitlements.

        Returns the user's subscription tier and list of entitlements.
        """
        user_id = user.get("id") or user.get("user_id") or str(user.get("sub", ""))

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not determine user ID",
            )

        try:
            from kagami.core.identity import (
                Entitlement,
                get_unified_identity_service,
            )

            service = await get_unified_identity_service()

            entitlements = await service.get_user_entitlements(user_id)
            tier = await service._get_user_tier(user_id)

            return EntitlementsResponse(
                tier=tier,
                entitlements=[e.value for e in entitlements],
                has_biometric_auth=Entitlement.BIOMETRIC_AUTH in entitlements,
                has_face_recognition=Entitlement.FACE_RECOGNITION in entitlements,
                has_voice_recognition=Entitlement.VOICE_RECOGNITION in entitlements,
            )

        except Exception as e:
            logger.error(f"Get entitlements error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            ) from e

    @router.get(
        "/status",
        response_model=BiometricStatusResponse,
        responses=get_error_responses(401, 500),
    )
    async def get_biometric_status(
        user: Any = Depends(get_current_user),
    ) -> BiometricStatusResponse:
        """Get biometric status for current user.

        Returns whether user has linked identity and biometric capabilities.
        """
        user_id = user.get("id") or user.get("user_id") or str(user.get("sub", ""))

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not determine user ID",
            )

        try:
            from kagami.core.identity import get_unified_identity_service

            service = await get_unified_identity_service()

            # Check if user has linked identity
            link = service._links.get(user_id)

            if not link:
                return BiometricStatusResponse(
                    has_linked_identity=False,
                    tier=await service._get_user_tier(user_id),
                )

            return BiometricStatusResponse(
                has_linked_identity=True,
                identity_id=link.identity_id,
                verified=link.verified,
                has_face=link.has_face,
                has_voice=link.has_voice,
                tier=link.tier,
            )

        except Exception as e:
            logger.error(f"Get biometric status error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(e),
            ) from e

    return router


__all__ = ["get_router", "router"]
