from __future__ import annotations

"""Socket.IO /agents namespace for agent monitoring and colony state.

This namespace provides real-time agent and colony state updates
to connected clients. It monitors the unified organism and broadcasts
agent/colony state changes periodically.

Events Emitted:
    - agents:state: Current state of all agents and colonies

Architecture:
    Client connects → Monitor task starts → Periodic state broadcast
                                         → Client disconnects → Task cancelled

Usage:
    >>> # Client-side (JavaScript)
    >>> socket = io('/agents')
    >>> socket.on('agents:state', (data) => {
    ...     console.log('Agents:', data.agents)
    ...     console.log('Colonies:', data.colonies)
    ... })
"""

# =============================================================================
# STANDARD LIBRARY IMPORTS
# =============================================================================
import asyncio  # Async I/O for monitor tasks
import logging  # Error and debug logging
import time  # Timestamps
from typing import Any  # Type hints

# =============================================================================
# INTERNAL IMPORTS
# =============================================================================
from kagami_api.socketio.namespaces.root import KagamiOSNamespace  # Base namespace

logger = logging.getLogger(__name__)


class AgentsNamespace(KagamiOSNamespace):
    """Socket.IO namespace for agent monitoring and colony state.

    Provides real-time agent status and colony health monitoring.
    Each connected client gets periodic state updates via background task.

    Attributes:
        _monitor_tasks: Dict mapping session ID to monitor task.

    Events:
        agents:state: Emitted periodically with agent/colony state.
    """

    def __init__(self) -> None:
        """Initialize agents namespace with monitor task tracking."""
        super().__init__(namespace="/agents")
        self._monitor_tasks: dict[str, asyncio.Task] = {}  # SID → monitor task

    async def on_connect(  # type: ignore[no-untyped-def]
        self, sid: str, environ: dict[str, Any], auth: dict[str, Any] | None = None
    ):
        """Handle client connection to /agents namespace.

        Starts a background monitor task for this client that periodically
        broadcasts agent and colony state.

        Args:
            sid: Socket.IO session ID.
            environ: WSGI environment dict.
            auth: Optional authentication data.

        Returns:
            True if connection allowed, False otherwise.
        """
        # Delegate to base class for auth
        result = await super().on_connect(sid, environ, auth)
        if not result:
            return False

        # Update metrics (best-effort)
        try:
            from kagami.observability.metrics import (
                SOCKETIO_CONNECTIONS_ACTIVE,
                SOCKETIO_CONNECTIONS_TOTAL,
            )

            SOCKETIO_CONNECTIONS_TOTAL.labels(namespace="/agents", status="connected").inc()
            SOCKETIO_CONNECTIONS_ACTIVE.labels(namespace="/agents").inc()
        except Exception:
            pass  # Metrics optional

        # Start monitor task for this client
        task = asyncio.create_task(self._monitor_agents(sid))
        self._monitor_tasks[sid] = task

        # Join agents room for broadcast (best-effort)
        try:
            await self.enter_room(sid, "agents")
        except Exception:
            pass

        return True

    async def on_disconnect(self, sid: str) -> None:
        """Handle client disconnection from /agents namespace.

        Cancels the monitor task for this client and updates metrics.

        Args:
            sid: Socket.IO session ID.
        """
        # Delegate to base class
        await super().on_disconnect(sid)

        # Cancel monitor task
        if sid in self._monitor_tasks:
            task = self._monitor_tasks.pop(sid)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass  # Expected on cancellation

        # Update metrics (best-effort)
        try:
            from kagami.observability.metrics import SOCKETIO_CONNECTIONS_ACTIVE

            SOCKETIO_CONNECTIONS_ACTIVE.labels(namespace="/agents").dec()
        except Exception:
            pass  # Metrics optional

    async def _monitor_agents(self, sid: str) -> None:
        """Background task that periodically emits agent/colony state.

        Runs continuously while client is connected, emitting state
        updates every 2 seconds.

        Args:
            sid: Socket.IO session ID to emit to.

        Note:
            Task is cancelled on client disconnect via on_disconnect().
        """
        try:
            try:
                from kagami.core.unified_agents import get_unified_organism
            except ImportError:
                return

            organism = get_unified_organism()

            while True:
                try:
                    agents = []
                    colonies = {}

                    for colony_name, colony in organism.colonies.items():
                        workers = colony.workers
                        active_statuses = {"active", "busy", "idle"}
                        colonies[colony_name] = {
                            "domain": colony_name,
                            "population_active": sum(
                                1 for w in workers if w.state.status.value in active_statuses
                            ),
                            "population_total": len(workers),
                            "avg_fitness": sum(w.fitness for w in workers) / max(1, len(workers)),
                            "tasks_completed": sum(w.state.completed_tasks for w in workers),
                        }

                        for worker in workers:
                            workload = (
                                float(worker.state.current_tasks)
                                / float(worker.config.max_concurrent)
                                if worker.config.max_concurrent > 0
                                else 0.0
                            )
                            agents.append(
                                {
                                    "id": worker.worker_id,
                                    "domain": colony_name,
                                    "status": worker.state.status.value,
                                    "workload": workload,
                                    "fitness": float(worker.fitness),
                                    "current_task": None,
                                    "tasks_completed": int(worker.state.completed_tasks),
                                    "age_seconds": max(
                                        0.0, time.time() - float(worker.state.created_at)
                                    ),
                                }
                            )

                    await self.emit(
                        "state_update",
                        {
                            "agents": agents,
                            "colonies": colonies,
                            "timestamp": asyncio.get_running_loop().time(),
                        },
                        room=sid,
                    )

                    try:
                        from kagami.observability.metrics import SOCKETIO_EVENTS_TOTAL

                        SOCKETIO_EVENTS_TOTAL.labels(
                            namespace="/agents", event_type="state_update", direction="outbound"
                        ).inc()
                    except Exception:
                        pass

                except Exception as e:
                    logger.error("[/agents] Error collecting agent state: %s", e)

                await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("[/agents] Monitoring error for %s: %s", sid, e)


__all__ = ["AgentsNamespace"]
