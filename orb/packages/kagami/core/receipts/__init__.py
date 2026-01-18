"""Unified receipts and idempotency module.

RECEIPTS AS EXECUTION COMMITS (Dec 27, 2025):
==============================================
Receipts are immutable audit logs - commits to the execution history.
They share deep structural similarity with git commits:

┌─────────────────────────────────────────────────────────────────┐
│                   DUAL COMMIT SEMANTICS                          │
├──────────────────────────┬──────────────────────────────────────┤
│   GIT COMMITS            │   RUNTIME RECEIPTS                    │
├──────────────────────────┼──────────────────────────────────────┤
│ correlation_id = hash    │ correlation_id = task UUID           │
│ author = git author      │ workspace_hash = colony identifier   │
│ timestamp = commit time  │ timestamp = execution time           │
│ message = commit msg     │ action = intent.action               │
│ diff = files changed     │ tool_calls = tools invoked           │
│ status = CI pass/fail    │ status = success/failure             │
│ parent = parent commit   │ parent_receipt_id = parent task      │
├──────────────────────────┴──────────────────────────────────────┤
│ BOTH ARE: Append-only, cryptographically signed, stigmergic     │
│           traces in the superorganism's collective memory.      │
└─────────────────────────────────────────────────────────────────┘

Git commits capture DEVELOPMENT stigmergy (how code evolved).
Runtime receipts capture EXECUTION stigmergy (how tasks executed).

Both enable indirect coordination:
- Git: Developers learn from past code changes
- Runtime: Agents learn from past task outcomes

See: CLAUDE.md for superorganism architecture.
See: .git/objects/ for development-level commits.
See: kagami/core/receipts/ for runtime execution commits.

Canonical implementation: All in kagami/core/receipts/
Consolidated Dec 7, 2025 - idempotency moved from kagami.core.idempotency to here.
"""

import logging

from kagami.core.receipts.emitters import (
    ContextEmitter,
    CoreEmitter,
    EmitterRegistry,
    IdentityEmitter,
    MetricsEmitter,
    SafetyEmitter,
    get_emitter_registry,
)
from kagami.core.receipts.facade import (
    UnifiedReceiptFacade,
    emit_receipt,
)
from kagami.core.receipts.store import (
    IdempotencyConfig,
    IdempotencyEntry,
    IdempotencyStore,
    get_idempotency_store,
)
from kagami.core.utils.ids import generate_correlation_id

logger = logging.getLogger(__name__)

# Provenance tracking state
_provenance_enabled: bool = False


async def enable_provenance_tracking() -> bool:
    """Enable cryptographic provenance tracking for receipts.

    Initializes the provenance chain for tamper-evident audit trails.
    Called during Full Operation Mode startup.

    Returns:
        True if provenance tracking was successfully enabled.
    """
    global _provenance_enabled
    try:
        from kagami.core.safety.provenance_chain import get_provenance_chain

        chain = get_provenance_chain()
        await chain.initialize()
        _provenance_enabled = True
        logger.info("Provenance tracking enabled")
        return True
    except Exception as e:
        logger.warning(f"Failed to enable provenance tracking: {e}")
        _provenance_enabled = False
        return False


async def disable_provenance_tracking() -> None:
    """Disable cryptographic provenance tracking.

    Called during shutdown to cleanly stop provenance recording.
    """
    global _provenance_enabled
    _provenance_enabled = False
    logger.info("Provenance tracking disabled")


def is_provenance_enabled() -> bool:
    """Check if provenance tracking is currently enabled."""
    return _provenance_enabled


async def ensure_ws_idempotency(
    session_key: str,
    idempotency_key: str,
    ttl_seconds: int = 300,
) -> str:
    """Best-effort idempotency guard for websocket mutations.

    Returns:
        "ok" if the key was accepted (first-seen within TTL), or "duplicate" if replayed.
    """
    store = get_idempotency_store()
    is_new, _entry = await store.check_and_acquire(
        path=session_key,
        idempotency_key=idempotency_key,
        ttl_seconds=ttl_seconds,
    )
    return "ok" if is_new else "duplicate"


__all__ = [
    "ContextEmitter",
    # Receipt emitters (TRAIL-010)
    "CoreEmitter",
    "EmitterRegistry",
    "IdempotencyConfig",
    "IdempotencyEntry",
    # Idempotency (consolidated from kagami.core.idempotency)
    "IdempotencyStore",
    "IdentityEmitter",
    "MetricsEmitter",
    "SafetyEmitter",
    # Receipt facade (URF pattern)
    "UnifiedReceiptFacade",
    "disable_provenance_tracking",
    # Convenience functions
    "emit_receipt",
    # Provenance tracking
    "enable_provenance_tracking",
    "ensure_ws_idempotency",
    "generate_correlation_id",
    "get_emitter_registry",
    "get_idempotency_store",
    "is_provenance_enabled",
]
