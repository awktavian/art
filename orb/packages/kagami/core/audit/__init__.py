"""Merkle tree audit logging module.

Provides tamper-proof append-only audit logging with cryptographic verification.

Created: January 2026
"""

from kagami.core.audit.merkle_log import (
    AuditBackend,
    AuditBackendBase,
    AuditEntry,
    AuditLogConfig,
    AuditLogIntegrityError,
    FilesystemAuditBackend,
    InclusionProof,
    MemoryAuditBackend,
    MerkleAuditLog,
    MerkleNode,
    MerkleTree,
    get_audit_log,
    shutdown_audit_log,
)

__all__ = [
    "AuditBackend",
    "AuditBackendBase",
    "AuditEntry",
    "AuditLogConfig",
    "AuditLogIntegrityError",
    "FilesystemAuditBackend",
    "InclusionProof",
    "MemoryAuditBackend",
    "MerkleAuditLog",
    "MerkleNode",
    "MerkleTree",
    "get_audit_log",
    "shutdown_audit_log",
]
