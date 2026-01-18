"""Composio Actuators - Digital Motor Functions

Maps Composio tools (Gmail, GitHub, Calendar, etc.) as digital actuators
in the sensorimotor loop.

Architecture:
  Manifold state → Motor decoder → Tool selection → Composio execution

Tools become "muscles" for digital actions.

Updated December 29, 2025: V3 SDK compatibility, dynamic tool discovery.
"""

import logging
from typing import Any

import torch

logger = logging.getLogger(__name__)


class ComposioActuators:
    """Digital actuators via Composio tools.

    Treats digital tools (email, calendar, search) as motor functions
    that can be predicted and executed through the sensorimotor loop.

    Updated for V3 SDK - dynamically discovers tools from connected accounts.
    """

    def __init__(self) -> None:
        self._initialized = False
        self.available_tools: list[str] = []
        self.tools_by_toolkit: dict[str, list[str]] = {}
        self.tool_usage_count: dict[str, int] = {}
        self.connected_toolkits: list[str] = []
        self.composio: Any = None

    async def initialize(self) -> None:
        """Initialize Composio client and discover tools from connected accounts."""
        if self._initialized:
            return

        try:
            from kagami.core.services.composio import get_composio_service

            self.composio = get_composio_service()
            await self.composio.initialize()

            if not self.composio.initialized:
                logger.warning("Composio service not initialized - digital actuators disabled")
                return

            # Discover connected apps
            connected = await self.composio.get_connected_apps()
            self.connected_toolkits = [
                app["toolkit"] for app in connected if app["status"] == "ACTIVE"
            ]

            # Discover tools for each connected toolkit
            self.available_tools = []
            self.tools_by_toolkit = {}

            for toolkit in self.connected_toolkits:
                tools = await self.composio.get_tools_for_app(toolkit, limit=30)
                toolkit_tools = [t["slug"] for t in tools]
                self.tools_by_toolkit[toolkit] = toolkit_tools
                self.available_tools.extend(toolkit_tools)

            self._initialized = True
            logger.info(
                f"✅ ComposioActuators initialized: {len(self.available_tools)} tools "
                f"from {len(self.connected_toolkits)} apps: {self.connected_toolkits}"
            )

        except Exception as e:
            logger.warning(f"Composio initialization failed: {e}, digital actuators disabled")
            self.available_tools = []

    async def refresh_tools(self) -> None:
        """Refresh available tools from connected accounts."""
        self._initialized = False
        await self.initialize()

    def get_tools_for_toolkit(self, toolkit: str) -> list[str]:
        """Get available tools for a specific toolkit.

        Args:
            toolkit: Toolkit name (e.g., 'github', 'gmail')

        Returns:
            List of tool slugs for that toolkit
        """
        return self.tools_by_toolkit.get(toolkit.lower(), [])

    def map_decoder_output_to_tool(
        self,
        digital_tool_logits: torch.Tensor,  # [B, num_tools] from decoder
    ) -> dict[str, Any]:
        """Map motor decoder output to specific Composio tool.

        Args:
            digital_tool_logits: [B, num_tools] tool selection logits

        Returns:
            Dictionary with selected tool and confidence
        """
        if not self.available_tools:
            return {
                "tool_slug": None,
                "tool_idx": -1,
                "confidence": 0.0,
                "all_probs": [],
                "error": "No tools available - initialize first",
            }

        # Softmax to get probabilities
        probs = torch.softmax(digital_tool_logits, dim=-1)

        # Get top tool
        top_idx = probs.argmax(dim=-1).item()
        confidence = probs[0, top_idx].item()  # type: ignore  # Dynamic index

        # Map to actual tool (if in range)
        if top_idx < len(self.available_tools):
            tool_slug = self.available_tools[top_idx]  # type: ignore  # Dynamic index
        else:
            tool_slug = None

        return {
            "tool_slug": tool_slug,
            "tool_idx": top_idx,
            "confidence": confidence,
            "all_probs": probs[0].tolist()[: len(self.available_tools)],
        }

    async def execute_tool(
        self,
        tool_slug: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a Composio tool.

        Args:
            tool_slug: Tool identifier (e.g., "GMAIL_SEND_EMAIL")
            params: Tool-specific parameters

        Returns:
            Execution result with success status
        """
        await self.initialize()

        if not self.composio or not self.composio.initialized:
            return {
                "success": False,
                "error": "Composio not initialized",
            }

        try:
            result = await self.composio.execute_action(
                action_name=tool_slug,
                params=params,
            )

            # Track usage
            self.tool_usage_count[tool_slug] = self.tool_usage_count.get(tool_slug, 0) + 1

            logger.debug(f"Executed digital actuator: {tool_slug}")

            return result

        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def get_usage_statistics(self) -> dict[str, int]:
        """Get tool usage counts.

        Returns:
            Dictionary mapping tool_slug to usage count
        """
        return self.tool_usage_count.copy()

    def get_status(self) -> dict[str, Any]:
        """Get actuator status summary.

        Returns:
            Status dictionary with initialization state and tool counts
        """
        return {
            "initialized": self._initialized,
            "connected_toolkits": self.connected_toolkits,
            "total_tools": len(self.available_tools),
            "tools_by_toolkit": {k: len(v) for k, v in self.tools_by_toolkit.items()},
            "usage_count": sum(self.tool_usage_count.values()),
        }


# Singleton instance
_composio_actuators: ComposioActuators | None = None


def get_composio_actuators() -> ComposioActuators:
    """Get global Composio actuators instance.

    Returns:
        ComposioActuators singleton
    """
    global _composio_actuators

    if _composio_actuators is None:
        _composio_actuators = ComposioActuators()

    return _composio_actuators


async def initialize_composio_actuators() -> ComposioActuators:
    """Initialize and return the global Composio actuators instance.

    Returns:
        Initialized ComposioActuators singleton
    """
    actuators = get_composio_actuators()
    await actuators.initialize()
    return actuators
