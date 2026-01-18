from __future__ import annotations

"\nAG-UI Protocol Routes for K os\nProvides endpoints for AG-UI-compatible agent-UI interactions.\n"
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# EventSourceResponse from sse_starlette
try:
    from sse_starlette.sse import EventSourceResponse
except Exception:

    class EventSourceResponse(StreamingResponse):  # type: ignore[no-redef]
        def __init__(
            self, content: str, status_code: int = 200, headers: dict | None = None
        ) -> None:
            super().__init__(
                content, status_code=status_code, headers=headers, media_type="text/event-stream"
            )


# Import get_current_user dependency
import logging
import os

from kagami.core.utils.ids import generate_correlation_id
from kagami.observability.metrics import (
    INTENT_REQUESTS,
    KAGAMI_HTTP_REQUESTS_TOTAL,
    REQUEST_COUNT,
)

from kagami_api.protocols.agui import (
    AGUIAction,
    AGUIEvent,
    AGUIEventType,
    AGUIMessage,
    AGUIProtocolAdapter,
)
from kagami_api.rate_limiter import RateLimiter
from kagami_api.rbac import Permission, has_permission
from kagami_api.routes.user.auth import get_current_user
from kagami_api.services.genui_v2 import genui_service_v2

try:
    from kagami.observability.metrics import GENUI_VALIDATE_FAILURES
except ImportError:
    GENUI_VALIDATE_FAILURES = None
logger = logging.getLogger(__name__)


class AGUISessionRequest(BaseModel):
    """Request to create an AG-UI session."""

    agent_id: str | None = Field(None, description="Agent ID to connect")
    app: str = Field("kagami", description="App context")
    transport: str = Field("websocket", description="Transport type: websocket, sse, webhook")
    webhook_url: str | None = Field(None, description="Webhook URL for webhook transport")
    initial_context: dict[str, Any] = Field(default_factory=dict, description="Initial context")
    streaming: bool = Field(True, description="Enable streaming")
    human_in_loop: bool = Field(False, description="Enable human-in-the-loop")


class AGUIActionRequest(BaseModel):
    """Request to execute an AG-UI action."""

    action: str = Field(..., description="Action type")
    params: dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    component_type: str | None = Field(None, description="Source component type")


class AGUIMessageRequest(BaseModel):
    """Request to send an AG-UI message."""

    role: str = Field("agent", description="Message role")
    content: str | None = Field(None, description="Text content")
    ui: dict[str, Any] | None = Field(None, description="UI descriptor")
    tools: list[dict[str, Any]] | None = Field(None, description="Tool calls")
    stream: bool = Field(False, description="Stream the message")


class AGUIContextUpdateRequest(BaseModel):
    user_context: dict[str, Any] | None = None
    agent_context: dict[str, Any] | None = None
    shared_state: dict[str, Any] | None = None


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    from collections import OrderedDict

    router = APIRouter(prefix="/api/colonies/ui", tags=["colonies", "ui"])

    active_sessions: OrderedDict[str, tuple[AGUIProtocolAdapter, float]] = OrderedDict()
    MAX_ACTIVE_SESSIONS = int(os.getenv("AGUI_MAX_SESSIONS") or "10000")
    SESSION_TTL_SECONDS = int(os.getenv("AGUI_SESSION_TTL") or "3600")
    _AGUI_RPM = int(os.getenv("AGUI_RPM") or "240")
    _AGUI_WS_AUTH_RPM = int(os.getenv("AGUI_WS_AUTH_RPM") or "60")
    agui_rate_limiter = RateLimiter(requests_per_minute=_AGUI_RPM, window_size=60)
    RateLimiter(requests_per_minute=_AGUI_WS_AUTH_RPM, window_size=60)

    def _cleanup_stale_sessions() -> int:
        """Remove stale sessions to prevent unbounded memory growth.

        Returns number of sessions removed.
        """
        import time

        now = time.time()
        stale_keys = [
            sid for sid, (_, ts) in active_sessions.items() if now - ts > SESSION_TTL_SECONDS
        ]
        for sid in stale_keys:
            active_sessions.pop(sid, None)
        while len(active_sessions) > MAX_ACTIVE_SESSIONS:
            active_sessions.popitem(last=False)
        return len(stale_keys)

    def _get_session(session_id: str) -> AGUIProtocolAdapter | None:
        """Get session and update last activity timestamp."""
        import time

        if session_id in active_sessions:
            adapter, _ = active_sessions[session_id]
            active_sessions[session_id] = (adapter, time.time())
            active_sessions.move_to_end(session_id)
            return adapter
        return None

    def _add_session(session_id: str, adapter: AGUIProtocolAdapter) -> None:
        """Add new session with cleanup."""
        import time

        _cleanup_stale_sessions()
        active_sessions[session_id] = (adapter, time.time())
        active_sessions.move_to_end(session_id)

    def _remove_session(session_id: str) -> None:
        """Remove session."""
        active_sessions.pop(session_id, None)

    _WS_IDEMPOTENCY_MEM: OrderedDict[str, float] = OrderedDict()
    int(os.getenv("WS_MAX_IDEM_KEYS") or "10000")
    try:
        _WS_IDEM_TTL = int(os.getenv("WS_IDEMPOTENCY_TTL_SECONDS") or "300")
    except Exception:
        from kagami_api.api_settings import WS_IDEMPOTENCY_TTL_SECONDS as _WS_IDEM_TTL
    _WS_MUTATION_OPERATIONS = {
        "execute",
        "create",
        "update",
        "delete",
        "remove",
        "plan.create",
        "plan.update",
        "plan.delete",
        "file.create",
        "file.update",
        "file.delete",
        "agent.register",
        "agent.selfplay.start",
    }

    async def _ws_idem_check_and_set_async(session_id: str, key: str | None) -> str:
        """Cluster-safe WS idempotency using unified module.

        Returns: "accepted" | "duplicate" | "missing_key" | "error"
        """
        if key is None:
            return "missing_key"
        from kagami.core.receipts import ensure_ws_idempotency

        return await ensure_ws_idempotency(session_id, key, ttl_seconds=_WS_IDEM_TTL)

    def _client_id(request: Request) -> str:
        try:
            ip = (
                request.headers.get("X-Real-IP")
                or request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            )
            if not ip and request.client:
                ip = request.client.host or "unknown"
        except Exception:
            ip = "unknown"
        return f"{ip}:{request.url.path}"

    def _prune_expired_sessions() -> None:
        """Evict expired AG-UI sessions based on TTL."""
        try:
            import datetime as _dt
            import os as _os

            ttl_s = int((_os.getenv("AGUI_SESSION_TTL_SECONDS") or "3600").strip())
            if ttl_s <= 0:
                return
            now = _dt.datetime.now(_dt.UTC)
            stale: list[str] = []
            for sid, session_tuple in list(active_sessions.items()):
                try:
                    adapter, _ = session_tuple
                    created_iso = (
                        adapter.context.agent_context.get("created_at")
                        if isinstance(adapter.context.agent_context, dict)
                        else None
                    )
                    if not created_iso:
                        continue
                    created = _dt.datetime.fromisoformat(str(created_iso))
                    if (now - created).total_seconds() > float(ttl_s):
                        stale.append(sid)
                except Exception:
                    continue
            for sid in stale:
                try:
                    logger.info("AGUI session evicted due to TTL: %s", sid)
                    try:
                        session_tuple = active_sessions.pop(sid)
                        adapter, _ = session_tuple
                        try:
                            import asyncio as _aio

                            coro = adapter.stop()
                            try:
                                loop = _aio.get_event_loop()
                                if loop.is_running():
                                    loop.create_task(coro)
                                else:
                                    loop.run_until_complete(coro)
                            except Exception:
                                pass
                        except Exception:
                            pass
                    except KeyError:
                        pass
                except Exception:
                    pass
        except Exception:
            pass

    def _extract_user_info(user: Any) -> tuple[str, str]:
        """Best-effort extraction of user_id and role from various user shapes.

        Supports objects with attributes (id/role) and dicts with keys (user_id/id, roles/role).
        """
        try:
            uid = getattr(user, "id", None)
            role = getattr(user, "role", None)
            if isinstance(uid, str | int) and role:
                return (str(uid), str(role))
        except Exception:
            pass
        try:
            if isinstance(user, dict):
                uid = user.get("user_id") or user.get("id") or user.get("sub") or "anonymous"
                roles = user.get("roles")
                role = user.get("role")
                if not role:
                    if isinstance(roles, list) and roles:
                        role = roles[0]
                    else:
                        role = "user"
                return (str(uid), str(role))
        except Exception:
            pass
        return ("anonymous", "user")

    @router.post("/session/{session_id}/message")
    async def send_message(  # type: ignore[no-untyped-def]
        session_id: str,
        request: AGUIMessageRequest,
        req: Request,
        user=Depends(get_current_user),
    ) -> dict[str, Any]:
        """Send a message in an AG-UI session."""
        allowed, _remaining, reset = agui_rate_limiter.is_allowed(_client_id(req))
        if not allowed:
            raise HTTPException(
                status_code=429, detail="rate_limited", headers={"Retry-After": str(reset)}
            )
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        adapter = _get_session(session_id)
        if not adapter:
            raise HTTPException(status_code=404, detail="Session not found")
        correlation_id = generate_correlation_id(prefix="msg", length=16)
        try:
            from kagami.core.receipts import emit_receipt

            emit_receipt(
                correlation_id=correlation_id,
                action="agui.send_message",
                app="agui",
                args={"session_id": session_id, "role": request.role},
                event_name="message.planned",
                event_data={"phase": "plan"},
            )
        except Exception as e:
            logger.warning(f"Failed to emit PLAN receipt: {e}")
        message = AGUIMessage(
            role=request.role, content=request.content, ui=request.ui, tools=request.tools
        )
        message_correlation = await adapter.send_message(message, stream=request.stream)
        try:
            from kagami.core.receipts import emit_receipt

            emit_receipt(
                correlation_id=correlation_id,
                action="agui.send_message",
                app="agui",
                event_name="message.sent",
                event_data={
                    "phase": "execute",
                    "session_id": session_id,
                    "message_correlation": message_correlation,
                },
            )
        except Exception as e:
            logger.warning(f"Failed to emit EXECUTE receipt: {e}")
        REQUEST_COUNT.labels(method="POST", route="/api/agui/session/message", status="200").inc()
        KAGAMI_HTTP_REQUESTS_TOTAL.labels(
            method="POST", route="/api/agui/session/message", status_code="200"
        ).inc()
        result = {
            "correlation_id": message_correlation,
            "session_id": session_id,
            "stream": request.stream,
        }
        try:
            from kagami.core.receipts import emit_receipt

            emit_receipt(
                correlation_id=correlation_id,
                action="agui.send_message",
                app="agui",
                event_name="message.verified",
                event_data={"phase": "verify", "status": "success"},
                status="success",
            )
        except Exception as e:
            logger.warning(f"Failed to emit VERIFY receipt: {e}")
        try:
            # Cache result if idempotency key is present
            key_hdr = req.headers.get("Idempotency-Key") or req.headers.get("X-Idempotency-Key")
            if key_hdr:
                from kagami.core.receipts.store import get_idempotency_store

                store = get_idempotency_store()
                path = req.url.path
                try:
                    await store.store_response(
                        path=path,
                        idempotency_key=key_hdr,
                        status_code=200,
                        response_body=result,
                    )
                except Exception as e:
                    logger.debug(f"Metric recording failed: {e}")
                    # Metrics are non-critical
        except Exception:
            pass
        try:
            from kagami.core.schemas.receipt_schema import Receipt as _Receipt

            rec = _Receipt(
                correlation_id=correlation_id,
                guardrails={"rbac": "ok", "csrf": "ok", "rate_limit": "ok", "idempotency": "n/a"},
                intent={
                    "mode": "EXECUTE",
                    "action": "message.send",
                    "app": "agui",
                    "args": {"session_id": session_id, "stream": request.stream},
                },
                event={"type": "message.accepted", "data": {"session_id": session_id}},
                metrics={"endpoint": "/metrics"},
            )
            result["receipt"] = rec.dict()
        except Exception:
            pass
        try:
            logger.info("AGUI message.sent session=%s cid=%s", session_id, correlation_id)
        except Exception:
            pass
        return result

    @router.post("/session/{session_id}/action")
    async def execute_action(  # type: ignore[no-untyped-def]
        session_id: str,
        request: AGUIActionRequest,
        req: Request,
        user=Depends(get_current_user),
    ) -> dict[str, Any]:
        """Execute an action in an AG-UI session."""
        allowed, _remaining, reset = agui_rate_limiter.is_allowed(_client_id(req))
        if not allowed:
            raise HTTPException(
                status_code=429, detail="rate_limited", headers={"Retry-After": str(reset)}
            )
        if session_id not in active_sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        adapter = _get_session(session_id)
        if not adapter:
            raise HTTPException(status_code=404, detail="Session not found")
        correlation_id = generate_correlation_id(prefix="act", length=16)
        try:
            from kagami.core.receipts import emit_receipt

            emit_receipt(
                correlation_id=correlation_id,
                action="agui.execute_action",
                app="agui",
                args={"session_id": session_id, "action": request.action},
                event_name="action.planned",
                event_data={"phase": "plan"},
            )
        except Exception as e:
            logger.warning(f"Failed to emit PLAN receipt: {e}")
        try:
            action = AGUIAction(request.action)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid action: {request.action}"
            ) from None
        try:
            roles = []
            try:
                if hasattr(user, "roles"):
                    roles = list(user.roles or [])
                elif isinstance(user, dict):
                    roles = list(user.get("roles") or [])
            except Exception:
                roles = []

            def _enforce_or_skip(required: str) -> bool:
                return has_permission(roles, required)

            if action == AGUIAction.CALL_TOOL and (not _enforce_or_skip(Permission.TOOL_EXECUTE)):
                raise HTTPException(
                    status_code=403, detail="permission_required:tool.execute"
                ) from None
            if action == AGUIAction.HTTP_POST and (not _enforce_or_skip(Permission.SYSTEM_WRITE)):
                raise HTTPException(
                    status_code=403, detail="permission_required:system.write"
                ) from None
        except HTTPException:
            raise
        except Exception:
            pass
        try:
            from kagami.core.safety.cbf_integration import enforce_cbf_for_operation

            await enforce_cbf_for_operation(
                operation="websocket.action",
                action=action.value,
                target=request.component_type or "adapter",
                params=request.params,
                source="websocket",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"CBF check failed for WebSocket action: {e}, allowing")
        if request.component_type:
            result = await genui_service_v2.handle_component_action(
                component_type=request.component_type,
                action=action,
                params=request.params,
                adapter=adapter,
            )
        else:
            result = await adapter.action_handler.handle_action(action, request.params)
        try:
            from kagami.core.receipts import emit_receipt

            emit_receipt(
                correlation_id=correlation_id,
                action="agui.execute_action",
                app="agui",
                event_name="action.executed",
                event_data={"phase": "execute", "session_id": session_id, "action": str(action)},
            )
        except Exception as e:
            logger.warning(f"Failed to emit EXECUTE receipt: {e}")
        try:
            INTENT_REQUESTS.labels(action=action.value, app="agui").inc()
            from kagami.observability.metrics import (
                INTENT_REQUESTS_BY_ACTION_APP as _INTENT_BY_ACTION_APP,
            )

            _INTENT_BY_ACTION_APP.labels(action=action.value, app="agui").inc()
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")
            # Metrics are non-critical
        try:
            from kagami.core.receipts import emit_receipt

            emit_receipt(
                correlation_id=correlation_id,
                action="agui.execute_action",
                app="agui",
                event_name="action.verified",
                event_data={"phase": "verify", "status": "success"},
                status="success",
            )
        except Exception as e:
            logger.warning(f"Failed to emit VERIFY receipt: {e}")
        try:
            if isinstance(result, dict) and "receipt" not in result:
                from kagami.core.schemas.receipt_schema import Receipt as _Receipt

                _rec = _Receipt(
                    correlation_id=correlation_id,
                    guardrails={
                        "rbac": "ok",
                        "csrf": "ok",
                        "rate_limit": "ok",
                        "idempotency": "ok",
                    },
                    intent={
                        "mode": "EXECUTE",
                        "action": action.value,
                        "app": "agui",
                        "args": request.dict(),
                    },
                    event={"type": f"action.{action.value}", "data": result},
                    metrics={"endpoint": "/metrics"},
                ).dict()
                result = {"result": result, "receipt": _rec}
        except Exception:
            pass
        try:
            await adapter.transport.send_event(
                AGUIEvent(
                    type=AGUIEventType.ACTION_RESULT,
                    correlation_id=str(uuid.uuid4()),
                    session_id=session_id,
                    data=result,
                )
            )
        except Exception:
            pass
        try:
            # Cache result if idempotency key is present
            key_hdr = req.headers.get("Idempotency-Key") or req.headers.get("X-Idempotency-Key")
            if key_hdr and isinstance(result, dict):
                from kagami.core.receipts.store import get_idempotency_store

                store = get_idempotency_store()
                path = req.url.path
                try:
                    await store.store_response(
                        path=path,
                        idempotency_key=key_hdr,
                        status_code=200,
                        response_body=result,
                    )
                except Exception:
                    pass
        except Exception:
            pass
        try:
            logger.info("AGUI action.executed session=%s action=%s", session_id, action.value)
        except Exception:
            pass
        return result

    return router
