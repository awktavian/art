"""K OS Privacy Module — Encryption, Anonymization, Token Scrubbing.

CONSOLIDATION (December 8, 2025):
================================
Merged: encryption.py, provider.py, token_scrubber.py
"""

from __future__ import annotations

import hashlib
import logging
import math
import os
import re
import time
import uuid
from collections import Counter
from typing import Any

from cryptography.fernet import Fernet

from kagami.core.interfaces import ConsentType, EncryptionProvider, PrivacyLevel, PrivacyProvider

logger = logging.getLogger(__name__)


# =============================================================================
# ENCRYPTION PROVIDER
# =============================================================================


class KagamiOSEncryptionProvider(EncryptionProvider):
    """Concrete implementation of EncryptionProvider using Fernet (AES)."""

    def __init__(self, key_store: dict[str, str] | None = None) -> None:
        """Initialize with optional key store."""
        self._keys: dict[str, Fernet] = {}
        self._active_key_id: str | None = None

        keys_str = os.getenv("KAGAMI_ENCRYPTION_KEYS", "")
        if keys_str:
            for pair in keys_str.split(","):
                if ":" in pair:
                    kid, kval = pair.split(":", 1)
                    try:
                        self._keys[kid] = Fernet(kval.encode())
                        if not self._active_key_id:
                            self._active_key_id = kid
                    except Exception as e:
                        logger.error(f"Failed to load key {kid}: {e}")

        if key_store:
            for kid, kval in key_store.items():
                try:
                    self._keys[kid] = Fernet(kval.encode())
                    if not self._active_key_id:
                        self._active_key_id = kid
                except Exception:
                    pass

        if not self._keys:
            temp_id = "dev_key_1"
            key = Fernet.generate_key()
            self._keys[temp_id] = Fernet(key)
            self._active_key_id = temp_id
            logger.warning("Using generated temporary encryption key (DEV MODE ONLY)")

    async def encrypt(self, data: bytes, key_id: str | None = None) -> bytes:
        """Encrypt data."""
        target_id = key_id or self._active_key_id
        if not target_id or target_id not in self._keys:
            raise ValueError(f"Encryption key {target_id} not found")
        fernet = self._keys[target_id]
        encrypted = fernet.encrypt(data)
        return f"{target_id}:".encode() + encrypted

    async def decrypt(self, encrypted_data: bytes, key_id: str | None = None) -> bytes:
        """Decrypt data."""
        extracted_id = None
        content = encrypted_data

        try:
            if b":" in encrypted_data:
                parts = encrypted_data.split(b":", 1)
                if len(parts) == 2:
                    possible_id = parts[0].decode()
                    if possible_id in self._keys:
                        extracted_id = possible_id
                        content = parts[1]
        except Exception:
            pass

        target_id = key_id or extracted_id or self._active_key_id
        if not target_id or target_id not in self._keys:
            raise ValueError(f"Decryption key {target_id} not found")
        fernet = self._keys[target_id]
        return fernet.decrypt(content)

    def get_key_id(self, data: bytes) -> str | None:
        """Get key ID used to encrypt data."""
        try:
            if b":" in data:
                parts = data.split(b":", 1)
                return parts[0].decode()
        except Exception:
            pass
        return None


# =============================================================================
# PRIVACY PROVIDER
# =============================================================================


class KagamiOSPrivacyProvider(PrivacyProvider):
    """Concrete implementation of PrivacyProvider."""

    def __init__(self) -> None:
        self._pii_patterns = {
            "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "phone": re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
            "credit_card": re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
        }
        self._consent_cache: dict[str, dict[ConsentType, bool]] = {}

    async def classify_data(self, data: dict[str, Any]) -> PrivacyLevel:
        """Classify data according to privacy level."""
        data_str = str(data)
        for pattern in self._pii_patterns.values():
            if pattern.search(data_str):
                return PrivacyLevel.CONFIDENTIAL
        return PrivacyLevel.INTERNAL

    async def anonymize(self, data: dict[str, Any], fields: list[str]) -> dict[str, Any]:
        """Anonymize specified fields in data."""
        result = data.copy()
        for field in fields:
            if field in result:
                val = str(result[field])
                salt = "kagami_privacy_salt"
                hashed = hashlib.sha256(f"{val}{salt}".encode()).hexdigest()[:16]
                result[field] = f"redacted_{hashed}"
        return result

    async def check_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        """Check if user has given specified consent."""
        user_consents = self._consent_cache.get(user_id, {})
        if consent_type in user_consents:
            return user_consents[consent_type]
        return False

    async def audit_access(self, user_id: str, resource: str, action: str) -> None:
        """Audit data access for compliance."""
        entry = {
            "timestamp": time.time(),
            "audit_id": str(uuid.uuid4()),
            "user_id": user_id,
            "resource": resource,
            "action": action,
        }
        logger.info(f"PRIVACY_AUDIT: {entry}")


# =============================================================================
# TOKEN SCRUBBER
# =============================================================================


class TokenScrubber:
    """Detects and scrubs tokens, API keys, PII from data."""

    def __init__(self) -> None:
        self.patterns = {
            "api_key": re.compile(
                r"(api[_-]?key|apikey)[\s:=]+['\"]?([a-zA-Z0-9_\-]{20,})['\"]?", re.I
            ),
            "bearer_token": re.compile(r"Bearer\s+([a-zA-Z0-9_\-\.]{20,})", re.I),
            "jwt": re.compile(r"eyJ[a-zA-Z0-9_\-]+\.eyJ[a-zA-Z0-9_\-]+\.[a-zA-Z0-9_\-]+"),
            "password": re.compile(r"(password|passwd|pwd)[\s:=]+['\"]?([^\s'\"]+)['\"]?", re.I),
            "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
            "credit_card": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
            "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        }
        self.min_entropy = 4.5

    def scrub(self, data: Any) -> Any:
        """Scrub sensitive data from any structure."""
        if isinstance(data, str):
            return self._scrub_string(data)
        elif isinstance(data, dict):
            return {k: self.scrub(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.scrub(item) for item in data]
        else:
            return data

    def _scrub_string(self, text: str) -> str:
        """Scrub string content."""
        scrubbed = text
        for pattern_name, pattern in self.patterns.items():
            scrubbed = pattern.sub(f"[REDACTED_{pattern_name.upper()}]", scrubbed)
        words = scrubbed.split()
        for word in words:
            if len(word) > 20 and self._calculate_entropy(word) > self.min_entropy:
                scrubbed = scrubbed.replace(word, "[REDACTED_HIGH_ENTROPY]")
        return scrubbed

    def _calculate_entropy(self, s: str) -> float:
        """Calculate Shannon entropy of string."""
        if not s:
            return 0.0
        counts = Counter(s)
        total = len(s)
        return -sum(count / total * math.log2(count / total) for count in counts.values())

    def detect_violations(self, data: Any) -> list[dict[str, Any]]:
        """Detect violations without scrubbing (for metrics)."""
        violations = []
        if isinstance(data, str):
            for pattern_name, pattern in self.patterns.items():
                if pattern.search(data):
                    violations.append({"type": pattern_name, "severity": "high"})
        elif isinstance(data, dict):
            for v in data.values():
                violations.extend(self.detect_violations(v))
        elif isinstance(data, list):
            for item in data:
                violations.extend(self.detect_violations(item))
        return violations


_scrubber: TokenScrubber | None = None


def get_scrubber() -> TokenScrubber:
    """Get singleton scrubber."""
    global _scrubber
    if _scrubber is None:
        _scrubber = TokenScrubber()
    return _scrubber


__all__ = ["KagamiOSEncryptionProvider", "KagamiOSPrivacyProvider", "TokenScrubber", "get_scrubber"]
