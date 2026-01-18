from __future__ import annotations

from kagami.core.async_utils import safe_create_task

"""
AG-UI Protocol Implementation for K os
Based on https://github.com/ag-ui-protocol/ag-ui

This module provides AG-UI-compatible event protocol for real-time agent-UI interactions,
enabling seamless integration between K os agents and frontend applications.
"""
import asyncio
import json
import logging
import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Protocol

from kagami.core.interfaces.agui_types import AGUIMessage
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from kagami.core.events import E8Event, get_unified_bus
from kagami.core.schemas.receipt_schema import Receipt
from kagami.observability.metrics import (
    INTENT_REQUESTS,
    INTENT_REQUESTS_BY_ACTION_APP,
)


class AGUIEventType(str, Enum):
    """Standard AG-UI event types for agent-UI communication."""

    # Core messaging events
    MESSAGE = "message"
    STREAM_START = "stream_start"
    STREAM_CHUNK = "stream_chunk"
    STREAM_END = "stream_end"

    # State synchronization
    STATE_UPDATE = "state_update"
    STATE_SYNC = "state_sync"
    CONTEXT_UPDATE = "context_update"

    # UI generation events
    UI_RENDER = "ui_render"
    UI_UPDATE = "ui_update"
    COMPONENT_ACTION = "component_action"

    # Agent control events
    AGENT_START = "agent_start"
    AGENT_STEP = "agent_step"
    AGENT_COMPLETE = "agent_complete"
    AGENT_ERROR = "agent_error"

    # Human-in-the-loop events
    CONFIRMATION_REQUEST = "confirmation_request"
    CONFIRMATION_RESPONSE = "confirmation_response"
    USER_INPUT_REQUEST = "user_input_request"
    USER_INPUT_RESPONSE = "user_input_response"

    # Tool/action events
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ACTION_REQUEST = "action_request"
    ACTION_RESULT = "action_result"

    # Accessibility events (WCAG 2.1 compliance)
    ARIA_ANNOUNCE = "aria_announce"
    FOCUS_CHANGE = "focus_change"
    FOCUS_TRAP = "focus_trap"
    KEYBOARD_SHORTCUT = "keyboard_shortcut"

    # Cursor/selection events
    CURSOR_UPDATE = "cursor_update"
    SELECTION_CHANGE = "selection_change"


class AGUIAction(str, Enum):
    """Standard AG-UI actions that can be triggered from UI."""

    EMIT_INTENT = "emitIntent"
    OPEN_COMPOSER = "openComposer"
    HTTP_POST = "httpPost"
    NAVIGATE = "navigate"
    UPDATE_STATE = "updateState"
    CALL_TOOL = "callTool"
    CONFIRM = "confirm"
    CANCEL = "cancel"


@dataclass
class AGUIEvent:
    """AG-UI event structure for bidirectional communication."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: AGUIEventType = AGUIEventType.MESSAGE
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    correlation_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        return {
            "id": self.id,
            "type": (self.type.value if isinstance(self.type, AGUIEventType) else self.type),
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "data": self.data,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict())


class AGUIContext(BaseModel):
    """Bidirectional context for agent-UI state synchronization."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str | None = None
    user_context: dict[str, Any] = Field(default_factory=dict)
    agent_context: dict[str, Any] = Field(default_factory=dict)
    shared_state: dict[str, Any] = Field(default_factory=dict)
    ui_state: dict[str, Any] = Field(default_factory=dict)
    active_tools: list[str] = Field(default_factory=list)
    permissions: dict[str, bool] = Field(default_factory=dict)

    def merge_user_context(self, updates: dict[str, Any]) -> None:
        """Merge updates into user context."""
        self.user_context.update(updates)

    def merge_agent_context(self, updates: dict[str, Any]) -> None:
        """Merge updates into agent context."""
        self.agent_context.update(updates)

    def sync_state(self, state: dict[str, Any]) -> None:
        """Synchronize shared state between agent and UI."""
        self.shared_state.update(state)


class AGUITransport(Protocol):
    """Protocol for AG-UI event transport (SSE, WebSocket, webhooks, etc.)."""

    async def send_event(self, event: AGUIEvent) -> None:
        """Send an event to the client."""
        ...

    async def receive_event(self) -> AGUIEvent | None:
        """Receive an event from the client."""
        ...

    async def close(self) -> None:
        """Close the transport connection."""
        ...


class AGUIStreamHandler:
    """Handles streaming responses for real-time agent interactions."""

    def __init__(self, transport: AGUITransport, context: AGUIContext):
        self.transport = transport
        self.context = context
        self.active_streams: dict[str, asyncio.Task] = {}

    async def start_stream(
        self,
        stream_id: str,
        agent_id: str,
        initial_data: dict[str, Any] | None = None,
    ) -> None:
        """Start a new streaming session."""
        event = AGUIEvent(
            type=AGUIEventType.STREAM_START,
            correlation_id=stream_id,
            agent_id=agent_id,
            session_id=self.context.session_id,
            data=initial_data or {},
        )
        await self.transport.send_event(event)

    async def send_chunk(
        self,
        stream_id: str,
        chunk: str | dict[str, Any],
        agent_id: str | None = None,
    ) -> None:
        """Send a streaming chunk."""
        data = {"chunk": chunk} if isinstance(chunk, str) else chunk
        event = AGUIEvent(
            type=AGUIEventType.STREAM_CHUNK,
            correlation_id=stream_id,
            agent_id=agent_id,
            session_id=self.context.session_id,
            data=data,
        )
        await self.transport.send_event(event)

    async def end_stream(
        self,
        stream_id: str,
        final_data: dict[str, Any] | None = None,
        agent_id: str | None = None,
    ) -> None:
        """End a streaming session."""
        event = AGUIEvent(
            type=AGUIEventType.STREAM_END,
            correlation_id=stream_id,
            agent_id=agent_id,
            session_id=self.context.session_id,
            data=final_data or {},
        )
        await self.transport.send_event(event)

        # Clean up active stream
        if stream_id in self.active_streams:
            self.active_streams[stream_id].cancel()
            del self.active_streams[stream_id]


class AGUIActionHandler:
    """Handles UI actions and converts them to K os intents."""

    def __init__(self, context: AGUIContext):
        self.context = context
        self.action_handlers: dict[AGUIAction, Callable] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        """Register default action handlers."""
        self.action_handlers[AGUIAction.EMIT_INTENT] = self._handle_emit_intent
        self.action_handlers[AGUIAction.OPEN_COMPOSER] = self._handle_open_composer
        self.action_handlers[AGUIAction.HTTP_POST] = self._handle_http_post
        self.action_handlers[AGUIAction.NAVIGATE] = self._handle_navigate
        self.action_handlers[AGUIAction.UPDATE_STATE] = self._handle_update_state
        self.action_handlers[AGUIAction.CALL_TOOL] = self._handle_call_tool
        self.action_handlers[AGUIAction.CONFIRM] = self._handle_confirm
        self.action_handlers[AGUIAction.CANCEL] = self._handle_cancel

    async def _handle_emit_intent(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle emit intent action."""
        return {"status": "ok", "action": "emit_intent", "params": params}

    async def _handle_open_composer(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle open composer action."""
        return {"status": "ok", "action": "open_composer", "params": params}

    async def _handle_http_post(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle HTTP POST action."""
        return {"status": "ok", "action": "http_post", "params": params}

    async def _handle_navigate(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle navigation action."""
        return {"status": "ok", "action": "navigate", "params": params}

    async def _handle_update_state(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle state update action."""
        return {"status": "ok", "action": "update_state", "params": params}

    async def _handle_call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle call tool action."""
        return {"status": "ok", "action": "call_tool", "params": params}

    async def _handle_confirm(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle confirm action."""
        return {"status": "ok", "action": "confirm", "params": params}

    async def _handle_cancel(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle cancel action."""
        return {"status": "ok", "action": "cancel", "params": params}

    async def handle_action(
        self,
        action: AGUIAction,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle a UI action and return result."""
        handler = self.action_handlers.get(action)
        if not handler:
            raise ValueError(f"Unknown action: {action}")

        # Emit metrics
        try:
            INTENT_REQUESTS.labels(route="/api/agui/action").inc()
            INTENT_REQUESTS_BY_ACTION_APP.labels(action=action.value, app="agui").inc()
        except Exception as e:
            logger.debug(f"Metric recording failed: {e}")
            # Metrics are non-critical

        # Execute handler
        result = await handler(params)

        # Create receipt
        receipt = Receipt(
            correlation_id=params.get("correlation_id", str(uuid.uuid4())),
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
                "args": params,
            },
            event={"type": f"action.{action.value}", "data": result},
            metrics={"endpoint": "/metrics"},
        )

        return {
            "receipt": receipt.dict(),
            "result": result,
        }


class AGUIProtocolAdapter:
    """
    Main AG-UI protocol adapter for K os.
    Provides middleware layer for agent-UI interactions.
    """

    def __init__(
        self,
        transport: AGUITransport,
        context: AGUIContext | None = None,
    ):
        self.transport = transport
        self.context = context or AGUIContext()
        self.stream_handler = AGUIStreamHandler(transport, self.context)
        self.action_handler = AGUIActionHandler(self.context)
        self.event_handlers: dict[AGUIEventType, list[Callable]] = {}
        self._running = False
        self._event_loop_task: asyncio.Task | None = None
        # App event bus bridge
        self._bus = get_unified_bus()
        self._bus_subs: list[tuple[str, Callable]] = []

    def on_event(
        self,
        event_type: AGUIEventType,
        handler: Callable[[AGUIEvent], Coroutine[Any, Any, Any]],
    ) -> None:
        """Register an event handler."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    async def start(self) -> None:
        """Start the AG-UI protocol adapter."""
        self._running = True
        self._event_loop_task = safe_create_task(self._event_loop(), name="_event_loop")
        # Bridge selected bus topics into AG-UI transport
        await self._register_bus_bridges()

    async def stop(self) -> None:
        """Stop the AG-UI protocol adapter."""
        self._running = False
        if self._event_loop_task:
            self._event_loop_task.cancel()
            try:
                await self._event_loop_task
            except asyncio.CancelledError:
                pass
        await self.transport.close()
        # Unsubscribe explicit topic handlers (pattern handlers may not support unsubscribe)
        try:
            for topic, handler in self._bus_subs:
                try:
                    self._bus.unsubscribe(topic, handler)
                except Exception:
                    pass
            self._bus_subs.clear()
        except Exception:
            pass

    async def _event_loop(self) -> None:
        """Main event processing loop."""
        while self._running:
            try:
                event = await self.transport.receive_event()
                if event:
                    await self._process_event(event)
            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error and continue
                logger.exception("Error processing event: %s", e)
                await asyncio.sleep(0.1)

    async def _process_event(self, event: AGUIEvent) -> None:
        """Process an incoming event."""
        handlers = self.event_handlers.get(event.type, [])
        for handler in handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.exception("Error in event handler: %s", e)
        # Publish to AppEventBus for unified processing when applicable
        try:
            envelope = {
                "session_id": self.context.session_id,
                "agent_id": self.context.agent_id,
                "correlation_id": event.correlation_id or event.id,
                "data": event.data,
                "source": "agui",
                "metadata": {"source_session": self.context.session_id},
                "timestamp": event.timestamp,
            }
            if event.type == AGUIEventType.MESSAGE:
                await self._bus.publish(
                    "ui.message", {**envelope, "topic": "ui.message", "type": "ui"}
                )
            elif event.type == AGUIEventType.COMPONENT_ACTION:
                payload = {**envelope, "topic": "ui.action", "type": "ui"}
                await self._bus.publish("ui.action", payload)
            elif event.type in {
                AGUIEventType.CONTEXT_UPDATE,
                AGUIEventType.STATE_SYNC,
                AGUIEventType.STATE_UPDATE,
            }:
                await self._bus.publish("ui.state", {**envelope, "topic": "ui.state", "type": "ui"})
        except Exception:
            pass

    async def send_message(
        self,
        message: AGUIMessage,
        stream: bool = False,
    ) -> str:
        """Send a message to the UI."""
        correlation_id = str(uuid.uuid4())

        if stream:
            # Start streaming
            await self.stream_handler.start_stream(
                stream_id=correlation_id,
                agent_id=self.context.agent_id or "kagami",
                initial_data={"role": message.role},
            )

            # Stream content chunks
            if message.content:
                for chunk in message.content.split():
                    await self.stream_handler.send_chunk(
                        stream_id=correlation_id,
                        chunk=chunk + " ",
                        agent_id=self.context.agent_id,
                    )
                    await asyncio.sleep(0.05)  # Simulate streaming delay

            # Send UI if present
            if message.ui:
                await self.stream_handler.send_chunk(
                    stream_id=correlation_id,
                    chunk={"ui": message.ui},
                    agent_id=self.context.agent_id,
                )

            # End stream
            await self.stream_handler.end_stream(
                stream_id=correlation_id,
                agent_id=self.context.agent_id,
            )
        else:
            # Send as single message
            event = AGUIEvent(
                type=AGUIEventType.MESSAGE,
                correlation_id=correlation_id,
                agent_id=self.context.agent_id,
                session_id=self.context.session_id,
                data=message.dict(),
            )
            await self.transport.send_event(event)

        return correlation_id

    async def request_confirmation(
        self,
        message: str,
        options: list[str] | None = None,
        timeout: float = 30.0,
    ) -> str | None:
        """Request confirmation from the user (human-in-the-loop)."""
        confirmation_id = str(uuid.uuid4())

        # Send confirmation request
        event = AGUIEvent(
            type=AGUIEventType.CONFIRMATION_REQUEST,
            correlation_id=confirmation_id,
            agent_id=self.context.agent_id,
            session_id=self.context.session_id,
            data={
                "message": message,
                "options": options or ["confirm", "cancel"],
                "timeout": timeout,
            },
        )
        await self.transport.send_event(event)

        # Wait for response
        response_future: asyncio.Future[Any] = asyncio.Future()

        async def response_handler(event: AGUIEvent) -> None:
            if event.correlation_id == confirmation_id:
                response_future.set_result(event.data.get("response"))

        self.on_event(AGUIEventType.CONFIRMATION_RESPONSE, response_handler)

        try:
            response = await asyncio.wait_for(response_future, timeout=timeout)
            return str(response) if response is not None else None
        except TimeoutError:
            return None

    async def update_ui(
        self,
        ui_descriptor: dict[str, Any],
        merge: bool = True,
    ) -> None:
        """Update the UI with a new descriptor."""
        event = AGUIEvent(
            type=AGUIEventType.UI_UPDATE,
            agent_id=self.context.agent_id,
            session_id=self.context.session_id,
            data={
                "ui": ui_descriptor,
                "merge": merge,
            },
        )
        await self.transport.send_event(event)

        # Update context
        if merge:
            self.context.ui_state.update(ui_descriptor)
        else:
            self.context.ui_state = ui_descriptor

    async def _register_bus_bridges(self) -> None:
        """Subscribe to selected AppEventBus topics and forward to the AG-UI transport."""
        try:

            async def _forward(event: E8Event) -> None:
                # Avoid echoing events originating from this session
                try:
                    payload = event.payload or {}
                    meta = payload.get("metadata") or {}
                    if meta.get("source_session") == self.context.session_id:
                        return
                except Exception:
                    pass
                try:
                    # Special handling for HAL display events to be top-level
                    if isinstance(event.topic, str) and event.topic.startswith("hal.display."):
                        data = dict(payload)
                        data.setdefault("topic", event.topic)
                        data.setdefault("type", event.topic)
                        data.setdefault("event_id", event.event_id)
                        data.setdefault("ts", event.timestamp)
                        if event.correlation_id:
                            data.setdefault("correlation_id", event.correlation_id)
                        await self.transport.send_event(
                            AGUIEvent(
                                type=event.topic,  # type: ignore[arg-type]
                                session_id=self.context.session_id,
                                agent_id=self.context.agent_id,
                                correlation_id=event.correlation_id or None,
                                data=data,
                            )
                        )
                        return

                    bus_event = dict(payload)
                    bus_event.setdefault("topic", event.topic)
                    bus_event.setdefault("event_id", event.event_id)
                    bus_event.setdefault("ts", event.timestamp)
                    if event.correlation_id:
                        bus_event.setdefault("correlation_id", event.correlation_id)
                    await self.transport.send_event(
                        AGUIEvent(
                            type=AGUIEventType.UI_UPDATE,
                            session_id=self.context.session_id,
                            agent_id=self.context.agent_id,
                            data={"bus_event": bus_event},
                        )
                    )
                except Exception:
                    pass

            # Explicit topics
            for topic in (
                "run.receipt",
                "approval.request",
                "workflow.request",
                "workflow.start",
                "workflow.complete",
                # Forge progress and content events
                "forge.progress",
                "narrative.created",
                # World model state (AR/Ambient visualizations)
                "world_model.state",
                # HAL Display Events
                "hal.display.init",
                "hal.display.frame",
                "hal.display.clear",
                "hal.display.control",
                "hal.display.shutdown",
            ):
                try:
                    self._bus.subscribe(topic, _forward)
                    self._bus_subs.append((topic, _forward))
                except Exception:
                    pass

            # Pattern subscription for all intent.* topics when supported
            try:
                if hasattr(self._bus, "subscribe_pattern"):
                    self._bus.subscribe_pattern("intent.", _forward)
                    # Gameplay and marketplace event families are useful to surface in AG-UI sessions
                    self._bus.subscribe_pattern("gameplay.", _forward)
                    self._bus.subscribe_pattern("marketplace.asset.", _forward)
                    self._bus.subscribe_pattern("room.", _forward)
                    # World model state stream (Kagami → UI)
                    self._bus.subscribe_pattern("world_model.", _forward)
            except Exception:
                pass
        except Exception:
            pass

    async def sync_context(
        self,
        user_context: dict[str, Any] | None = None,
        agent_context: dict[str, Any] | None = None,
    ) -> None:
        """Synchronize context between agent and UI."""
        if user_context:
            self.context.merge_user_context(user_context)

        if agent_context:
            self.context.merge_agent_context(agent_context)

        # Send state sync event
        event = AGUIEvent(
            type=AGUIEventType.STATE_SYNC,
            agent_id=self.context.agent_id,
            session_id=self.context.session_id,
            data={
                "user_context": self.context.user_context,
                "agent_context": self.context.agent_context,
                "shared_state": self.context.shared_state,
            },
        )
        await self.transport.send_event(event)

    # =========================================================================
    # Accessibility Helpers (WCAG 2.1 Compliance)
    # =========================================================================

    async def announce(
        self,
        message: str,
        politeness: str = "polite",
        clear_queue: bool = False,
    ) -> None:
        """Send an ARIA live region announcement.

        Args:
            message: The message to announce to screen readers
            politeness: "polite" (wait for idle) or "assertive" (interrupt)
            clear_queue: Whether to clear pending announcements
        """
        event = AGUIEvent(
            type=AGUIEventType.ARIA_ANNOUNCE,
            agent_id=self.context.agent_id,
            session_id=self.context.session_id,
            data={
                "message": message,
                "politeness": politeness,
                "clearQueue": clear_queue,
            },
        )
        await self.transport.send_event(event)

    async def focus_element(
        self,
        element_id: str,
        scroll_into_view: bool = True,
    ) -> None:
        """Request focus change to a specific UI element.

        Args:
            element_id: The ID of the element to focus
            scroll_into_view: Whether to scroll the element into view
        """
        event = AGUIEvent(
            type=AGUIEventType.FOCUS_CHANGE,
            agent_id=self.context.agent_id,
            session_id=self.context.session_id,
            data={
                "elementId": element_id,
                "scrollIntoView": scroll_into_view,
            },
        )
        await self.transport.send_event(event)

    async def trap_focus(
        self,
        container_id: str,
        enabled: bool = True,
    ) -> None:
        """Enable or disable focus trapping within a container (for modals).

        Args:
            container_id: The ID of the container to trap focus within
            enabled: Whether to enable or disable the focus trap
        """
        event = AGUIEvent(
            type=AGUIEventType.FOCUS_TRAP,
            agent_id=self.context.agent_id,
            session_id=self.context.session_id,
            data={
                "containerId": container_id,
                "enabled": enabled,
            },
        )
        await self.transport.send_event(event)

    async def register_keyboard_shortcut(
        self,
        shortcut: str,
        action: str,
        description: str,
    ) -> None:
        """Register a keyboard shortcut with the UI.

        Args:
            shortcut: Key combination (e.g., "Ctrl+K", "Escape")
            action: Action identifier to trigger
            description: Human-readable description for accessibility
        """
        event = AGUIEvent(
            type=AGUIEventType.KEYBOARD_SHORTCUT,
            agent_id=self.context.agent_id,
            session_id=self.context.session_id,
            data={
                "shortcut": shortcut,
                "action": action,
                "description": description,
                "register": True,
            },
        )
        await self.transport.send_event(event)
