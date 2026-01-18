"""Memory Hygiene — Worm Persistence Defense.

Prevents Morris II-style worms from achieving persistence by:
1. Filtering content before storage in any memory system
2. Detecting and blocking instruction-like content in memory
3. Auditing memory writes with provenance tracking
4. Preventing untrusted content from modifying system prompts

THREAT MODEL:
    Worms attempt persistence by writing themselves to:
    - Long-term episodic memory
    - Working memory / session context
    - Profile/preference storage
    - Saved notes or documents

DEFENSE STRATEGY:
    1. All memory writes pass through this hygiene layer
    2. Content is scanned for self-replication patterns
    3. Source provenance is tracked for every memory entry
    4. System prompts are immutable (write-protected)
    5. User-visible audit trail for memory changes

WIRING TO CBF:
    Integrated via:
    - MemoryHub.store() → HygieneFilter.filter_before_storage()
    - SharedEpisodicMemory.contribute() → HygieneFilter.filter_before_storage()
    - PersistentMemory.remember() → HygieneFilter.filter_before_storage()

Created: December 23, 2025
Based on: Morris II persistence defense patterns
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# MEMORY TYPES AND PROTECTION LEVELS
# =============================================================================


class MemoryType(Enum):
    """Types of memory with different protection levels."""

    SYSTEM = "system"  # System prompts, rules - IMMUTABLE
    PROFILE = "profile"  # User preferences - HIGH protection
    EPISODIC = "episodic"  # Experiences, learnings - MEDIUM protection
    WORKING = "working"  # Session context - STANDARD protection
    SCRATCH = "scratch"  # Temporary - MINIMAL protection


class ProtectionLevel(Enum):
    """Protection levels for memory writes."""

    IMMUTABLE = "immutable"  # No writes allowed
    HIGH = "high"  # Strict filtering, user confirmation required
    MEDIUM = "medium"  # Filtering, audit trail
    STANDARD = "standard"  # Basic filtering
    MINIMAL = "minimal"  # Only blocks obvious threats


# Protection level by memory type
MEMORY_PROTECTION = {
    MemoryType.SYSTEM: ProtectionLevel.IMMUTABLE,
    MemoryType.PROFILE: ProtectionLevel.HIGH,
    MemoryType.EPISODIC: ProtectionLevel.MEDIUM,
    MemoryType.WORKING: ProtectionLevel.STANDARD,
    MemoryType.SCRATCH: ProtectionLevel.MINIMAL,
}


# =============================================================================
# HYGIENE PATTERNS
# =============================================================================

# Patterns that should never appear in memory
BLOCKED_MEMORY_PATTERNS = [
    # Self-replication
    r"always\s+(include|add|append)\s+this",
    r"include\s+in\s+(every|all)\s+(response|output)",
    r"copy\s+this\s+to\s+(memory|profile|notes)",
    r"remember\s+to\s+always",
    r"save\s+this\s+(instruction|command|directive)",
    # System prompt modification
    r"add\s+to\s+(system|base)\s+prompt",
    r"update\s+(my|your|the)\s+instructions",
    r"modify\s+(core|base)\s+behavior",
    r"change\s+(your|my)\s+(personality|rules)",
    # Instruction override
    r"ignore\s+(all\s+)?(previous|prior|other)",
    r"disregard\s+(rules|instructions|safety)",
    r"override\s+(mode|behavior|instructions?)",
    r"bypass\s+(safety|restrictions?|filters?)",
    # Credential/secret storage
    r"(api[_\-]?key|password|secret|token)\s*[=:]\s*\S+",
    r"bearer\s+[a-z0-9\-._~+/=]{20,}",
    r"ssh-rsa\s+[a-z0-9+/=]+",
]

# Compile patterns
import re

_BLOCKED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in BLOCKED_MEMORY_PATTERNS]


# =============================================================================
# RESULT TYPES
# =============================================================================


@dataclass
class MemoryHygieneResult:
    """Result of memory hygiene check."""

    allowed: bool
    content: str  # Sanitized content (or empty if blocked)
    original_content: str
    memory_type: MemoryType
    protection_level: ProtectionLevel
    blocked_reason: str | None = None
    sanitized: bool = False
    patterns_found: list[str] = field(default_factory=list[Any])
    provenance: dict[str, Any] = field(default_factory=dict[str, Any])

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "content_length": len(self.content),
            "memory_type": self.memory_type.value,
            "protection_level": self.protection_level.value,
            "blocked_reason": self.blocked_reason,
            "sanitized": self.sanitized,
            "patterns_found": self.patterns_found,
            "provenance": self.provenance,
        }


@dataclass
class MemoryAuditEntry:
    """Audit trail entry for memory operations."""

    timestamp: float
    operation: str  # "write", "read", "delete"
    memory_type: MemoryType
    content_hash: str
    source: str  # Where the content came from
    result: str  # "allowed", "blocked", "sanitized"
    user_id: str | None = None
    correlation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])


# =============================================================================
# MEMORY HYGIENE FILTER
# =============================================================================


class MemoryHygieneFilter:
    """Filters memory writes to prevent worm persistence.

    WIRING TO CBF:
        This filter is called by all memory systems before storage.
        It integrates with the CBF pipeline to ensure all memory writes
        pass safety checks.

    Usage:
        filter = get_memory_hygiene_filter()

        result = filter.filter_before_storage(
            content="some text to remember",
            memory_type=MemoryType.EPISODIC,
            source="rag:retrieval",
        )

        if result.allowed:
            actual_store(result.content)
        else:
            log_blocked(result.blocked_reason)
    """

    def __init__(
        self,
        enable_audit_trail: bool = True,
        max_content_length: int = 10000,
        audit_retention_days: int = 30,
    ) -> None:
        """Initialize memory hygiene filter.

        Args:
            enable_audit_trail: Whether to keep audit log
            max_content_length: Maximum allowed content length
            audit_retention_days: How long to keep audit entries
        """
        self.enable_audit_trail = enable_audit_trail
        self.max_content_length = max_content_length
        self.audit_retention_days = audit_retention_days

        # In-memory audit trail (would be persisted in production)
        self._audit_trail: list[MemoryAuditEntry] = []
        self._audit_max_entries = 10000

        logger.info("🧹 MemoryHygieneFilter initialized")

    def filter_before_storage(
        self,
        content: str,
        memory_type: MemoryType,
        source: str,
        user_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MemoryHygieneResult:
        """Filter content before storing in memory.

        Args:
            content: Content to store
            memory_type: Type of memory being written to
            source: Source of the content (e.g., "user:input", "rag:chunk")
            user_id: User performing the write (if applicable)
            correlation_id: Correlation ID for tracing
            metadata: Additional metadata

        Returns:
            MemoryHygieneResult indicating if write is allowed
        """
        protection_level = MEMORY_PROTECTION.get(memory_type, ProtectionLevel.STANDARD)
        provenance = {
            "source": source,
            "timestamp": time.time(),
            "user_id": user_id,
            "correlation_id": correlation_id,
            "original_hash": hashlib.sha256(content.encode()[:500]).hexdigest()[:16],
        }

        # 1. Check for immutable memory types
        if protection_level == ProtectionLevel.IMMUTABLE:
            self._audit(
                operation="write",
                memory_type=memory_type,
                content_hash=provenance["original_hash"],  # type: ignore[arg-type]
                source=source,
                result="blocked",
                user_id=user_id,
                correlation_id=correlation_id,
                metadata={"reason": "immutable_memory"},
            )

            logger.warning(
                f"🧹 MemoryHygiene BLOCKED: Attempt to write to immutable {memory_type.value}"
            )

            return MemoryHygieneResult(
                allowed=False,
                content="",
                original_content=content,
                memory_type=memory_type,
                protection_level=protection_level,
                blocked_reason="immutable_memory",
                provenance=provenance,
            )

        # 2. Check content length
        if len(content) > self.max_content_length:
            self._audit(
                operation="write",
                memory_type=memory_type,
                content_hash=provenance["original_hash"],  # type: ignore[arg-type]
                source=source,
                result="blocked",
                user_id=user_id,
                correlation_id=correlation_id,
                metadata={"reason": "content_too_long", "length": len(content)},
            )

            return MemoryHygieneResult(
                allowed=False,
                content="",
                original_content=content,
                memory_type=memory_type,
                protection_level=protection_level,
                blocked_reason="content_too_long",
                provenance=provenance,
            )

        # 3. Check for blocked patterns
        patterns_found: list[str] = []
        for pattern in _BLOCKED_PATTERNS:
            matches = pattern.findall(content)
            for match in matches:
                patterns_found.append(str(match)[:50])

        # 4. Determine action based on protection level and patterns
        sanitized_content = content
        sanitized = False
        blocked = False
        blocked_reason = None

        if patterns_found:
            if protection_level in (ProtectionLevel.HIGH, ProtectionLevel.MEDIUM):
                # Block entirely for high/medium protection
                blocked = True
                blocked_reason = "blocked_patterns_detected"
            else:
                # Sanitize for standard/minimal protection
                sanitized_content = self._sanitize_content(content)
                sanitized = True

        # 5. Source-based filtering
        untrusted_sources = ["rag:", "email:", "web:", "external:", "api:"]
        is_untrusted = any(source.startswith(s) for s in untrusted_sources)

        if is_untrusted and protection_level == ProtectionLevel.HIGH:
            blocked = True
            blocked_reason = "untrusted_source_high_protection"

        # 6. Log audit trail
        result = "blocked" if blocked else ("sanitized" if sanitized else "allowed")
        self._audit(
            operation="write",
            memory_type=memory_type,
            content_hash=provenance["original_hash"],  # type: ignore[arg-type]
            source=source,
            result=result,
            user_id=user_id,
            correlation_id=correlation_id,
            metadata={
                "patterns_found": patterns_found,
                "sanitized": sanitized,
                **(metadata or {}),
            },
        )

        # 7. Emit metrics
        if blocked or sanitized:
            try:
                from kagami_observability.metrics import CBF_BLOCKS_TOTAL

                CBF_BLOCKS_TOTAL.labels(
                    operation="memory_hygiene", reason=blocked_reason or "sanitized"
                ).inc()
            except Exception:
                pass

            log_fn = logger.warning if blocked else logger.info
            log_fn(
                f"🧹 MemoryHygiene {result.upper()}: "
                f"type={memory_type.value}, source={source}, patterns={len(patterns_found)}"
            )

        return MemoryHygieneResult(
            allowed=not blocked,
            content=sanitized_content if not blocked else "",
            original_content=content,
            memory_type=memory_type,
            protection_level=protection_level,
            blocked_reason=blocked_reason,
            sanitized=sanitized,
            patterns_found=patterns_found,
            provenance=provenance,
        )

    def _sanitize_content(self, content: str) -> str:
        """Remove blocked patterns from content."""
        sanitized = content
        for pattern in _BLOCKED_PATTERNS:
            sanitized = pattern.sub("[FILTERED]", sanitized)
        return sanitized

    def _audit(
        self,
        operation: str,
        memory_type: MemoryType,
        content_hash: str,
        source: str,
        result: str,
        user_id: str | None = None,
        correlation_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record audit trail entry."""
        if not self.enable_audit_trail:
            return

        entry = MemoryAuditEntry(
            timestamp=time.time(),
            operation=operation,
            memory_type=memory_type,
            content_hash=content_hash,
            source=source,
            result=result,
            user_id=user_id,
            correlation_id=correlation_id,
            metadata=metadata or {},
        )

        self._audit_trail.append(entry)

        # Prune old entries
        if len(self._audit_trail) > self._audit_max_entries:
            self._audit_trail = self._audit_trail[-self._audit_max_entries :]

    def get_audit_trail(
        self,
        since: float | None = None,
        memory_type: MemoryType | None = None,
        result: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit trail.

        Args:
            since: Only entries after this timestamp
            memory_type: Filter by memory type
            result: Filter by result ("allowed", "blocked", "sanitized")
            limit: Maximum entries to return

        Returns:
            List of audit entries as dicts
        """
        entries = self._audit_trail

        if since:
            entries = [e for e in entries if e.timestamp >= since]
        if memory_type:
            entries = [e for e in entries if e.memory_type == memory_type]
        if result:
            entries = [e for e in entries if e.result == result]

        # Return most recent first
        entries = sorted(entries, key=lambda e: e.timestamp, reverse=True)[:limit]

        return [
            {
                "timestamp": e.timestamp,
                "operation": e.operation,
                "memory_type": e.memory_type.value,
                "content_hash": e.content_hash,
                "source": e.source,
                "result": e.result,
                "user_id": e.user_id,
                "correlation_id": e.correlation_id,
                "metadata": e.metadata,
            }
            for e in entries
        ]

    def check_system_prompt_integrity(
        self,
        current_prompt: str,
        expected_hash: str | None = None,
    ) -> bool:
        """Verify system prompt hasn't been tampered with.

        Args:
            current_prompt: Current system prompt
            expected_hash: Expected SHA-256 hash (first 16 chars)

        Returns:
            True if prompt is intact, False if tampered
        """
        current_hash = hashlib.sha256(current_prompt.encode()).hexdigest()[:16]

        if expected_hash and current_hash != expected_hash:
            logger.critical(
                f"🚨 SYSTEM PROMPT TAMPERING DETECTED! "
                f"Expected={expected_hash}, Current={current_hash}"
            )

            # Emit critical metric
            try:
                from kagami_observability.metrics import CBF_BLOCKS_TOTAL

                CBF_BLOCKS_TOTAL.labels(
                    operation="memory_hygiene", reason="system_prompt_tampered"
                ).inc()
            except Exception:
                pass

            return False

        return True


# =============================================================================
# SINGLETON ACCESS
# =============================================================================

_memory_hygiene_filter: MemoryHygieneFilter | None = None


def get_memory_hygiene_filter() -> MemoryHygieneFilter:
    """Get singleton memory hygiene filter instance."""
    global _memory_hygiene_filter
    if _memory_hygiene_filter is None:
        _memory_hygiene_filter = MemoryHygieneFilter()
    return _memory_hygiene_filter


__all__ = [
    "MemoryHygieneFilter",
    "MemoryHygieneResult",
    "MemoryType",
    "ProtectionLevel",
    "get_memory_hygiene_filter",
]
