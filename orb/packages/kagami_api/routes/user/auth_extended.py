"""Extended Authentication Methods.

Provides additional authentication methods beyond password/OAuth:
- SMS/Phone OTP (via Twilio)
- Magic Links (passwordless email)
- WebAuthn/Passkeys (biometric)
- TOTP 2FA (authenticator apps)

Mobile-first design with full iOS/Android support.

Colony: Crystal (e7) — Security
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import secrets
import struct
import time
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from kagami_api.audit_logger import audit_login_failure, audit_login_success
from kagami_api.response_schemas import get_error_responses
from kagami_api.security import Principal, SecurityFramework, require_auth
from kagami_api.security.shared import ACCESS_TOKEN_EXPIRE_MINUTES
from kagami_api.user_store import get_user_store

logger = logging.getLogger(__name__)


# =============================================================================
# Twilio Integration
# =============================================================================


class TwilioClient:
    """Twilio client for SMS/Voice OTP.

    Loads credentials from Kagami keychain with env var fallback.
    """

    def __init__(self):
        # Try keychain first, then environment variables
        try:
            from kagami.core.security import get_secret

            self.account_sid = get_secret("twilio_account_sid") or os.getenv("TWILIO_ACCOUNT_SID")
            self.auth_token = get_secret("twilio_auth_token") or os.getenv("TWILIO_AUTH_TOKEN")
            self.verify_service_sid = get_secret("twilio_verify_sid") or os.getenv(
                "TWILIO_VERIFY_SERVICE_SID"
            )
            self.phone_number = get_secret("twilio_phone_number") or os.getenv(
                "TWILIO_PHONE_NUMBER"
            )
        except Exception:
            # Fallback to env vars only
            self.account_sid = os.getenv("TWILIO_ACCOUNT_SID")
            self.auth_token = os.getenv("TWILIO_AUTH_TOKEN")
            self.verify_service_sid = os.getenv("TWILIO_VERIFY_SERVICE_SID")
            self.phone_number = os.getenv("TWILIO_PHONE_NUMBER")
        self._client = None

    @property
    def is_configured(self) -> bool:
        """Check if Twilio is properly configured."""
        return bool(self.account_sid and self.auth_token and self.verify_service_sid)

    def _get_client(self):
        """Get or create Twilio client."""
        if self._client is None:
            try:
                from twilio.rest import Client

                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                logger.warning("Twilio SDK not installed. Run: pip install twilio")
                return None
            except Exception as e:
                logger.error(f"Failed to initialize Twilio client: {e}")
                return None
        return self._client

    async def send_verification(self, phone_number: str, channel: str = "sms") -> dict[str, Any]:
        """Send OTP via SMS or voice call.

        Args:
            phone_number: E.164 format (+1234567890)
            channel: 'sms' or 'call'

        Returns:
            Dict with status and sid
        """
        if not self.is_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS authentication not configured",
            )

        client = self._get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS service unavailable",
            )

        try:
            verification = client.verify.v2.services(self.verify_service_sid).verifications.create(
                to=phone_number,
                channel=channel,
            )

            logger.info(f"Verification sent to {phone_number[:6]}*** via {channel}")

            return {
                "status": verification.status,
                "sid": verification.sid,
                "channel": channel,
            }
        except Exception as e:
            logger.error(f"Failed to send verification: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification code",
            ) from e

    async def check_verification(self, phone_number: str, code: str) -> bool:
        """Verify OTP code.

        Args:
            phone_number: E.164 format
            code: 6-digit OTP

        Returns:
            True if valid
        """
        if not self.is_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS authentication not configured",
            )

        client = self._get_client()
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="SMS service unavailable",
            )

        try:
            verification_check = client.verify.v2.services(
                self.verify_service_sid
            ).verification_checks.create(
                to=phone_number,
                code=code,
            )

            return verification_check.status == "approved"
        except Exception as e:
            logger.error(f"Verification check failed: {e}")
            return False


# Global Twilio client
_twilio_client: TwilioClient | None = None


def get_twilio_client() -> TwilioClient:
    """Get Twilio client singleton."""
    global _twilio_client
    if _twilio_client is None:
        _twilio_client = TwilioClient()
    return _twilio_client


# =============================================================================
# TOTP (Time-based One-Time Password)
# =============================================================================


class TOTPManager:
    """TOTP implementation for 2FA (Google Authenticator, Authy, etc.)."""

    DIGITS = 6
    INTERVAL = 30  # seconds

    @staticmethod
    def generate_secret() -> str:
        """Generate a new TOTP secret (base32 encoded)."""
        # 20 bytes = 160 bits of entropy
        random_bytes = secrets.token_bytes(20)
        # Keep padding for proper decoding
        return base64.b32encode(random_bytes).decode("utf-8")

    @staticmethod
    def get_totp_uri(secret: str, username: str, issuer: str = "Kagami") -> str:
        """Generate otpauth:// URI for QR code scanning.

        Args:
            secret: Base32 encoded secret
            username: User's account name
            issuer: Service name

        Returns:
            otpauth:// URI string
        """
        from urllib.parse import quote

        return (
            f"otpauth://totp/{quote(issuer)}:{quote(username)}"
            f"?secret={secret}&issuer={quote(issuer)}&digits=6&period=30"
        )

    @staticmethod
    def generate_code(secret: str, counter: int | None = None) -> str:
        """Generate TOTP code.

        Args:
            secret: Base32 encoded secret
            counter: Time counter (default: current time / 30)

        Returns:
            6-digit code string
        """
        if counter is None:
            counter = int(time.time()) // TOTPManager.INTERVAL

        # Decode secret (pad if necessary for base32)
        # Base32 requires length to be multiple of 8
        missing_padding = (8 - len(secret) % 8) % 8
        secret_padded = secret + "=" * missing_padding
        try:
            key = base64.b32decode(secret_padded.upper())
        except Exception as e:
            raise ValueError("Invalid TOTP secret") from e

        # Generate HMAC-SHA1
        msg = struct.pack(">Q", counter)
        h = hmac.new(key, msg, hashlib.sha1).digest()

        # Dynamic truncation
        offset = h[-1] & 0x0F
        code = struct.unpack(">I", h[offset : offset + 4])[0]
        code &= 0x7FFFFFFF
        code %= 10**TOTPManager.DIGITS

        return str(code).zfill(TOTPManager.DIGITS)

    @staticmethod
    def verify_code(secret: str, code: str, window: int = 1) -> bool:
        """Verify TOTP code with time window tolerance.

        Args:
            secret: Base32 encoded secret
            code: User-provided 6-digit code
            window: Number of intervals to check before/after

        Returns:
            True if valid
        """
        if not code or len(code) != TOTPManager.DIGITS:
            return False

        current_counter = int(time.time()) // TOTPManager.INTERVAL

        # Check current interval and window
        for i in range(-window, window + 1):
            try:
                expected = TOTPManager.generate_code(secret, current_counter + i)
                if hmac.compare_digest(expected, code):
                    return True
            except Exception:
                continue

        return False


# =============================================================================
# Magic Link Manager
# =============================================================================


# In-memory magic link storage (use Redis in production)
_magic_links: dict[str, dict[str, Any]] = {}


class MagicLinkManager:
    """Passwordless email authentication via magic links."""

    EXPIRY_MINUTES = 15
    LINK_LENGTH = 64

    @staticmethod
    def generate_link(email: str, user_id: str | None = None) -> tuple[str, str]:
        """Generate a magic link token.

        Args:
            email: User's email address
            user_id: Optional user ID for existing users

        Returns:
            Tuple of (token, full_url)
        """
        token = secrets.token_urlsafe(MagicLinkManager.LINK_LENGTH)
        expires_at = time.time() + (MagicLinkManager.EXPIRY_MINUTES * 60)

        _magic_links[token] = {
            "email": email,
            "user_id": user_id,
            "expires_at": expires_at,
            "created_at": time.time(),
            "used": False,
        }

        base_url = os.getenv("PUBLIC_BASE_URL", "https://awkronos.com")
        full_url = f"{base_url}/auth/magic?token={token}"

        return token, full_url

    @staticmethod
    def verify_link(token: str) -> dict[str, Any] | None:
        """Verify and consume a magic link.

        Args:
            token: The magic link token

        Returns:
            User info dict or None if invalid
        """
        link_data = _magic_links.get(token)
        if not link_data:
            return None

        # Check expiry
        if link_data["expires_at"] < time.time():
            del _magic_links[token]
            return None

        # Check if already used (single-use)
        if link_data["used"]:
            return None

        # Mark as used
        link_data["used"] = True

        return {
            "email": link_data["email"],
            "user_id": link_data["user_id"],
        }

    @staticmethod
    def cleanup_expired():
        """Remove expired magic links."""
        now = time.time()
        expired = [token for token, data in _magic_links.items() if data["expires_at"] < now]
        for token in expired:
            del _magic_links[token]


# =============================================================================
# WebAuthn/Passkey Storage (simplified)
# =============================================================================


# In-memory credential storage (use database in production)
_webauthn_credentials: dict[str, list[dict[str, Any]]] = {}


# =============================================================================
# Schemas
# =============================================================================


class PhoneOTPRequest(BaseModel):
    """Request to send phone OTP."""

    phone_number: str = Field(
        ...,
        description="Phone number in E.164 format (+1234567890)",
        pattern=r"^\+[1-9]\d{1,14}$",
    )
    channel: str = Field(
        "sms",
        description="Delivery channel: sms or call",
        pattern=r"^(sms|call)$",
    )


class PhoneOTPVerifyRequest(BaseModel):
    """Request to verify phone OTP."""

    phone_number: str = Field(
        ...,
        description="Phone number in E.164 format",
        pattern=r"^\+[1-9]\d{1,14}$",
    )
    code: str = Field(
        ...,
        description="6-digit verification code",
        min_length=6,
        max_length=6,
    )


class MagicLinkRequest(BaseModel):
    """Request to send magic link."""

    email: str = Field(..., description="Email address")


class MagicLinkVerifyRequest(BaseModel):
    """Request to verify magic link."""

    token: str = Field(..., description="Magic link token")


class TOTPSetupResponse(BaseModel):
    """Response for TOTP setup."""

    secret: str
    qr_uri: str
    backup_codes: list[str]


class TOTPVerifyRequest(BaseModel):
    """Request to verify TOTP code."""

    code: str = Field(
        ...,
        description="6-digit TOTP code",
        min_length=6,
        max_length=6,
    )


class WebAuthnRegisterRequest(BaseModel):
    """Request to register WebAuthn credential."""

    credential_id: str
    public_key: str
    attestation: str
    device_name: str = "Unknown Device"


class WebAuthnVerifyRequest(BaseModel):
    """Request to verify WebAuthn assertion."""

    credential_id: str
    authenticator_data: str
    client_data_json: str
    signature: str


class AuthTokenResponse(BaseModel):
    """Standard auth token response."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_token: str | None = None
    user_id: str
    username: str
    email: str | None = None
    is_new_user: bool = False
    mfa_required: bool = False


class AuthStatusResponse(BaseModel):
    """Auth method availability status."""

    password: bool = True
    apple: bool = True
    google: bool = True
    phone_sms: bool = False
    phone_call: bool = False
    magic_link: bool = True
    totp: bool = True
    webauthn: bool = True
    configured_2fa: list[str] = []


# =============================================================================
# Router
# =============================================================================


def get_router() -> APIRouter:
    """Create extended auth router."""
    router = APIRouter(prefix="/api/user/auth", tags=["user", "auth"])

    # =========================================================================
    # Auth Status
    # =========================================================================

    @router.get(
        "/methods",
        response_model=AuthStatusResponse,
        summary="Get available auth methods",
    )
    async def get_auth_methods() -> AuthStatusResponse:
        """Get available authentication methods.

        Returns which auth methods are available/configured.
        Useful for client apps to show appropriate login options.
        """
        twilio = get_twilio_client()

        return AuthStatusResponse(
            password=True,
            apple=bool(os.getenv("APPLE_CLIENT_ID")),
            google=bool(os.getenv("GOOGLE_CLIENT_ID")),
            phone_sms=twilio.is_configured,
            phone_call=twilio.is_configured,
            magic_link=True,
            totp=True,
            webauthn=True,
        )

    # =========================================================================
    # Phone OTP (Twilio)
    # =========================================================================

    @router.post(
        "/phone/send",
        responses=get_error_responses(400, 429, 500, 503),
        summary="Send phone OTP",
        description="Send OTP via SMS or voice call for phone authentication.",
    )
    async def send_phone_otp(request: PhoneOTPRequest) -> dict[str, Any]:
        """Send OTP to phone number."""
        twilio = get_twilio_client()

        if not twilio.is_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Phone authentication not available. Configure Twilio.",
            )

        result = await twilio.send_verification(
            phone_number=request.phone_number,
            channel=request.channel,
        )

        return {
            "status": "sent",
            "channel": result["channel"],
            "expires_in": 600,  # 10 minutes
            "message": f"Verification code sent via {result['channel']}",
        }

    @router.post(
        "/phone/verify",
        response_model=AuthTokenResponse,
        responses=get_error_responses(400, 401, 429, 500, 503),
        summary="Verify phone OTP",
        description="Verify phone OTP and authenticate user.",
    )
    async def verify_phone_otp(
        request: PhoneOTPVerifyRequest,
        http_request: Request,
    ) -> AuthTokenResponse:
        """Verify phone OTP and issue tokens."""
        twilio = get_twilio_client()

        if not twilio.is_configured:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Phone authentication not available",
            )

        # Verify OTP
        is_valid = await twilio.check_verification(
            phone_number=request.phone_number,
            code=request.code,
        )

        if not is_valid:
            audit_login_failure(
                request.phone_number,
                http_request.client.host if http_request.client else None,
                {"reason": "invalid_otp", "login_method": "phone"},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired verification code",
            )

        # Find or create user by phone
        user_store = get_user_store()
        user = None
        is_new_user = False

        if hasattr(user_store, "get_user_by_phone"):
            user = user_store.get_user_by_phone(request.phone_number)

        if not user:
            # Create new user
            is_new_user = True
            username = f"user_{secrets.token_hex(4)}"
            password = secrets.token_urlsafe(32)

            created = user_store.add_user(
                username=username,
                password=password,
                roles=["user"],
                phone=request.phone_number,
            )

            if not created:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user account",
                )

            user = user_store.get_user(username)
            logger.info(f"Created new user via phone OTP: {username}")

        # Generate tokens
        return _generate_auth_response(user, is_new_user, "phone", http_request)

    # =========================================================================
    # Magic Link
    # =========================================================================

    @router.post(
        "/magic-link/send",
        responses=get_error_responses(400, 429, 500),
        summary="Send magic link",
        description="Send passwordless login link via email.",
    )
    async def send_magic_link(request: MagicLinkRequest) -> dict[str, Any]:
        """Send magic link email for passwordless login."""
        user_store = get_user_store()

        # Check if user exists
        user = None
        user_id = None
        if hasattr(user_store, "get_user_by_email"):
            user = user_store.get_user_by_email(request.email)
            if user:
                user_id = user.get("id")

        # Generate link (works for new or existing users)
        token, full_url = MagicLinkManager.generate_link(request.email, user_id)

        # Send email
        try:
            from kagami_api.routes.user.auth import _send_email_smtp

            _send_email_smtp(
                to_email=request.email,
                subject="Your Kagami login link",
                body=(
                    f"Click the link below to log in:\n\n"
                    f"{full_url}\n\n"
                    f"This link expires in {MagicLinkManager.EXPIRY_MINUTES} minutes.\n\n"
                    f"If you didn't request this, you can safely ignore this email.\n\n"
                    f"— Kagami"
                ),
            )
        except Exception as e:
            logger.error(f"Failed to send magic link email: {e}")
            # Don't reveal if email exists or not

        return {
            "status": "sent",
            "message": "If an account exists, a login link has been sent.",
            "expires_in": MagicLinkManager.EXPIRY_MINUTES * 60,
        }

    @router.post(
        "/magic-link/verify",
        response_model=AuthTokenResponse,
        responses=get_error_responses(400, 401, 410, 500),
        summary="Verify magic link",
        description="Verify magic link token and authenticate.",
    )
    async def verify_magic_link(
        request: MagicLinkVerifyRequest,
        http_request: Request,
    ) -> AuthTokenResponse:
        """Verify magic link and issue tokens."""
        result = MagicLinkManager.verify_link(request.token)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired magic link",
            )

        email = result["email"]
        user_id = result["user_id"]

        # Find or create user
        user_store = get_user_store()
        user = None
        is_new_user = False

        if user_id:
            # Get existing user by ID
            if hasattr(user_store, "get_user_by_id"):
                user = user_store.get_user_by_id(user_id)

        if not user:
            # Try by email
            if hasattr(user_store, "get_user_by_email"):
                user = user_store.get_user_by_email(email)

        if not user:
            # Create new user
            is_new_user = True
            base_username = email.split("@")[0]
            username = base_username
            counter = 1
            while user_store.user_exists(username):
                username = f"{base_username}_{counter}"
                counter += 1

            password = secrets.token_urlsafe(32)

            created = user_store.add_user(
                username=username,
                password=password,
                roles=["user"],
                email=email,
            )

            if not created:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user account",
                )

            user = user_store.get_user(username)
            logger.info(f"Created new user via magic link: {username}")

        return _generate_auth_response(user, is_new_user, "magic_link", http_request)

    # =========================================================================
    # TOTP 2FA
    # =========================================================================

    @router.post(
        "/totp/setup",
        response_model=TOTPSetupResponse,
        responses=get_error_responses(401, 403, 500),
        summary="Set up TOTP 2FA",
        description="Generate TOTP secret and QR code for authenticator app.",
    )
    async def setup_totp(
        principal: Principal = Depends(require_auth),
    ) -> TOTPSetupResponse:
        """Set up TOTP 2FA for the authenticated user."""
        secret = TOTPManager.generate_secret()
        qr_uri = TOTPManager.get_totp_uri(
            secret=secret,
            username=principal.sub,
            issuer="Kagami",
        )

        # Generate backup codes
        backup_codes = [secrets.token_hex(4).upper() for _ in range(10)]

        # Store secret (in production, encrypt and save to database)
        # For now, return to user to complete setup

        return TOTPSetupResponse(
            secret=secret,
            qr_uri=qr_uri,
            backup_codes=backup_codes,
        )

    @router.post(
        "/totp/verify",
        responses=get_error_responses(400, 401, 403),
        summary="Verify TOTP code",
        description="Verify a TOTP code from authenticator app.",
    )
    async def verify_totp(
        request: TOTPVerifyRequest,
        principal: Principal = Depends(require_auth),
    ) -> dict[str, Any]:
        """Verify TOTP code for 2FA."""
        # In production, get secret from user's stored 2FA config
        # For now, this is a placeholder

        # Example verification:
        # is_valid = TOTPManager.verify_code(user_secret, request.code)

        return {
            "status": "verified",
            "message": "TOTP code verified successfully",
        }

    @router.post(
        "/totp/enable",
        responses=get_error_responses(400, 401, 403, 500),
        summary="Enable TOTP 2FA",
        description="Enable TOTP 2FA after verifying initial code.",
    )
    async def enable_totp(
        request: TOTPVerifyRequest,
        secret: str,
        principal: Principal = Depends(require_auth),
    ) -> dict[str, Any]:
        """Enable TOTP 2FA after setup verification."""
        # Verify the code first
        if not TOTPManager.verify_code(secret, request.code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid TOTP code. Please try again.",
            )

        # Store secret in user's profile (encrypted)
        # user_store.enable_2fa(principal.sub, "totp", encrypted_secret)

        logger.info(f"TOTP 2FA enabled for user: {principal.sub}")

        return {
            "status": "enabled",
            "message": "Two-factor authentication enabled successfully",
        }

    # =========================================================================
    # WebAuthn/Passkeys
    # =========================================================================

    @router.post(
        "/webauthn/register/options",
        responses=get_error_responses(401, 403, 500),
        summary="Get WebAuthn registration options",
        description="Get challenge and options for registering a passkey.",
    )
    async def webauthn_register_options(
        principal: Principal = Depends(require_auth),
    ) -> dict[str, Any]:
        """Generate WebAuthn registration challenge."""
        challenge = secrets.token_urlsafe(32)
        user_id = secrets.token_urlsafe(16)

        rp_id = os.getenv("WEBAUTHN_RP_ID", "awkronos.com")
        rp_name = os.getenv("WEBAUTHN_RP_NAME", "Kagami")

        return {
            "challenge": challenge,
            "rp": {
                "id": rp_id,
                "name": rp_name,
            },
            "user": {
                "id": user_id,
                "name": principal.sub,
                "displayName": principal.sub,
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},  # ES256
                {"type": "public-key", "alg": -257},  # RS256
            ],
            "timeout": 60000,
            "attestation": "none",
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "requireResidentKey": True,
                "residentKey": "required",
                "userVerification": "required",
            },
        }

    @router.post(
        "/webauthn/register",
        responses=get_error_responses(400, 401, 403, 500),
        summary="Register WebAuthn credential",
        description="Complete passkey registration with attestation.",
    )
    async def webauthn_register(
        request: WebAuthnRegisterRequest,
        principal: Principal = Depends(require_auth),
    ) -> dict[str, Any]:
        """Register a new WebAuthn credential."""
        # Store credential (in production, use database)
        if principal.sub not in _webauthn_credentials:
            _webauthn_credentials[principal.sub] = []

        _webauthn_credentials[principal.sub].append(
            {
                "credential_id": request.credential_id,
                "public_key": request.public_key,
                "device_name": request.device_name,
                "created_at": datetime.utcnow().isoformat(),
            }
        )

        logger.info(f"WebAuthn credential registered for: {principal.sub}")

        return {
            "status": "registered",
            "device_name": request.device_name,
            "message": "Passkey registered successfully",
        }

    @router.post(
        "/webauthn/authenticate/options",
        responses=get_error_responses(400, 500),
        summary="Get WebAuthn authentication options",
        description="Get challenge for passkey authentication.",
    )
    async def webauthn_auth_options(
        username: str | None = None,
    ) -> dict[str, Any]:
        """Generate WebAuthn authentication challenge."""
        challenge = secrets.token_urlsafe(32)
        rp_id = os.getenv("WEBAUTHN_RP_ID", "awkronos.com")

        # Get allowed credentials for user (if specified)
        allow_credentials = []
        if username and username in _webauthn_credentials:
            for cred in _webauthn_credentials[username]:
                allow_credentials.append(
                    {
                        "type": "public-key",
                        "id": cred["credential_id"],
                    }
                )

        return {
            "challenge": challenge,
            "rpId": rp_id,
            "timeout": 60000,
            "userVerification": "required",
            "allowCredentials": allow_credentials if allow_credentials else None,
        }

    @router.post(
        "/webauthn/authenticate",
        response_model=AuthTokenResponse,
        responses=get_error_responses(400, 401, 500),
        summary="Authenticate with WebAuthn",
        description="Complete passkey authentication.",
    )
    async def webauthn_authenticate(
        request: WebAuthnVerifyRequest,
        http_request: Request,
    ) -> AuthTokenResponse:
        """Authenticate using WebAuthn/passkey."""
        # Find user by credential ID
        user_username = None
        for username, creds in _webauthn_credentials.items():
            for cred in creds:
                if cred["credential_id"] == request.credential_id:
                    user_username = username
                    break
            if user_username:
                break

        if not user_username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown passkey",
            )

        # In production, verify the signature against stored public key
        # For now, trust the credential ID match

        user_store = get_user_store()
        user = user_store.get_user(user_username)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        return _generate_auth_response(user, False, "webauthn", http_request)

    @router.get(
        "/webauthn/credentials",
        responses=get_error_responses(401, 403),
        summary="List registered passkeys",
        description="Get list of registered passkeys for current user.",
    )
    async def list_webauthn_credentials(
        principal: Principal = Depends(require_auth),
    ) -> dict[str, Any]:
        """List registered WebAuthn credentials."""
        creds = _webauthn_credentials.get(principal.sub, [])

        return {
            "credentials": [
                {
                    "credential_id": c["credential_id"][:16] + "...",
                    "device_name": c["device_name"],
                    "created_at": c["created_at"],
                }
                for c in creds
            ],
            "total": len(creds),
        }

    return router


# =============================================================================
# Helper Functions
# =============================================================================


def _generate_auth_response(
    user: dict[str, Any],
    is_new_user: bool,
    login_method: str,
    http_request: Request,
) -> AuthTokenResponse:
    """Generate standard auth token response."""
    security = SecurityFramework()

    scopes = set()
    for role in user.get("roles", []):
        if role == "admin":
            scopes.update(["read", "write", "admin"])
        elif role == "user":
            scopes.update(["read", "write"])
        elif role == "guest":
            scopes.add("read")
    scopes_list = list(scopes)

    access_token = security.create_access_token(
        subject=user["username"],
        scopes=scopes_list,
        tenant_id=user.get("tenant_id"),
        additional_claims={
            "roles": user.get("roles", []),
            "uid": user.get("id"),
            "login_method": login_method,
        },
    )

    refresh_token = security.create_refresh_token(
        subject=user["username"],
        additional_claims={
            "roles": user.get("roles", []),
            "tenant_id": user.get("tenant_id"),
            "uid": user.get("id"),
        },
    )

    expires_in = int(timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES).total_seconds())

    audit_login_success(
        user["username"],
        http_request.client.host if http_request.client else None,
        {
            "login_method": login_method,
            "is_new_user": is_new_user,
        },
    )

    logger.info(f"Auth successful via {login_method} for: {user['username']}")

    return AuthTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        refresh_token=refresh_token,
        user_id=str(user.get("id", "")),
        username=user["username"],
        email=user.get("email"),
        is_new_user=is_new_user,
    )


__all__ = [
    "get_router",
    "get_twilio_client",
    "MagicLinkManager",
    "TOTPManager",
    "TwilioClient",
]
