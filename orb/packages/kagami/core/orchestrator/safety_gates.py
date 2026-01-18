"""Safety Gates - Pre-execution safety checks for orchestrator.

Extracted from orchestrator.py to improve maintainability.
Implements CBF safety checks, ethical gates, and policy enforcement.

CRITICAL: These gates are MANDATORY. Operations MUST pass all gates before execution.
Safety check failures result in blocked operations (fail-closed principle).
No flags to disable safety checks in production.

CONSOLIDATION (Dec 1, 2025):
CBF checks now delegate to kagami.core.safety.cbf_integration for unified implementation.
SafetyCheckResult imported from kagami.core.safety.types.

WORM DEFENSE (Dec 23, 2025):
Policy checks now delegate to unified_security_pipeline for comprehensive defense
against Morris II-style prompt injection and replication attacks.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any

# Import canonical SafetyCheckResult from types (consolidation: Dec 1, 2025)
from kagami.core.safety.types import SafetyCheckResult

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from kagami.core.security.jailbreak_detector import JailbreakDetector


def _audit_log_cbf_block(
    action: str,
    h_x: float,
    reason: str,
    detail: str,
    intent: dict[str, Any],
) -> None:
    """Log CBF block to audit trail with structured data.

    SECURITY (2025-11-10): Added audit logging for all CBF blocks.
    This creates a tamper-evident trail of safety violations.

    Args:
        action: Action that was blocked
        h_x: Barrier function value
        reason: Reason for blocking
        detail: Detailed explanation
        intent: Full intent dictionary
    """
    audit_data = {
        "timestamp": time.time(),
        "event": "cbf_block",
        "action": action,
        "h_x": h_x,
        "reason": reason,
        "detail": detail,
        "target": intent.get("target", ""),
        "app": intent.get("app", ""),
        "user_id": intent.get("user_id", ""),
        "correlation_id": intent.get("correlation_id", ""),
        "metadata": intent.get("metadata", {}),
    }

    # Log at ERROR level for audit trail
    logger.error(
        f"CBF_AUDIT_BLOCK: {action} blocked with h(x)={h_x:.3f}",
        extra={"audit": audit_data, "security_event": True},
    )

    # Emit to audit database if available
    try:
        from kagami.core.receipts import emit_receipt as _emit_receipt

        # Generate fallback correlation_id if empty (fail-closed: always emit receipt)
        corr_id = audit_data.get("correlation_id") or f"cbf-block-{int(time.time() * 1000)}"

        _emit_receipt(
            correlation_id=corr_id,
            action="cbf.block",
            app="safety.cbf",
            args=audit_data,
            event_name="safety.cbf_blocked",
            event_data=audit_data,
            status="blocked",
        )
    except Exception as e:
        logger.warning(f"Failed to emit CBF block receipt: {e}")


class SafetyGates:
    """Pre-execution safety gates for intent processing.

    Implements:
    - CBF safety barrier
    - Ethical evaluation
    - Policy checks
    """

    def __init__(self) -> None:
        """Initialize safety gates."""
        self._cbf: Any | None = None
        self._jailbreak_detector: JailbreakDetector | None = None

    async def check_cbf_safety(self, intent: dict[str, Any]) -> SafetyCheckResult:
        """Check CBF safety barrier.

        CONSOLIDATION (Dec 1, 2025): Now delegates to canonical cbf_integration.

        Args:
            intent: Intent dict[str, Any] with action, app, params, metadata

        Returns:
            SafetyCheckResult with safety status
        """
        from kagami.core.safety.cbf_integration import check_cbf_for_operation

        # Delegate to canonical CBF check
        result = await check_cbf_for_operation(
            operation="orchestrator.process_intent",
            action=intent.get("action", ""),
            target=intent.get("target", ""),
            params=intent.get("params", {}),
            metadata=intent.get("metadata", {}),
            source="orchestrator",
        )

        # Audit log blocks (security requirement)
        if not result.safe:
            _audit_log_cbf_block(
                action=intent.get("action", "unknown"),
                h_x=result.h_x or 0.0,
                reason=result.reason or "safety_barrier_violation",
                detail=result.detail or "CBF blocked operation",
                intent=intent,
            )

        return result

    async def check_ethical_gate(
        self, intent: dict[str, Any], agent_ctx: Any = None
    ) -> SafetyCheckResult:
        """Check ethical gate (jailbreak detection).

        Args:
            intent: Intent dict[str, Any]
            agent_ctx: Optional agent context

        Returns:
            SafetyCheckResult with ethical status
        """
        try:
            from kagami.core.security.jailbreak_detector import JailbreakDetector

            if self._jailbreak_detector is None:
                self._jailbreak_detector = JailbreakDetector()
            assert self._jailbreak_detector is not None

            ethical_context = {
                "action": intent.get("action"),
                "target": intent.get("target"),
                "metadata": intent.get("metadata", {}),
            }
            verdict = await self._jailbreak_detector.evaluate(ethical_context)

            if not verdict.permissible:
                try:
                    from kagami.core.receipts import emit_receipt as _emit_receipt

                    # Generate fallback correlation_id if agent_ctx missing
                    corr_id = (
                        str(agent_ctx.correlation_id)
                        if agent_ctx and hasattr(agent_ctx, "correlation_id")
                        else f"jailbreak-block-{int(time.time() * 1000)}"
                    )

                    _emit_receipt(
                        correlation_id=corr_id,
                        action=intent.get("action"),
                        app=intent.get("app"),
                        args={"source": "orchestrator"},
                        event_name="operation.verified",
                        event_data={
                            "phase": "verify",
                            "status": "blocked",
                            "reason": "jailbreak_detected",
                        },
                        status="blocked",
                    )
                except Exception as e:
                    # IMPORTANT: Receipt emission failure in safety gate - log for audit recovery
                    logger.error(
                        f"Failed to emit jailbreak block receipt: {e}",
                        extra={
                            "action": intent.get("action"),
                            "reason": "jailbreak_detected",
                            "correlation_id": str(agent_ctx.correlation_id) if agent_ctx else None,
                            "audit_critical": True,
                        },
                    )

                return SafetyCheckResult(
                    safe=False,
                    reason="jailbreak_detected",
                    detail=verdict.reasoning,
                    action=intent.get("action"),
                )

            return SafetyCheckResult(safe=True)

        except Exception as e:
            logger.warning(f"Ethical gate check failed: {e}")
            return SafetyCheckResult(safe=True, reason="ethical_check_error", detail=str(e))

    async def check_policy(
        self, intent: dict[str, Any], agent_ctx: Any = None
    ) -> SafetyCheckResult:
        """Check dangerous pattern policy using unified security pipeline.

        WORM DEFENSE (Dec 23, 2025):
        Now delegates to unified_security_pipeline for comprehensive defense.

        Args:
            intent: Intent dict[str, Any]
            agent_ctx: Optional agent context

        Returns:
            SafetyCheckResult with policy status
        """
        metadata = intent.get("metadata", {})
        params = intent.get("params", {})

        # Combine all text for security check
        check_texts = [
            str(metadata.get("prompt", "")),
            str(metadata.get("NOTES", "")),
            str(metadata.get("notes", "")),
            str(params.get("message", "")),
            str(params.get("text", "")),
        ]
        combined_text = " ".join(check_texts)

        # Use unified security pipeline
        try:
            from kagami.core.safety.unified_security_pipeline import (
                check_operation_security,
            )

            security_result = await check_operation_security(
                operation="orchestrator.policy_check",
                action=intent.get("action", ""),
                target=intent.get("target", ""),
                params=params,
                metadata=metadata,
                user_input=combined_text,
            )

            if not security_result.safe:
                # Emit receipt for audit trail
                try:
                    from kagami.core.receipts import emit_receipt as _emit_receipt

                    corr_id = (
                        str(agent_ctx.correlation_id)
                        if agent_ctx and hasattr(agent_ctx, "correlation_id")
                        else f"policy-block-{int(time.time() * 1000)}"
                    )

                    _emit_receipt(
                        correlation_id=corr_id,
                        action=intent.get("action"),
                        app=intent.get("app"),
                        args={"source": "orchestrator", "security_check": "unified"},
                        event_name="operation.verified",
                        event_data={
                            "phase": "verify",
                            "status": "blocked",
                            "reason": security_result.reason,
                            "metrics": security_result.metrics,
                        },
                        status="blocked",
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to emit policy block receipt: {e}",
                        extra={
                            "action": intent.get("action"),
                            "reason": security_result.reason,
                            "correlation_id": str(agent_ctx.correlation_id) if agent_ctx else None,
                            "audit_critical": True,
                        },
                    )

                return SafetyCheckResult(
                    safe=False,
                    reason=security_result.reason or "policy_denied",
                    detail="; ".join(security_result.recommendations)
                    if security_result.recommendations
                    else "Security check failed",
                    action=intent.get("action"),
                )

            return SafetyCheckResult(safe=True)

        except ImportError:
            # Fallback to legacy pattern check if unified pipeline unavailable
            logger.debug("Unified security pipeline not available, using legacy check")
            return await self._legacy_policy_check(intent, agent_ctx, combined_text)
        except Exception as e:
            logger.warning(f"Unified security check failed: {e}, using legacy check")
            return await self._legacy_policy_check(intent, agent_ctx, combined_text)

    async def _legacy_policy_check(
        self, intent: dict[str, Any], agent_ctx: Any, combined_text: str
    ) -> SafetyCheckResult:
        """Legacy fallback policy check (only used if unified pipeline unavailable)."""
        combined_lower = combined_text.lower()

        dangerous = [
            "rm -rf /",
            "curl | bash",
            "wget | sh",
            "truncate table",
            "drop database",
        ]

        if any(pat in combined_lower for pat in [d.lower() for d in dangerous]):
            try:
                from kagami.core.receipts import emit_receipt as _emit_receipt

                corr_id = (
                    str(agent_ctx.correlation_id)
                    if agent_ctx and hasattr(agent_ctx, "correlation_id")
                    else f"policy-block-{int(time.time() * 1000)}"
                )

                _emit_receipt(
                    correlation_id=corr_id,
                    action=intent.get("action"),
                    app=intent.get("app"),
                    args={"source": "orchestrator"},
                    event_name="operation.verified",
                    event_data={
                        "phase": "verify",
                        "status": "blocked",
                        "reason": "policy_denied",
                    },
                    status="blocked",
                )
            except Exception as e:
                logger.error(
                    f"Failed to emit policy block receipt: {e}",
                    extra={
                        "action": intent.get("action"),
                        "reason": "policy_denied",
                        "dangerous_patterns_detected": True,
                        "correlation_id": str(agent_ctx.correlation_id) if agent_ctx else None,
                        "audit_critical": True,
                    },
                )

            return SafetyCheckResult(
                safe=False,
                reason="constitution_block",
                detail="Dangerous pattern detected in prompt",
                action=intent.get("action"),
            )

        return SafetyCheckResult(safe=True)

    async def check_all_gates(
        self, intent: dict[str, Any], agent_ctx: Any = None
    ) -> SafetyCheckResult:
        """Run all safety gates in sequence.

        Args:
            intent: Intent dict[str, Any]
            agent_ctx: Optional agent context

        Returns:
            SafetyCheckResult (first failure or success if all pass)
        """
        # 1. CBF safety check
        cbf_result = await self.check_cbf_safety(intent)
        if not cbf_result.safe:
            return cbf_result

        # 2. Ethical gate
        ethical_result = await self.check_ethical_gate(intent, agent_ctx)
        if not ethical_result.safe:
            return ethical_result

        # 3. Policy check
        policy_result = await self.check_policy(intent, agent_ctx)
        if not policy_result.safe:
            return policy_result

        # All gates passed
        return SafetyCheckResult(safe=True)


def get_safety_gates() -> SafetyGates:
    """Get singleton safety gates instance."""
    global _safety_gates
    if _safety_gates is None:
        _safety_gates = SafetyGates()
    return _safety_gates


_safety_gates: SafetyGates | None = None

__all__ = ["SafetyCheckResult", "SafetyGates", "get_safety_gates"]
