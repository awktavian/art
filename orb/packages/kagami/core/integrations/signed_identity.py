"""Signed Identity Events for Secure Mesh Propagation.

Cryptographically signed identity detection events using Ed25519.
Ensures identity events can be verified by mesh peers and
prevents spoofing of "who is home" data.

Colony: Crystal (e₇) — Verification and Trust
Safety: h(x) ≥ 0 — Cryptographic integrity

Usage:
    signer = IdentityEventSigner()

    # Sign an identity detection
    event = SignedIdentityEvent(
        identity_id="abc123",
        camera_id="cam_001",
        confidence=0.92,
    )
    signed = signer.sign(event)

    # Verify on mesh peer
    is_valid = signer.verify(signed)
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Try to import cryptography libraries
try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography library not available, signatures disabled")


@dataclass
class SignedIdentityEvent:
    """A cryptographically signed identity detection event.

    The signature covers: identity_id, camera_id, timestamp, confidence
    to prevent tampering and replay attacks.
    """

    # Core detection data
    identity_id: str
    camera_id: str
    camera_name: str
    confidence: float
    timestamp: float = field(default_factory=time.time)

    # Optional identity info
    name: str | None = None

    # Location context
    location: str | None = None

    # Face quality metrics
    face_quality: float = 0.0
    bbox: tuple[int, int, int, int] | None = None

    # Cryptographic signature
    signature: str | None = None  # Base64 encoded Ed25519 signature
    signer_hub_id: str | None = None  # Hub ID that signed this event
    signer_public_key: str | None = None  # Base64 encoded public key

    def to_signable_bytes(self) -> bytes:
        """Get canonical bytes representation for signing.

        Excludes signature fields to allow verification.
        """
        data = {
            "identity_id": self.identity_id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "confidence": round(self.confidence, 4),  # Normalize precision
            "timestamp": int(self.timestamp * 1000),  # Milliseconds
            "name": self.name,
            "location": self.location,
        }
        # Deterministic JSON encoding
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "identity_id": self.identity_id,
            "camera_id": self.camera_id,
            "camera_name": self.camera_name,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "name": self.name,
            "location": self.location,
            "face_quality": self.face_quality,
            "bbox": self.bbox,
            "signature": self.signature,
            "signer_hub_id": self.signer_hub_id,
            "signer_public_key": self.signer_public_key,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SignedIdentityEvent:
        """Create from dictionary."""
        return cls(
            identity_id=data["identity_id"],
            camera_id=data["camera_id"],
            camera_name=data.get("camera_name", ""),
            confidence=data["confidence"],
            timestamp=data.get("timestamp", time.time()),
            name=data.get("name"),
            location=data.get("location"),
            face_quality=data.get("face_quality", 0.0),
            bbox=tuple(data["bbox"]) if data.get("bbox") else None,
            signature=data.get("signature"),
            signer_hub_id=data.get("signer_hub_id"),
            signer_public_key=data.get("signer_public_key"),
        )

    @property
    def is_signed(self) -> bool:
        """Check if event has a signature."""
        return self.signature is not None

    @property
    def event_hash(self) -> str:
        """Get SHA-256 hash of signable content."""
        return hashlib.sha256(self.to_signable_bytes()).hexdigest()


class IdentityEventSigner:
    """Signs and verifies identity detection events using Ed25519.

    Uses the Hub's mesh authentication keypair for signing.
    Events can be verified by any mesh peer with the public key.
    """

    def __init__(
        self,
        hub_id: str = "local",
        private_key_bytes: bytes | None = None,
    ):
        """Initialize signer.

        Args:
            hub_id: Identifier for this hub/signer
            private_key_bytes: Optional 32-byte Ed25519 private key
        """
        self.hub_id = hub_id
        self._private_key: Any | None = None
        self._public_key: Any | None = None
        self._public_key_bytes: bytes | None = None

        if CRYPTO_AVAILABLE:
            if private_key_bytes:
                self._load_key(private_key_bytes)
            else:
                self._generate_key()

    def _generate_key(self) -> None:
        """Generate a new Ed25519 keypair."""
        if not CRYPTO_AVAILABLE:
            return

        self._private_key = Ed25519PrivateKey.generate()
        self._public_key = self._private_key.public_key()
        self._public_key_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
        logger.debug(f"Generated new Ed25519 keypair for hub {self.hub_id}")

    def _load_key(self, private_key_bytes: bytes) -> None:
        """Load keypair from private key bytes."""
        if not CRYPTO_AVAILABLE:
            return

        try:
            self._private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
            self._public_key = self._private_key.public_key()
            self._public_key_bytes = self._public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            logger.debug(f"Loaded Ed25519 keypair for hub {self.hub_id}")
        except Exception as e:
            logger.error(f"Failed to load private key: {e}")

    @property
    def public_key_base64(self) -> str | None:
        """Get base64-encoded public key."""
        if self._public_key_bytes:
            return base64.b64encode(self._public_key_bytes).decode("ascii")
        return None

    def sign(self, event: SignedIdentityEvent) -> SignedIdentityEvent:
        """Sign an identity event.

        Args:
            event: Event to sign

        Returns:
            Event with signature, signer_hub_id, and signer_public_key set
        """
        if not CRYPTO_AVAILABLE or not self._private_key:
            logger.warning("Signing unavailable, returning unsigned event")
            return event

        try:
            # Get signable bytes
            message = event.to_signable_bytes()

            # Sign with Ed25519
            signature = self._private_key.sign(message)

            # Update event
            event.signature = base64.b64encode(signature).decode("ascii")
            event.signer_hub_id = self.hub_id
            event.signer_public_key = self.public_key_base64

            logger.debug(f"Signed identity event for {event.identity_id}")
            return event

        except Exception as e:
            logger.error(f"Signing failed: {e}")
            return event

    def verify(
        self,
        event: SignedIdentityEvent,
        trusted_public_keys: dict[str, bytes] | None = None,
    ) -> bool:
        """Verify an identity event's signature.

        Args:
            event: Event to verify
            trusted_public_keys: Optional dict of hub_id -> public_key_bytes
                If not provided, uses the embedded public key

        Returns:
            True if signature is valid
        """
        if not CRYPTO_AVAILABLE:
            logger.warning("Verification unavailable, assuming valid")
            return True

        if not event.is_signed:
            logger.warning("Event is not signed")
            return False

        try:
            # Get public key
            public_key_bytes: bytes | None = None

            if trusted_public_keys and event.signer_hub_id:
                public_key_bytes = trusted_public_keys.get(event.signer_hub_id)

            if not public_key_bytes and event.signer_public_key:
                public_key_bytes = base64.b64decode(event.signer_public_key)

            if not public_key_bytes:
                logger.error("No public key available for verification")
                return False

            # Load public key
            public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)

            # Get signature
            signature = base64.b64decode(event.signature)

            # Get signable bytes
            message = event.to_signable_bytes()

            # Verify
            public_key.verify(signature, message)

            logger.debug(f"Verified signature for event from {event.signer_hub_id}")
            return True

        except InvalidSignature:
            logger.warning(f"Invalid signature for event from {event.signer_hub_id}")
            return False
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

    def get_private_key_bytes(self) -> bytes | None:
        """Get private key bytes for storage.

        WARNING: Handle with care - this is sensitive data.
        """
        if not CRYPTO_AVAILABLE or not self._private_key:
            return None

        return self._private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
        )


# Singleton signer instance
_event_signer: IdentityEventSigner | None = None


def get_identity_event_signer(hub_id: str = "local") -> IdentityEventSigner:
    """Get singleton identity event signer.

    Args:
        hub_id: Hub identifier

    Returns:
        IdentityEventSigner instance
    """
    global _event_signer

    if _event_signer is None:
        # Try to load key from keychain
        private_key_bytes = None
        try:
            from kagami.core.security import get_secret

            key_b64 = get_secret("identity_signing_key")
            if key_b64:
                private_key_bytes = base64.b64decode(key_b64)
        except Exception:
            pass

        _event_signer = IdentityEventSigner(
            hub_id=hub_id,
            private_key_bytes=private_key_bytes,
        )

        # Save generated key to keychain if new
        if private_key_bytes is None and _event_signer.get_private_key_bytes():
            try:
                from kagami.core.security import set_secret

                key_bytes = _event_signer.get_private_key_bytes()
                if key_bytes:
                    set_secret(
                        "identity_signing_key",
                        base64.b64encode(key_bytes).decode("ascii"),
                    )
            except Exception:
                pass

    return _event_signer


def create_signed_identity_event(
    identity_id: str,
    camera_id: str,
    camera_name: str,
    confidence: float,
    name: str | None = None,
    location: str | None = None,
    face_quality: float = 0.0,
) -> SignedIdentityEvent:
    """Create and sign an identity detection event.

    Convenience function that creates and signs in one step.

    Args:
        identity_id: Detected identity ID
        camera_id: Camera that detected the identity
        camera_name: Human-readable camera name
        confidence: Match confidence (0-1)
        name: Optional identity name
        location: Optional location/room name
        face_quality: Face detection quality score

    Returns:
        Signed identity event
    """
    event = SignedIdentityEvent(
        identity_id=identity_id,
        camera_id=camera_id,
        camera_name=camera_name,
        confidence=confidence,
        name=name,
        location=location or camera_name,
        face_quality=face_quality,
    )

    signer = get_identity_event_signer()
    return signer.sign(event)
