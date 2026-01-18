"""Identity Package — Unified Identity Management.

Provides integrated identity services connecting:
- Authentication (login, SSO, biometric)
- Billing (entitlements, subscription tiers)
- Biometrics (face, voice recognition)
- World ID (proof-of-personhood verification)

Usage:
    from kagami.core.identity import (
        get_unified_identity_service,
        BiometricType,
        Entitlement,
        get_world_id_service,
    )

    service = await get_unified_identity_service()

    # Link user to biometric identity
    link = await service.link_identity(user_id, identity_id)

    # Authenticate via face
    result = await service.authenticate_biometric(embedding, BiometricType.FACE)

    # World ID human verification
    world_id = await get_world_id_service()
    url = world_id.get_verification_url("user_123")

Colony: Nexus (e₄) — Integration
h(x) ≥ 0. Privacy IS safety.

Created: January 2026
"""

from kagami.core.identity.unified_identity_service import (
    TIER_ENTITLEMENTS,
    AuthMethod,
    BiometricAuthResult,
    BiometricType,
    Entitlement,
    IdentityAuditEvent,
    LinkedIdentity,
    UnifiedIdentityConfig,
    UnifiedIdentityService,
    get_unified_identity_service,
    shutdown_unified_identity,
)
from kagami.core.identity.world_id import (
    HumanVerification,
    VerificationLevel,
    VerificationResult,
    WorldIDClient,
    WorldIDConfig,
    WorldIDError,
    WorldIDProof,
    WorldIDService,
    create_world_id_router,
    get_world_id_service,
    shutdown_world_id_service,
)

__all__ = [
    "TIER_ENTITLEMENTS",
    # Unified Identity Service
    "AuthMethod",
    "BiometricAuthResult",
    "BiometricType",
    "Entitlement",
    # World ID (Proof of Personhood)
    "HumanVerification",
    "IdentityAuditEvent",
    "LinkedIdentity",
    "UnifiedIdentityConfig",
    "UnifiedIdentityService",
    "VerificationLevel",
    "VerificationResult",
    "WorldIDClient",
    "WorldIDConfig",
    "WorldIDError",
    "WorldIDProof",
    "WorldIDService",
    "create_world_id_router",
    "get_unified_identity_service",
    "get_world_id_service",
    "shutdown_unified_identity",
    "shutdown_world_id_service",
]
