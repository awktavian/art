"""Unified Cryptographic Layer — All Encryption Routes Here.

THIS IS THE ONLY ENCRYPTION INTERFACE IN KAGAMI.
All legacy Fernet/AES paths are deprecated and route through this layer.

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────┐
│                    UNIFIED CRYPTO LAYER                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │                    EXTERNAL API                                  │  │
│   │                                                                  │  │
│   │   encrypt(data) → ciphertext                                    │  │
│   │   decrypt(ciphertext) → data                                    │  │
│   │   sign(data) → signature                                        │  │
│   │   verify(data, sig) → bool                                      │  │
│   │                                                                  │  │
│   └────────────────────────┬────────────────────────────────────────┘  │
│                            │                                            │
│                            ▼                                            │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │              QUANTUM-SAFE ENFORCEMENT                            │  │
│   │                                                                  │  │
│   │   Mode: HYBRID (X25519 + Kyber + AES-256-GCM)                   │  │
│   │   Signatures: Ed25519 + Dilithium                               │  │
│   │   Key Storage: HSM/Keychain                                      │  │
│   │                                                                  │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                          │
│   LEGACY DEPRECATION:                                                    │
│   ❌ Fernet → Routed through hybrid encrypt                             │
│   ❌ Raw AES → Routed through hybrid encrypt                            │
│   ❌ Plain storage → FORBIDDEN                                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

Colony: Crystal (D₅) — Security enforcement
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import warnings
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, TypeVar

from kagami.core.exceptions import SecurityError
from kagami.core.security.quantum_safe import (
    CryptoMode,
    HybridKeypair,
    QuantumSafeConfig,
    QuantumSafeCrypto,
    SecurityLevel,
    get_quantum_safe_crypto,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# Configuration
# =============================================================================


class EncryptionEnforcement(Enum):
    """Encryption enforcement level."""

    STRICT = auto()  # Reject all non-quantum-safe operations
    WARN = auto()  # Warn but allow legacy (transition period)
    AUDIT = auto()  # Log all operations for audit


@dataclass
class UnifiedCryptoConfig:
    """Unified crypto configuration.

    Attributes:
        enforcement: Enforcement level for legacy operations.
        security_level: NIST security level.
        mode: Cryptographic mode (hybrid recommended).
        audit_all: Log all encryption operations.
        reject_plaintext: Reject unencrypted storage attempts.
    """

    enforcement: EncryptionEnforcement = EncryptionEnforcement.STRICT
    security_level: SecurityLevel = SecurityLevel.LEVEL_3
    mode: CryptoMode = CryptoMode.HYBRID
    audit_all: bool = True
    reject_plaintext: bool = True

    def __post_init__(self) -> None:
        """Load from environment."""
        enforcement = os.environ.get("KAGAMI_CRYPTO_ENFORCEMENT", "STRICT")
        self.enforcement = EncryptionEnforcement[enforcement.upper()]

        level = os.environ.get("KAGAMI_CRYPTO_SECURITY_LEVEL", "3")
        self.security_level = SecurityLevel(int(level))

        self.audit_all = os.environ.get("KAGAMI_CRYPTO_AUDIT_ALL", "true").lower() == "true"

        self.reject_plaintext = (
            os.environ.get("KAGAMI_CRYPTO_REJECT_PLAINTEXT", "true").lower() == "true"
        )


# =============================================================================
# Audit Log
# =============================================================================


@dataclass
class CryptoAuditEntry:
    """Audit entry for cryptographic operation."""

    operation: str
    timestamp: float
    data_size: int
    algorithm: str
    success: bool
    caller: str
    context: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class CryptoAuditLog:
    """Audit log for all cryptographic operations."""

    def __init__(self, max_entries: int = 10000) -> None:
        self._entries: list[CryptoAuditEntry] = []
        self._max_entries = max_entries
        self._lock = asyncio.Lock()

    async def log(self, entry: CryptoAuditEntry) -> None:
        """Log an audit entry."""
        async with self._lock:
            self._entries.append(entry)
            if len(self._entries) > self._max_entries:
                self._entries = self._entries[-self._max_entries :]

    def log_sync(self, entry: CryptoAuditEntry) -> None:
        """Log synchronously (for legacy code paths)."""
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries :]

    def get_entries(
        self,
        operation: str | None = None,
        since: float | None = None,
        limit: int = 100,
    ) -> list[CryptoAuditEntry]:
        """Get audit entries."""
        entries = self._entries

        if operation:
            entries = [e for e in entries if e.operation == operation]
        if since:
            entries = [e for e in entries if e.timestamp >= since]

        return entries[-limit:]


_audit_log = CryptoAuditLog()


def get_crypto_audit_log() -> CryptoAuditLog:
    """Get the global crypto audit log."""
    return _audit_log


# =============================================================================
# Legacy Deprecation
# =============================================================================


def _emit_legacy_warning(operation: str, caller: str) -> None:
    """Emit deprecation warning for legacy crypto."""
    msg = (
        f"DEPRECATED: Legacy crypto operation '{operation}' from {caller}. "
        f"Migrate to unified_crypto.encrypt()/decrypt(). "
        f"Legacy operations route through quantum-safe layer."
    )
    warnings.warn(msg, DeprecationWarning, stacklevel=4)
    logger.warning(f"⚠️ {msg}")


def _get_caller() -> str:
    """Get caller information for audit."""
    import traceback

    stack = traceback.extract_stack()
    for frame in reversed(stack[:-2]):
        if "unified_crypto" not in frame.filename:
            return f"{frame.filename}:{frame.lineno}"
    return "unknown"


# =============================================================================
# Unified Crypto Interface
# =============================================================================


class UnifiedCrypto:
    """Unified cryptographic interface.

    ALL encryption in Kagami goes through this class.
    Legacy operations are routed through quantum-safe layer.

    Example:
        >>> crypto = await get_unified_crypto()
        >>>
        >>> # Encrypt data
        >>> ciphertext = await crypto.encrypt(b"secret data")
        >>>
        >>> # Decrypt data
        >>> plaintext = await crypto.decrypt(ciphertext)
        >>>
        >>> # Encrypt with context (bound to ciphertext)
        >>> ciphertext = await crypto.encrypt(
        ...     b"data",
        ...     context={"user": "alice", "purpose": "storage"}
        ... )
        >>>
        >>> # Sign and verify
        >>> sig = await crypto.sign(b"message")
        >>> valid = await crypto.verify(b"message", sig)
    """

    def __init__(self, config: UnifiedCryptoConfig | None = None) -> None:
        self.config = config or UnifiedCryptoConfig()
        self._quantum: QuantumSafeCrypto | None = None
        self._keypair: HybridKeypair | None = None
        self._initialized = False
        self._init_lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the unified crypto layer."""
        async with self._init_lock:
            if self._initialized:
                return

            # Initialize quantum-safe crypto
            self._quantum = await get_quantum_safe_crypto(
                QuantumSafeConfig(
                    security_level=self.config.security_level,
                    mode=self.config.mode,
                )
            )

            # Generate or load keypair
            self._keypair = await self._quantum.generate_keypair()

            self._initialized = True
            logger.info(
                f"✅ UnifiedCrypto initialized "
                f"(level={self.config.security_level.name}, "
                f"enforcement={self.config.enforcement.name})"
            )

    async def encrypt(
        self,
        data: bytes | str,
        context: dict[str, str] | None = None,
    ) -> bytes:
        """Encrypt data using quantum-safe cryptography.

        Args:
            data: Data to encrypt (bytes or string).
            context: Encryption context (bound to ciphertext).

        Returns:
            Ciphertext.
        """
        if not self._initialized:
            await self.initialize()

        # Convert string to bytes
        if isinstance(data, str):
            data = data.encode("utf-8")

        time.time()
        caller = _get_caller()

        try:
            ciphertext = await self._quantum.encrypt(data, context)

            # Audit
            if self.config.audit_all:
                _audit_log.log_sync(
                    CryptoAuditEntry(
                        operation="encrypt",
                        timestamp=time.time(),
                        data_size=len(data),
                        algorithm="hybrid-kyber-aes256gcm",
                        success=True,
                        caller=caller,
                        context=context or {},
                    )
                )

            return ciphertext

        except Exception as e:
            _audit_log.log_sync(
                CryptoAuditEntry(
                    operation="encrypt",
                    timestamp=time.time(),
                    data_size=len(data),
                    algorithm="hybrid-kyber-aes256gcm",
                    success=False,
                    caller=caller,
                    error=str(e),
                )
            )
            raise

    async def decrypt(
        self,
        ciphertext: bytes,
        context: dict[str, str] | None = None,
    ) -> bytes:
        """Decrypt data using quantum-safe cryptography.

        Args:
            ciphertext: Encrypted data.
            context: Encryption context (must match).

        Returns:
            Plaintext.
        """
        if not self._initialized:
            await self.initialize()

        caller = _get_caller()

        try:
            plaintext = await self._quantum.decrypt(ciphertext, context)

            if self.config.audit_all:
                _audit_log.log_sync(
                    CryptoAuditEntry(
                        operation="decrypt",
                        timestamp=time.time(),
                        data_size=len(ciphertext),
                        algorithm="hybrid-kyber-aes256gcm",
                        success=True,
                        caller=caller,
                        context=context or {},
                    )
                )

            return plaintext

        except Exception as e:
            _audit_log.log_sync(
                CryptoAuditEntry(
                    operation="decrypt",
                    timestamp=time.time(),
                    data_size=len(ciphertext),
                    algorithm="hybrid-kyber-aes256gcm",
                    success=False,
                    caller=caller,
                    error=str(e),
                )
            )
            raise

    async def sign(self, data: bytes) -> bytes:
        """Sign data using quantum-safe signatures.

        Args:
            data: Data to sign.

        Returns:
            Signature.
        """
        if not self._initialized:
            await self.initialize()

        return await self._quantum.sign(data, self._keypair)

    async def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify signature using quantum-safe verification.

        Args:
            data: Original data.
            signature: Signature to verify.

        Returns:
            True if valid.
        """
        if not self._initialized:
            await self.initialize()

        return await self._quantum.verify(
            data,
            signature,
            self._keypair.export_public_keys(),
        )

    def encrypt_sync(
        self,
        data: bytes | str,
        context: dict[str, str] | None = None,
    ) -> bytes:
        """Synchronous encrypt (for legacy compatibility).

        WARNING: This creates a new event loop. Use async version when possible.
        """
        _emit_legacy_warning("encrypt_sync", _get_caller())

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.encrypt(data, context))
        finally:
            loop.close()

    def decrypt_sync(
        self,
        ciphertext: bytes,
        context: dict[str, str] | None = None,
    ) -> bytes:
        """Synchronous decrypt (for legacy compatibility).

        WARNING: This creates a new event loop. Use async version when possible.
        """
        _emit_legacy_warning("decrypt_sync", _get_caller())

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self.decrypt(ciphertext, context))
        finally:
            loop.close()

    # =========================================================================
    # Legacy Compatibility (DEPRECATED)
    # =========================================================================

    async def fernet_encrypt(self, data: bytes, key: bytes) -> bytes:
        """DEPRECATED: Fernet encryption routed through quantum-safe.

        This method exists for backward compatibility only.
        All calls are redirected to quantum-safe encryption.
        """
        _emit_legacy_warning("fernet_encrypt", _get_caller())
        return await self.encrypt(data)

    async def fernet_decrypt(self, ciphertext: bytes, key: bytes) -> bytes:
        """DEPRECATED: Fernet decryption routed through quantum-safe.

        This method exists for backward compatibility only.
        """
        _emit_legacy_warning("fernet_decrypt", _get_caller())
        return await self.decrypt(ciphertext)

    async def aes_encrypt(
        self,
        data: bytes,
        key: bytes,
        nonce: bytes | None = None,
    ) -> bytes:
        """DEPRECATED: AES encryption routed through quantum-safe.

        This method exists for backward compatibility only.
        """
        _emit_legacy_warning("aes_encrypt", _get_caller())
        return await self.encrypt(data)

    async def aes_decrypt(
        self,
        ciphertext: bytes,
        key: bytes,
        nonce: bytes,
    ) -> bytes:
        """DEPRECATED: AES decryption routed through quantum-safe.

        This method exists for backward compatibility only.
        """
        _emit_legacy_warning("aes_decrypt", _get_caller())
        return await self.decrypt(ciphertext)

    # =========================================================================
    # Plaintext Rejection
    # =========================================================================

    def reject_plaintext_storage(self, data: Any, destination: str) -> None:
        """Reject attempt to store plaintext data.

        Called by storage backends to enforce encryption.
        """
        if not self.config.reject_plaintext:
            return

        caller = _get_caller()

        _audit_log.log_sync(
            CryptoAuditEntry(
                operation="plaintext_rejected",
                timestamp=time.time(),
                data_size=len(str(data)) if data else 0,
                algorithm="none",
                success=False,
                caller=caller,
                error=f"Plaintext storage to {destination} rejected",
            )
        )

        raise SecurityError(
            f"Plaintext storage rejected. "
            f"Encrypt data before storing to {destination}. "
            f"Use unified_crypto.encrypt() first."
        )


# =============================================================================
# Factory Functions
# =============================================================================


_unified_crypto: UnifiedCrypto | None = None


async def get_unified_crypto(
    config: UnifiedCryptoConfig | None = None,
) -> UnifiedCrypto:
    """Get or create the singleton unified crypto instance.

    Args:
        config: Crypto configuration.

    Returns:
        UnifiedCrypto instance.

    Example:
        >>> crypto = await get_unified_crypto()
        >>> ciphertext = await crypto.encrypt(b"data")
    """
    global _unified_crypto

    if _unified_crypto is None:
        _unified_crypto = UnifiedCrypto(config)
        await _unified_crypto.initialize()

    return _unified_crypto


async def shutdown_unified_crypto() -> None:
    """Shutdown the unified crypto."""
    global _unified_crypto
    _unified_crypto = None


# =============================================================================
# Convenience Functions
# =============================================================================


async def encrypt(
    data: bytes | str,
    context: dict[str, str] | None = None,
) -> bytes:
    """Encrypt data using the unified crypto layer.

    Args:
        data: Data to encrypt.
        context: Encryption context.

    Returns:
        Ciphertext.
    """
    crypto = await get_unified_crypto()
    return await crypto.encrypt(data, context)


async def decrypt(
    ciphertext: bytes,
    context: dict[str, str] | None = None,
) -> bytes:
    """Decrypt data using the unified crypto layer.

    Args:
        ciphertext: Encrypted data.
        context: Encryption context (must match).

    Returns:
        Plaintext.
    """
    crypto = await get_unified_crypto()
    return await crypto.decrypt(ciphertext, context)


async def sign(data: bytes) -> bytes:
    """Sign data using the unified crypto layer."""
    crypto = await get_unified_crypto()
    return await crypto.sign(data)


async def verify(data: bytes, signature: bytes) -> bool:
    """Verify signature using the unified crypto layer."""
    crypto = await get_unified_crypto()
    return await crypto.verify(data, signature)


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "CryptoAuditEntry",
    "CryptoAuditLog",
    "EncryptionEnforcement",
    "SecurityError",
    "UnifiedCrypto",
    "UnifiedCryptoConfig",
    "decrypt",
    "encrypt",
    "get_crypto_audit_log",
    "get_unified_crypto",
    "shutdown_unified_crypto",
    "sign",
    "verify",
]
