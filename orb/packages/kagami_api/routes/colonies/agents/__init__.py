"""Colony Agents API - Agent state and management.

Endpoints:
- GET /api/colony/agents/list - List all agents
- GET /api/colony/agents/status - Agent status overview
- GET /api/colony/agents/{agent_id}/state - Individual agent state
"""

from .core import get_router

__all__ = ["get_router"]
