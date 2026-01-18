"""Kagami Security Package

Security-related modules for authentication, authorization, encryption, and secrets.

SECRETS MANAGEMENT (CANONICAL):
===============================
    from kagami.core.security import get_secret, set_secret

    # Get a secret (cross-platform, automatic backend selection)
    password = get_secret("unifi_password")
    api_key = get_secret("anthropic_api_key")

    # Set a secret
    set_secret("control4_bearer_token", new_token)

    # List all secrets (admin)
    from kagami.core.security import get_secrets_backend
    backend = get_secrets_backend()
    keys = backend.list()

Backend selection (automatic):
- macOS: Keychain
- Linux/Windows: LocalEncrypted (~/.kagami/secrets/)
- CI/CD: Environment variables
- Production: AWS/Vault/GCP/Azure (via KAGAMI_SECRET_BACKEND env var)

SECURITY PIPELINE:
==================
    from kagami.core.security import check_operation_security

    result = await check_operation_security(
        operation="intent.execute",
        action="delete",
        target="file.txt",
        user_input="delete this file",
    )

Defense layers against Morris II-style attacks:
1. INGRESS: content_boundary.py filters RAG/external content
2. PROCESSING: jailbreak_detector.py catches injection attempts
3. EGRESS: anti_replication.py blocks worm propagation
4. PERSISTENCE: memory_hygiene.py prevents worm storage

All security checks integrate with CBF (Control Barrier Function):
    h(x) ≥ 0   Always. Inviolable.

Created: December 23, 2025
Updated: December 31, 2025 - Unified secrets API
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# SECRETS MANAGEMENT (CANONICAL ENTRY POINT)
# =============================================================================


def get_secret(key: str, default: str | None = None) -> str | None:
    """Get a secret from the unified secrets backend.

    This is the ONLY way to access secrets in Kagami. Backend is selected
    automatically based on platform and environment.

    Args:
        key: Secret key (e.g., "unifi_password", "anthropic_api_key")
        default: Default value if secret not found

    Returns:
        Secret value or default if not found

    Example:
        from kagami.core.security import get_secret

        password = get_secret("unifi_password")
        api_key = get_secret("anthropic_api_key")
    """
    from kagami.core.security.backends.unified_backend import get_sync_backend

    backend = get_sync_backend()
    return backend.get(key, default)


def set_secret(key: str, value: str) -> bool:
    """Set a secret in the unified secrets backend.

    Args:
        key: Secret key
        value: Secret value

    Returns:
        True if stored successfully

    Example:
        from kagami.core.security import set_secret

        set_secret("control4_bearer_token", new_token)
    """
    from kagami.core.security.backends.unified_backend import get_sync_backend

    backend = get_sync_backend()
    return backend.set(key, value)


def delete_secret(key: str) -> bool:
    """Delete a secret from the unified secrets backend.

    Args:
        key: Secret key

    Returns:
        True if deleted successfully
    """
    from kagami.core.security.backends.unified_backend import get_sync_backend

    backend = get_sync_backend()
    return backend.delete(key)


def list_secrets() -> list[str]:
    """List all secrets in the unified secrets backend.

    Returns:
        List of secret keys
    """
    from kagami.core.security.backends.unified_backend import get_sync_backend

    backend = get_sync_backend()
    return backend.list()


def has_secret(key: str) -> bool:
    """Check if a secret exists.

    Args:
        key: Secret key

    Returns:
        True if secret exists
    """
    from kagami.core.security.backends.unified_backend import get_sync_backend

    backend = get_sync_backend()
    return backend.has(key)


def get_secrets_backend() -> Any:
    """Get the underlying secrets backend (for advanced use).

    Returns:
        SyncSecretsBackend instance

    Example:
        from kagami.core.security import get_secrets_backend

        backend = get_secrets_backend()
        print(f"Backend type: {backend.backend_type}")
        keys = backend.list()
    """
    from kagami.core.security.backends.unified_backend import get_sync_backend

    return get_sync_backend()


async def get_secret_async(key: str, default: str | None = None) -> str | None:
    """Get a secret asynchronously.

    Args:
        key: Secret key
        default: Default value if not found

    Returns:
        Secret value or default
    """
    from kagami.core.security.backends.unified_backend import get_unified_backend

    backend = get_unified_backend()
    result = await backend.get_secret(key)
    return result if result is not None else default


async def set_secret_async(key: str, value: str) -> bool:
    """Set a secret asynchronously.

    Args:
        key: Secret key
        value: Secret value

    Returns:
        True if successful
    """
    from kagami.core.security.backends.unified_backend import get_unified_backend

    backend = get_unified_backend()
    try:
        await backend.set_secret(key, value)
        return True
    except Exception as e:
        logger.error(f"Failed to set secret {key}: {e}")
        return False


# =============================================================================
# SECURITY FILTERS
# =============================================================================


def get_jailbreak_detector() -> Any:
    """Get singleton jailbreak detector instance."""
    from kagami.core.security.jailbreak_detector import get_jailbreak_detector as _get

    return _get()


def get_anti_replication_filter() -> Any:
    """Get singleton anti-replication filter instance."""
    from kagami.core.security.anti_replication import get_anti_replication_filter as _get

    return _get()


def get_content_boundary_enforcer() -> Any:
    """Get singleton content boundary enforcer instance."""
    from kagami.core.security.content_boundary import get_content_boundary_enforcer as _get

    return _get()


def get_memory_hygiene_filter() -> Any:
    """Get singleton memory hygiene filter instance."""
    from kagami.core.security.memory_hygiene import get_memory_hygiene_filter as _get

    return _get()


# =============================================================================
# UNIFIED SECURITY PIPELINE
# =============================================================================


async def check_operation_security(  # type: ignore[no-untyped-def]
    operation: str,
    action: str = "",
    target: str = "",
    params: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    user_input: str = "",
    content: str = "",
    context_chunks: list[Any] | None = None,
):
    """Run full security pipeline for an operation.

    This is the main entry point for all security checks.
    Use this instead of calling individual filters directly.

    Args:
        operation: Operation identifier (e.g., "intent.execute")
        action: Action being performed
        target: Target of action
        params: Operation parameters
        metadata: Operation metadata
        user_input: User input text
        content: Content being processed
        context_chunks: RAG chunks in context

    Returns:
        UnifiedSecurityResult with aggregated security assessment
    """
    from kagami.core.safety.unified_security_pipeline import (
        check_operation_security as _check,
    )

    return await _check(
        operation=operation,
        action=action,
        target=target,
        params=params,
        metadata=metadata,
        user_input=user_input,
        content=content,
        context_chunks=context_chunks,
    )


def filter_rag_content(chunks: list[Any], source: str = "rag:unknown") -> Any:
    """Filter RAG chunks for injection patterns."""
    from kagami.core.safety.unified_security_pipeline import filter_rag_content as _filter

    return _filter(chunks, source)


async def check_output_safety(  # type: ignore[no-untyped-def]
    output: str,
    input_context: str | None = None,
    retrieved_chunks: list[Any] | None = None,
    metadata: dict[str, Any] | None = None,
):
    """Check LLM output for replication/worm patterns."""
    from kagami.core.safety.unified_security_pipeline import check_output_safety as _check

    return await _check(output, input_context, retrieved_chunks, metadata)  # type: ignore[misc]


async def filter_memory_write(  # type: ignore[no-untyped-def]
    content: str,
    memory_type: str,
    source: str = "unknown",
    user_id: str | None = None,
    correlation_id: str | None = None,
):
    """Filter content before memory storage."""
    from kagami.core.safety.unified_security_pipeline import filter_memory_write as _filter

    return await _filter(content, memory_type, source, user_id, correlation_id)  # type: ignore[misc]


# =============================================================================
# UNIFIED CRYPTO LAYER (PRIMARY ENCRYPTION INTERFACE)
# =============================================================================
# ALL encryption in Kagami routes through this layer.
# Quantum-safe by default. Legacy operations emit deprecation warnings.

# =============================================================================
# ENCRYPTION UTILITIES (LEGACY - USE UNIFIED CRYPTO FOR NEW CODE)
# =============================================================================
from kagami.core.security.encryption import (
    SecretEncryption,
    generate_secret,
    validate_secret_strength,
)

# =============================================================================
# HSM / KMS KEY MANAGEMENT (PRODUCTION)
# =============================================================================
from kagami.core.security.hsm_manager import (
    AWSKMSBackend,
    HSMBackend,
    HSMBackendBase,
    HSMConfig,
    HSMManager,
    HSMResult,
    KeyInfo,
    KeyType,
    KeyUsage,
    SoftwareHSMBackend,
    get_hsm_manager,
    shutdown_hsm_manager,
)

# =============================================================================
# PROTECTED INFORMATION (PERSONAL OWNERSHIP)
# =============================================================================
# Privacy Rules:
# - Every person owns their own information
# - You may not share information about another person without consent
# - There are NO privileged users - nobody is "owner" of another's data
# - Access requires identity verification and explicit sharing
from kagami.core.security.protected_info import (
    KNOWN_IDENTITIES,
    AccessLevel,
    ProtectedInfo,
    ProtectedInfoStore,
    can_access,
    delete_my_info,
    filter_for_identity,
    get_my_info,
    get_protected_store,
    is_known_identity,
    list_my_info,
    store_my_info,
)

# =============================================================================
# QUANTUM-SAFE CRYPTOGRAPHY (DEFAULT FOR ALL NEW DATA)
# =============================================================================
from kagami.core.security.quantum_safe import (
    CryptoMode,
    DilithiumSignature,
    HybridCrypto,
    HybridKeypair,
    KyberKEM,
    QuantumSafeConfig,
    QuantumSafeCrypto,
    SecurityLevel,
    get_quantum_safe_crypto,
    shutdown_quantum_safe,
)

# =============================================================================
# THRESHOLD SIGNATURES (N-OF-M DISTRIBUTED SIGNING)
# =============================================================================
from kagami.core.security.threshold_signatures import (
    KeyShare,
    PartialSignature,
    ShamirSecretSharing,
    ThresholdPolicy,
    ThresholdPolicyManager,
    ThresholdSignature,
    ThresholdSigner,
    get_policy_manager,
    get_threshold_signer,
)
from kagami.core.security.unified_crypto import (
    CryptoAuditEntry,
    CryptoAuditLog,
    EncryptionEnforcement,
    SecurityError,
    UnifiedCrypto,
    UnifiedCryptoConfig,
    decrypt,
    encrypt,
    get_crypto_audit_log,
    get_unified_crypto,
    shutdown_unified_crypto,
    sign,
    verify,
)

# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "KNOWN_IDENTITIES",
    # HSM / KMS Key Management (Production)
    "AWSKMSBackend",
    # Protected Information (Personal Ownership - No Privileges)
    "AccessLevel",
    # UNIFIED CRYPTO (PRIMARY INTERFACE - USE THIS)
    "CryptoAuditEntry",
    "CryptoAuditLog",
    # Quantum-Safe Cryptography (DEFAULT FOR ALL NEW DATA)
    "CryptoMode",
    "DilithiumSignature",
    "EncryptionEnforcement",
    "HSMBackend",
    "HSMBackendBase",
    "HSMConfig",
    "HSMManager",
    "HSMResult",
    "HybridCrypto",
    "HybridKeypair",
    "KeyInfo",
    # Threshold Signatures (N-of-M)
    "KeyShare",
    "KeyType",
    "KeyUsage",
    "KyberKEM",
    "PartialSignature",
    "ProtectedInfo",
    "ProtectedInfoStore",
    "QuantumSafeConfig",
    "QuantumSafeCrypto",
    # Encryption (Legacy - emit deprecation warnings)
    "SecretEncryption",
    "SecurityError",
    "SecurityLevel",
    "ShamirSecretSharing",
    "SoftwareHSMBackend",
    "ThresholdPolicy",
    "ThresholdPolicyManager",
    "ThresholdSignature",
    "ThresholdSigner",
    "UnifiedCrypto",
    "UnifiedCryptoConfig",
    "can_access",
    # Security Pipeline
    "check_operation_security",
    "check_output_safety",
    "decrypt",
    "delete_my_info",
    "delete_secret",
    "encrypt",
    "filter_for_identity",
    "filter_memory_write",
    "filter_rag_content",
    "generate_secret",
    # Security Filters
    "get_anti_replication_filter",
    "get_content_boundary_enforcer",
    "get_crypto_audit_log",
    "get_hsm_manager",
    "get_jailbreak_detector",
    "get_memory_hygiene_filter",
    "get_my_info",
    "get_policy_manager",
    "get_protected_store",
    "get_quantum_safe_crypto",
    # Secrets Management (CANONICAL)
    "get_secret",
    "get_secret_async",
    "get_secrets_backend",
    "get_threshold_signer",
    "get_unified_crypto",
    "has_secret",
    "is_known_identity",
    "list_my_info",
    "list_secrets",
    "set_secret",
    "set_secret_async",
    "shutdown_hsm_manager",
    "shutdown_quantum_safe",
    "shutdown_unified_crypto",
    "sign",
    "store_my_info",
    "validate_secret_strength",
    "verify",
]
