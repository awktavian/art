"""World ID Integration — Proof-of-Personhood Verification.

Integrates with World ID (Worldcoin) for anonymous human verification.
World ID uses iris-scanning technology to create unique identifiers
that prove humanity without revealing identity.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                       WORLD ID INTEGRATION                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                    IDKit Integration                             │  │
│   │                                                                  │  │
│   │   verify_proof(proof) → VerificationResult                      │  │
│   │   get_verification_url() → str                                  │  │
│   │   is_human_verified(user_id) → bool                             │  │
│   │                                                                  │  │
│   └────────────────────────┬────────────────────────────────────────┘  │
│                            │                                            │
│                            ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                 World ID Developer Portal                        │  │
│   │                                                                  │
│   │   Action: "verify-human" (device or orb)                        │  │
│   │   Signal: User identifier (hashed)                               │  │
│   │   Proof: Zero-knowledge proof of personhood                      │  │
│   │                                                                  │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│   Privacy Features:                                                      │
│   • Zero-knowledge proofs — verify without revealing identity           │
│   • Unique per-app ID — prevents cross-app tracking                     │
│   • No biometric data stored — only cryptographic proof                 │
│   • Sybil-resistant — each human can verify only once                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

World ID Documentation: https://docs.worldcoin.org/
IDKit SDK: https://github.com/worldcoin/idkit-js

Colony: Crystal (D₅) — Identity verification
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class VerificationLevel(Enum):
    """World ID verification levels."""

    DEVICE = "device"  # Phone verification (lower assurance)
    ORB = "orb"  # Orb verification (highest assurance, iris scan)


class WorldIDError(Exception):
    """Raised when World ID verification fails."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail


@dataclass
class WorldIDConfig:
    """World ID configuration.

    Attributes:
        app_id: World ID App ID from Developer Portal.
        action: Action identifier for this verification.
        verification_level: Minimum verification level required.
        api_url: World ID API endpoint.
        timeout: Request timeout in seconds.
    """

    app_id: str = ""
    action: str = "verify-human"
    verification_level: VerificationLevel = VerificationLevel.DEVICE
    api_url: str = "https://developer.worldcoin.org"
    timeout: float = 30.0

    def __post_init__(self) -> None:
        """Load from environment."""
        if not self.app_id:
            self.app_id = os.environ.get("WORLD_ID_APP_ID", "")

        self.action = os.environ.get("WORLD_ID_ACTION", self.action)

        level = os.environ.get("WORLD_ID_VERIFICATION_LEVEL", "device")
        self.verification_level = VerificationLevel(level.lower())

        self.api_url = os.environ.get("WORLD_ID_API_URL", self.api_url)

    @property
    def is_configured(self) -> bool:
        """Check if World ID is configured."""
        return bool(self.app_id)


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class WorldIDProof:
    """World ID zero-knowledge proof.

    Attributes:
        merkle_root: Merkle root of the identity commitment.
        nullifier_hash: Unique hash for this action (prevents double-spend).
        proof: The zero-knowledge proof data.
        verification_level: Level of verification (device or orb).
        credential_type: Type of credential used.
    """

    merkle_root: str
    nullifier_hash: str
    proof: str
    verification_level: str
    credential_type: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorldIDProof:
        """Create from dictionary."""
        return cls(
            merkle_root=data["merkle_root"],
            nullifier_hash=data["nullifier_hash"],
            proof=data["proof"],
            verification_level=data.get("verification_level", "device"),
            credential_type=data.get("credential_type"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "merkle_root": self.merkle_root,
            "nullifier_hash": self.nullifier_hash,
            "proof": self.proof,
            "verification_level": self.verification_level,
            "credential_type": self.credential_type,
        }


@dataclass
class VerificationResult:
    """Result of World ID verification.

    Attributes:
        success: Whether verification succeeded.
        nullifier_hash: Unique identifier for this verification.
        verification_level: Level achieved (device or orb).
        action: Action that was verified.
        signal_hash: Hash of the signal (user identifier).
        created_at: Timestamp of verification.
        error: Error message if verification failed.
        code: Error code if verification failed.
    """

    success: bool
    nullifier_hash: str = ""
    verification_level: str = ""
    action: str = ""
    signal_hash: str = ""
    created_at: float = field(default_factory=time.time)
    error: str | None = None
    code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "nullifier_hash": self.nullifier_hash,
            "verification_level": self.verification_level,
            "action": self.action,
            "signal_hash": self.signal_hash,
            "created_at": self.created_at,
            "error": self.error,
            "code": self.code,
        }


@dataclass
class HumanVerification:
    """Stored human verification status.

    Attributes:
        user_id: Internal user identifier.
        nullifier_hash: World ID nullifier (unique per user per action).
        verification_level: Level achieved.
        verified_at: Timestamp of verification.
        expires_at: Optional expiration (for periodic re-verification).
    """

    user_id: str
    nullifier_hash: str
    verification_level: str
    verified_at: float
    expires_at: float | None = None

    @property
    def is_valid(self) -> bool:
        """Check if verification is still valid."""
        if self.expires_at and time.time() > self.expires_at:
            return False
        return True


# =============================================================================
# World ID Client
# =============================================================================


class WorldIDClient:
    """Client for World ID API.

    Handles verification of World ID proofs via the Developer Portal API.

    Example:
        >>> client = WorldIDClient(config)
        >>> await client.initialize()
        >>>
        >>> # Verify a proof from IDKit
        >>> result = await client.verify_proof(
        ...     proof=proof_from_idkit,
        ...     signal="user_12345",
        ... )
        >>>
        >>> if result.success:
        ...     print(f"Human verified! Nullifier: {result.nullifier_hash}")
    """

    def __init__(self, config: WorldIDConfig | None = None) -> None:
        self.config = config or WorldIDConfig()
        self._http_client: httpx.AsyncClient | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the HTTP client."""
        if self._initialized:
            return

        if not self.config.is_configured:
            logger.warning("⚠️ World ID not configured. Set WORLD_ID_APP_ID environment variable.")

        self._http_client = httpx.AsyncClient(
            timeout=self.config.timeout,
            headers={
                "Content-Type": "application/json",
            },
        )

        self._initialized = True
        logger.info("✅ WorldIDClient initialized")

    async def shutdown(self) -> None:
        """Shutdown the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self._initialized = False

    async def verify_proof(
        self,
        proof: WorldIDProof,
        signal: str,
        action: str | None = None,
    ) -> VerificationResult:
        """Verify a World ID proof.

        Args:
            proof: The zero-knowledge proof from IDKit.
            signal: The signal (typically user identifier) that was signed.
            action: Action identifier (defaults to config action).

        Returns:
            VerificationResult with success status.

        Raises:
            WorldIDError: If API call fails.
        """
        if not self._initialized:
            await self.initialize()

        if not self.config.is_configured:
            return VerificationResult(
                success=False,
                error="World ID not configured",
                code="not_configured",
            )

        action = action or self.config.action

        # Hash the signal for privacy
        signal_hash = hashlib.sha256(signal.encode()).hexdigest()

        # Prepare verification request
        verify_url = f"{self.config.api_url}/api/v1/verify/{self.config.app_id}"

        payload = {
            "merkle_root": proof.merkle_root,
            "nullifier_hash": proof.nullifier_hash,
            "proof": proof.proof,
            "verification_level": proof.verification_level,
            "action": action,
            "signal_hash": signal_hash,
        }

        try:
            response = await self._http_client.post(
                verify_url,
                json=payload,
            )

            data = response.json()

            if response.status_code == 200:
                # Successful verification
                return VerificationResult(
                    success=True,
                    nullifier_hash=proof.nullifier_hash,
                    verification_level=proof.verification_level,
                    action=action,
                    signal_hash=signal_hash,
                )

            # Verification failed
            return VerificationResult(
                success=False,
                nullifier_hash=proof.nullifier_hash,
                error=data.get("detail", "Verification failed"),
                code=data.get("code", "verification_failed"),
            )

        except httpx.HTTPError as e:
            logger.error(f"World ID API error: {e}")
            return VerificationResult(
                success=False,
                error=f"API error: {e!s}",
                code="api_error",
            )

    def get_verification_url(
        self,
        signal: str,
        action: str | None = None,
        redirect_uri: str | None = None,
    ) -> str:
        """Generate a World ID verification URL.

        This URL can be used to redirect users to the World ID verification flow.

        Args:
            signal: User identifier to bind to verification.
            action: Action identifier.
            redirect_uri: URI to redirect after verification.

        Returns:
            URL for World ID verification.
        """
        action = action or self.config.action
        signal_hash = hashlib.sha256(signal.encode()).hexdigest()

        params = {
            "app_id": self.config.app_id,
            "action": action,
            "signal": signal_hash,
        }

        if redirect_uri:
            params["redirect_uri"] = redirect_uri

        # Build query string
        query = "&".join(f"{k}={v}" for k, v in params.items())

        return f"https://id.worldcoin.org/verify?{query}"


# =============================================================================
# World ID Service
# =============================================================================


class WorldIDService:
    """Service for managing World ID verifications.

    Provides a higher-level interface for human verification,
    including storage of verification status and duplicate detection.

    Example:
        >>> service = await get_world_id_service()
        >>>
        >>> # Check if user is verified
        >>> if not await service.is_human_verified("user_123"):
        ...     # Start verification flow
        ...     url = service.get_verification_url("user_123")
        ...     print(f"Please verify: {url}")
        >>>
        >>> # After user completes verification
        >>> result = await service.verify_and_store(proof, "user_123")
    """

    def __init__(self, config: WorldIDConfig | None = None) -> None:
        self.config = config or WorldIDConfig()
        self._client = WorldIDClient(self.config)
        self._verifications: dict[str, HumanVerification] = {}
        self._nullifier_to_user: dict[str, str] = {}  # Prevent Sybil
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the service."""
        if self._initialized:
            return

        await self._client.initialize()
        self._initialized = True
        logger.info("✅ WorldIDService initialized")

    async def shutdown(self) -> None:
        """Shutdown the service."""
        await self._client.shutdown()
        self._initialized = False

    async def verify_proof(
        self,
        proof: WorldIDProof,
        signal: str,
    ) -> VerificationResult:
        """Verify a World ID proof.

        Args:
            proof: The ZK proof from IDKit.
            signal: The signal (user identifier).

        Returns:
            VerificationResult.
        """
        if not self._initialized:
            await self.initialize()

        return await self._client.verify_proof(proof, signal)

    async def verify_and_store(
        self,
        proof: WorldIDProof,
        user_id: str,
        expiration_days: int | None = None,
    ) -> VerificationResult:
        """Verify proof and store the result.

        Args:
            proof: The ZK proof from IDKit.
            user_id: Internal user identifier.
            expiration_days: Days until verification expires (None = never).

        Returns:
            VerificationResult.

        Raises:
            WorldIDError: If nullifier already used by another user (Sybil).
        """
        if not self._initialized:
            await self.initialize()

        # Check for Sybil attack (same person, different user_id)
        if proof.nullifier_hash in self._nullifier_to_user:
            existing_user = self._nullifier_to_user[proof.nullifier_hash]
            if existing_user != user_id:
                raise WorldIDError(
                    "This World ID has already been used by another user",
                    code="sybil_detected",
                    detail="Nullifier already associated with user",
                )

        # Verify the proof
        result = await self._client.verify_proof(proof, user_id)

        if result.success:
            # Check verification level
            if self.config.verification_level == VerificationLevel.ORB:
                if proof.verification_level != "orb":
                    return VerificationResult(
                        success=False,
                        error="Orb verification required",
                        code="orb_required",
                    )

            # Calculate expiration
            expires_at = None
            if expiration_days:
                expires_at = time.time() + (expiration_days * 24 * 60 * 60)

            # Store verification
            verification = HumanVerification(
                user_id=user_id,
                nullifier_hash=proof.nullifier_hash,
                verification_level=proof.verification_level,
                verified_at=time.time(),
                expires_at=expires_at,
            )

            self._verifications[user_id] = verification
            self._nullifier_to_user[proof.nullifier_hash] = user_id

            logger.info(f"✅ Human verified: user={user_id}, level={proof.verification_level}")

        return result

    async def is_human_verified(
        self,
        user_id: str,
        require_orb: bool = False,
    ) -> bool:
        """Check if a user is verified as human.

        Args:
            user_id: User identifier.
            require_orb: Require orb-level verification.

        Returns:
            True if user has valid human verification.
        """
        if user_id not in self._verifications:
            return False

        verification = self._verifications[user_id]

        if not verification.is_valid:
            return False

        if require_orb and verification.verification_level != "orb":
            return False

        return True

    async def get_verification(
        self,
        user_id: str,
    ) -> HumanVerification | None:
        """Get verification details for a user.

        Args:
            user_id: User identifier.

        Returns:
            HumanVerification or None.
        """
        return self._verifications.get(user_id)

    async def revoke_verification(self, user_id: str) -> bool:
        """Revoke a user's verification.

        Args:
            user_id: User identifier.

        Returns:
            True if revoked.
        """
        if user_id not in self._verifications:
            return False

        verification = self._verifications[user_id]

        # Remove from mappings
        del self._verifications[user_id]
        if verification.nullifier_hash in self._nullifier_to_user:
            del self._nullifier_to_user[verification.nullifier_hash]

        logger.info(f"Revoked verification for user: {user_id}")
        return True

    def get_verification_url(
        self,
        user_id: str,
        redirect_uri: str | None = None,
    ) -> str:
        """Generate verification URL for a user.

        Args:
            user_id: User identifier (becomes the signal).
            redirect_uri: Redirect after verification.

        Returns:
            URL for World ID verification flow.
        """
        return self._client.get_verification_url(
            signal=user_id,
            redirect_uri=redirect_uri,
        )

    def get_status(self) -> dict[str, Any]:
        """Get service status."""
        return {
            "initialized": self._initialized,
            "configured": self.config.is_configured,
            "app_id": self.config.app_id[:8] + "..." if self.config.app_id else None,
            "verification_level": self.config.verification_level.value,
            "action": self.config.action,
            "verified_users": len(self._verifications),
            "unique_humans": len(self._nullifier_to_user),
        }


# =============================================================================
# Factory Functions
# =============================================================================


_world_id_service: WorldIDService | None = None


async def get_world_id_service(
    config: WorldIDConfig | None = None,
) -> WorldIDService:
    """Get or create the singleton World ID service.

    Args:
        config: World ID configuration.

    Returns:
        WorldIDService instance.

    Example:
        >>> service = await get_world_id_service()
        >>> url = service.get_verification_url("user_123")
    """
    global _world_id_service

    if _world_id_service is None:
        _world_id_service = WorldIDService(config)
        await _world_id_service.initialize()

    return _world_id_service


async def shutdown_world_id_service() -> None:
    """Shutdown the World ID service."""
    global _world_id_service

    if _world_id_service:
        await _world_id_service.shutdown()
        _world_id_service = None


# =============================================================================
# FastAPI Integration
# =============================================================================


def create_world_id_router():
    """Create FastAPI router for World ID endpoints.

    Returns:
        FastAPI APIRouter with World ID endpoints.
    """
    from fastapi import APIRouter, HTTPException
    from pydantic import BaseModel

    router = APIRouter(prefix="/worldid", tags=["World ID"])

    class VerifyRequest(BaseModel):
        """Request to verify World ID proof."""

        merkle_root: str
        nullifier_hash: str
        proof: str
        verification_level: str
        credential_type: str | None = None
        signal: str

    class VerifyResponse(BaseModel):
        """Response from verification."""

        success: bool
        nullifier_hash: str = ""
        verification_level: str = ""
        error: str | None = None
        code: str | None = None

    @router.post("/verify", response_model=VerifyResponse)
    async def verify_proof(request: VerifyRequest):
        """Verify a World ID proof.

        This endpoint receives the proof from IDKit and verifies it
        with the World ID Developer Portal API.
        """
        service = await get_world_id_service()

        proof = WorldIDProof(
            merkle_root=request.merkle_root,
            nullifier_hash=request.nullifier_hash,
            proof=request.proof,
            verification_level=request.verification_level,
            credential_type=request.credential_type,
        )

        try:
            result = await service.verify_and_store(
                proof=proof,
                user_id=request.signal,
            )

            return VerifyResponse(
                success=result.success,
                nullifier_hash=result.nullifier_hash,
                verification_level=result.verification_level,
                error=result.error,
                code=result.code,
            )

        except WorldIDError as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": str(e),
                    "code": e.code,
                },
            ) from e

    @router.get("/status/{user_id}")
    async def get_verification_status(user_id: str):
        """Get verification status for a user."""
        service = await get_world_id_service()

        is_verified = await service.is_human_verified(user_id)
        verification = await service.get_verification(user_id)

        return {
            "user_id": user_id,
            "is_verified": is_verified,
            "verification_level": verification.verification_level if verification else None,
            "verified_at": verification.verified_at if verification else None,
            "expires_at": verification.expires_at if verification else None,
        }

    @router.get("/url/{user_id}")
    async def get_verification_url(
        user_id: str,
        redirect_uri: str | None = None,
    ):
        """Get World ID verification URL for a user."""
        service = await get_world_id_service()

        url = service.get_verification_url(user_id, redirect_uri)

        return {
            "verification_url": url,
            "user_id": user_id,
        }

    @router.get("/health")
    async def health_check():
        """World ID service health check."""
        service = await get_world_id_service()
        return service.get_status()

    return router


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "HumanVerification",
    "VerificationLevel",
    "VerificationResult",
    "WorldIDClient",
    "WorldIDConfig",
    "WorldIDError",
    "WorldIDProof",
    "WorldIDService",
    "create_world_id_router",
    "get_world_id_service",
    "shutdown_world_id_service",
]
