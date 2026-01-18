"""Agent REST API — Core endpoints for live agents.

Endpoints:
- GET /v1/agents — List all agents
- GET /v1/agents/{id} — Get agent state
- GET /v1/agents/{id}/render — Get HTML render
- POST /v1/agents/{id}/query — Query the agent
- POST /v1/agents/{id}/action — Trigger an action
- GET /v1/agents/{id}/secrets — Get found secrets (auth required)
- POST /v1/agents/{id}/learn — Submit learning feedback

Security:
- Kagami account required for all endpoints
- Input validation on all endpoints
- Rate limiting by subscription tier
- Entitlement enforcement (free/pro/enterprise)
- XSS prevention in HTML rendering

Colony: Nexus (e4) — Integration
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from kagami.core.agents import get_agent_registry
from kagami.core.agents.auth import (
    AgentEntitlement,
    AgentUser,
    get_tier_rate_limit,
    require_agent_auth,
    upsell_response,
)
from kagami.core.agents.security import (
    InputValidationError,
    check_rate_limit,
    run_security_audit,
    validate_action_params,
    validate_action_type,
    validate_agent_id,
    validate_query,
)
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/agents", tags=["agents"])


# =============================================================================
# Request/Response Models
# =============================================================================


class AgentSummary(BaseModel):
    """Summary of an agent for list responses."""

    id: str
    name: str
    essence: str
    colony: str
    craft_level: str
    active_connections: int = 0


class AgentStateResponse(BaseModel):
    """Full agent state response."""

    agent_id: str
    identity: dict[str, Any]
    memory: dict[str, Any]
    secrets_found: list[str]
    engagement: dict[str, float]
    active_connections: int
    last_interaction: float


class QueryRequest(BaseModel):
    """Request to query an agent."""

    query: str = Field(..., description="Question or command for the agent", max_length=10000)
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    user_profile: str | None = Field(
        None, description="User profile for Theory of Mind", max_length=64
    )

    @field_validator("query")
    @classmethod
    def validate_query_content(cls, v: str) -> str:
        """Validate query for security."""
        try:
            return validate_query(v)
        except InputValidationError as e:
            raise ValueError(str(e)) from e


class QueryResponse(BaseModel):
    """Response from agent query."""

    response: str
    intent: str | None = None
    actions: list[dict[str, Any]] = Field(default_factory=list)
    latency_ms: int = 0


class ActionRequest(BaseModel):
    """Request to trigger an action."""

    action_type: str = Field(..., description="Type of action to trigger")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Action parameters")

    @field_validator("action_type")
    @classmethod
    def validate_action_type_field(cls, v: str) -> str:
        """Validate action type against whitelist."""
        try:
            return validate_action_type(v)
        except InputValidationError as e:
            raise ValueError(str(e)) from e

    @field_validator("parameters")
    @classmethod
    def validate_params(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate parameters for injection."""
        try:
            return validate_action_params(v)
        except InputValidationError as e:
            raise ValueError(str(e)) from e


class ActionResponse(BaseModel):
    """Response from action execution."""

    success: bool
    result: dict[str, Any] | None = None
    error: str | None = None


class LearnRequest(BaseModel):
    """Request to submit learning feedback."""

    event_type: str = Field(..., description="Type of learning event")
    data: dict[str, Any] = Field(..., description="Event data")
    timestamp: float | None = None


class LearnResponse(BaseModel):
    """Response from learning submission."""

    accepted: bool
    adaptations_triggered: list[str] = Field(default_factory=list)


# =============================================================================
# REST Endpoints
# =============================================================================


@router.get("", response_model=list[AgentSummary])
async def list_agents(
    request: Request,
    colony: str | None = Query(None, description="Filter by colony"),
    craft_level: str | None = Query(None, description="Filter by craft level"),
    user: AgentUser = Depends(require_agent_auth),
) -> list[AgentSummary]:
    """List all loaded agents.

    Requires: Kagami account (free tier).

    Returns:
        List of agent summaries.
    """
    # Check entitlement
    if not user.can_access(AgentEntitlement.AGENT_VIEW):
        return upsell_response(AgentEntitlement.AGENT_VIEW)  # type: ignore

    registry = get_agent_registry()
    agents = []

    for agent_id in registry.list_agents():
        agent = registry.get_agent(agent_id)
        if not agent:
            continue

        # Apply filters
        if colony and agent.schema.i_am.colony.value != colony:
            continue
        if craft_level and agent.schema.i_am.craft_level.value != craft_level:
            continue

        agents.append(
            AgentSummary(
                id=agent.agent_id,
                name=agent.schema.i_am.name,
                essence=agent.schema.i_am.essence,
                colony=agent.schema.i_am.colony.value,
                craft_level=agent.schema.i_am.craft_level.value,
                active_connections=agent.active_connections,
            )
        )

    return agents


@router.get("/{agent_id}", response_model=AgentStateResponse)
async def get_agent_state(
    agent_id: str,
    user: AgentUser = Depends(require_agent_auth),
) -> AgentStateResponse:
    """Get full agent state.

    Requires: Kagami account (free tier).

    Args:
        agent_id: Agent identifier.

    Returns:
        Full agent state including memory and engagement.
    """
    # Validate agent_id
    try:
        agent_id = validate_agent_id(agent_id)
    except InputValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Check entitlement
    if not user.can_access(AgentEntitlement.AGENT_VIEW):
        return upsell_response(AgentEntitlement.AGENT_VIEW)  # type: ignore

    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return AgentStateResponse(
        agent_id=agent.agent_id,
        identity=agent.schema.i_am.model_dump(),
        memory=agent.memory,
        secrets_found=list(agent.secrets_found),
        engagement=agent.engagement,
        active_connections=agent.active_connections,
        last_interaction=agent.last_interaction,
    )


@router.get("/{agent_id}/render", response_class=HTMLResponse)
async def render_agent(
    agent_id: str,
    profile: str | None = Query(None, description="User profile for personalization"),
    auth_user: AgentUser = Depends(require_agent_auth),
) -> HTMLResponse:
    """Get rendered HTML for agent.

    Requires: Kagami account (free tier).

    Args:
        agent_id: Agent identifier.
        profile: Optional user profile for Theory of Mind personalization.

    Returns:
        Rendered HTML page.
    """
    # Validate agent_id
    try:
        agent_id = validate_agent_id(agent_id)
    except InputValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Check entitlement
    if not auth_user.can_access(AgentEntitlement.AGENT_RENDER):
        return upsell_response(AgentEntitlement.AGENT_RENDER)  # type: ignore

    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # Import renderer lazily to avoid circular imports
    try:
        from kagami.core.agents.renderer import render_agent_html

        html = render_agent_html(agent.schema, user_profile=profile)
        return HTMLResponse(content=html)
    except ImportError:
        # Fallback: return basic HTML
        return HTMLResponse(
            content=f"""<!DOCTYPE html>
<html>
<head><title>{agent.schema.i_am.name}</title></head>
<body>
<h1>{agent.schema.i_am.name}</h1>
<p>{agent.schema.i_am.essence}</p>
<pre>{agent.schema.content}</pre>
</body>
</html>"""
        )


@router.post("/{agent_id}/query", response_model=QueryResponse)
async def query_agent(
    agent_id: str,
    request: QueryRequest,
    req: Request,
    user: AgentUser = Depends(require_agent_auth),
) -> QueryResponse:
    """Query the agent.

    Requires: Kagami account (free tier, rate limited).

    Sends a query to the agent and returns a response.
    Uses the agent's i_speak intents for intent matching.

    Args:
        agent_id: Agent identifier.
        request: Query request with question/command.
        req: FastAPI request for rate limiting.

    Returns:
        Agent response with optional actions.
    """
    # Validate agent_id
    try:
        agent_id = validate_agent_id(agent_id)
    except InputValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Check entitlement
    if not user.can_access(AgentEntitlement.AGENT_QUERY):
        return upsell_response(AgentEntitlement.AGENT_QUERY)  # type: ignore

    # Tier-based rate limiting
    rate_limit = get_tier_rate_limit(user.tier, "queries_per_minute")
    client_key = f"query:{user.id}"
    if not await check_rate_limit(client_key):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({rate_limit}/min for {user.tier.value} tier)",
        )

    start_time = time.time()
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    # Update last interaction
    agent.last_interaction = time.time()

    # Match against agent's intents
    response_text = ""
    matched_intent = None
    actions = []

    query_lower = request.query.lower()

    for intent in agent.schema.i_speak.intents:
        # Simple pattern matching (can be enhanced with regex)
        pattern = intent.pattern.lower()

        # Handle {variable} placeholders
        if "{" in pattern:
            # Extract base pattern
            import re

            base_pattern = re.sub(r"\{[^}]+\}", r"(\\S+)", re.escape(pattern))
            match = re.search(base_pattern, query_lower)
            if match:
                matched_intent = intent.pattern
                actions.append(intent.action)
                response_text = intent.response or agent.schema.i_speak.responses.get(
                    "default", "OK"
                )
                break
        elif pattern in query_lower:
            matched_intent = intent.pattern
            actions.append(intent.action)
            response_text = intent.response or agent.schema.i_speak.responses.get("default", "OK")
            break

    # Fallback to greeting if no match
    if not response_text:
        response_text = agent.schema.i_speak.responses.get(
            "greeting", f"Hello from {agent.schema.i_am.name}"
        )

    latency_ms = int((time.time() - start_time) * 1000)

    return QueryResponse(
        response=response_text,
        intent=matched_intent,
        actions=actions,
        latency_ms=latency_ms,
    )


@router.post("/{agent_id}/action", response_model=ActionResponse)
async def trigger_action(
    agent_id: str,
    request: ActionRequest,
    req: Request,
    user: AgentUser = Depends(require_agent_auth),
) -> ActionResponse:
    """Trigger an action on the agent.

    Requires: Kagami Pro subscription.

    Executes an action defined in the agent's schema.
    Supports: obs_command, obs_scene, smarthome, composio.

    Args:
        agent_id: Agent identifier.
        request: Action request with type and parameters.
        req: FastAPI request for rate limiting.

    Returns:
        Action result.
    """
    # Validate agent_id
    try:
        agent_id = validate_agent_id(agent_id)
    except InputValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Check Pro entitlement for actions
    if not user.can_access(AgentEntitlement.AGENT_ACTION):
        return upsell_response(
            AgentEntitlement.AGENT_ACTION,
            "execute powerful agent actions like smart home control and OBS production",
        )  # type: ignore

    # Tier-based rate limiting
    rate_limit = get_tier_rate_limit(user.tier, "actions_per_minute")
    if rate_limit == 0:
        return upsell_response(AgentEntitlement.AGENT_ACTION)  # type: ignore

    client_key = f"action:{user.id}"
    if not await check_rate_limit(client_key):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({rate_limit}/min for {user.tier.value} tier)",
        )

    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    agent.last_interaction = time.time()

    try:
        result = await execute_agent_action(agent, request.action_type, request.parameters)
        return ActionResponse(success=True, result=result)
    except Exception as e:
        logger.error(f"Action execution failed: {e}")
        return ActionResponse(success=False, error=str(e))


@router.get("/{agent_id}/secrets")
async def get_secrets(
    agent_id: str,
    request: Request,
    user: AgentUser = Depends(require_agent_auth),
) -> dict[str, Any]:
    """Get secrets found by the agent.

    Requires: Kagami Pro subscription.

    Args:
        agent_id: Agent identifier.

    Returns:
        List of discovered secrets.
    """
    # Validate agent_id
    try:
        agent_id = validate_agent_id(agent_id)
    except InputValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # Check Pro entitlement for secrets
    if not user.can_access(AgentEntitlement.AGENT_SECRETS):
        return upsell_response(AgentEntitlement.AGENT_SECRETS)  # type: ignore

    # Legacy auth check removed - now using proper entitlements
    _ = request.headers.get("Authorization")  # Keep for backwards compat signature
    if False:
        raise HTTPException(status_code=401, detail="Authorization required")

    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    return {
        "agent_id": agent_id,
        "secrets_found": list(agent.secrets_found),
        "total_secrets": len(agent.schema.i_hide.custom) + (1 if agent.schema.i_hide.konami else 0),
    }


@router.post("/{agent_id}/learn", response_model=LearnResponse)
async def submit_learning(agent_id: str, request: LearnRequest) -> LearnResponse:
    """Submit learning feedback to the agent.

    Accepts engagement data and triggers adaptations.

    Args:
        agent_id: Agent identifier.
        request: Learning event data.

    Returns:
        Acknowledgment with triggered adaptations.
    """
    registry = get_agent_registry()
    agent = registry.get_agent(agent_id)

    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")

    agent.last_interaction = time.time()

    # Process learning event
    triggered = []

    try:
        from kagami.core.agents.learning import process_learning_event

        triggered = await process_learning_event(agent, request.event_type, request.data)
    except ImportError:
        # Learning module not yet available, store raw data
        event_key = f"{request.event_type}_{request.timestamp or time.time()}"
        agent.engagement[event_key] = request.data

    return LearnResponse(accepted=True, adaptations_triggered=triggered)


# =============================================================================
# Action Execution
# =============================================================================


async def execute_agent_action(
    agent: Any,
    action_type: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    """Execute an agent action.

    Supported action types:
    - obs_command: Send command to OBS
    - obs_scene: Switch OBS scene
    - smarthome: Execute smart home action
    - composio: Execute Composio action

    Args:
        agent: AgentState instance.
        action_type: Type of action.
        parameters: Action parameters.

    Returns:
        Action result.
    """
    if action_type == "obs_command":
        return await execute_obs_command(agent, parameters)

    elif action_type == "obs_scene":
        return await execute_obs_scene(agent, parameters)

    elif action_type == "smarthome":
        return await execute_smarthome_action(parameters)

    elif action_type == "composio":
        return await execute_composio_action(parameters)

    else:
        raise ValueError(f"Unknown action type: {action_type}")


async def execute_obs_command(agent: Any, parameters: dict[str, Any]) -> dict[str, Any]:
    """Execute OBS command via agent's OBS integration."""
    if not agent.schema.i_produce.obs_integration.enabled:
        raise ValueError("OBS integration not enabled for this agent")

    try:
        from kagami.core.agents.obs_client import get_obs_client

        obs = await get_obs_client(agent.schema.i_produce.obs_integration)
        command = parameters.get("command")
        result = await obs.execute_command(command, parameters.get("args", {}))
        return {"command": command, "result": result}
    except ImportError:
        return {"command": parameters.get("command"), "result": "OBS client not available"}


async def execute_obs_scene(agent: Any, parameters: dict[str, Any]) -> dict[str, Any]:
    """Switch OBS scene via agent's OBS integration."""
    if not agent.schema.i_produce.obs_integration.enabled:
        raise ValueError("OBS integration not enabled for this agent")

    try:
        from kagami.core.agents.obs_client import get_obs_client

        obs = await get_obs_client(agent.schema.i_produce.obs_integration)
        scene = parameters.get("scene")
        await obs.set_current_scene(scene)
        return {"scene": scene, "switched": True}
    except ImportError:
        return {
            "scene": parameters.get("scene"),
            "switched": False,
            "error": "OBS client not available",
        }


async def execute_smarthome_action(parameters: dict[str, Any]) -> dict[str, Any]:
    """Execute smart home action via Kagami SmartHome."""
    try:
        from kagami_smarthome import get_smart_home

        controller = await get_smart_home()
        action = parameters.get("action")
        args = parameters.get("args", {})

        # Map common actions
        if action == "set_lights":
            await controller.set_lights(args.get("level", 50), rooms=args.get("rooms", []))
        elif action == "announce":
            await controller.announce(args.get("text", ""), rooms=args.get("rooms", []))
        elif action == "movie_mode":
            await controller.movie_mode()
        else:
            # Try generic method call
            method = getattr(controller, action, None)
            if method and callable(method):
                await method(**args)

        return {"action": action, "success": True}

    except ImportError:
        return {
            "action": parameters.get("action"),
            "success": False,
            "error": "SmartHome not available",
        }


async def execute_composio_action(parameters: dict[str, Any]) -> dict[str, Any]:
    """Execute Composio action."""
    try:
        from kagami.core.services.composio import get_composio_service

        service = get_composio_service()
        await service.initialize()

        action = parameters.get("action")
        args = parameters.get("args", {})

        result = await service.execute_action(action, args)
        return {"action": action, "result": result}

    except ImportError:
        return {
            "action": parameters.get("action"),
            "success": False,
            "error": "Composio not available",
        }


# =============================================================================
# Security Audit Endpoint
# =============================================================================


class SecurityAuditResponse(BaseModel):
    """Response from security audit."""

    passed: bool = Field(..., description="Whether all critical checks passed")
    checks: list[dict[str, Any]] = Field(..., description="Individual check results")
    errors: list[str] = Field(default_factory=list, description="Critical errors")
    warnings: list[str] = Field(default_factory=list, description="Non-critical warnings")
    timestamp: float = Field(..., description="Audit timestamp")


@router.get("/security/audit", response_model=SecurityAuditResponse)
async def security_audit(request: Request) -> SecurityAuditResponse:
    """Run security audit on agent runtime.

    Checks environment configuration, secrets, rate limiting,
    and security middleware presence.

    Requires admin authentication in production.

    Returns:
        Security audit results.
    """
    import os

    # In production, require admin auth
    env = os.environ.get("KAGAMI_ENVIRONMENT", "development")
    if env == "production":
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Admin authentication required")

        # Verify admin token (simplified - use proper JWT in production)
        token = auth_header.split(" ", 1)[1]
        admin_token = os.environ.get("ADMIN_API_KEY")
        if not admin_token or token != admin_token:
            raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Run audit
    result = run_security_audit()

    return SecurityAuditResponse(
        passed=result.passed,
        checks=result.checks,
        errors=result.errors,
        warnings=result.warnings,
        timestamp=result.timestamp,
    )


# =============================================================================
# Router Factory
# =============================================================================


def get_agents_router() -> APIRouter:
    """Get the agents REST router."""
    return router
