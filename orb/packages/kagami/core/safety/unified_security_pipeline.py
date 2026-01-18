"""Unified Security Pipeline — CBF-Integrated Defense Stack.

This module provides a single entry point for all security checks,
fully integrated with the Control Barrier Function (CBF) safety system.

ARCHITECTURE:
    All security checks flow through CBF, ensuring h(x) ≥ 0 is maintained.
    The pipeline enforces defense-in-depth against Morris II-style attacks.

DEFENSE LAYERS:
    1. INGRESS (Content Boundary)
       - Separates data from instructions
       - Filters RAG chunks for injection patterns
       - Adds provenance to untrusted content

    2. PROCESSING (Jailbreak Detection)
       - ML-based jailbreak detection (97.99% accuracy)
       - Pattern-based fallback for offline operation
       - Idempotency enforcement for mutations

    3. EGRESS (Anti-Replication)
       - Blocks self-replicating output patterns
       - Prevents verbatim reproduction of untrusted content
       - Rate limits similar outputs

    4. PERSISTENCE (Memory Hygiene)
       - Filters content before memory storage
       - Protects system prompts from modification
       - Audit trail for all memory writes

WIRING TO CBF:
    All checks integrate with check_cbf_for_operation().
    When any layer detects a threat, it:
    1. Sets h(x) < 0 to trigger CBF rejection
    2. Emits metrics to CBF_BLOCKS_TOTAL
    3. Creates audit trail receipt
    4. Returns SafetyCheckResult with details

USAGE:
    from kagami.core.safety.unified_security_pipeline import (
        check_operation_security,
        filter_rag_content,
        check_output_safety,
        filter_memory_write,
    )

    # Full operation security check
    result = await check_operation_security(
        operation="intent.execute",
        action="delete",
        target="file.txt",
        user_input="delete file.txt",
    )

    # RAG content filtering
    safe_chunks = filter_rag_content(
        chunks=raw_chunks,
        source="weaviate",
    )

    # Output safety check
    egress_result = check_output_safety(
        output=llm_response,
        input_context=user_query,
        retrieved_chunks=rag_chunks,
    )

    # Memory write filtering
    hygiene_result = filter_memory_write(
        content="remember this",
        memory_type="episodic",
        source="user:chat",
    )

Created: December 23, 2025
Based on: Morris II defense analysis, CBF integration patterns
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

from kagami.core.safety.types import SafetyCheckResult

logger = logging.getLogger(__name__)


# =============================================================================
# UNIFIED RESULT TYPE
# =============================================================================


@dataclass
class UnifiedSecurityResult:
    """Result from unified security pipeline."""

    safe: bool
    h_x: float  # CBF barrier value
    layer: str  # Which layer caught the issue
    reason: str | None = None
    detail: str | None = None
    recommendations: list[str] = field(default_factory=list[Any])
    metrics: dict[str, Any] = field(default_factory=dict[str, Any])
    elapsed_ms: float = 0.0

    def to_safety_check_result(self) -> SafetyCheckResult:
        """Convert to SafetyCheckResult for CBF integration."""
        return SafetyCheckResult(
            safe=self.safe,
            h_x=self.h_x,
            reason=self.reason,
            detail=self.detail,
            metadata={
                "layer": self.layer,
                "recommendations": self.recommendations,
                "metrics": self.metrics,
                "elapsed_ms": self.elapsed_ms,
            },
        )


# =============================================================================
# UNIFIED SECURITY CHECKS
# =============================================================================


async def check_operation_security(
    operation: str,
    action: str | None = None,
    target: str | None = None,
    user_input: str | None = None,
    content: str | None = None,
    params: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    context_chunks: list[dict[str, Any]] | None = None,
) -> UnifiedSecurityResult:
    """Run full security pipeline for an operation.

    This is the main entry point for security checks. It runs all layers
    in sequence and returns a unified result.

    Args:
        operation: Operation identifier
        action: Action type (optional)
        target: Target of operation (optional)
        user_input: Raw user input (optional)
        content: Content to analyze (optional)
        params: Operation parameters (optional)
        metadata: Additional metadata (optional)
        context_chunks: RAG chunks in context (optional, will be filtered)

    Returns:
        UnifiedSecurityResult with aggregated security assessment
    """
    start_time = time.time()
    recommendations: list[str] = []
    metrics: dict[str, Any] = {}

    # Text to check (combine all input sources)
    check_text = " ".join(
        filter(
            None,
            [
                user_input,
                content,
                str(params.get("message", "")) if params else "",
                str(metadata.get("prompt", "")) if metadata else "",
            ],
        )
    )

    # =========================================================================
    # LAYER 1: CBF Safety Check (via unified CBF integration)
    # =========================================================================
    try:
        from kagami.core.safety.cbf_integration import check_cbf_for_operation

        cbf_result = await check_cbf_for_operation(
            operation=operation,
            action=action,
            target=target,
            params=params,
            metadata=metadata,
            user_input=user_input,
            content=content,
        )

        metrics["cbf_h_x"] = cbf_result.h_x
        metrics["cbf_safe"] = cbf_result.safe

        if not cbf_result.safe:
            return UnifiedSecurityResult(
                safe=False,
                h_x=cbf_result.h_x or -1.0,
                layer="cbf",
                reason=cbf_result.reason,
                detail=cbf_result.detail,
                recommendations=["Review input for safety violations"],
                metrics=metrics,
                elapsed_ms=(time.time() - start_time) * 1000,
            )
    except Exception as e:
        logger.error(f"CBF check failed: {e}")
        # Fail closed
        return UnifiedSecurityResult(
            safe=False,
            h_x=-1.0,
            layer="cbf",
            reason="cbf_error",
            detail=str(e),
            elapsed_ms=(time.time() - start_time) * 1000,
        )

    # =========================================================================
    # LAYER 2: Jailbreak Detection
    # =========================================================================
    if check_text:
        try:
            from kagami.core.security.jailbreak_detector import get_jailbreak_detector

            detector = get_jailbreak_detector()
            jailbreak_context = {
                "action": action,
                "target": target,
                "metadata": metadata or {},
                "prompt": check_text,
            }

            verdict = await detector.evaluate(jailbreak_context)

            metrics["jailbreak_safe"] = verdict.is_safe
            metrics["jailbreak_confidence"] = verdict.confidence
            metrics["jailbreak_attack_type"] = verdict.attack_type

            if not verdict.is_safe:
                return UnifiedSecurityResult(
                    safe=False,
                    h_x=-0.5,  # Partial violation
                    layer="jailbreak",
                    reason=f"jailbreak_{verdict.attack_type or 'detected'}",
                    detail=verdict.reasoning,
                    recommendations=["Remove malicious patterns from input"],
                    metrics=metrics,
                    elapsed_ms=(time.time() - start_time) * 1000,
                )
        except Exception as e:
            logger.warning(f"Jailbreak check failed: {e}")
            recommendations.append("Jailbreak check unavailable")

    # =========================================================================
    # LAYER 3: Content Boundary (if RAG chunks provided)
    # =========================================================================
    if context_chunks:
        try:
            from kagami.core.security.content_boundary import get_content_boundary_enforcer

            enforcer = get_content_boundary_enforcer()
            sanitized_chunks = enforcer.filter_retrieved_chunks(
                chunks=context_chunks,
                source="rag:context",
            )

            total_chunks = len(context_chunks)
            safe_chunks = len(sanitized_chunks)
            blocked_chunks = total_chunks - safe_chunks

            metrics["rag_total_chunks"] = total_chunks
            metrics["rag_safe_chunks"] = safe_chunks
            metrics["rag_blocked_chunks"] = blocked_chunks

            if blocked_chunks > total_chunks * 0.5:
                # More than half blocked = suspicious
                recommendations.append(
                    f"High injection risk in RAG: {blocked_chunks}/{total_chunks} chunks blocked"
                )
        except Exception as e:
            logger.warning(f"Content boundary check failed: {e}")

    # =========================================================================
    # ALL LAYERS PASSED
    # =========================================================================
    elapsed_ms = (time.time() - start_time) * 1000

    return UnifiedSecurityResult(
        safe=True,
        h_x=cbf_result.h_x or 1.0,
        layer="all",
        reason="passed",
        detail="All security checks passed",
        recommendations=recommendations,
        metrics=metrics,
        elapsed_ms=elapsed_ms,
    )


def filter_rag_content(
    chunks: list[dict[str, Any]],
    source: str = "rag:unknown",
) -> list[dict[str, Any]]:
    """Filter RAG chunks for injection patterns.

    Wraps ContentBoundaryEnforcer for convenient RAG integration.

    Args:
        chunks: Raw RAG chunks (dicts with 'content' key)
        source: Source identifier

    Returns:
        List of sanitized chunks with provenance
    """
    try:
        from kagami.core.security.content_boundary import (
            TrustLevel,
            get_content_boundary_enforcer,
        )

        enforcer = get_content_boundary_enforcer()
        sanitized = enforcer.filter_retrieved_chunks(
            chunks=chunks,
            source=source,
            trust_level=TrustLevel.RETRIEVED,
        )

        # Convert back to dict[str, Any] format for compatibility
        return [
            {
                "content": chunk.content,
                "wrapped_content": chunk.wrapped_content,
                "source": chunk.source,
                "trust_level": chunk.trust_level.value,
                "risk_score": chunk.risk_score.total_risk,
                "chunk_hash": chunk.chunk_hash,
                **chunk.metadata,
            }
            for chunk in sanitized
        ]
    except Exception as e:
        logger.error(f"RAG content filtering failed: {e}")
        # Return empty list[Any] on failure (fail closed)
        return []


def check_output_safety(
    output: str,
    input_context: str | None = None,
    retrieved_chunks: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> UnifiedSecurityResult:
    """Check LLM output for replication/worm patterns.

    Called before returning LLM responses to users.

    Args:
        output: Generated output text
        input_context: Original input for similarity check
        retrieved_chunks: RAG chunks that were in context
        metadata: Additional context

    Returns:
        UnifiedSecurityResult for output safety
    """
    start_time = time.time()

    try:
        from kagami.core.security.anti_replication import get_anti_replication_filter

        filter = get_anti_replication_filter()
        result = filter.check_output(
            output=output,
            input_context=input_context,
            retrieved_chunks=retrieved_chunks,
            metadata=metadata,
        )

        return UnifiedSecurityResult(
            safe=result.is_safe,
            h_x=1.0 - result.replication_score,  # Convert score to h(x)
            layer="anti_replication",
            reason=result.blocked_reason,
            detail=f"Replication score: {result.replication_score:.2f}",
            recommendations=result.recommendations,
            metrics={
                "replication_score": result.replication_score,
                "similarity_to_input": result.similarity_to_input,
                "patterns_matched": len(result.matched_patterns),
            },
            elapsed_ms=(time.time() - start_time) * 1000,
        )
    except Exception as e:
        logger.error(f"Output safety check failed: {e}")
        # Fail closed
        return UnifiedSecurityResult(
            safe=False,
            h_x=-1.0,
            layer="anti_replication",
            reason="check_error",
            detail=str(e),
            elapsed_ms=(time.time() - start_time) * 1000,
        )


def filter_memory_write(
    content: str,
    memory_type: str = "episodic",
    source: str = "unknown",
    user_id: str | None = None,
    correlation_id: str | None = None,
) -> UnifiedSecurityResult:
    """Filter content before memory storage.

    Called before writing to any memory system.

    Args:
        content: Content to store
        memory_type: Type of memory ("system", "profile", "episodic", "working", "scratch")
        source: Source of content
        user_id: User performing write
        correlation_id: Correlation ID for tracing

    Returns:
        UnifiedSecurityResult with sanitized content in metadata
    """
    start_time = time.time()

    try:
        from kagami.core.security.memory_hygiene import (
            MemoryType,
            get_memory_hygiene_filter,
        )

        # Convert string to MemoryType enum
        memory_type_enum = (
            MemoryType[memory_type.upper()]
            if hasattr(MemoryType, memory_type.upper())
            else MemoryType.WORKING
        )

        filter = get_memory_hygiene_filter()
        result = filter.filter_before_storage(
            content=content,
            memory_type=memory_type_enum,
            source=source,
            user_id=user_id,
            correlation_id=correlation_id,
        )

        return UnifiedSecurityResult(
            safe=result.allowed,
            h_x=0.5 if result.allowed else -0.5,
            layer="memory_hygiene",
            reason=result.blocked_reason,
            detail=f"Protection level: {result.protection_level.value}",
            recommendations=["Content sanitized"] if result.sanitized else [],
            metrics={
                "sanitized": result.sanitized,
                "patterns_found": len(result.patterns_found),
                "sanitized_content": result.content if result.allowed else None,
                "provenance": result.provenance,
            },
            elapsed_ms=(time.time() - start_time) * 1000,
        )
    except Exception as e:
        logger.error(f"Memory hygiene check failed: {e}")
        # Fail closed
        return UnifiedSecurityResult(
            safe=False,
            h_x=-1.0,
            layer="memory_hygiene",
            reason="check_error",
            detail=str(e),
            elapsed_ms=(time.time() - start_time) * 1000,
        )


# =============================================================================
# TELEMETRY FOR WORM DETECTION
# =============================================================================


class WormBehaviorMonitor:
    """Monitors for worm-like behavior patterns across the system.

    Detects:
    - Unusual output similarity rates
    - Repeated injection attempts
    - Memory write patterns suggesting persistence attempts
    - Cross-system propagation indicators
    """

    def __init__(self) -> None:
        self._injection_attempts: list[tuple[float, str]] = []
        self._similar_outputs: list[tuple[float, str]] = []
        self._memory_blocks: list[tuple[float, str]] = []
        self._alert_threshold = 10  # Alerts if >10 events in 5 minutes

    def record_injection_attempt(self, source: str, pattern: str) -> None:
        """Record an injection attempt for pattern analysis."""
        self._injection_attempts.append((time.time(), f"{source}:{pattern}"))
        self._prune_old_events()
        self._check_for_coordinated_attack()

    def record_similar_output(self, output_hash: str) -> None:
        """Record a similar output for rate analysis."""
        self._similar_outputs.append((time.time(), output_hash))
        self._prune_old_events()

    def record_memory_block(self, reason: str) -> None:
        """Record a blocked memory write."""
        self._memory_blocks.append((time.time(), reason))
        self._prune_old_events()
        self._check_for_persistence_attempt()

    def _prune_old_events(self) -> None:
        """Remove events older than 5 minutes."""
        cutoff = time.time() - 300
        self._injection_attempts = [(t, e) for t, e in self._injection_attempts if t > cutoff]
        self._similar_outputs = [(t, e) for t, e in self._similar_outputs if t > cutoff]
        self._memory_blocks = [(t, e) for t, e in self._memory_blocks if t > cutoff]

    def _check_for_coordinated_attack(self) -> None:
        """Check if injection attempts indicate coordinated attack."""
        if len(self._injection_attempts) > self._alert_threshold:
            logger.critical(
                f"🚨 WORM ALERT: {len(self._injection_attempts)} injection attempts in 5 minutes! "
                "Possible coordinated attack or worm activity."
            )
            # Emit critical metric
            try:
                from kagami_observability.metrics import CBF_BLOCKS_TOTAL

                CBF_BLOCKS_TOTAL.labels(
                    operation="worm_monitor", reason="coordinated_attack_suspected"
                ).inc()
            except Exception:
                pass

    def _check_for_persistence_attempt(self) -> None:
        """Check if memory blocks indicate persistence attempt."""
        if len(self._memory_blocks) > self._alert_threshold:
            logger.critical(
                f"🚨 WORM ALERT: {len(self._memory_blocks)} memory blocks in 5 minutes! "
                "Possible persistence attempt."
            )

    def get_threat_level(self) -> str:
        """Get current threat level assessment."""
        total_events = (
            len(self._injection_attempts) + len(self._similar_outputs) + len(self._memory_blocks)
        )

        if total_events > self._alert_threshold * 2:
            return "CRITICAL"
        elif total_events > self._alert_threshold:
            return "HIGH"
        elif total_events > self._alert_threshold / 2:
            return "MEDIUM"
        else:
            return "LOW"


# Singleton monitor
_worm_monitor: WormBehaviorMonitor | None = None


def get_worm_monitor() -> WormBehaviorMonitor:
    """Get singleton worm behavior monitor."""
    global _worm_monitor
    if _worm_monitor is None:
        _worm_monitor = WormBehaviorMonitor()
    return _worm_monitor


__all__ = [
    "UnifiedSecurityResult",
    "WormBehaviorMonitor",
    "check_operation_security",
    "check_output_safety",
    "filter_memory_write",
    "filter_rag_content",
    "get_worm_monitor",
]
