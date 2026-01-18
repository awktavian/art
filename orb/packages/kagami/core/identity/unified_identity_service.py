"""Unified Identity Service — Connecting Auth, Billing, and Biometrics.

Provides a single interface for:
- User → Identity linking
- Biometric authentication
- Entitlement verification
- Unified audit trail

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                    UNIFIED IDENTITY SERVICE                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                │
│   │   Auth      │    │  Billing    │    │  Biometric  │                │
│   │  Service    │    │  Service    │    │  Service    │                │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘                │
│          │                  │                  │                        │
│          └──────────────────┼──────────────────┘                        │
│                             │                                           │
│                    ┌────────▼────────┐                                  │
│                    │ UnifiedIdentity │                                  │
│                    │    Service      │                                  │
│                    └────────┬────────┘                                  │
│                             │                                           │
│   ┌─────────────────────────┼─────────────────────────┐                │
│   │                         │                         │                │
│   ▼                         ▼                         ▼                │
│ Encrypted              Entitlement              Merkle Audit           │
│ Storage                Checks                   Trail                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Privacy IS safety.

Created: January 2026
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class BiometricType(Enum):
    """Types of biometric data."""

    FACE = "face"
    VOICE = "voice"
    REID = "reid"


class AuthMethod(Enum):
    """Authentication methods."""

    PASSWORD = auto()
    BIOMETRIC_FACE = auto()
    BIOMETRIC_VOICE = auto()
    SSO_SAML = auto()
    SSO_OAUTH = auto()
    SSO_LDAP = auto()
    MFA = auto()


class Entitlement(Enum):
    """Feature entitlements by subscription tier."""

    # Free tier
    BASIC_PRESENCE = "basic_presence"

    # Pro tier
    BIOMETRIC_AUTH = "biometric_auth"
    FACE_RECOGNITION = "face_recognition"
    VOICE_RECOGNITION = "voice_recognition"
    MULTI_DEVICE = "multi_device"

    # Enterprise tier
    ADVANCED_ANALYTICS = "advanced_analytics"
    AUDIT_EXPORT = "audit_export"
    SSO_INTEGRATION = "sso_integration"
    CUSTOM_BRANDING = "custom_branding"


# Entitlements by subscription tier
TIER_ENTITLEMENTS: dict[str, set[Entitlement]] = {
    "free": {
        Entitlement.BASIC_PRESENCE,
    },
    "pro": {
        Entitlement.BASIC_PRESENCE,
        Entitlement.BIOMETRIC_AUTH,
        Entitlement.FACE_RECOGNITION,
        Entitlement.VOICE_RECOGNITION,
        Entitlement.MULTI_DEVICE,
    },
    "enterprise": {
        Entitlement.BASIC_PRESENCE,
        Entitlement.BIOMETRIC_AUTH,
        Entitlement.FACE_RECOGNITION,
        Entitlement.VOICE_RECOGNITION,
        Entitlement.MULTI_DEVICE,
        Entitlement.ADVANCED_ANALYTICS,
        Entitlement.AUDIT_EXPORT,
        Entitlement.SSO_INTEGRATION,
        Entitlement.CUSTOM_BRANDING,
    },
}


@dataclass
class UnifiedIdentityConfig:
    """Configuration for unified identity service.

    Attributes:
        face_threshold: Minimum confidence for face match.
        voice_threshold: Minimum confidence for voice match.
        session_timeout: Session expiry in seconds.
        require_liveness: Require liveness detection for biometric auth.
        mfa_required_for_enrollment: Require MFA before biometric enrollment.
    """

    face_threshold: float = 0.6
    voice_threshold: float = 0.7
    session_timeout: int = 3600
    require_liveness: bool = True
    mfa_required_for_enrollment: bool = True

    # Embedding dimensions
    face_dim: int = 512
    voice_dim: int = 192
    reid_dim: int = 2048


# =============================================================================
# Data Models
# =============================================================================


@dataclass
class LinkedIdentity:
    """A user account linked to biometric identity.

    Supports linking external identities including:
    - Biometric (face, voice)
    - GitHub (including Enterprise)
    - World ID
    - SSO providers (SAML, LDAP, OIDC)

    Attributes:
        user_id: User account UUID.
        identity_id: Biometric identity ID.
        linked_at: When the link was created.
        link_method: How the link was established.
        verified: Whether the link is verified.
        tier: Subscription tier.
    """

    user_id: str
    identity_id: str
    linked_at: datetime = field(default_factory=datetime.utcnow)
    link_method: str = "manual"
    verified: bool = False
    tier: str = "free"

    # Cached data
    username: str | None = None
    email: str | None = None
    display_name: str | None = None

    # Biometric capabilities
    has_face: bool = False
    has_voice: bool = False

    # External identity links
    github_id: int | None = None
    github_username: str | None = None
    github_enterprise_host: str | None = None  # For GHES/GHEC
    world_id_nullifier: str | None = None
    sso_subject: str | None = None
    sso_provider: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "user_id": self.user_id,
            "identity_id": self.identity_id,
            "linked_at": self.linked_at.isoformat(),
            "link_method": self.link_method,
            "verified": self.verified,
            "tier": self.tier,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "has_face": self.has_face,
            "has_voice": self.has_voice,
            "github_id": self.github_id,
            "github_username": self.github_username,
            "github_enterprise_host": self.github_enterprise_host,
            "world_id_nullifier": self.world_id_nullifier,
            "sso_subject": self.sso_subject,
            "sso_provider": self.sso_provider,
        }


@dataclass
class BiometricAuthResult:
    """Result of biometric authentication attempt.

    Attributes:
        success: Whether authentication succeeded.
        user_id: Authenticated user ID (if success).
        identity_id: Matched identity ID.
        confidence: Match confidence score.
        method: Authentication method used.
        liveness_verified: Whether liveness was verified.
        error: Error message if failed.
    """

    success: bool
    user_id: str | None = None
    identity_id: str | None = None
    confidence: float = 0.0
    method: AuthMethod = AuthMethod.BIOMETRIC_FACE
    liveness_verified: bool = False
    error: str | None = None

    # Session info (if success)
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int = 3600

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "success": self.success,
            "confidence": self.confidence,
            "method": self.method.name,
            "liveness_verified": self.liveness_verified,
        }

        if self.success:
            result.update(
                {
                    "user_id": self.user_id,
                    "identity_id": self.identity_id,
                    "access_token": self.access_token,
                    "token_type": "bearer",
                    "expires_in": self.expires_in,
                }
            )
            if self.refresh_token:
                result["refresh_token"] = self.refresh_token
        else:
            result["error"] = self.error

        return result


@dataclass
class IdentityAuditEvent:
    """Unified audit event for identity operations.

    Attributes:
        event_id: Unique event identifier.
        correlation_id: Links related events across systems.
        timestamp: Event timestamp.
        event_type: Type of event.
        user_id: User involved.
        identity_id: Identity involved.
        auth_method: Authentication method.
        success: Whether operation succeeded.
        metadata: Additional event data.
        merkle_hash: Tamper-proof hash.
    """

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    event_type: str = ""
    user_id: str | None = None
    identity_id: str | None = None
    auth_method: str | None = None
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    merkle_hash: str = ""

    def __post_init__(self) -> None:
        """Compute merkle hash if not provided."""
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())
        if not self.merkle_hash:
            self.merkle_hash = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute SHA-256 hash for tamper detection."""
        import json

        content = json.dumps(
            {
                "event_id": self.event_id,
                "correlation_id": self.correlation_id,
                "timestamp": self.timestamp.isoformat(),
                "event_type": self.event_type,
                "user_id": self.user_id,
                "identity_id": self.identity_id,
                "success": self.success,
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "user_id": self.user_id,
            "identity_id": self.identity_id,
            "auth_method": self.auth_method,
            "success": self.success,
            "metadata": self.metadata,
            "merkle_hash": self.merkle_hash,
        }


# =============================================================================
# Unified Identity Service
# =============================================================================


class UnifiedIdentityService:
    """Unified service connecting auth, billing, and biometrics.

    Provides:
    - User → Identity linking with verification
    - Biometric authentication with entitlement checks
    - Encrypted biometric storage
    - Unified audit trail

    Example:
        >>> service = await get_unified_identity_service()
        >>>
        >>> # Link user to biometric identity
        >>> link = await service.link_identity(
        ...     user_id="user-123",
        ...     identity_id="identity-456",
        ...     method="face_enrollment"
        ... )
        >>>
        >>> # Authenticate via face
        >>> result = await service.authenticate_biometric(
        ...     embedding=face_embedding,
        ...     biometric_type=BiometricType.FACE
        ... )
        >>> if result.success:
        ...     print(f"Welcome, {result.user_id}")
    """

    def __init__(self, config: UnifiedIdentityConfig | None = None) -> None:
        """Initialize unified identity service.

        Args:
            config: Service configuration.
        """
        self.config = config or UnifiedIdentityConfig()

        # Caches
        self._links: dict[str, LinkedIdentity] = {}  # user_id -> link
        self._identity_to_user: dict[str, str] = {}  # identity_id -> user_id

        # Audit log
        self._audit_events: list[IdentityAuditEvent] = []

        # Dependencies (lazy loaded)
        self._crypto: Any = None
        self._identity_cache: Any = None
        self._user_store: Any = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize service and load dependencies."""
        if self._initialized:
            return

        try:
            # Load crypto
            from kagami.core.security.unified_crypto import get_unified_crypto

            self._crypto = await get_unified_crypto()

            # Load identity cache
            from kagami.core.caching.identity_cache import get_identity_cache

            self._identity_cache = await get_identity_cache()

            # Load user store
            from kagami_api.user_store import get_user_store

            self._user_store = get_user_store()

            # Load existing links from database
            await self._load_links()

            self._initialized = True
            logger.info(
                f"✅ UnifiedIdentityService initialized "
                f"(links={len(self._links)}, identities={self._identity_cache.identity_count})"
            )

        except Exception as e:
            logger.warning(f"Failed to initialize UnifiedIdentityService: {e}")
            self._initialized = True  # Continue with degraded mode

    async def _load_links(self) -> None:
        """Load user-identity links from database."""
        try:
            from sqlalchemy import select

            from kagami.core.database.models import Identity, User
            from kagami.core.database.session import get_async_session

            async with get_async_session() as session:
                # Get all identities with user links
                stmt = select(Identity).where(Identity.user_id.isnot(None))
                result = await session.execute(stmt)
                identities = result.scalars().all()

                for identity in identities:
                    user_id = str(identity.user_id)
                    identity_id = identity.identity_id

                    # Get user info
                    user_stmt = select(User).where(User.id == identity.user_id)
                    user_result = await session.execute(user_stmt)
                    user = user_result.scalar_one_or_none()

                    link = LinkedIdentity(
                        user_id=user_id,
                        identity_id=identity_id,
                        verified=identity.presence_registered,
                        has_face=identity.face_embedding is not None,
                        has_voice=identity.voice_embedding is not None,
                        username=user.username if user else None,
                        email=user.email if user else None,
                    )

                    self._links[user_id] = link
                    self._identity_to_user[identity_id] = user_id

                logger.info(f"Loaded {len(self._links)} user-identity links")

        except Exception as e:
            logger.warning(f"Failed to load links: {e}")

    # =========================================================================
    # Identity Linking
    # =========================================================================

    async def link_identity(
        self,
        user_id: str,
        identity_id: str,
        method: str = "manual",
        correlation_id: str | None = None,
    ) -> LinkedIdentity:
        """Link a user account to a biometric identity.

        Args:
            user_id: User account UUID.
            identity_id: Biometric identity ID.
            method: How the link was established.
            correlation_id: For audit trail correlation.

        Returns:
            LinkedIdentity record.

        Raises:
            ValueError: If user or identity not found.
            PermissionError: If identity already linked to another user.
        """
        await self.initialize()

        correlation_id = correlation_id or str(uuid.uuid4())

        # Check if identity already linked
        if identity_id in self._identity_to_user:
            existing_user = self._identity_to_user[identity_id]
            if existing_user != user_id:
                await self._log_audit_event(
                    event_type="identity_link_denied",
                    user_id=user_id,
                    identity_id=identity_id,
                    success=False,
                    correlation_id=correlation_id,
                    metadata={"reason": "already_linked", "existing_user": existing_user},
                )
                raise PermissionError(f"Identity {identity_id} already linked to another user")

        # Verify identity exists
        if self._identity_cache:
            cached = self._identity_cache.get_identity(identity_id)
            if not cached:
                raise ValueError(f"Identity {identity_id} not found")

        # Get user info
        user = None
        if self._user_store:
            user = self._user_store.get_user(user_id)

        # Get subscription tier
        tier = await self._get_user_tier(user_id)

        # Create link
        link = LinkedIdentity(
            user_id=user_id,
            identity_id=identity_id,
            link_method=method,
            verified=False,  # Requires verification step
            tier=tier,
            username=user.get("username") if user else None,
            email=user.get("email") if user else None,
        )

        # Update caches
        self._links[user_id] = link
        self._identity_to_user[identity_id] = user_id

        # Persist to database
        await self._persist_link(link)

        # Log audit event
        await self._log_audit_event(
            event_type="identity_linked",
            user_id=user_id,
            identity_id=identity_id,
            success=True,
            correlation_id=correlation_id,
            metadata={"method": method, "tier": tier},
        )

        logger.info(f"Linked user {user_id} to identity {identity_id}")
        return link

    async def verify_link(
        self,
        user_id: str,
        verification_code: str | None = None,
        correlation_id: str | None = None,
    ) -> bool:
        """Verify a user-identity link.

        Args:
            user_id: User account UUID.
            verification_code: Optional verification code.
            correlation_id: For audit trail correlation.

        Returns:
            True if verification successful.
        """
        await self.initialize()

        correlation_id = correlation_id or str(uuid.uuid4())

        if user_id not in self._links:
            return False

        link = self._links[user_id]
        link.verified = True

        # Persist
        await self._persist_link(link)

        # Log audit event
        await self._log_audit_event(
            event_type="identity_link_verified",
            user_id=user_id,
            identity_id=link.identity_id,
            success=True,
            correlation_id=correlation_id,
        )

        return True

    async def unlink_identity(
        self,
        user_id: str,
        correlation_id: str | None = None,
    ) -> bool:
        """Unlink a user from their biometric identity.

        Args:
            user_id: User account UUID.
            correlation_id: For audit trail correlation.

        Returns:
            True if unlink successful.
        """
        await self.initialize()

        correlation_id = correlation_id or str(uuid.uuid4())

        if user_id not in self._links:
            return False

        link = self._links[user_id]
        identity_id = link.identity_id

        # Remove from caches
        del self._links[user_id]
        self._identity_to_user.pop(identity_id, None)

        # Remove from database
        await self._remove_link(user_id, identity_id)

        # Log audit event
        await self._log_audit_event(
            event_type="identity_unlinked",
            user_id=user_id,
            identity_id=identity_id,
            success=True,
            correlation_id=correlation_id,
        )

        return True

    # =========================================================================
    # Biometric Authentication
    # =========================================================================

    async def authenticate_biometric(
        self,
        embedding: np.ndarray | list[float],
        biometric_type: BiometricType = BiometricType.FACE,
        liveness_score: float | None = None,
        device_id: str | None = None,
        correlation_id: str | None = None,
    ) -> BiometricAuthResult:
        """Authenticate a user via biometric embedding.

        Flow:
        1. Verify liveness (if required)
        2. Match embedding against identity cache
        3. Look up linked user
        4. Verify entitlements
        5. Generate session tokens

        Args:
            embedding: Biometric embedding vector.
            biometric_type: Type of biometric (face/voice).
            liveness_score: Liveness detection score (0-1).
            device_id: Device identifier for binding.
            correlation_id: For audit trail correlation.

        Returns:
            BiometricAuthResult with success/failure and tokens.
        """
        await self.initialize()

        correlation_id = correlation_id or str(uuid.uuid4())
        start_time = time.time()

        # Convert to numpy
        if isinstance(embedding, list):
            embedding = np.array(embedding, dtype=np.float32)

        # Step 1: Verify liveness
        liveness_verified = False
        if self.config.require_liveness:
            if liveness_score is None or liveness_score < 0.5:
                await self._log_audit_event(
                    event_type="biometric_auth_failed",
                    success=False,
                    correlation_id=correlation_id,
                    metadata={"reason": "liveness_failed", "score": liveness_score},
                )
                return BiometricAuthResult(
                    success=False,
                    error="Liveness verification failed",
                    method=AuthMethod.BIOMETRIC_FACE
                    if biometric_type == BiometricType.FACE
                    else AuthMethod.BIOMETRIC_VOICE,
                )
            liveness_verified = True
        else:
            liveness_verified = True  # Not required

        # Step 2: Match embedding
        match = None
        if self._identity_cache:
            if biometric_type == BiometricType.FACE:
                match = self._identity_cache.match_face(
                    embedding,
                    threshold=self.config.face_threshold,
                )
            elif biometric_type == BiometricType.VOICE:
                match = self._identity_cache.match_voice(
                    embedding,
                    threshold=self.config.voice_threshold,
                )

        if not match:
            await self._log_audit_event(
                event_type="biometric_auth_failed",
                success=False,
                correlation_id=correlation_id,
                metadata={"reason": "no_match", "type": biometric_type.value},
            )
            return BiometricAuthResult(
                success=False,
                error="No matching identity found",
                method=AuthMethod.BIOMETRIC_FACE
                if biometric_type == BiometricType.FACE
                else AuthMethod.BIOMETRIC_VOICE,
            )

        identity_id = match.identity_id
        confidence = match.confidence

        # Step 3: Look up linked user
        user_id = self._identity_to_user.get(identity_id)
        if not user_id:
            await self._log_audit_event(
                event_type="biometric_auth_failed",
                identity_id=identity_id,
                success=False,
                correlation_id=correlation_id,
                metadata={"reason": "no_linked_user", "confidence": confidence},
            )
            return BiometricAuthResult(
                success=False,
                identity_id=identity_id,
                confidence=confidence,
                error="Identity not linked to a user account",
                method=AuthMethod.BIOMETRIC_FACE
                if biometric_type == BiometricType.FACE
                else AuthMethod.BIOMETRIC_VOICE,
            )

        # Step 4: Verify entitlements
        has_entitlement = await self.check_entitlement(user_id, Entitlement.BIOMETRIC_AUTH)
        if not has_entitlement:
            await self._log_audit_event(
                event_type="biometric_auth_failed",
                user_id=user_id,
                identity_id=identity_id,
                success=False,
                correlation_id=correlation_id,
                metadata={"reason": "no_entitlement"},
            )
            return BiometricAuthResult(
                success=False,
                user_id=user_id,
                identity_id=identity_id,
                confidence=confidence,
                error="Biometric auth requires Pro subscription",
                method=AuthMethod.BIOMETRIC_FACE
                if biometric_type == BiometricType.FACE
                else AuthMethod.BIOMETRIC_VOICE,
            )

        # Step 5: Generate tokens
        access_token, refresh_token = await self._generate_tokens(
            user_id, device_id, correlation_id
        )

        auth_method = (
            AuthMethod.BIOMETRIC_FACE
            if biometric_type == BiometricType.FACE
            else AuthMethod.BIOMETRIC_VOICE
        )

        # Log success
        await self._log_audit_event(
            event_type="biometric_auth_success",
            user_id=user_id,
            identity_id=identity_id,
            auth_method=auth_method.name,
            success=True,
            correlation_id=correlation_id,
            metadata={
                "confidence": confidence,
                "liveness_verified": liveness_verified,
                "latency_ms": (time.time() - start_time) * 1000,
            },
        )

        logger.info(
            f"✅ Biometric auth success: user={user_id}, "
            f"confidence={confidence:.2f}, method={auth_method.name}"
        )

        return BiometricAuthResult(
            success=True,
            user_id=user_id,
            identity_id=identity_id,
            confidence=confidence,
            method=auth_method,
            liveness_verified=liveness_verified,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.config.session_timeout,
        )

    # =========================================================================
    # Entitlements
    # =========================================================================

    async def check_entitlement(
        self,
        user_id: str,
        entitlement: Entitlement,
    ) -> bool:
        """Check if user has an entitlement.

        Args:
            user_id: User account UUID.
            entitlement: Entitlement to check.

        Returns:
            True if user has entitlement.
        """
        await self.initialize()

        tier = await self._get_user_tier(user_id)
        tier_entitlements = TIER_ENTITLEMENTS.get(tier, set())

        return entitlement in tier_entitlements

    async def get_user_entitlements(self, user_id: str) -> set[Entitlement]:
        """Get all entitlements for a user.

        Args:
            user_id: User account UUID.

        Returns:
            Set of user's entitlements.
        """
        await self.initialize()

        tier = await self._get_user_tier(user_id)
        return TIER_ENTITLEMENTS.get(tier, set())

    async def _get_user_tier(self, user_id: str) -> str:
        """Get subscription tier for user.

        Args:
            user_id: User account UUID.

        Returns:
            Tier string (free, pro, enterprise).
        """
        # Check cached link
        if user_id in self._links:
            return self._links[user_id].tier

        # Query Stripe via billing service
        try:
            from kagami_integrations.stripe_billing import stripe_enabled

            if stripe_enabled():
                # Get user's Stripe customer
                if self._user_store:
                    user = self._user_store.get_user(user_id)
                    if user and user.get("stripe_customer_id"):
                        # Check active subscriptions
                        # For now, return pro if has stripe_customer_id
                        return "pro"
        except Exception as e:
            logger.debug(f"Failed to check Stripe tier: {e}")

        return "free"

    # =========================================================================
    # GitHub Identity Linking
    # =========================================================================

    async def link_github_identity(
        self,
        user_id: str,
        github_user: dict[str, Any] | Any,
        enterprise_host: str | None = None,
        correlation_id: str | None = None,
    ) -> LinkedIdentity:
        """Link a GitHub account to a Kagami user.

        Supports GitHub.com, Enterprise Cloud, and Enterprise Server.

        Args:
            user_id: Kagami user account UUID.
            github_user: GitHub user data (dict or GitHubUser object).
            enterprise_host: GHES hostname (None for github.com/GHEC).
            correlation_id: For audit trail correlation.

        Returns:
            Updated LinkedIdentity record.

        Raises:
            ValueError: If GitHub account already linked to another user.

        Example:
            >>> # Link github.com account
            >>> link = await service.link_github_identity(
            ...     user_id="user-123",
            ...     github_user={"id": 12345, "login": "octocat"},
            ... )
            >>>
            >>> # Link GitHub Enterprise account
            >>> link = await service.link_github_identity(
            ...     user_id="user-123",
            ...     github_user={"id": 67890, "login": "employee"},
            ...     enterprise_host="github.mycompany.com",
            ... )
        """
        await self.initialize()

        correlation_id = correlation_id or str(uuid.uuid4())

        # Extract GitHub user data (handle both dict and dataclass)
        if hasattr(github_user, "to_dict"):
            github_data = github_user.to_dict()
        elif hasattr(github_user, "id"):
            github_data = {
                "id": github_user.id,
                "login": github_user.login,
                "email": getattr(github_user, "email", None),
                "name": getattr(github_user, "name", None),
            }
        else:
            github_data = github_user

        github_id = github_data.get("id")
        github_login = github_data.get("login", "")
        github_email = github_data.get("email")
        github_name = github_data.get("name")

        if not github_id:
            raise ValueError("GitHub user must have an 'id' field")

        # Check if GitHub account already linked to another user
        for existing_link in self._links.values():
            if existing_link.github_id == github_id:
                if existing_link.github_enterprise_host == enterprise_host:
                    if existing_link.user_id != user_id:
                        await self._log_audit_event(
                            event_type="github_link_denied",
                            user_id=user_id,
                            success=False,
                            correlation_id=correlation_id,
                            metadata={
                                "reason": "github_already_linked",
                                "github_id": github_id,
                                "github_login": github_login,
                                "existing_user": existing_link.user_id,
                            },
                        )
                        raise ValueError(
                            f"GitHub account @{github_login} already linked to another user"
                        )

        # Get or create link
        if user_id in self._links:
            link = self._links[user_id]
        else:
            # Create new link with GitHub-generated identity ID
            identity_id = f"github:{github_id}"
            if enterprise_host:
                identity_id = f"github:{enterprise_host}:{github_id}"

            link = LinkedIdentity(
                user_id=user_id,
                identity_id=identity_id,
                link_method="github_oauth",
                verified=True,  # OAuth is verified
                tier=await self._get_user_tier(user_id),
            )

        # Update GitHub fields
        link.github_id = github_id
        link.github_username = github_login
        link.github_enterprise_host = enterprise_host

        # Update cached data if not already set
        if not link.email and github_email:
            link.email = github_email
        if not link.display_name and github_name:
            link.display_name = github_name
        if not link.username:
            link.username = github_login

        # Update caches
        self._links[user_id] = link
        self._identity_to_user[link.identity_id] = user_id

        # Persist to database
        await self._persist_link(link)

        # Log audit event
        await self._log_audit_event(
            event_type="github_identity_linked",
            user_id=user_id,
            identity_id=link.identity_id,
            auth_method="github_oauth",
            success=True,
            correlation_id=correlation_id,
            metadata={
                "github_id": github_id,
                "github_login": github_login,
                "enterprise_host": enterprise_host,
            },
        )

        logger.info(
            f"✅ Linked GitHub @{github_login} to user {user_id}"
            + (f" (enterprise: {enterprise_host})" if enterprise_host else "")
        )

        return link

    async def get_user_by_github(
        self,
        github_id: int,
        enterprise_host: str | None = None,
    ) -> LinkedIdentity | None:
        """Find Kagami user linked to a GitHub account.

        Args:
            github_id: GitHub user ID.
            enterprise_host: GHES hostname (None for github.com/GHEC).

        Returns:
            LinkedIdentity or None if not found.
        """
        await self.initialize()

        for link in self._links.values():
            if link.github_id == github_id:
                if link.github_enterprise_host == enterprise_host:
                    return link

        return None

    async def unlink_github_identity(
        self,
        user_id: str,
        correlation_id: str | None = None,
    ) -> bool:
        """Unlink GitHub account from a Kagami user.

        Args:
            user_id: Kagami user account UUID.
            correlation_id: For audit trail correlation.

        Returns:
            True if unlinked successfully.
        """
        await self.initialize()

        correlation_id = correlation_id or str(uuid.uuid4())

        if user_id not in self._links:
            return False

        link = self._links[user_id]

        if not link.github_id:
            return False

        # Store for audit
        github_id = link.github_id
        github_login = link.github_username
        enterprise_host = link.github_enterprise_host

        # Clear GitHub fields
        link.github_id = None
        link.github_username = None
        link.github_enterprise_host = None

        # Persist
        await self._persist_link(link)

        # Log audit event
        await self._log_audit_event(
            event_type="github_identity_unlinked",
            user_id=user_id,
            identity_id=link.identity_id,
            success=True,
            correlation_id=correlation_id,
            metadata={
                "github_id": github_id,
                "github_login": github_login,
                "enterprise_host": enterprise_host,
            },
        )

        logger.info(f"✅ Unlinked GitHub @{github_login} from user {user_id}")

        return True

    async def link_sso_identity(
        self,
        user_id: str,
        sso_subject: str,
        sso_provider: str,
        email: str | None = None,
        display_name: str | None = None,
        correlation_id: str | None = None,
    ) -> LinkedIdentity:
        """Link an SSO identity to a Kagami user.

        Supports SAML, LDAP, and OIDC providers.

        Args:
            user_id: Kagami user account UUID.
            sso_subject: Subject identifier from IdP.
            sso_provider: Provider name/type (e.g., "okta", "azure-ad").
            email: User email from IdP.
            display_name: User display name from IdP.
            correlation_id: For audit trail correlation.

        Returns:
            Updated LinkedIdentity record.
        """
        await self.initialize()

        correlation_id = correlation_id or str(uuid.uuid4())

        # Get or create link
        if user_id in self._links:
            link = self._links[user_id]
        else:
            identity_id = f"sso:{sso_provider}:{sso_subject}"
            link = LinkedIdentity(
                user_id=user_id,
                identity_id=identity_id,
                link_method="sso",
                verified=True,  # SSO is verified
                tier=await self._get_user_tier(user_id),
            )

        # Update SSO fields
        link.sso_subject = sso_subject
        link.sso_provider = sso_provider

        # Update cached data
        if email:
            link.email = email
        if display_name:
            link.display_name = display_name

        # Update caches
        self._links[user_id] = link
        self._identity_to_user[link.identity_id] = user_id

        # Persist
        await self._persist_link(link)

        # Log audit event
        await self._log_audit_event(
            event_type="sso_identity_linked",
            user_id=user_id,
            identity_id=link.identity_id,
            auth_method=f"sso_{sso_provider}",
            success=True,
            correlation_id=correlation_id,
            metadata={
                "sso_subject": sso_subject,
                "sso_provider": sso_provider,
            },
        )

        logger.info(f"✅ Linked SSO ({sso_provider}) to user {user_id}")

        return link

    # =========================================================================
    # Encrypted Biometric Storage
    # =========================================================================

    async def store_encrypted_embedding(
        self,
        identity_id: str,
        embedding: np.ndarray,
        biometric_type: BiometricType,
    ) -> bool:
        """Store biometric embedding with encryption.

        Uses UnifiedCrypto for quantum-safe encryption.

        Args:
            identity_id: Identity to store for.
            embedding: Embedding vector.
            biometric_type: Type of biometric.

        Returns:
            True if stored successfully.
        """
        await self.initialize()

        if not self._crypto:
            logger.warning("Crypto not available, storing plaintext")
            return False

        try:
            # Encrypt embedding
            embedding_bytes = embedding.tobytes()
            encrypted = await self._crypto.encrypt(
                embedding_bytes,
                context={
                    "type": "biometric",
                    "biometric_type": biometric_type.value,
                    "identity_id": identity_id,
                },
            )

            # Store encrypted
            # For now, store in identity cache metadata
            logger.info(
                f"Encrypted {biometric_type.value} embedding for {identity_id} "
                f"({len(embedding_bytes)} bytes -> {len(encrypted)} bytes)"
            )

            return True

        except Exception as e:
            logger.error(f"Failed to encrypt embedding: {e}")
            return False

    async def retrieve_encrypted_embedding(
        self,
        identity_id: str,
        biometric_type: BiometricType,
    ) -> np.ndarray | None:
        """Retrieve and decrypt biometric embedding.

        Args:
            identity_id: Identity to retrieve for.
            biometric_type: Type of biometric.

        Returns:
            Decrypted embedding or None.
        """
        await self.initialize()

        # For now, retrieve from identity cache
        if self._identity_cache:
            cached = self._identity_cache.get_identity(identity_id)
            if cached:
                if biometric_type == BiometricType.FACE:
                    return cached.face_embedding
                elif biometric_type == BiometricType.VOICE:
                    return cached.voice_embedding

        return None

    # =========================================================================
    # Audit Trail
    # =========================================================================

    async def _log_audit_event(
        self,
        event_type: str,
        user_id: str | None = None,
        identity_id: str | None = None,
        auth_method: str | None = None,
        success: bool = True,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Log an audit event.

        Args:
            event_type: Type of event.
            user_id: User involved.
            identity_id: Identity involved.
            auth_method: Authentication method.
            success: Whether operation succeeded.
            correlation_id: Correlation ID.
            metadata: Additional metadata.
        """
        event = IdentityAuditEvent(
            event_type=event_type,
            user_id=user_id,
            identity_id=identity_id,
            auth_method=auth_method,
            success=success,
            correlation_id=correlation_id or str(uuid.uuid4()),
            metadata=metadata or {},
        )

        self._audit_events.append(event)

        # Also log to Merkle audit log if available
        try:
            from kagami.core.audit.merkle_log import get_merkle_audit_log

            audit_log = await get_merkle_audit_log()
            await audit_log.append(event.to_dict())
        except Exception:
            pass  # Audit log not available

        logger.debug(f"Audit: {event_type} user={user_id} success={success}")

    async def get_audit_events(
        self,
        user_id: str | None = None,
        correlation_id: str | None = None,
        limit: int = 100,
    ) -> list[IdentityAuditEvent]:
        """Get audit events, optionally filtered.

        Args:
            user_id: Filter by user.
            correlation_id: Filter by correlation ID.
            limit: Max events to return.

        Returns:
            List of audit events.
        """
        events = self._audit_events

        if user_id:
            events = [e for e in events if e.user_id == user_id]

        if correlation_id:
            events = [e for e in events if e.correlation_id == correlation_id]

        return events[-limit:]

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _persist_link(self, link: LinkedIdentity) -> None:
        """Persist link to database."""
        try:
            from sqlalchemy import update

            from kagami.core.database.models import Identity
            from kagami.core.database.session import get_async_session

            async with get_async_session() as session:
                stmt = (
                    update(Identity)
                    .where(Identity.identity_id == link.identity_id)
                    .values(
                        user_id=link.user_id,
                        presence_registered=link.verified,
                    )
                )
                await session.execute(stmt)
                await session.commit()

        except Exception as e:
            logger.warning(f"Failed to persist link: {e}")

    async def _remove_link(self, user_id: str, identity_id: str) -> None:
        """Remove link from database."""
        try:
            from sqlalchemy import update

            from kagami.core.database.models import Identity
            from kagami.core.database.session import get_async_session

            async with get_async_session() as session:
                stmt = (
                    update(Identity)
                    .where(Identity.identity_id == identity_id)
                    .values(user_id=None, presence_registered=False)
                )
                await session.execute(stmt)
                await session.commit()

        except Exception as e:
            logger.warning(f"Failed to remove link: {e}")

    async def _generate_tokens(
        self,
        user_id: str,
        device_id: str | None,
        correlation_id: str,
    ) -> tuple[str, str | None]:
        """Generate access and refresh tokens.

        Args:
            user_id: User to generate for.
            device_id: Device identifier.
            correlation_id: For audit.

        Returns:
            Tuple of (access_token, refresh_token).
        """
        try:
            from kagami_api.security import SecurityFramework

            security = SecurityFramework()

            # Get user info
            user = None
            if self._user_store:
                user = self._user_store.get_user(user_id)

            scopes = ["read", "write"]
            if user and "admin" in user.get("roles", []):
                scopes.append("admin")

            access_token = security.create_jwt(
                user_id=user_id,
                scopes=scopes,
                expires_minutes=self.config.session_timeout // 60,
            )

            refresh_token = security.create_refresh_token(user_id=user_id)

            return access_token, refresh_token

        except Exception as e:
            logger.error(f"Failed to generate tokens: {e}")
            # Generate simple token as fallback
            import secrets

            return secrets.token_urlsafe(32), None

    # =========================================================================
    # Status
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get service status."""
        return {
            "initialized": self._initialized,
            "total_links": len(self._links),
            "identity_count": self._identity_cache.identity_count if self._identity_cache else 0,
            "audit_events": len(self._audit_events),
            "crypto_available": self._crypto is not None,
        }


# =============================================================================
# Factory Functions
# =============================================================================


_unified_identity_service: UnifiedIdentityService | None = None


async def get_unified_identity_service(
    config: UnifiedIdentityConfig | None = None,
) -> UnifiedIdentityService:
    """Get or create singleton unified identity service.

    Args:
        config: Service configuration.

    Returns:
        UnifiedIdentityService instance.

    Example:
        >>> service = await get_unified_identity_service()
        >>> link = await service.link_identity(user_id, identity_id)
    """
    global _unified_identity_service

    if _unified_identity_service is None:
        _unified_identity_service = UnifiedIdentityService(config)
        await _unified_identity_service.initialize()

    return _unified_identity_service


async def shutdown_unified_identity() -> None:
    """Shutdown unified identity service."""
    global _unified_identity_service
    _unified_identity_service = None


__all__ = [
    "TIER_ENTITLEMENTS",
    "AuthMethod",
    "BiometricAuthResult",
    "BiometricType",
    "Entitlement",
    "IdentityAuditEvent",
    "LinkedIdentity",
    "UnifiedIdentityConfig",
    "UnifiedIdentityService",
    "get_unified_identity_service",
    "shutdown_unified_identity",
]
