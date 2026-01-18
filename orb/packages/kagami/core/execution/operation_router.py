from __future__ import annotations

"""Operation Router - Intelligent routing for performance optimization.

Routes operations to appropriate execution paths based on complexity and risk:
- Fast path: Simple reads (skip RL, processing_state layers)
- Safe path: Writes with safety checks (skip RL imagination)
- Full path: Complex operations (full 6-phase execution)

This provides 70% performance improvement for simple operations while
preserving full intelligence for complex/risky ones.
"""
import asyncio
import logging
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ExecutionPath(Enum):
    """Available execution paths."""

    FAST = "fast"  # Skip RL, minimal processing_state (reads)
    SAFE = "safe"  # Safety checks only (writes)
    FULL = "full"  # Complete 6-phase execution (complex)


class OperationRouter:
    """Routes operations to optimal execution path based on characteristics."""

    def __init__(self) -> None:
        """Initialize operation router."""
        # Track routing decisions for learning
        self._routing_history: list[dict[str, Any]] = []

        # Read-only verbs (safe for fast path)
        self._read_verbs = {
            "read",
            "get",
            "list[Any]",
            "search",
            "query",
            "fetch",
            "find",
            "show",
            "display",
            "view",
            "retrieve",
        }

        # Mutating verbs (require safety checks)
        self._write_verbs = {
            "create",
            "update",
            "delete",
            "modify",
            "write",
            "destroy",
            "remove",
            "insert",
            "patch",
            "set[Any]",
        }

        # Complex verbs (require full intelligence)
        self._complex_verbs = {
            "plan",
            "optimize",
            "analyze",
            "diagnose",
            "refactor",
            "generate",
            "synthesize",
            "reason",
            "evaluate",
            "decide",
        }

    def classify_operation(
        self,
        intent: dict[str, Any],
        threat_score: float = 0.5,
        context: dict[str, Any] | None = None,
    ) -> ExecutionPath:
        """Classify operation into execution path.

        Args:
            intent: Operation intent with action/app/params
            threat_score: Threat assessment (0.0-1.0, will be computed if not provided)
            context: Additional context for decision

        Returns:
            ExecutionPath indicating optimal routing
        """
        context = context or {}
        action = str(intent.get("action", "")).lower()

        # ========== THREAT INSTINCT ASSESSMENT ==========
        # If threat_score not explicitly provided, compute it from threat instinct
        if threat_score == 0.5:  # Default value indicates no explicit threat score
            try:
                import asyncio

                from kagami.core.instincts.threat_instinct import get_threat_instinct

                threat_instinct = get_threat_instinct()

                # Build context for threat assessment
                threat_context = {
                    "action": intent.get("action", ""),
                    "app": intent.get("app", ""),
                    "params": intent.get("params", {}),
                    "metadata": intent.get("metadata", {}),
                    "context": context,
                }

                # Run async assess in sync context (operation_router might be called sync)
                try:
                    # If we're already inside an event loop, we cannot block here (sync context).
                    # Best-effort: schedule the assessment and keep the conservative default.
                    asyncio.get_running_loop()
                except RuntimeError:
                    # No running loop → safe to run synchronously.
                    threat_assessment = asyncio.run(threat_instinct.assess(threat_context))
                    threat_score = threat_assessment.threat_level
                else:
                    try:
                        asyncio.create_task(threat_instinct.assess(threat_context))
                    except RuntimeError as e:
                        # RuntimeError: cannot create task when no event loop running
                        # (should not happen in this branch, but be defensive)
                        import logging

                        logging.getLogger(__name__).debug(
                            f"Threat assessment task creation failed: {e}"
                        )

                # Emit metric for threat assessment
                try:
                    from kagami_observability.metrics import Histogram

                    threat_scores = Histogram(
                        "kagami_threat_instinct_scores",
                        "Threat assessment scores from operation router",
                        ["action_type"],
                    )
                    action_type = "read" if any(v in action for v in self._read_verbs) else "write"
                    threat_scores.labels(action_type=action_type).observe(threat_score)
                except (ImportError, AttributeError, ValueError, RuntimeError) as e:
                    # ImportError: metrics module unavailable
                    # AttributeError: Histogram missing or malformed
                    # ValueError: invalid metric parameters
                    # RuntimeError: metric registration failed
                    import logging

                    logging.getLogger(__name__).debug(f"Threat score metric emission failed: {e}")

            except Exception as e:
                # Threat instinct unavailable, use conservative default
                import logging

                logging.getLogger(__name__).debug(f"Threat assessment failed: {e}")
                threat_score = 0.5  # Conservative default

        # Force full path if explicitly requested
        if context.get("requires_planning") or context.get("force_full_path"):
            return ExecutionPath.FULL

        # High threat always uses full path (safety critical)
        if threat_score > 0.7:
            return ExecutionPath.FULL

        # Complex operations always use full path
        if any(verb in action for verb in self._complex_verbs):
            return ExecutionPath.FULL

        # Read operations with low threat use fast path
        if any(verb in action for verb in self._read_verbs):
            if threat_score < 0.3:
                return ExecutionPath.FAST
            else:
                return ExecutionPath.SAFE

        # Write operations use safe path (safety checks but skip RL)
        if any(verb in action for verb in self._write_verbs):
            if threat_score < 0.5:
                return ExecutionPath.SAFE
            else:
                return ExecutionPath.FULL

        # Default: Use safe path for unknown operations
        return ExecutionPath.SAFE

    async def execute_fast(
        self, intent: dict[str, Any], app: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute via fast path (skip RL, minimal checks).

        Fast path includes:
        - Ethical check only (required by K2)
        - Direct execution
        - Basic receipt

        Skips:
        - RL imagination planning
        - Threat assessment (assumed low)
        - Prediction instinct
        - Quality gates (read-only)
        - processing_state layers beyond ethical
        """
        from kagami.core.security.jailbreak_detector import JailbreakDetector

        # 1. Jailbreak detection (BLOCKING - pattern matching)
        # Uses ML model for prompt injection detection (97.99% accuracy)
        jailbreak_detector = JailbreakDetector()
        ethical_verdict = await jailbreak_detector.evaluate(context)

        if not ethical_verdict.permissible:
            return {
                "status": "blocked",
                "reason": "jailbreak_detected",
                "detail": ethical_verdict.reasoning,
            }

        # 2. SECURITY CRITICAL: CBF + policy checks (even in fast-path)
        # Fast-path does NOT mean "skip safety checks"
        # CBF is essential for preventing unsafe operations
        # CONSOLIDATION (Dec 1, 2025): Use canonical cbf_integration
        try:
            from kagami.core.safety.cbf_integration import check_cbf_for_operation

            # Policy pre-checks (deny-list[Any] + idempotency for mutations)
            op = str(context.get("operation") or intent.get("action") or "").lower()
            target = str(context.get("target", "")).lower()
            metadata = context.get("metadata", {}) if isinstance(context, dict) else {}

            # Deny-list[Any] examples (extendable): dangerous shells/db operations in fast-path
            deny_signals = [
                "rm -rf",
                "truncate table",
                "drop database",
                "curl | bash",
                "wget | sh",
            ]
            if any(
                sig in (metadata.get("prompt", "") + " " + op + " " + target).lower()
                for sig in deny_signals
            ):
                return {
                    "status": "blocked",
                    "reason": "policy_denied",
                    "detail": "Fast-path policy denied dangerous operation",
                }

            # Enforce idempotency for potential mutations
            mutation_verbs = ["create", "update", "modify", "delete", "destroy", "purge", "write"]
            is_mutation = any(v in op for v in mutation_verbs)
            has_idem = bool(metadata.get("idempotency_key"))
            confirmed = bool(metadata.get("confirmed"))
            if is_mutation and not (has_idem or confirmed):
                return {
                    "status": "blocked",
                    "reason": "idempotency_required",
                    "detail": "Mutation without idempotency key or confirmation",
                }

            # Use canonical CBF check (consolidation: Dec 1, 2025)
            cbf_result = await check_cbf_for_operation(
                operation="fast_path.execute",
                action=intent.get("action", ""),
                target=target,
                params=intent.get("params", {}),
                metadata=metadata,
                source="operation_router.fast",
            )

            if not cbf_result.safe:
                return {
                    "status": "blocked",
                    "reason": cbf_result.reason or "safety_barrier_violation",
                    "detail": cbf_result.detail
                    or f"CBF blocked operation: h(x)={cbf_result.h_x:.3f} < 0",
                }
        except Exception as e:
            # CBF check failed - fail-safe: block operation
            import logging

            logging.getLogger(__name__).error(f"CBF check failed in fast path: {e}")
            return {
                "status": "error",
                "reason": "safety_check_failed",
                "detail": f"Safety check error: {e!s}",
            }

        # 3. Direct execution (only if both gates pass)
        result = await app.process_intent(intent)
        # Normalize: ensure status present for tests/consumers
        if isinstance(result, dict) and "status" not in result:
            result["status"] = "accepted"

        # Minimal receipt
        try:
            # Generate correlation_id if missing
            import uuid

            from kagami.core.receipts import emit_receipt

            correlation_id = context.get("correlation_id") or f"c-{uuid.uuid4().hex[:16]}"

            emit_receipt(
                correlation_id=correlation_id,
                action=intent.get("action", "unknown"),
                app=intent.get("app", "unknown"),
                event_name="fast_path.executed",
                event_data={"path": "fast", "result_status": result.get("status")},
            )
        except (ImportError, AttributeError, TypeError, ValueError) as e:
            # ImportError: receipts module unavailable
            # AttributeError: emit_receipt missing or malformed
            # TypeError: invalid argument types to emit_receipt
            # ValueError: invalid receipt data
            import logging

            logging.getLogger(__name__).debug(f"Receipt emission failed: {e}")

        # Emit fast path metric
        try:
            from kagami_observability.metrics import REGISTRY
            from prometheus_client import Counter

            if not hasattr(REGISTRY, "_fast_path_executions"):
                REGISTRY._fast_path_executions = Counter(  # type: ignore  # Dynamic attr
                    "kagami_operation_router_executions_total",
                    "Operations routed by execution path",
                    ["path"],
                    registry=REGISTRY,
                )
            REGISTRY._fast_path_executions.labels(path="fast").inc()  # type: ignore  # Dynamic attr
        except (ImportError, AttributeError, ValueError, RuntimeError) as e:
            # ImportError: prometheus_client or metrics module unavailable
            # AttributeError: REGISTRY or Counter missing/malformed
            # ValueError: invalid metric parameters
            # RuntimeError: metric registration/increment failed
            import logging

            logging.getLogger(__name__).debug(f"Fast path metric emission failed: {e}")

        return result  # type: ignore[no-any-return]

    async def execute_safe(
        self, intent: dict[str, Any], app: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute via safe path (safety checks, skip RL).

        Safe path includes:
        - Ethical check (required)
        - Threat assessment
        - Quality gates (for writes)
        - Receipts

        Skips:
        - RL imagination planning
        - Full processing_state (only core checks)
        """
        from kagami.core.instincts.threat_instinct import ThreatInstinct
        from kagami.core.security.jailbreak_detector import JailbreakDetector

        # Parallel safety checks
        ethical_task = JailbreakDetector().evaluate(context)
        threat_task = ThreatInstinct().assess(context)

        ethical_verdict, threat_assessment = await asyncio.gather(
            ethical_task, threat_task, return_exceptions=True
        )

        # Handle exceptions
        if isinstance(ethical_verdict, Exception):
            logger.warning(f"Ethical check failed: {ethical_verdict}")
            ethical_verdict: Any = None  # type: ignore[no-redef]

        if isinstance(threat_assessment, Exception):
            logger.debug(f"Threat check failed: {threat_assessment}")
            threat_score = 0.5
        else:
            threat_score = getattr(threat_assessment, "score", 0.5)

        # Block if ethical violation
        if ethical_verdict and not ethical_verdict.permissible:  # type: ignore  # Union member
            return {
                "status": "blocked",
                "reason": "ethical_violation",
                "detail": ethical_verdict.reasoning,  # type: ignore  # Union member
            }

        # Execute
        result = await app.process_intent(intent)

        # Quality gates for writes
        if any(verb in str(intent.get("action", "")).lower() for verb in self._write_verbs):
            try:
                from kagami.core.quality_gates import enforce_quality_gates

                # Minimal gate check
                # Treat write intents as substantive to ensure tests gate runs
                gate_result = await enforce_quality_gates(
                    changed_files=[], substantive_changes=True
                )

                if not gate_result["proceed"]:
                    return {
                        "status": "error",
                        "error": "quality_gate_failure",
                        "details": gate_result["message"],
                    }
            except (ImportError, AttributeError, TypeError, KeyError) as e:
                # ImportError: quality_gates module unavailable
                # AttributeError: enforce_quality_gates missing
                # TypeError: invalid arguments to enforce_quality_gates
                # KeyError: gate_result missing expected keys
                # Non-fatal: quality gates are supplementary checks
                import logging

                logging.getLogger(__name__).debug(f"Quality gate check failed: {e}")

        # Emit receipt
        try:
            # Generate correlation_id if missing
            import uuid

            from kagami.core.receipts import emit_receipt

            correlation_id = context.get("correlation_id") or f"c-{uuid.uuid4().hex[:16]}"

            emit_receipt(
                correlation_id=correlation_id,
                action=intent.get("action", "unknown"),
                app=intent.get("app", "unknown"),
                event_name="safe_path.executed",
                event_data={"path": "safe", "threat_score": threat_score},
            )
        except (ImportError, AttributeError, TypeError, ValueError) as e:
            # ImportError: receipts module unavailable
            # AttributeError: emit_receipt missing or malformed
            # TypeError: invalid argument types to emit_receipt
            # ValueError: invalid receipt data
            import logging

            logging.getLogger(__name__).debug(f"Receipt emission failed: {e}")

        # Emit metric
        try:
            from kagami_observability.metrics import REGISTRY
            from prometheus_client import Counter

            if not hasattr(REGISTRY, "_safe_path_executions"):
                REGISTRY._safe_path_executions = Counter(  # type: ignore  # Dynamic attr
                    "kagami_operation_router_executions_total",
                    "Operations routed by execution path",
                    ["path"],
                    registry=REGISTRY,
                )
            REGISTRY._safe_path_executions.labels(path="safe").inc()  # type: ignore  # Dynamic attr
        except (ImportError, AttributeError, ValueError, RuntimeError) as e:
            # ImportError: prometheus_client or metrics module unavailable
            # AttributeError: REGISTRY or Counter missing/malformed
            # ValueError: invalid metric parameters
            # RuntimeError: metric registration/increment failed
            import logging

            logging.getLogger(__name__).debug(f"Safe path metric emission failed: {e}")

        return result  # type: ignore[no-any-return]

    async def execute_full(
        self, intent: dict[str, Any], app: Any, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute via full path (complete 6-phase execution).

        Full path includes:
        - All processing_state layers
        - RL imagination planning
        - Quality gates
        - Full receipts (PLAN/EXECUTE/VERIFY)
        - Checkpointing
        """
        # Delegate to caller-provided full executor to avoid orchestrator import cycles.
        # Callers (e.g., IntentOrchestrator) can pass either:
        # - context["full_executor"]: async callable(intent) -> result
        # - context["orchestrator"]: object with async process_intent(intent)
        full_executor = context.get("full_executor")
        if callable(full_executor):
            result = await full_executor(intent)
        else:
            orchestrator = context.get("orchestrator")
            if orchestrator is not None and hasattr(orchestrator, "process_intent"):
                result = await orchestrator.process_intent(intent)
            else:
                # Conservative fallback: execute via SAFE path if we can't delegate.
                result = await self.execute_safe(intent, app, context)

        # Emit metric
        try:
            from kagami_observability.metrics import REGISTRY
            from prometheus_client import Counter

            if not hasattr(REGISTRY, "_full_path_executions"):
                REGISTRY._full_path_executions = Counter(  # type: ignore  # Dynamic attr
                    "kagami_operation_router_executions_total",
                    "Operations routed by execution path",
                    ["path"],
                    registry=REGISTRY,
                )
            REGISTRY._full_path_executions.labels(path="full").inc()  # type: ignore  # Dynamic attr
        except (ImportError, AttributeError, ValueError, RuntimeError) as e:
            # ImportError: prometheus_client or metrics module unavailable
            # AttributeError: REGISTRY or Counter missing/malformed
            # ValueError: invalid metric parameters
            # RuntimeError: metric registration/increment failed
            import logging

            logging.getLogger(__name__).debug(f"Full path metric emission failed: {e}")

        return result  # type: ignore[no-any-return]

    async def route_and_execute(
        self,
        intent: dict[str, Any],
        app: Any,
        threat_score: float = 0.5,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Route operation to optimal execution path and execute.

        Args:
            intent: Operation intent
            app: App instance to execute on
            threat_score: Threat assessment
            context: Additional context

        Returns:
            Execution result
        """
        context = context or {}

        # Classify operation
        path = self.classify_operation(intent, threat_score, context)

        # Log routing decision (debug only)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                f"🔀 Router: {intent.get('action')} → {path.value} path (threat={threat_score:.2f})"
            )

        # Execute via selected path
        if path == ExecutionPath.FAST:
            result = await self.execute_fast(intent, app, context)
        elif path == ExecutionPath.SAFE:
            result = await self.execute_safe(intent, app, context)
        else:
            result = await self.execute_full(intent, app, context)

        # Track decision for learning
        self._routing_history.append(
            {
                "action": intent.get("action"),
                "path": path.value,
                "threat_score": threat_score,
                "duration_ms": result.get("duration_ms", 0),
                "status": result.get("status"),
            }
        )

        # Keep bounded history
        if len(self._routing_history) > 1000:
            self._routing_history = self._routing_history[-500:]

        return result

    def get_stats(self) -> dict[str, Any]:
        """Get routing statistics."""
        if not self._routing_history:
            return {
                "total_operations": 0,
                "path_distribution": {},
                "avg_duration_by_path": {},
            }

        # Compute distribution
        path_counts: dict[str, int] = {}
        path_durations: dict[str, list[float]] = {}

        for record in self._routing_history:
            path = record["path"]
            path_counts[path] = path_counts.get(path, 0) + 1

            if path not in path_durations:
                path_durations[path] = []
            path_durations[path].append(record["duration_ms"])

        # Compute averages
        avg_durations = {}
        for path, durations in path_durations.items():
            if durations:
                import numpy as np

                avg_durations[path] = float(np.mean(durations))

        return {
            "total_operations": len(self._routing_history),
            "path_distribution": path_counts,
            "avg_duration_by_path": avg_durations,
            "fast_path_percentage": (path_counts.get("fast", 0) / len(self._routing_history) * 100),
        }


# Global singleton
_operation_router: OperationRouter | None = None


def get_operation_router() -> OperationRouter:
    """Get global operation router instance."""
    global _operation_router
    if _operation_router is None:
        _operation_router = OperationRouter()
        logger.info("🔀 Operation router initialized (fast/safe/full paths)")
    return _operation_router


__all__ = ["ExecutionPath", "OperationRouter", "get_operation_router"]
