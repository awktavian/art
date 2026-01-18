"""User API - Authentication, authorization, and preferences.

Authentication Methods:
- /api/user/token - Password login (JWT)
- /api/user/oauth/apple - Apple Sign In
- /api/user/oauth/google - Google Sign In
- /api/user/auth/phone/* - SMS/Voice OTP (Twilio)
- /api/user/auth/magic-link/* - Passwordless email login
- /api/user/auth/totp/* - Authenticator app 2FA
- /api/user/auth/webauthn/* - Passkeys/biometric
- /oauth/* - Login with Kagami (OAuth2 provider)

Other Endpoints:
- /api/auth/saml/* - SAML SSO (enterprise)
- /api/auth/ldap/* - LDAP/AD (enterprise)
- /api/user/rbac/* - Role-based access control
- /api/user/keys/* - API key management
- /api/user/preferences - User preferences
- /api/user/smart-home/* - Smart home configuration
- /api/user/household/* - Household/family sharing
- /api/users/voice-profiles/* - Voice profile storage
- /api/voice/* - Voice pipeline (STT, TTS)
- /api/user/custody/* - Co-parenting coordination
- /api/user/shared-spaces/* - Coliving/community
- /api/user/caregiving/* - Caregiver coordination
"""

from fastapi import APIRouter


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Sub-routers are imported and included when this is called.
    """
    # Import sub-routers lazily
    from . import (
        api_keys,
        auth,
        caregiving,
        custody,
        household,
        preferences,
        rbac_admin,
        shared_spaces,
        smart_home,
        voice_profiles,
    )

    router = APIRouter(tags=["user"])

    # Include all sub-routers
    if hasattr(auth, "get_router"):
        auth_router = auth.get_router()
    else:
        auth_router = auth.router  # type: ignore[attr-defined]

    router.include_router(auth_router)

    # Back-compat alias for /api/auth/*
    if hasattr(auth, "auth_router"):
        router.include_router(auth.auth_router)

    # OAuth2 Consumer (Apple, Google) - Phase 1.1
    try:
        from . import oauth

        if hasattr(oauth, "get_router"):
            router.include_router(oauth.get_router())
        else:
            router.include_router(oauth.router)  # type: ignore[attr-defined]
    except ImportError:
        pass  # OAuth not available

    # Extended Auth (Phone OTP, Magic Link, WebAuthn, TOTP)
    try:
        from . import auth_extended

        if hasattr(auth_extended, "get_router"):
            router.include_router(auth_extended.get_router())
        else:
            router.include_router(auth_extended.router)  # type: ignore[attr-defined]
    except ImportError:
        pass  # Extended auth not available

    # OAuth2 Provider (Login with Kagami) - Phase 1.2
    try:
        from . import oauth_provider

        if hasattr(oauth_provider, "get_router"):
            router.include_router(oauth_provider.get_router())
        else:
            router.include_router(oauth_provider.router)  # type: ignore[attr-defined]
    except ImportError:
        pass  # OAuth Provider not available

    # Enterprise SSO - SAML (RALPH Week 3)
    try:
        from . import saml

        if hasattr(saml, "get_router"):
            router.include_router(saml.get_router())
        else:
            router.include_router(saml.router)  # type: ignore[attr-defined]
    except ImportError:
        pass  # SAML not available

    # Enterprise SSO - LDAP/AD (RALPH Week 3)
    try:
        from . import ldap

        if hasattr(ldap, "get_router"):
            router.include_router(ldap.get_router())
        else:
            router.include_router(ldap.router)  # type: ignore[attr-defined]
    except ImportError:
        pass  # LDAP not available

    if hasattr(rbac_admin, "get_router"):
        router.include_router(rbac_admin.get_router())
    else:
        router.include_router(rbac_admin.router)  # type: ignore[attr-defined]

    if hasattr(api_keys, "get_router"):
        router.include_router(api_keys.get_router())
    else:
        router.include_router(api_keys.router)  # type: ignore[attr-defined]

    # Smart home configuration (RALPH Week 2)
    if hasattr(smart_home, "get_router"):
        router.include_router(smart_home.get_router())
    else:
        router.include_router(smart_home.router)  # type: ignore[attr-defined]

    # User preferences (RALPH Week 2)
    if hasattr(preferences, "get_router"):
        router.include_router(preferences.get_router())
    else:
        router.include_router(preferences.router)  # type: ignore[attr-defined]

    # Household/family sharing (RALPH Week 3)
    if hasattr(household, "get_router"):
        router.include_router(household.get_router())
    else:
        router.include_router(household.router)  # type: ignore[attr-defined]

    # Voice profiles for speaker identification
    if hasattr(voice_profiles, "get_router"):
        router.include_router(voice_profiles.get_router())
    else:
        router.include_router(voice_profiles.router)  # type: ignore[attr-defined]

    # Unified voice pipeline (STT, Speaker ID, TTS)
    try:
        from . import voice

        if hasattr(voice, "get_router"):
            router.include_router(voice.get_router())
        else:
            router.include_router(voice.router)  # type: ignore[attr-defined]
    except ImportError:
        pass  # Voice pipeline not available

    # Biometric authentication (face, voice)
    try:
        from . import biometric

        if hasattr(biometric, "get_router"):
            router.include_router(biometric.get_router())
        else:
            router.include_router(biometric.router)  # type: ignore[attr-defined]
    except ImportError:
        pass  # Biometric auth not available

    # Co-parenting coordination
    if hasattr(custody, "get_router"):
        router.include_router(custody.get_router())
    else:
        router.include_router(custody.router)  # type: ignore[attr-defined]

    # Coliving/intentional community
    if hasattr(shared_spaces, "get_router"):
        router.include_router(shared_spaces.get_router())
    else:
        router.include_router(shared_spaces.router)  # type: ignore[attr-defined]

    # Caregiver coordination
    if hasattr(caregiving, "get_router"):
        router.include_router(caregiving.get_router())
    else:
        router.include_router(caregiving.router)  # type: ignore[attr-defined]

    return router


__all__ = ["get_router"]
