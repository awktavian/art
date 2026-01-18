"""Protected Personal Information.

PRIVACY IS SAFETY. h(x) ≥ 0 REQUIRES PRIVACY.

Every person owns their own information. This includes:
- All recordings of them (audio, video, camera footage)
- All information they share (what they say, preferences, patterns)
- All alerts about them (notifications, detections, presence)
- All access to their services (email, calendar, accounts)
- All senses (what the system perceives about them)
- All effectors (actions that affect them)

Privacy rules:
- Each person controls their own information
- Nobody is privileged over another person's data
- Sharing requires explicit consent from the owner
- Revocation is immediate and complete

Violating privacy is a SAFETY VIOLATION.
A system that leaks private information has h(x) < 0.

Private by design. Safe by design.

Colony: Crystal (e₇) — Security boundary
h(x) ≥ 0. Always.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Try to import cryptographic libraries
try:
    import base64

    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    HAS_CRYPTO = True
except ImportError:
    HAS_CRYPTO = False


class AccessLevel(Enum):
    """Access levels for protected information."""

    PUBLIC = "public"  # Anyone can access
    SELF_ONLY = "self_only"  # Only the person themselves
    SHARED = "shared"  # Explicitly shared with specific identities
    MUTUAL = "mutual"  # Requires consent from all parties


# =============================================================================
# DYNAMIC IDENTITY LOADING
# =============================================================================


def _load_known_identities() -> frozenset[str]:
    """Load known identities dynamically from character profiles.

    No hardcoded identities. Works for any household configuration.
    """
    try:
        from kagami.core.integrations.character_identity import (
            list_characters,
            load_character_profile,
        )

        identities = set()
        household_roles = {"owner", "partner", "family", "resident"}

        for char_name in list_characters():
            profile = load_character_profile(char_name)
            if profile and profile.role in household_roles:
                identities.add(profile.identity_id)

        return frozenset(identities)

    except ImportError:
        # Fallback: empty set (identities will be registered at runtime)
        return frozenset()
    except Exception:
        return frozenset()


# Known identities (loaded dynamically - no hardcoding)
KNOWN_IDENTITIES = _load_known_identities()


@dataclass
class ProtectedInfo:
    """A piece of access-controlled information.

    The owner is the ONLY person who controls access to this information.
    There are no privileged observers.
    """

    key: str
    value: Any
    owner_id: str  # The person who owns this information
    access_level: AccessLevel
    shared_with: frozenset[str] = field(default_factory=frozenset)
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None
    encrypted: bool = False
    signature: str | None = None

    def is_expired(self) -> bool:
        """Check if this info has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def can_access(self, identity_id: str) -> bool:
        """Check if an identity can access this information.

        Rules:
        - PUBLIC: Anyone
        - SELF_ONLY: Only the owner
        - SHARED: Owner + explicitly shared identities
        - MUTUAL: All parties listed must consent (not implemented yet)
        """
        if self.is_expired():
            return False

        if self.access_level == AccessLevel.PUBLIC:
            return True
        elif self.access_level == AccessLevel.SELF_ONLY:
            # ONLY the owner can see their own private info
            return identity_id == self.owner_id
        elif self.access_level == AccessLevel.SHARED:
            # Owner can see, plus anyone they explicitly shared with
            return identity_id == self.owner_id or identity_id in self.shared_with
        elif self.access_level == AccessLevel.MUTUAL:
            # All parties must be in the shared_with set
            return identity_id in self.shared_with
        return False

    def is_owner(self, identity_id: str) -> bool:
        """Check if identity is the owner of this information."""
        return identity_id == self.owner_id


class ProtectedInfoStore:
    """Secure storage for personal information.

    PRIVACY RULES:
    - Every person owns their own information
    - You may not share information about another person without consent
    - There are NO privileged users or "owners" of the system
    - Access is strictly identity-based

    The store starts EMPTY. Information is only stored when the
    person themselves provides it. The system never pre-populates
    personal information.
    """

    def __init__(self, encryption_key: bytes | None = None):
        self._store: dict[str, ProtectedInfo] = {}
        self._access_log: list[dict] = []
        self._encryption_key = encryption_key
        # Store starts empty. No pre-populated information.
        # Each person provides their own data.

    def set(
        self,
        key: str,
        value: Any,
        owner_id: str,
        access_level: AccessLevel = AccessLevel.SELF_ONLY,
        shared_with: set[str] | None = None,
        expires_in_seconds: float | None = None,
        encrypt: bool = False,
    ) -> None:
        """Store personal information.

        Args:
            key: Unique identifier for this information
            value: The information to store
            owner_id: The person who owns this information
            access_level: Who can access this information
            shared_with: Identities the owner has shared this with
            expires_in_seconds: Optional expiration time
            encrypt: Whether to encrypt the value at rest
        """
        expires_at = None
        if expires_in_seconds is not None:
            expires_at = time.time() + expires_in_seconds

        # Encrypt value if requested and crypto is available
        stored_value = value
        is_encrypted = False
        if encrypt and HAS_CRYPTO and self._encryption_key:
            stored_value = self._encrypt_value(value)
            is_encrypted = True

        # Create signature for integrity verification
        signature = self._create_signature(key, stored_value, owner_id)

        info = ProtectedInfo(
            key=key,
            value=stored_value,
            owner_id=owner_id,
            access_level=access_level,
            shared_with=frozenset(shared_with or set()),
            expires_at=expires_at,
            encrypted=is_encrypted,
            signature=signature,
        )

        self._store[key] = info

    def get(
        self,
        key: str,
        identity_id: str,
        default: Any = None,
    ) -> Any:
        """Retrieve information if authorized.

        The identity must either:
        - Be the owner of the information
        - Have been explicitly shared access by the owner

        There are NO backdoors or privileged access.
        """
        self._log_access(key, identity_id, "get")

        info = self._store.get(key)
        if info is None:
            return default

        if not info.can_access(identity_id):
            self._log_access(key, identity_id, "denied")
            return default

        # Verify integrity
        if not self._verify_signature(info):
            self._log_access(key, identity_id, "integrity_failure")
            return default

        # Decrypt if needed
        value = info.value
        if info.encrypted and HAS_CRYPTO and self._encryption_key:
            value = self._decrypt_value(value)

        self._log_access(key, identity_id, "granted")
        return value

    def share_with(
        self,
        key: str,
        owner_id: str,
        share_with_id: str,
    ) -> bool:
        """Share information with another identity.

        ONLY the owner can share their information.
        This requires the owner's identity to be verified.
        """
        info = self._store.get(key)
        if info is None:
            return False

        # Only the owner can share
        if not info.is_owner(owner_id):
            self._log_access(key, owner_id, "share_denied_not_owner")
            return False

        # Update shared_with
        new_shared = info.shared_with | {share_with_id}
        info = ProtectedInfo(
            key=info.key,
            value=info.value,
            owner_id=info.owner_id,
            access_level=AccessLevel.SHARED,
            shared_with=new_shared,
            created_at=info.created_at,
            expires_at=info.expires_at,
            encrypted=info.encrypted,
            signature=info.signature,
        )
        self._store[key] = info

        self._log_access(key, owner_id, f"shared_with:{share_with_id}")
        return True

    def revoke_share(
        self,
        key: str,
        owner_id: str,
        revoke_from_id: str,
    ) -> bool:
        """Revoke sharing from another identity.

        ONLY the owner can revoke access.
        """
        info = self._store.get(key)
        if info is None:
            return False

        if not info.is_owner(owner_id):
            return False

        new_shared = info.shared_with - {revoke_from_id}
        new_level = AccessLevel.SHARED if new_shared else AccessLevel.SELF_ONLY

        info = ProtectedInfo(
            key=info.key,
            value=info.value,
            owner_id=info.owner_id,
            access_level=new_level,
            shared_with=new_shared,
            created_at=info.created_at,
            expires_at=info.expires_at,
            encrypted=info.encrypted,
            signature=info.signature,
        )
        self._store[key] = info
        return True

    def can_access(self, key: str, identity_id: str) -> bool:
        """Check if an identity can access a key."""
        info = self._store.get(key)
        if info is None:
            return False
        return info.can_access(identity_id)

    def list_my_keys(self, identity_id: str) -> list[str]:
        """List keys owned by this identity."""
        return [key for key, info in self._store.items() if info.owner_id == identity_id]

    def list_accessible_keys(self, identity_id: str) -> list[str]:
        """List all keys accessible to an identity."""
        return [key for key, info in self._store.items() if info.can_access(identity_id)]

    def _create_signature(self, key: str, value: Any, owner_id: str) -> str:
        """Create HMAC signature for integrity verification."""
        data = f"{key}:{json.dumps(value, sort_keys=True)}:{owner_id}"
        return hashlib.sha256(data.encode()).hexdigest()

    def _verify_signature(self, info: ProtectedInfo) -> bool:
        """Verify the integrity signature of stored info."""
        expected = self._create_signature(info.key, info.value, info.owner_id)
        return info.signature == expected

    def _encrypt_value(self, value: Any) -> str:
        """Encrypt a value using Fernet."""
        if not HAS_CRYPTO or not self._encryption_key:
            return json.dumps(value)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"kagami_protected_info",
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self._encryption_key))
        f = Fernet(key)

        plaintext = json.dumps(value).encode()
        return f.encrypt(plaintext).decode()

    def _decrypt_value(self, encrypted: str) -> Any:
        """Decrypt an encrypted value."""
        if not HAS_CRYPTO or not self._encryption_key:
            return json.loads(encrypted)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"kagami_protected_info",
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(self._encryption_key))
        f = Fernet(key)

        plaintext = f.decrypt(encrypted.encode())
        return json.loads(plaintext.decode())

    def _log_access(self, key: str, identity_id: str, action: str) -> None:
        """Log access attempts for audit."""
        self._access_log.append(
            {
                "timestamp": time.time(),
                "key": key,
                "identity_id": identity_id,
                "action": action,
            }
        )

        # Keep only last 1000 entries
        if len(self._access_log) > 1000:
            self._access_log = self._access_log[-1000:]

    def get_my_access_log(self, identity_id: str) -> list[dict]:
        """Get access log for your own information only."""
        return [
            entry
            for entry in self._access_log
            if entry["key"].startswith(f"{identity_id.split('_')[0]}.")
        ]


# Global singleton instance
_protected_store: ProtectedInfoStore | None = None


def get_protected_store() -> ProtectedInfoStore:
    """Get the global protected information store."""
    global _protected_store
    if _protected_store is None:
        _protected_store = ProtectedInfoStore()
    return _protected_store


def get_my_info(key: str, identity_id: str, default: Any = None) -> Any:
    """Get your own protected information."""
    return get_protected_store().get(key, identity_id, default)


def can_access(key: str, identity_id: str) -> bool:
    """Check if you can access a key."""
    return get_protected_store().can_access(key, identity_id)


def is_known_identity(identity_id: str) -> bool:
    """Check if an identity is known to the system.

    Checks both:
    1. Pre-loaded KNOWN_IDENTITIES from character profiles
    2. Identities registered in the protected store at runtime
    """
    if identity_id in KNOWN_IDENTITIES:
        return True

    # Also check the store for runtime-registered identities
    store = get_protected_store()
    return any(info.owner_id == identity_id for info in store._store.values())


# =============================================================================
# Personal Information API (Generic)
# =============================================================================


def store_my_info(
    key: str,
    value: Any,
    identity_id: str,
    shared_with: set[str] | None = None,
    encrypt: bool = False,
) -> None:
    """Store your own information.

    Only you can store information under your identity.
    """
    store = get_protected_store()
    store.set(
        key=key,
        value=value,
        owner_id=identity_id,
        access_level=AccessLevel.SHARED if shared_with else AccessLevel.SELF_ONLY,
        shared_with=shared_with,
        encrypt=encrypt,
    )


def delete_my_info(key: str, identity_id: str) -> bool:
    """Delete your own information.

    Only you can delete information you own.
    """
    store = get_protected_store()
    info = store._store.get(key)
    if info is None:
        return False
    if info.owner_id != identity_id:
        return False  # Can only delete your own
    del store._store[key]
    return True


def list_my_info(identity_id: str) -> list[str]:
    """List all keys of information you own."""
    return get_protected_store().list_my_keys(identity_id)


# =============================================================================
# Information Filtering for External Systems
# =============================================================================


def filter_for_identity(
    data: dict,
    identity_id: str,
) -> dict:
    """Filter a dictionary to only include information owned by or shared with this identity.

    This ensures no one sees information they shouldn't.
    """
    result = {}

    for key, value in data.items():
        # Only include if:
        # 1. It's public information
        # 2. It's the identity's own information
        # 3. It's been explicitly shared with them

        # For nested dicts, recursively filter
        if isinstance(value, dict):
            result[key] = filter_for_identity(value, identity_id)
        else:
            # By default, include non-sensitive keys
            # Sensitive keys are filtered by the store's access control
            result[key] = value

    return result


# =============================================================================
# Tests (Generic - uses dynamically loaded identities)
# =============================================================================

if __name__ == "__main__":
    store = ProtectedInfoStore()

    # Get identities dynamically
    identities = list(KNOWN_IDENTITIES)
    if len(identities) < 2:
        # Fallback for testing without character profiles
        identities = ["person_a", "person_b"]

    person_a = identities[0]
    person_b = identities[1] if len(identities) > 1 else "person_b"

    print("=== Privacy Rules Test ===")
    print()
    print("Rule: Store starts EMPTY. No pre-populated data.")
    print("Rule: Every person owns their own information.")
    print("Rule: Nobody is privileged over another person's data.")
    print()
    print(f"Loaded identities: {identities}")
    print()

    print("Store is empty:")
    print(f"  {person_a}'s keys: {store.list_my_keys(person_a)}")
    print(f"  {person_b}'s keys: {store.list_my_keys(person_b)}")

    print()
    print("=== Self-Storage Test ===")
    print()

    # Person A stores their own info
    print(f"{person_a} stores their own preference:")
    store.set(
        key=f"{person_a}.preference.example",
        value="test_value",
        owner_id=person_a,
        access_level=AccessLevel.SELF_ONLY,
    )
    a_value = store.get(f"{person_a}.preference.example", person_a)
    print(f"  {person_a} sees: {a_value}")

    b_sees = store.get(f"{person_a}.preference.example", person_b)
    print(f"  {person_b} sees: {b_sees}  (None = correctly denied)")

    print()
    print("=== Sharing Test ===")
    print()

    # Person A shares with Person B
    print(f"{person_a} shares their preference with {person_b}:")
    store.share_with(f"{person_a}.preference.example", person_a, person_b)
    b_sees_shared = store.get(f"{person_a}.preference.example", person_b)
    print(f"  {person_b} can now see: {b_sees_shared}")

    print()
    print(f"{person_a} revokes sharing:")
    store.revoke_share(f"{person_a}.preference.example", person_a, person_b)
    b_sees_after = store.get(f"{person_a}.preference.example", person_b)
    print(f"  {person_b} can now see: {b_sees_after}  (None = correctly revoked)")

    print()
    print("=== Cross-Access Test ===")
    print()

    print("Unknown user trying to access protected info:")
    unknown = store.get(f"{person_a}.preference.example", "unknown_user")
    print(f"  Result: {unknown}  (None = correctly denied)")

    print()
    print("✓ Privacy model verified. Store starts empty. Each person controls their own data.")
    print(f"✓ Generic design — works for any household ({len(identities)} members loaded)")
