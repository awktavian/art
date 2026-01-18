"""Ralph AI Monitor WebSocket Server.

Streams real-time training data from ralph_tui.py to web clients.

Architecture:
    ralph_tui.py → Log Files → Parser → WebSocket → Clients
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Factory function for WebSocket router."""
    router = APIRouter(tags=["ralph"])

    class ConnectionManager:
        """Manage WebSocket connections."""

        def __init__(self):
            self.active_connections: list[WebSocket] = []

        async def connect(self, websocket: WebSocket):
            """Accept new WebSocket connection."""
            await websocket.accept()
            self.active_connections.append(websocket)
            logger.info(f"Client connected. Total: {len(self.active_connections)}")

        def disconnect(self, websocket: WebSocket):
            """Remove WebSocket connection."""
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total: {len(self.active_connections)}")

        async def broadcast(self, message: dict[str, Any]):
            """Broadcast message to all connected clients."""
            dead_connections = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to client: {e}")
                    dead_connections.append(connection)

            # Remove dead connections
            for conn in dead_connections:
                self.disconnect(conn)

    manager = ConnectionManager()

    class RalphLogParser:
        """Parse ralph_tui.py log output."""

        @staticmethod
        def parse_agent_update(line: str) -> dict[str, Any] | None:
            """Parse agent status line."""
            # Example: "[Agent 1] Score: 75, Status: running, Message: Training..."
            agent_pattern = r"\[Agent (\d+)\] Score: (\d+), Status: (\w+), Message: (.+)"
            match = re.search(agent_pattern, line)
            if match:
                agent_id, score, status, message = match.groups()
                return {
                    "type": "agent_update",
                    "data": {
                        "id": int(agent_id),
                        "name": f"Agent {agent_id}",
                        "score": int(score),
                        "status": status,
                        "message": message,
                        "vote": None,  # Updated later
                        "lastUpdate": asyncio.get_event_loop().time(),
                    },
                    "timestamp": asyncio.get_event_loop().time(),
                }
            return None

        @staticmethod
        def parse_consensus_vote(line: str) -> dict[str, Any] | None:
            """Parse Byzantine consensus vote."""
            # Example: "Agent 1: ✓ APPROVE (score: 85)"
            vote_pattern = r"Agent (\d+): ([✓✗]) (\w+) \(score: (\d+)\)"
            match = re.search(vote_pattern, line)
            if match:
                agent_id, symbol, verdict, score = match.groups()
                return {
                    "type": "consensus_update",
                    "data": {
                        "agentId": int(agent_id),
                        "vote": symbol == "✓",
                        "score": int(score),
                        "timestamp": asyncio.get_event_loop().time(),
                    },
                    "timestamp": asyncio.get_event_loop().time(),
                }
            return None

        @staticmethod
        def parse_metrics(line: str) -> dict[str, Any] | None:
            """Parse training metrics."""
            # Example: "Step: 1000, Loss: 1.234, Phase: training"
            metrics_pattern = r"Step: (\d+), Loss: ([\d.]+), Phase: (\w+)"
            match = re.search(metrics_pattern, line)
            if match:
                step, loss, phase = match.groups()
                return {
                    "type": "metrics_update",
                    "data": {
                        "step": int(step),
                        "loss": float(loss),
                        "phase": phase,
                        "receipts": 0,  # TODO: Parse from logs
                        "validations": 0,  # TODO: Parse from logs
                        "uptime": asyncio.get_event_loop().time(),
                    },
                    "timestamp": asyncio.get_event_loop().time(),
                }
            return None

    class LogFileWatcher(FileSystemEventHandler):
        """Watch log directory for changes."""

        def __init__(self, log_dir: Path, parser: RalphLogParser, manager: ConnectionManager):
            self.log_dir = log_dir
            self.parser = parser
            self.manager = manager
            self.file_positions: dict[str, int] = {}

        def on_modified(self, event: FileSystemEvent):
            """Handle file modification."""
            if event.is_directory or not event.src_path.endswith(".log"):
                return

            asyncio.create_task(self.process_log_file(Path(event.src_path)))

        async def process_log_file(self, log_file: Path):
            """Process new lines in log file."""
            try:
                # Get last read position
                last_pos = self.file_positions.get(str(log_file), 0)

                with open(log_file) as f:
                    f.seek(last_pos)
                    new_lines = f.readlines()
                    self.file_positions[str(log_file)] = f.tell()

                # Parse and broadcast each line
                for line in new_lines:
                    line = line.strip()
                    if not line:
                        continue

                    # Try each parser
                    message = (
                        self.parser.parse_agent_update(line)
                        or self.parser.parse_consensus_vote(line)
                        or self.parser.parse_metrics(line)
                    )

                    if message:
                        await self.manager.broadcast(message)

            except Exception as e:
                logger.error(f"Error processing log file {log_file}: {e}")

    @router.websocket("/ws/ralph")
    async def ralph_websocket(websocket: WebSocket):
        """WebSocket endpoint for Ralph AI monitor.

        Streams real-time training data to web clients.
        """
        await manager.connect(websocket)

        try:
            # Start log watcher if not already running
            log_dir = Path("logs")
            if log_dir.exists():
                parser = RalphLogParser()
                watcher = LogFileWatcher(log_dir, parser, manager)
                observer = Observer()
                observer.schedule(watcher, str(log_dir), recursive=False)
                observer.start()

            # Send initial welcome message
            await websocket.send_json(
                {
                    "type": "connection",
                    "data": {
                        "message": "Connected to Ralph AI Monitor",
                        "timestamp": asyncio.get_event_loop().time(),
                    },
                    "timestamp": asyncio.get_event_loop().time(),
                }
            )

            # Keep connection alive and handle pings
            while True:
                try:
                    data = await websocket.receive_json()
                    if data.get("type") == "ping":
                        await websocket.send_json(
                            {
                                "type": "pong",
                                "timestamp": asyncio.get_event_loop().time(),
                            }
                        )
                except WebSocketDisconnect:
                    break
                except Exception as e:
                    logger.error(f"Error in WebSocket loop: {e}")
                    break

        except WebSocketDisconnect:
            manager.disconnect(websocket)
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            manager.disconnect(websocket)
        finally:
            manager.disconnect(websocket)

    return router
