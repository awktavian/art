from __future__ import annotations

import logging
from typing import Any

from kagami_api.socketio.namespaces.root import KagamiOSNamespace
from kagami_api.socketio.telemetry import traced_operation

logger = logging.getLogger(__name__)


class IntentNamespace(KagamiOSNamespace):
    """Namespace for intent-related events."""

    def __init__(self) -> None:
        super().__init__("/intents")

    async def on_execute(self, sid: str, data: dict[str, Any]) -> None:
        """Handle intent execution request."""
        if not await self._require_auth(sid):
            return

        with traced_operation("socketio.intent.execute", attributes={"sid": sid}):
            from kagami_api.socketio_helpers import (
                apply_policy_gates,
                build_error_response,
                emit_blocked_verify_receipt,
                emit_idempotency_blocked_receipt,
                emit_intent_execute_receipt,
                emit_intent_plan_receipt,
                extract_idempotency_key,
                handle_ws_idempotency,
                is_mutation_intent,
                parse_intent_to_orch_format,
            )

            user = self.session_users.get(sid, {})
            intent = (data or {}).get("intent")
            idem_key = extract_idempotency_key(data)

            if not intent:
                await self.emit(
                    "error",
                    build_error_response("INVALID_INTENT", "Intent required"),
                    room=sid,
                )
                return

            try:
                idem_status, idem_error = await handle_ws_idempotency(
                    idem_key,
                    user.get("id", "unknown"),
                    is_mutation_intent(intent),
                )
                if idem_status == "missing":
                    await emit_idempotency_blocked_receipt(intent, sid)
                    await self.emit(
                        "intent.error",
                        build_error_response("IDEMPOTENCY_KEY_REQUIRED", idem_error),  # type: ignore[arg-type]
                        room=sid,
                    )
                    return
                if idem_status == "duplicate":
                    await self.emit(
                        "intent.error",
                        {"intent": intent, "error": idem_error, "status": "error"},
                        room=sid,
                    )
                    return

                orch_intent = parse_intent_to_orch_format(intent)

                emit_intent_plan_receipt(orch_intent, sid, idem_key)

                md = orch_intent.setdefault("metadata", {})
                md.setdefault("user_id", user.get("id"))
                md.setdefault("context", {"source": "socketio", "sid": sid})

                constitution_verdict, cbf_decision, cbf_reason = await apply_policy_gates(
                    orch_intent
                )
                if constitution_verdict == "fail":
                    await self.emit(
                        "intent.error",
                        {
                            "intent": intent,
                            "error": f"constitution_block:{cbf_reason}",
                            "status": "error",
                        },
                        room=sid,
                    )
                    return
                if cbf_decision == "blocked":
                    emit_blocked_verify_receipt(orch_intent, sid, "cbf_constraint_violation")
                    await self.emit(
                        "intent.error",
                        {"intent": intent, "error": "cbf_constraint_violation", "status": "error"},
                        room=sid,
                    )
                    return

                import time as _t

                from kagami.core.orchestrator import KagamiOSOrchestrator as Orchestrator

                _t0 = _t.perf_counter()
                orchestrator = Orchestrator()
                self._apply_fixed_point_refinement(orch_intent)
                result = await orchestrator.process_intent(orch_intent)
                duration_ms = int(max(0.0, _t.perf_counter() - _t0) * 1000)

                correlation_id = emit_intent_execute_receipt(
                    orch_intent,
                    result,
                    sid,
                    idem_key,
                    constitution_verdict,
                    cbf_decision,
                    cbf_reason,
                    duration_ms,
                )
                if isinstance(result, dict):
                    result.setdefault("correlation_id", correlation_id)
                    result.setdefault("receipt", {"correlation_id": correlation_id})
                    result.setdefault("predictive_confidence", 0.6)
                    await self._maybe_attach_imagination(
                        result, orch_intent, constitution_verdict, cbf_decision
                    )

                await self.emit(
                    "intent.result",
                    {"intent": intent, "result": result, "status": "success"},
                    room=sid,
                )

            except Exception as e:
                logger.error("Intent execution failed: %s", e)
                await self.emit(
                    "intent.error",
                    {"intent": intent, "error": str(e), "status": "error"},
                    room=sid,
                )

    def _apply_fixed_point_refinement(self, orch_intent: dict[str, Any]) -> None:
        try:
            from kagami.policy.fixed_point import refine_metadata as _refine

            refined_md, _ok, _n = _refine(
                type("_W", (), {"metadata": orch_intent.get("metadata", {})})()
            )
            orch_intent["metadata"].update(refined_md)
        except Exception:
            pass

    async def _maybe_attach_imagination(
        self, result: dict, orch_intent: dict, constitution_verdict: str, cbf_decision: str
    ) -> None:
        try:
            from kagami.core.embodiment.embodied_simulator import (
                imagine_intent as _imagine,  # type: ignore[attr-defined]
            )

            low_conf = constitution_verdict == "fail" or cbf_decision == "adjusted"
            if low_conf:
                preview = await _imagine(
                    {"action": orch_intent.get("action"), "app": orch_intent.get("app")}
                )
                result.setdefault("imagination_preview", preview)
        except Exception:
            pass


__all__ = ["IntentNamespace"]
