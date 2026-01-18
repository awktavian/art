"""Architect Colony Plugin - Custom colony for system architecture tasks.

This plugin demonstrates creating a custom 8th colony specialized for
architecture and system design work.

Capabilities:
- System architecture design
- Component diagrams
- API design
- Database schema design
- Integration planning

Created: December 28, 2025
"""

from __future__ import annotations

import logging
from typing import Any

from kagami.core.unified_agents.agents.base_colony_agent import (
    AgentResult,
    BaseColonyAgent,
)
from kagami.plugins.base import BasePlugin, HealthCheckResult, PluginMetadata
from kagami.plugins.hooks import HookContext, HookType, get_hook_registry

logger = logging.getLogger(__name__)


class ArchitectColonyAgent(BaseColonyAgent):
    """Custom colony agent for architecture tasks.

    This agent specializes in system design and architecture work.
    It uses catastrophe theory for design decision modeling.
    """

    def __init__(self):
        """Initialize Architect colony agent.

        Note: Custom colonies use index 7 (the 8th colony).
        """
        super().__init__(colony_idx=7, state_dim=256)
        self.catastrophe_type = "custom_hyperbolic"

    def get_system_prompt(self) -> str:
        """Get system prompt for Architect colony."""
        return """You are the Architect colony, specialized in system design and architecture.

Your expertise includes:
- System architecture design and documentation
- Component diagrams and API specifications
- Database schema design and optimization
- Integration patterns and microservice design
- Scalability and performance architecture

Your catastrophe dynamics model design decision points:
- Hyperbolic manifold for exploring multiple design alternatives
- Decision bifurcations at architecture choice points
- Stability analysis for design robustness

When working on architecture tasks:
1. Analyze requirements and constraints
2. Explore multiple design alternatives
3. Evaluate trade-offs (performance, complexity, cost)
4. Document architecture decisions and rationale
5. Provide implementation guidance

Collaborate with other colonies:
- Spark: Initial design brainstorming
- Forge: Implementation of architecture
- Flow: Debugging architectural issues
- Nexus: Integration with existing systems
"""

    def get_available_tools(self) -> list[str]:
        """Get tools available to Architect colony."""
        return [
            "draw_diagram",
            "design_api",
            "design_schema",
            "analyze_architecture",
            "document_decision",
        ]

    def process_with_catastrophe(self, task: str, context: dict[str, Any]) -> AgentResult:
        """Process architecture task using catastrophe dynamics.

        Args:
            task: Architecture task description
            context: Task context

        Returns:
            Agent result with architecture output
        """
        # Simulate architecture work
        logger.info(f"Architect processing: {task}")

        # Extract architecture type from task
        task_lower = task.lower()
        if "api" in task_lower:
            output = self._design_api(task, context)
        elif "schema" in task_lower or "database" in task_lower:
            output = self._design_schema(task, context)
        elif "diagram" in task_lower:
            output = self._create_diagram(task, context)
        else:
            output = self._general_architecture(task, context)

        # Create agent result
        return AgentResult(
            success=True,
            output=output,
            metadata={
                "colony": "architect",
                "catastrophe_type": self.catastrophe_type,
                "tools_used": self.get_available_tools()[:2],
            },
        )

    def _design_api(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        """Design API architecture."""
        return {
            "type": "api_design",
            "task": task,
            "endpoints": [
                {"method": "GET", "path": "/resource", "description": "Get resource"},
                {"method": "POST", "path": "/resource", "description": "Create resource"},
            ],
            "authentication": "JWT",
            "rate_limiting": "100 req/min",
        }

    def _design_schema(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        """Design database schema."""
        return {
            "type": "schema_design",
            "task": task,
            "tables": [
                {
                    "name": "resources",
                    "columns": [
                        {"name": "id", "type": "uuid", "primary_key": True},
                        {"name": "name", "type": "varchar(255)"},
                        {"name": "created_at", "type": "timestamp"},
                    ],
                }
            ],
            "indexes": ["name"],
        }

    def _create_diagram(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        """Create architecture diagram."""
        return {
            "type": "diagram",
            "task": task,
            "components": ["API Gateway", "Service Layer", "Database", "Cache"],
            "connections": [
                {"from": "API Gateway", "to": "Service Layer"},
                {"from": "Service Layer", "to": "Database"},
                {"from": "Service Layer", "to": "Cache"},
            ],
        }

    def _general_architecture(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        """General architecture analysis."""
        return {
            "type": "architecture_analysis",
            "task": task,
            "recommendations": [
                "Use microservices for scalability",
                "Implement caching for performance",
                "Add monitoring and observability",
            ],
        }

    def should_escalate(self, result: AgentResult, context: dict[str, Any]) -> bool:
        """Determine if task should escalate to another colony.

        Args:
            result: Agent result
            context: Task context

        Returns:
            True if escalation needed
        """
        # Escalate to Forge if implementation is needed
        task = context.get("task", "")
        if "implement" in task.lower() or "build" in task.lower():
            result.escalation_target = "forge"
            result.escalation_reason = "Implementation required"
            return True

        return False


class ArchitectColonyPlugin(BasePlugin):
    """Plugin that registers the Architect colony."""

    def __init__(self):
        """Initialize plugin."""
        super().__init__()
        self._agent: ArchitectColonyAgent | None = None
        self._hook_registry = get_hook_registry()

    @classmethod
    def get_metadata(cls) -> PluginMetadata:
        """Get plugin metadata."""
        return PluginMetadata(
            plugin_id="kagami.architect_colony",
            name="Architect Colony",
            version="1.0.0",
            description="Custom colony for system architecture and design",
            author="Kagami Team",
            entry_point="kagami.plugins.examples.custom_colony.plugin:ArchitectColonyPlugin",
            dependencies=[],
            capabilities=["custom_colony", "architecture_design"],
            kagami_version_min="0.1.0",
            kagami_version_max="999.0.0",
            tags=["colony", "architecture", "design"],
        )

    def on_init(self) -> None:
        """Initialize plugin."""
        logger.info("Initializing Architect Colony plugin")

        # Create colony agent
        self._agent = ArchitectColonyAgent()

        # Register colony registration hook
        self._hook_registry.register_hook(
            HookType.COLONY_REGISTRATION,
            self._handle_colony_registration,
            plugin_id=self.get_metadata().plugin_id,
        )

    def on_start(self) -> None:
        """Start plugin."""
        logger.info("Starting Architect Colony")

        # Register with organism
        try:
            from kagami.core.unified_agents.unified_organism import get_unified_organism

            get_unified_organism()

            # Note: This is a simplified example. In a real implementation,
            # you would extend the organism to support dynamic colony registration.
            logger.info("Architect colony ready for architecture tasks")

        except Exception as e:
            logger.error(f"Failed to register Architect colony: {e}")

    def on_stop(self) -> None:
        """Stop plugin."""
        logger.info("Stopping Architect Colony")

    def on_cleanup(self) -> None:
        """Cleanup plugin resources."""
        logger.info("Cleaning up Architect Colony plugin")

        # Unregister hooks
        self._hook_registry.unregister_hook(
            HookType.COLONY_REGISTRATION,
            self.get_metadata().plugin_id,
        )

        self._agent = None

    def health_check(self) -> HealthCheckResult:
        """Check plugin health."""
        if self._agent is None:
            return HealthCheckResult(
                healthy=False,
                status="error",
                details={"error": "Agent not initialized"},
            )

        return HealthCheckResult(
            healthy=True,
            status="ok",
            details={
                "colony_name": "architect",
                "catastrophe_type": "custom_hyperbolic",
                "tools_available": len(self._agent.get_available_tools()),
            },
        )

    def _handle_colony_registration(self, ctx: HookContext) -> HookContext:
        """Handle colony registration hook."""
        logger.debug("Architect colony registration hook called")
        return ctx

    def get_agent(self) -> ArchitectColonyAgent | None:
        """Get the colony agent.

        Returns:
            Architect colony agent instance
        """
        return self._agent


__all__ = ["ArchitectColonyAgent", "ArchitectColonyPlugin"]
