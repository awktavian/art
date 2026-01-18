from __future__ import annotations

"""
Enhanced GenUI Service v2 with AG-UI Protocol Integration

Unified generative UI service with LLM-driven UI generation,
Pydantic structured output, and full AG-UI protocol support.

All base classes are inlined here. Legacy genui.py has been removed.
"""
import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from kagami.core.services.llm.service import get_llm_service
from kagami.core.unified_agents.app_registry import list_apps_v2
from kagami.observability.metrics import (
    GENUI_CACHE_HITS,
    GENUI_GENERATE_DURATION,
    GENUI_REQUESTS,
    GENUI_VALIDATE_FAILURES,
)
from pydantic import BaseModel, Field

from kagami_api.protocols.agui import (
    AGUIAction,
    AGUIContext,
    AGUIEvent,
    AGUIEventType,
    AGUIMessage,
    AGUIProtocolAdapter,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Structured Output Models for LLM UI Generation
# ============================================================================


class AGUIGridSpec(BaseModel):
    """Grid positioning for a component."""

    span: int = Field(default=12, ge=1, le=12, description="Column span (1-12)")
    offset: int = Field(default=0, ge=0, le=11, description="Column offset")


class AGUIActionSpec(BaseModel):
    """Action binding for a component."""

    type: str = Field(..., description="Action type (emitIntent, callTool, etc.)", alias="type")
    label: str = Field(..., description="Button label")
    icon: str | None = Field(None, description="Emoji or icon identifier")
    style: str | None = Field(None, description="primary, secondary, danger")
    requiresSelection: bool = Field(default=False)


class AGUIComponentSpec(BaseModel):
    """A single UI component in the descriptor."""

    type: str = Field(..., description="Component type")
    grid: AGUIGridSpec = Field(default_factory=AGUIGridSpec)
    props: dict[str, Any] = Field(default_factory=dict, description="Component props")
    actions: list[AGUIActionSpec] = Field(default_factory=list)
    dataBinding: str | None = Field(None, description="Data binding key")


class AGUILayoutSpec(BaseModel):
    """Layout configuration."""

    type: Literal["grid", "flex", "stack"] = "grid"
    columns: int = Field(default=12, ge=1, le=24)
    gutter: int = Field(default=8, ge=0)


class AGUIMetaSpec(BaseModel):
    """Descriptor metadata."""

    appId: str
    sessionId: str | None = None
    agentId: str | None = None
    generated_at: str | None = None
    enhanced_at: str | None = None
    context_version: str | None = None


class AGUIDescriptor(BaseModel):
    """
    Complete AG-UI descriptor for LLM structured output.

    This model enforces the agui/v1 schema and enables type-safe
    UI generation from LLM responses.
    """

    version: Literal["agui/v1"] = "agui/v1"
    meta: AGUIMetaSpec
    layout: AGUILayoutSpec = Field(default_factory=AGUILayoutSpec)
    components: list[AGUIComponentSpec] = Field(default_factory=list)
    dataBindings: dict[str, str] = Field(default_factory=dict)


# ============================================================================
# Component Registry (Extended with AG-UI patterns)
# ============================================================================

AGUI_COMPONENTS = frozenset(
    {
        # Core layout components
        "Card",
        "Table",
        "List",
        "Tabs",
        "Chart",
        # Form components
        "Form",
        "Modal",
        "Accordion",
        "Timeline",
        "Progress",
        "Badge",
        "Alert",
        "Avatar",
        "Button",
        "Input",
        "Select",
        "Checkbox",
        "Radio",
        "Toggle",
        "Slider",
        "DatePicker",
        "FilePicker",
        "RichText",
        "Code",
        "Markdown",
        "Image",
        "Video",
        "Audio",
        "Map",
        "Canvas",
        "Custom",
        # AG-UI interactive components
        "MessageStream",
        "ContextPanel",
        "ToolPanel",
        "ConfirmationDialog",
        "InputForm",
        "StateViewer",
        "AgentStatus",
        "ActionButtons",
    }
)

# AG-UI action bindings for components (pluggable via ENV overrides)
COMPONENT_ACTIONS = {
    "MessageStream": [AGUIAction.EMIT_INTENT, AGUIAction.OPEN_COMPOSER],
    "ContextPanel": [AGUIAction.UPDATE_STATE],
    "ToolPanel": [AGUIAction.CALL_TOOL],
    "ConfirmationDialog": [AGUIAction.CONFIRM, AGUIAction.CANCEL],
    "InputForm": [AGUIAction.HTTP_POST, AGUIAction.EMIT_INTENT],
    "ActionButtons": [AGUIAction.EMIT_INTENT, AGUIAction.NAVIGATE],
}


# ============================================================================
# Context Classes (Inlined from legacy genui.py)
# ============================================================================


@dataclass
class GenUIContext:
    """Base context for GenUI generation sessions.

    Holds session state, user preferences, and generation parameters.
    """

    # Session identification
    user_id: str = "anonymous"
    user_role: str = "user"
    app: str = "kagami"
    view: str | None = None

    # Generation parameters
    theme: str = "default"
    locale: str = "en"
    # REMOVED: responsive: bool = True  # Field was never used - responsiveness handled client-side via CSS
    # REMOVED: accessibility: bool = True  # Field was never used - accessibility baked into LLM prompt

    # State management
    state: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)

    # Component preferences
    preferred_components: list[str] = field(default_factory=list)
    disabled_components: list[str] = field(default_factory=list)

    # Generation constraints
    max_depth: int = 5
    max_components: int = 64
    timeout_ms: int = 5000


@dataclass
class GenUIContextV2(GenUIContext):
    """Extended GenUI context with AG-UI capabilities."""

    # AG-UI specific fields
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str | None = None
    streaming_enabled: bool = True
    bidirectional_state: dict[str, Any] = field(default_factory=dict)
    active_tools: list[str] = field(default_factory=list)
    human_in_loop: bool = False
    context_enrichment: dict[str, Any] = field(default_factory=dict)


class UIComponentBuilder:
    """Builder for AG-UI enhanced UI components."""

    @staticmethod
    def build_message_stream(
        messages: list[dict[str, Any]],
        streaming: bool = True,
    ) -> dict[str, Any]:
        """Build a message stream component for real-time agent chat."""
        return {
            "type": "MessageStream",
            "grid": {"span": 12},
            "props": {
                "messages": messages,
                "streaming": streaming,
                "showTypingIndicator": streaming,
                "enableMarkdown": True,
                "enableCodeHighlight": True,
            },
            "actions": [
                {
                    "type": AGUIAction.OPEN_COMPOSER.value,
                    "label": "Reply",
                    "icon": "💬",
                },
                {
                    "type": AGUIAction.EMIT_INTENT.value,
                    "label": "New Task",
                    "icon": "➕",
                },
            ],
        }

    @staticmethod
    def build_context_panel(
        user_context: dict[str, Any],
        agent_context: dict[str, Any],
        shared_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Build a context panel for bidirectional state sync."""
        return {
            "type": "ContextPanel",
            "grid": {"span": 4},
            "props": {
                "sections": [
                    {
                        "title": "User Context",
                        "data": user_context,
                        "editable": True,
                    },
                    {
                        "title": "Agent Context",
                        "data": agent_context,
                        "editable": False,
                    },
                    {
                        "title": "Shared State",
                        "data": shared_state,
                        "editable": True,
                    },
                ],
                "autoSync": True,
                "syncInterval": 5000,
            },
            "actions": [
                {
                    "type": AGUIAction.UPDATE_STATE.value,
                    "label": "Sync",
                    "icon": "🔄",
                },
            ],
        }

    @staticmethod
    def build_tool_panel(tools: list[dict[str, Any]]) -> dict[str, Any]:
        """Build a tool panel for frontend tool integration."""
        return {
            "type": "ToolPanel",
            "grid": {"span": 4},
            "props": {
                "tools": tools,
                "groupByCategory": True,
                "showDescription": True,
                "enableSearch": True,
            },
            "actions": [
                {
                    "type": AGUIAction.CALL_TOOL.value,
                    "label": "Execute",
                    "requiresSelection": True,
                },
            ],
        }

    @staticmethod
    def build_agent_status(
        agent_id: str,
        status: str,
        current_step: str | None = None,
        progress: float | None = None,
    ) -> dict[str, Any]:
        """Build an agent status component."""
        return {
            "type": "AgentStatus",
            "grid": {"span": 12},
            "props": {
                "agentId": agent_id,
                "status": status,
                "currentStep": current_step,
                "progress": progress,
                "showTimeline": True,
                "showLogs": False,
            },
        }


class GenUIService:
    """Base GenUI service with component validation (inlined from legacy)."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._logger = logging.getLogger(__name__)

    def validate_component(
        self,
        component_type: str,
        props: dict[str, Any] | None = None,
    ) -> tuple[bool, str | None]:
        """Validate a component type and its properties."""
        if component_type not in AGUI_COMPONENTS:
            return False, f"Unknown component type: {component_type}"
        if props is not None and not isinstance(props, dict):
            return False, "Props must be a dictionary"  # type: ignore[unreachable]
        return True, None


class GenUIServiceV2(GenUIService):
    """
    Enhanced GenUI service with AG-UI protocol integration.
    Provides real-time, bidirectional agent-UI interactions.
    """

    def __init__(self) -> None:
        super().__init__()
        self.component_builder = UIComponentBuilder()
        self.active_sessions: dict[str, AGUIContext] = {}
        # Optional Redis cache. Defer actual client resolution to first async use.
        self.redis = None
        # Default cache TTL for AG-UI descriptors
        self.CACHE_TTL_SECONDS = 300

    def _cache_key(self, app: str, view: str) -> str:
        """Generate cache key for UI descriptor."""
        return f"agui:descriptor:{app}:{view}:v1"

    def _validate_descriptor_v2(self, desc: dict[str, Any]) -> str | None:
        """Validate UI descriptor with AG-UI components."""
        try:
            if not isinstance(desc, dict):
                return "descriptor_not_object"  # type: ignore[unreachable]

            version = desc.get("version")
            if version != "agui/v1":
                return "bad_version"

            comps = desc.get("components")
            if not isinstance(comps, list):
                return "components_not_array"
            # Enforce a hard cap on component count
            if len(comps) > 64:
                return "too_many_components"

            for c in comps:
                if not isinstance(c, dict):
                    return "component_not_object"

                comp_type = c.get("type")
                # Allow pluggable component registry via env (comma-separated), in addition to defaults
                import os as _os

                extra = (_os.getenv("AGUI_COMPONENTS_EXTRA") or "").split(",")
                allowed_components = set(AGUI_COMPONENTS) | {s.strip() for s in extra if s.strip()}
                if comp_type not in allowed_components:
                    return f"component_not_allowed:{comp_type}"

                # Validate component actions
                actions = c.get("actions", [])
                for action in actions:
                    action_type = action.get("type")
                    # Support extra actions via env for experimentation (must be a subset of AGUIAction or extra list)
                    extra_actions = [
                        s.strip()
                        for s in (_os.getenv("AGUI_ACTIONS_EXTRA") or "").split(",")
                        if s.strip()
                    ]
                    allowed_actions = [a.value for a in AGUIAction] + extra_actions
                    if action_type and action_type not in allowed_actions:
                        return f"action_not_allowed:{action_type}"

            return None
        except Exception:
            return "validation_exception"

    def _build_agui_prompt(
        self,
        ctx: GenUIContextV2,
        meta: dict[str, str],
        endpoints: list[dict[str, str]],
    ) -> str:
        """Build prompt for AG-UI enhanced UI generation."""
        system = (
            "You are an expert UI/UX developer creating AG-UI compatible interfaces for K os.\n"
            "Return ONLY a strict agui/v1 JSON object. No prose. No markdown fences.\n"
            "Components: Card, Table, List, Tabs, Chart, MessageStream, ContextPanel, ToolPanel, "
            "ConfirmationDialog, InputForm, StateViewer, AgentStatus, ActionButtons.\n"
            "Actions: emitIntent, openComposer, httpPost, navigate, updateState, callTool, confirm, cancel.\n"
            "Focus on real-time agent interactions, bidirectional state sync, and human-in-the-loop patterns.\n"
            "Keep ≤64 components. Mobile-first 12-column grid. Accessibility-first design.\n"
            "NOTE: Responsiveness is handled client-side via CSS breakpoints at 600px (mobile) and 900px (tablet)."
        )

        user = {
            "app": meta,
            "endpoints": endpoints,
            "context": {
                "user": {"role": ctx.user_role, "locale": ctx.locale},
                "agent": {"id": ctx.agent_id, "capabilities": ctx.active_tools},
                "session": {"id": ctx.session_id, "streaming": ctx.streaming_enabled},
                "state": ctx.bidirectional_state,
            },
            "requirements": {
                "streaming": ctx.streaming_enabled,
                "bidirectional": True,
                "human_in_loop": ctx.human_in_loop,
                "context_enrichment": bool(ctx.context_enrichment),
            },
            "task": (
                "Compose an AG-UI dashboard with:\n"
                "1. MessageStream for real-time agent chat\n"
                "2. ContextPanel for state synchronization\n"
                "3. ToolPanel if tools available\n"
                "4. AgentStatus for progress tracking\n"
                "5. Appropriate action buttons for user interactions\n"
                "Use dataBindings for endpoints and actions for AG-UI events."
            ),
            "return": "agui/v1 JSON only",
        }

        return system + "\n\n" + json.dumps(user)

    async def generate_agui(
        self,
        ctx: GenUIContextV2,
        adapter: AGUIProtocolAdapter | None = None,
    ) -> dict[str, Any]:
        """Generate AG-UI enhanced UI descriptor."""
        app = ctx.app.lower().strip()
        view = (ctx.view or "default").lower().strip()

        # Align label names with metrics definition (operation, status)
        try:
            GENUI_REQUESTS.labels(operation="generate", status="started").inc()
        except Exception:
            pass  # Best-effort metrics
        start = time.time()

        try:
            # Check cache first
            cache_key = self._cache_key(app, view)
            if getattr(self, "redis", None) is None:
                # Resolve lazily at first async use
                try:
                    from kagami.core.caching.redis import RedisClientFactory

                    RedisClientFactory.get_client("default")
                except Exception:
                    self.redis = None
            if getattr(self, "redis", None):
                cached = await self.redis.get(cache_key)  # type: ignore  # Union member
                if cached:
                    try:
                        GENUI_CACHE_HITS.labels(operation="generate").inc()
                    except Exception:
                        pass
                    desc = json.loads(cached)

                    # Enhance with real-time context if adapter provided
                    if adapter:
                        desc = await self._enhance_with_context(desc, adapter)

                    return desc  # type: ignore[no-any-return]

            # Get app metadata
            apps = list_apps_v2()
            app_meta = apps.get(app, {})
            if not app_meta:
                # Return minimal AG-UI descriptor
                return self._make_minimal_agui_descriptor(app, ctx)

            # Get app endpoints
            endpoints: list[dict[str, str]] = app_meta.get("endpoints", [])  # type: ignore[assignment]

            # Build prompt
            prompt = self._build_agui_prompt(ctx, app_meta, endpoints)  # type: ignore[arg-type]

            # Generate with LLM - try structured output first, fall back to text
            llm = get_llm_service()
            try:
                from kagami.core.services.llm.service import TaskType as _TaskType
            except Exception:
                _TaskType = None  # type: ignore

            desc: dict[str, Any] | None = None  # type: ignore[no-redef]

            # Try structured output if available (preferred for type safety)
            try:
                structured_result = await llm.generate(
                    prompt=prompt,
                    app_name=app,
                    task_type=_TaskType.CONFIGURATION if _TaskType else None,  # type: ignore[truthy-function]
                    max_tokens=2048,
                    temperature=0.3,
                    structured_output=AGUIDescriptor,
                    routing_hints={"format": "json"},
                )
                if isinstance(structured_result, AGUIDescriptor):
                    desc = structured_result.model_dump()
                    logger.debug("Generated UI via structured output")
            except Exception as e:
                logger.debug(f"Structured output failed, falling back to text: {e}")

            # Fall back to text generation with JSON parsing
            if desc is None:
                text = await llm.generate(
                    prompt=prompt,
                    app_name=app,
                    task_type=_TaskType.CONFIGURATION if _TaskType else None,  # type: ignore[truthy-function]
                    max_tokens=2048,
                    temperature=0.3,
                    routing_hints={"format": "json"},
                )
                try:
                    desc = json.loads(str(text))
                except Exception:
                    # Extract JSON object from text
                    s = str(text)
                    snippet = s[s.find("{") : s.rfind("}") + 1]
                    desc = json.loads(snippet)

            # Validate
            error = self._validate_descriptor_v2(desc)
            if error:
                GENUI_VALIDATE_FAILURES.labels(reason=error).inc()
                return self._make_minimal_agui_descriptor(app, ctx)

            # Cache
            if getattr(self, "redis", None) is None:
                try:
                    from kagami.core.caching.redis import RedisClientFactory

                    RedisClientFactory.get_client("default")
                except Exception:
                    self.redis = None
            if getattr(self, "redis", None):
                await self.redis.setex(  # type: ignore  # Union member
                    cache_key,
                    self.CACHE_TTL_SECONDS,  # seconds
                    json.dumps(desc),
                )

            # Enhance with real-time context if adapter provided
            if adapter:
                desc = await self._enhance_with_context(desc, adapter)

            return desc  # type: ignore[no-any-return]

        finally:
            duration = time.time() - start
            # Align label names with metrics definition (app, path)
            try:
                GENUI_GENERATE_DURATION.labels(operation="generate").observe(duration)
            except Exception:
                pass  # Best-effort metrics

    def _make_minimal_agui_descriptor(
        self,
        app_id: str,
        ctx: GenUIContextV2,
    ) -> dict[str, Any]:
        """Create minimal AG-UI descriptor."""
        return {
            "version": "agui/v1",
            "meta": {
                "appId": app_id,
                "sessionId": ctx.session_id,
                "agentId": ctx.agent_id,
                "generated_at": datetime.now(UTC).isoformat(),
            },
            "layout": {"type": "grid", "columns": 12, "gutter": 8},
            "dataBindings": {},
            "components": [
                # Message stream for agent interaction
                self.component_builder.build_message_stream(
                    messages=[],
                    streaming=ctx.streaming_enabled,
                ),
                # Agent status
                self.component_builder.build_agent_status(
                    agent_id=ctx.agent_id or "default",
                    status="ready",
                ),
                # Basic action buttons
                {
                    "type": "ActionButtons",
                    "grid": {"span": 12},
                    "actions": [
                        {
                            "type": AGUIAction.EMIT_INTENT.value,
                            "label": "Start Task",
                            "icon": "🚀",
                            "style": "primary",
                        },
                        {
                            "type": AGUIAction.OPEN_COMPOSER.value,
                            "label": "Ask Question",
                            "icon": "❓",
                        },
                    ],
                },
            ],
        }

    async def _enhance_with_context(
        self,
        descriptor: dict[str, Any],
        adapter: AGUIProtocolAdapter,
    ) -> dict[str, Any]:
        """Enhance UI descriptor with real-time AG-UI context."""
        # Add context panel if not present
        has_context_panel = any(
            c.get("type") == "ContextPanel" for c in descriptor.get("components", [])
        )

        if not has_context_panel and adapter.context.shared_state:
            context_panel = self.component_builder.build_context_panel(
                user_context=adapter.context.user_context,
                agent_context=adapter.context.agent_context,
                shared_state=adapter.context.shared_state,
            )
            descriptor["components"].append(context_panel)

        # Add tool panel if tools available
        if adapter.context.active_tools:
            has_tool_panel = any(
                c.get("type") == "ToolPanel" for c in descriptor.get("components", [])
            )

            if not has_tool_panel:
                tools = [
                    {"name": tool, "category": "default"} for tool in adapter.context.active_tools
                ]
                tool_panel = self.component_builder.build_tool_panel(tools)
                descriptor["components"].append(tool_panel)

        # Update metadata
        descriptor["meta"]["enhanced_at"] = datetime.now(UTC).isoformat()
        descriptor["meta"]["context_version"] = "agui/v1"

        return descriptor

    async def handle_component_action(
        self,
        component_type: str,
        action: AGUIAction,
        params: dict[str, Any],
        adapter: AGUIProtocolAdapter,
    ) -> dict[str, Any]:
        """Handle an action from an AG-UI component."""
        # Validate action is allowed for component
        allowed_actions = COMPONENT_ACTIONS.get(component_type, [])
        if allowed_actions and action not in allowed_actions:
            raise ValueError(f"Action {action} not allowed for component {component_type}")

        # Process through adapter's action handler
        result = await adapter.action_handler.handle_action(action, params)

        # Update UI if needed based on action result
        if action == AGUIAction.UPDATE_STATE:
            # Trigger UI re-render with new state
            await adapter.update_ui(
                {"stateUpdate": result["result"]},
                merge=True,
            )
        elif action == AGUIAction.CALL_TOOL:
            # Show tool result in UI
            await adapter.send_message(
                AGUIMessage(  # Call sig
                    role="system",
                    content=f"Tool {params.get('tool')} executed",
                    tools=[result["result"]],
                ),
            )

        return result

    async def stream_ui_updates(
        self,
        ctx: GenUIContextV2,
        adapter: AGUIProtocolAdapter,
        update_interval: float = 1.0,
    ) -> None:
        """Stream UI updates based on context changes."""
        last_state_hash = hash(str(adapter.context.shared_state))

        while True:
            await asyncio.sleep(update_interval)

            # Check for state changes
            current_state_hash = hash(str(adapter.context.shared_state))
            if current_state_hash != last_state_hash:
                # State changed, send update
                await adapter.transport.send_event(
                    AGUIEvent(
                        type=AGUIEventType.STATE_UPDATE,
                        session_id=ctx.session_id,
                        agent_id=ctx.agent_id,
                        data={
                            "shared_state": adapter.context.shared_state,
                            "timestamp": datetime.now(UTC).isoformat(),
                        },
                    ),
                )
                last_state_hash = current_state_hash


# Global service instance
genui_service_v2 = GenUIServiceV2()
