"""Colony Activity Stream WebSocket Endpoint.

Real-time streaming of all colony activity, plans, and tasks to the UI.
Makes the organism feel ALIVE.

Created: November 9, 2025
Enhanced: December 4, 2025 - Added heartbeat/keepalive
Updated: December 24, 2025 - Added proper authentication (Socket.IO migration)

Authentication:
- First-frame auth: Send {"type": "auth", "api_key": "...", "token": "..."} as first message
- Query param: ?api_key=sk_... or ?token=...
- Auth timeout: 5 seconds
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/colonies", tags=["colonies"])

    # Heartbeat configuration
    HEARTBEAT_INTERVAL_SECONDS = 30  # Send heartbeat every 30 seconds
    HEARTBEAT_TIMEOUT_SECONDS = 90  # Consider connection dead after 90 seconds without response

    @router.websocket("/stream")
    async def colony_activity_stream(websocket: WebSocket) -> None:
        """
        Stream real-time colony activity to connected clients.

        Streams:
        - Colony heartbeats
        - Active plans and progress
        - Task updates
        - Agent spawning/death
        - Discoveries and errors
        - Collaborations between colonies

        Authentication:
        - Query param: ?api_key=sk_... or ?token=...
        - First-frame auth: {"type": "auth", "api_key": "...", "token": "..."}

        Protocol:
        1. Client connects with auth (query param or first message)
        2. Server validates authentication (5s timeout)
        3. Server sends initial state snapshot
        4. Server streams activity events as they occur
        5. Client can request full state refresh
        """
        from kagami_api.security import SecurityFramework
        from kagami_api.security.websocket import (
            WS_AUTH_TIMEOUT_SECONDS,
            WS_CLOSE_UNAUTHORIZED,
            authenticate_ws,
            emit_auth_metrics,
        )

        # Check for auth in query params first
        api_key = websocket.query_params.get("api_key", "")
        token = websocket.query_params.get("token", "")
        auth_info = None

        if api_key and SecurityFramework.validate_api_key(api_key):
            auth_info = {"user_id": "api_key_user", "roles": ["api_user"], "tenant_id": None}
        elif token:
            try:
                principal = SecurityFramework.verify_token(token)
                auth_info = {
                    "user_id": principal.sub,
                    "roles": principal.roles,
                    "tenant_id": principal.tenant_id,
                }
            except Exception:
                pass

        # Accept connection first (required for first-frame auth)
        await websocket.accept()

        # If no query param auth, try first-frame auth
        if not auth_info:
            try:
                # Wait for auth message with timeout
                auth_msg = await asyncio.wait_for(
                    websocket.receive_json(), timeout=WS_AUTH_TIMEOUT_SECONDS
                )
                auth_info = await authenticate_ws(auth_msg)
            except TimeoutError:
                logger.warning(f"Colony stream auth timeout: {websocket.client}")
                emit_auth_metrics(success=False, reason="timeout")
                await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Authentication timeout")
                return
            except Exception as e:
                logger.warning(f"Colony stream auth error: {e}")
                emit_auth_metrics(success=False, reason="invalid_message")
                await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Invalid auth message")
                return

        if not auth_info:
            logger.warning(f"Colony stream auth failed: {websocket.client}")
            emit_auth_metrics(success=False, reason="invalid_credentials")
            await websocket.close(code=WS_CLOSE_UNAUTHORIZED, reason="Authentication failed")
            return

        emit_auth_metrics(success=True)
        logger.info(
            f"Colony stream WebSocket authenticated: {websocket.client} (user={auth_info.get('user_id')})"
        )

        try:
            from kagami.core.unified_agents import get_shared_awareness, get_unified_organism

            awareness = get_shared_awareness()
            organism = get_unified_organism()

            # Gather initial agents list for 3D visualization
            agents_list = []
            if organism:
                try:
                    for _, colony_obj in organism._iter_colony_items():  # type: ignore[attr-defined]
                        colony_domain = getattr(colony_obj, "domain", "unknown")
                        colony_name = getattr(colony_domain, "value", str(colony_domain))

                        colony_agents = list(getattr(colony_obj, "agents", {}).values())
                        for agent in colony_agents:
                            status_obj = getattr(agent, "status", None)
                            status_value = getattr(
                                status_obj, "value", str(status_obj) if status_obj else "unknown"
                            )

                            # SAFE DATE HANDLING
                            created_val = getattr(agent, "created_at", None)
                            if isinstance(created_val, int | float):
                                created_at_str = datetime.fromtimestamp(created_val).isoformat()
                            elif isinstance(created_val, datetime):
                                created_at_str = created_val.isoformat()
                            else:
                                created_at_str = datetime.now().isoformat()

                            agents_list.append(
                                {
                                    "id": getattr(agent, "agent_id", "unknown"),
                                    "colony": colony_name,
                                    "status": status_value,
                                    "fitness": getattr(agent, "fitness", 0.0),
                                    "name": getattr(agent, "agent_id", "unknown"),
                                    "workload": getattr(agent, "workload", 0.0),
                                    "created_at": created_at_str,
                                }
                            )
                except Exception as e:
                    logger.warning(f"Failed to gather agents for stream: {e}")

            # Get vitals and collaboration health
            vitals_data = _get_vitals_snapshot(organism)

            # Send initial state snapshot
            await websocket.send_json(
                {
                    "type": "initial_state",
                    "data": {
                        "active_plans": [
                            {
                                "id": plan.plan_id,
                                "colony": plan.colony_name,
                                "goal": plan.goal,
                                "progress": plan.progress,
                                "status": plan.status,
                                "steps": plan.steps,
                                "current_step": plan.current_step,
                                "created_at": plan.created_at.isoformat(),
                                "updated_at": plan.updated_at.isoformat(),
                            }
                            for plan in awareness.get_all_plans()  # type: ignore[attr-defined]
                        ],
                        "colonies": [
                            {"name": name, **status}
                            for name, status in awareness.colony_status.items()  # type: ignore[attr-defined]
                        ],
                        "agents": agents_list,
                        "statistics": awareness.get_statistics(),  # type: ignore[attr-defined]
                        "vitals": vitals_data,
                    },
                }
            )
            logger.info(f"Sent initial state snapshot with {len(agents_list)} agents")

            # Subscribe to activity stream
            activity_queue = await awareness.subscribe_to_activity()  # type: ignore[attr-defined]

            # Background task to receive from queue and send to WebSocket
            async def send_activities() -> None:
                while True:
                    try:
                        activity_data = await activity_queue.get()
                        await websocket.send_json(activity_data)
                    except Exception as e:
                        logger.error(f"Error sending activity: {e}")
                        break

            # Track last activity for heartbeat
            last_client_activity = time.time()

            # Background task to send heartbeats
            async def send_heartbeats() -> None:
                nonlocal last_client_activity
                while True:
                    try:
                        await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

                        # Check if client is still responsive
                        if time.time() - last_client_activity > HEARTBEAT_TIMEOUT_SECONDS:
                            logger.warning(f"WebSocket heartbeat timeout for {websocket.client}")
                            await websocket.close(code=1000, reason="Heartbeat timeout")
                            break

                        # Send heartbeat
                        await websocket.send_json(
                            {
                                "type": "heartbeat",
                                "timestamp": datetime.now().isoformat(),
                                "server_time_ms": int(time.time() * 1000),
                            }
                        )
                        logger.debug(f"Sent heartbeat to {websocket.client}")

                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.debug(f"Heartbeat send failed: {e}")
                        break

            # Background task to handle incoming messages (for state refresh requests)
            async def handle_messages() -> None:
                nonlocal last_client_activity
                while True:
                    try:
                        data = await websocket.receive_json()
                        last_client_activity = time.time()  # Update activity timestamp

                        if data.get("type") == "request_state":
                            # Client requested full state refresh
                            await websocket.send_json(
                                {
                                    "type": "state_refresh",
                                    "data": {
                                        "active_plans": [
                                            {
                                                "id": plan.plan_id,
                                                "colony": plan.colony_name,
                                                "goal": plan.goal,
                                                "progress": plan.progress,
                                                "status": plan.status,
                                            }
                                            for plan in awareness.get_all_plans()  # type: ignore[attr-defined]
                                        ],
                                        "statistics": awareness.get_statistics(),  # type: ignore[attr-defined]
                                    },
                                }
                            )
                            logger.debug("Sent state refresh")

                        elif data.get("type") == "ping":
                            # Simple keepalive
                            await websocket.send_json(
                                {
                                    "type": "pong",
                                    "timestamp": datetime.now().isoformat(),
                                }
                            )

                        elif data.get("type") == "pong":
                            # Client responding to heartbeat - just update activity
                            pass

                        elif data.get("type") == "heartbeat_ack":
                            # Client acknowledging heartbeat
                            pass

                    except WebSocketDisconnect:
                        break
                    except Exception as e:
                        logger.error(f"Error handling message: {e}")
                        break

            # Run all tasks concurrently
            send_task = asyncio.create_task(send_activities())
            receive_task = asyncio.create_task(handle_messages())
            heartbeat_task = asyncio.create_task(send_heartbeats())

            # Wait for any task to finish (disconnect or error)
            _done, pending = await asyncio.wait(
                [send_task, receive_task, heartbeat_task], return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()

            # Unsubscribe from activity stream
            awareness.unsubscribe(activity_queue)

            logger.info(f"Colony stream WebSocket disconnected: {websocket.client}")

        except WebSocketDisconnect:
            logger.info(f"Colony stream WebSocket disconnected: {websocket.client}")
        except Exception as e:
            logger.error(f"Colony stream WebSocket error: {e}", exc_info=True)
            try:
                await websocket.close(code=1011, reason=str(e))
            except Exception:
                pass

    def _get_vitals_snapshot(organism: Any) -> dict[str, Any]:
        """Get vitals and collaboration health for streaming.

        Args:
            organism: FractalOrganism instance

        Returns:
            Vitals snapshot including Fano collaboration health
        """
        if not organism:
            return {"status": "offline"}

        try:
            raw_vitals = getattr(organism, "vital_signs", {})

            # Core vitals
            vitals = {
                "metabolism": round(raw_vitals.get("metabolism", 0.0), 1),
                "coherence_pct": round(raw_vitals.get("coherence", 1.0) * 100, 1),
                "load": round(raw_vitals.get("load", 0.0), 1),
                "success_rate_pct": round(raw_vitals.get("success_rate", 1.0) * 100, 1),
                "pending_tasks": raw_vitals.get("pending_tasks", 0),
            }

            # Collaboration health
            collab_health = raw_vitals.get("collaboration_health", {})
            fano_lines = raw_vitals.get("fano_lines", {})

            # If not in vitals, fetch directly
            if not collab_health:
                try:
                    from kagami.core.unified_agents import get_collaboration_health

                    full_collab = get_collaboration_health()
                    collab_health = full_collab.get("system", {})
                    fano_lines = full_collab.get("lines", {})
                except Exception:
                    pass

            # Active Fano lines (for UI visualization)
            active_lines = []
            for line_name, line_data in fano_lines.items():
                if line_data.get("activation", 0) > 0.1:
                    active_lines.append(
                        {
                            "name": line_name,
                            "activation": round(line_data.get("activation", 0), 3),
                            "coherence_pct": round(line_data.get("coherence", 1.0) * 100, 1),
                        }
                    )

            vitals["collaboration"] = {
                "overall_coherence_pct": round(
                    collab_health.get("overall_coherence", 1.0) * 100, 1
                ),
                "geometric_fidelity_pct": round(
                    collab_health.get("geometric_fidelity", 1.0) * 100, 1
                ),
                "collaboration_rate": round(collab_health.get("collaboration_rate", 0.0), 2),
                "active_line_count": len(active_lines),
                "active_lines": active_lines,
            }

            # Overall status
            coherence = raw_vitals.get("coherence", 1.0)
            load = raw_vitals.get("load", 0.0)

            if coherence < 0.7 or load > 80:
                vitals["status"] = "attention"
                vitals["status_color"] = "#EF4444"
            elif coherence < 0.85 or load > 60:
                vitals["status"] = "nominal"
                vitals["status_color"] = "#F59E0B"
            else:
                vitals["status"] = "optimal"
                vitals["status_color"] = "#10B981"

            return vitals

        except Exception as e:
            logger.debug(f"Vitals snapshot failed: {e}")
            return {"status": "unknown"}

    return router
