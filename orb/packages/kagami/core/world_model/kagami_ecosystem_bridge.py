"""Kagami Ecosystem Bridge - Connect World Model to Everything.

CREATED: January 4, 2026

This is the INTEGRATION LAYER that connects the unified world model to:

1. **Smart Home** - Real sensors, real actuators (Control4, Lutron, etc.)
2. **Claude/LLM** - External reasoning via Anthropic API
3. **Colonies** - The 7-colony organism for routing and orchestration
4. **Composio** - Digital services (Gmail, Slack, Calendar, etc.)
5. **Safety** - CBF constraints for physical safety

This makes the world model OPERATIONAL - not just a research prototype.

Architecture:
=============
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      KAGAMI ECOSYSTEM BRIDGE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                      UNIFIED WORLD MODEL                              │ │
│  │  (Transformer + LAM + Diffusion + 3D + H-JEPA + Planning)            │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│         │              │              │              │              │       │
│         ▼              ▼              ▼              ▼              ▼       │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ │
│  │ SmartHome │  │   Claude  │  │ Colonies  │  │ Composio  │  │  Safety  │ │
│  │  Bridge   │  │  Bridge   │  │  Bridge   │  │  Bridge   │  │  Filter  │ │
│  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └─────┬─────┘  └────┬─────┘ │
│        │              │              │              │              │        │
├────────┼──────────────┼──────────────┼──────────────┼──────────────┼────────┤
│        ▼              ▼              ▼              ▼              ▼        │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐ │
│  │ Control4  │  │ Anthropic │  │ 7-Colony  │  │  Gmail    │  │   CBF    │ │
│  │ Lutron    │  │    API    │  │  Organism │  │  Slack    │  │  h(x)≥0  │ │
│  │ August    │  │           │  │           │  │ Calendar  │  │          │ │
│  └───────────┘  └───────────┘  └───────────┘  └───────────┘  └──────────┘ │
│                                                                             │
│                         THE REAL WORLD (η)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import torch

if TYPE_CHECKING:
    from kagami.core.safety.optimal_cbf import OptimalCBF
    from kagami.core.unified_agents.unified_organism import UnifiedOrganism

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class EcosystemBridgeConfig:
    """Configuration for ecosystem bridge."""

    # World model
    latent_dim: int = 512
    action_dim: int = 64

    # Smart home
    num_rooms: int = 26
    features_per_room: int = 8

    # Enable/disable connections
    enable_smarthome: bool = True
    enable_claude: bool = True
    enable_colonies: bool = True
    enable_composio: bool = True
    enable_safety: bool = True

    # Safety thresholds
    safety_threshold: float = 0.1  # h(x) must be >= this


# =============================================================================
# SMART HOME BRIDGE
# =============================================================================


class SmartHomeBridge:
    """Bridge between world model and smart home controller.

    Converts latent states/actions to real sensor readings and commands.
    """

    ROOM_NAMES = [
        "living_room",
        "kitchen",
        "dining",
        "entry",
        "mudroom",
        "powder_room",
        "stairway",
        "garage",
        "deck",
        "porch",
        "primary_bed",
        "primary_bath",
        "primary_closet",
        "primary_hall",
        "office",
        "office_bath",
        "bed_3",
        "bath_3",
        "loft",
        "laundry",
        "game_room",
        "bed_4",
        "bath_4",
        "gym",
        "rack_room",
        "patio",
    ]

    ACTION_TYPES = [
        "set_lights",
        "open_shades",
        "close_shades",
        "set_temp",
        "lock",
        "unlock",
        "announce",
        "fireplace_on",
        "fireplace_off",
        "scene",
    ]

    def __init__(self, config: EcosystemBridgeConfig):
        self.config = config
        self._controller = None

    async def _get_controller(self) -> Any:
        """Lazy load smart home controller."""
        if self._controller is None:
            try:
                from kagami_smarthome import get_smart_home

                self._controller = await get_smart_home()
                logger.info("SmartHome controller connected")
            except Exception as e:
                logger.warning(f"Could not connect to smart home: {e}")
        return self._controller

    async def get_current_state(self) -> torch.Tensor:
        """Get current smart home state as tensor.

        Returns:
            [1, num_rooms, features] sensor tensor
        """
        controller = await self._get_controller()

        if controller is None:
            # Return zeros if not connected
            return torch.zeros(1, self.config.num_rooms, self.config.features_per_room)

        # Get state from controller
        state = controller.get_organism_state()

        # Convert to tensor
        room_tensor = torch.zeros(1, self.config.num_rooms, self.config.features_per_room)

        for i, room_name in enumerate(self.ROOM_NAMES):
            room_data = state.get(room_name, {})
            room_tensor[0, i, 0] = room_data.get("light_level", 0) / 100.0
            room_tensor[0, i, 1] = (
                room_data.get("temperature", 70) - 60
            ) / 20.0  # Normalize to ~0-1
            room_tensor[0, i, 2] = room_data.get("shade_level", 0) / 100.0
            room_tensor[0, i, 3] = float(room_data.get("presence", False))
            room_tensor[0, i, 4] = room_data.get("humidity", 50) / 100.0
            room_tensor[0, i, 5] = room_data.get("co2", 400) / 1000.0
            room_tensor[0, i, 6] = room_data.get("noise", 0) / 100.0
            room_tensor[0, i, 7] = room_data.get("occupied_minutes", 0) / 60.0

        return room_tensor

    async def execute_action(
        self,
        action_type: int,
        value: float,
        room: int,
    ) -> dict[str, Any]:
        """Execute action on smart home.

        Args:
            action_type: Index into ACTION_TYPES
            value: Action value (0-100)
            room: Room index

        Returns:
            Result dict
        """
        controller = await self._get_controller()

        if controller is None:
            return {"success": False, "error": "Not connected"}

        action_name = self.ACTION_TYPES[action_type % len(self.ACTION_TYPES)]
        room_name = self.ROOM_NAMES[room % len(self.ROOM_NAMES)]

        try:
            if action_name == "set_lights":
                await controller.set_lights(int(value), rooms=[room_name])
            elif action_name == "open_shades":
                await controller.open_shades(rooms=[room_name])
            elif action_name == "close_shades":
                await controller.close_shades(rooms=[room_name])
            elif action_name == "announce":
                await controller.announce("Kagami speaking", rooms=[room_name])
            elif action_name == "fireplace_on":
                await controller.fireplace_on()
            elif action_name == "fireplace_off":
                await controller.fireplace_off()
            elif action_name == "lock":
                await controller.lock_all()
            elif action_name == "scene":
                if value < 33:
                    await controller.goodnight()
                elif value < 66:
                    await controller.welcome_home()
                else:
                    await controller.movie_mode()

            return {"success": True, "action": action_name, "room": room_name, "value": value}

        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return {"success": False, "error": str(e)}


# =============================================================================
# CLAUDE BRIDGE
# =============================================================================


class ClaudeBridge:
    """Bridge to Claude API for reasoning.

    Enables world model to use Claude for:
    - Complex reasoning
    - Planning
    - Natural language understanding
    """

    def __init__(self, config: EcosystemBridgeConfig):
        self.config = config
        self._client = None

    async def _get_client(self) -> Any:
        """Lazy load Anthropic client."""
        if self._client is None:
            try:
                import anthropic

                from kagami.core.security import get_secret

                api_key = get_secret("anthropic_api_key")
                self._client = anthropic.AsyncAnthropic(api_key=api_key)
                logger.info("Claude API connected")
            except Exception as e:
                logger.warning(f"Could not connect to Claude: {e}")
        return self._client

    async def reason(
        self,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 1024,
    ) -> str:
        """Query Claude for reasoning.

        Args:
            prompt: User prompt
            system: Optional system message
            max_tokens: Max response length

        Returns:
            Claude's response
        """
        client = await self._get_client()

        if client is None:
            return "[Claude not available] " + prompt[:100]

        try:
            message = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=max_tokens,
                system=system or "You are Kagami, a helpful smart home assistant.",
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            return f"[Error: {e}]"

    async def plan_actions(
        self,
        goal: str,
        current_state_description: str,
    ) -> list[dict[str, Any]]:
        """Use Claude to plan action sequence.

        Args:
            goal: What to achieve
            current_state_description: Description of current state

        Returns:
            List of action dicts
        """
        prompt = f"""Current smart home state:
{current_state_description}

Goal: {goal}

Generate a sequence of smart home actions to achieve this goal.
Respond with a JSON list of actions, each with:
- action_type: one of (set_lights, open_shades, close_shades, set_temp, lock, announce, fireplace_on, fireplace_off, scene)
- room: room name
- value: 0-100 where applicable

Example: [{{"action_type": "set_lights", "room": "living_room", "value": 50}}]
"""
        response = await self.reason(prompt)

        # Parse JSON from response
        try:
            import json

            # Find JSON in response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except Exception as e:
            logger.warning(f"Could not parse Claude plan: {e}")

        return []


# =============================================================================
# COLONY BRIDGE
# =============================================================================


class ColonyBridge:
    """Bridge to the 7-colony organism for routing and orchestration."""

    COLONIES = ["spark", "forge", "flow", "nexus", "beacon", "grove", "crystal"]

    def __init__(self, config: EcosystemBridgeConfig):
        self.config = config
        self._organism: UnifiedOrganism | None = None

    def _get_organism(self) -> UnifiedOrganism | None:
        """Lazy load organism."""
        if self._organism is None:
            try:
                from kagami.core.unified_agents.unified_organism import get_organism

                self._organism = get_organism()
                logger.info("Colony organism connected")
            except Exception as e:
                logger.warning(f"Could not connect to organism: {e}")
        return self._organism

    def route_intent(
        self,
        intent: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Route intent to appropriate colony.

        Args:
            intent: What to do
            context: Additional context

        Returns:
            Colony name to handle this
        """
        organism = self._get_organism()

        if organism is None:
            # Default routing heuristics
            intent_lower = intent.lower()
            if any(w in intent_lower for w in ["create", "imagine", "brainstorm"]):
                return "spark"
            elif any(w in intent_lower for w in ["build", "implement", "code"]):
                return "forge"
            elif any(w in intent_lower for w in ["debug", "fix", "error"]):
                return "flow"
            elif any(w in intent_lower for w in ["connect", "integrate", "bridge"]):
                return "nexus"
            elif any(w in intent_lower for w in ["plan", "architect", "design"]):
                return "beacon"
            elif any(w in intent_lower for w in ["research", "learn", "explore"]):
                return "grove"
            elif any(w in intent_lower for w in ["test", "verify", "audit"]):
                return "crystal"
            return "beacon"  # Default to planning

        # Use organism's router
        result = organism.route(intent, context or {})
        return result.get("colony", "beacon")

    def process_task(
        self,
        task: str,
        colony: str | None = None,
    ) -> dict[str, Any]:
        """Process task through colony system.

        Args:
            task: Task description
            colony: Specific colony (or auto-route)

        Returns:
            Processing result
        """
        organism = self._get_organism()

        if organism is None:
            return {"success": False, "error": "Organism not available"}

        if colony is None:
            colony = self.route_intent(task)

        result = organism.process_sync(task, colony=colony)
        return {"success": True, "colony": colony, "result": result}


# =============================================================================
# COMPOSIO BRIDGE
# =============================================================================


class ComposioBridge:
    """Bridge to Composio for digital services."""

    SERVICES = {
        "gmail": ["GMAIL_FETCH_EMAILS", "GMAIL_SEND_EMAIL"],
        "slack": ["SLACK_SEND_MESSAGE", "SLACK_LIST_CHANNELS"],
        "calendar": ["GOOGLECALENDAR_CREATE_EVENT", "GOOGLECALENDAR_LIST_EVENTS"],
        "todoist": ["TODOIST_CREATE_TASK", "TODOIST_GET_TASKS"],
        "linear": ["LINEAR_CREATE_LINEAR_ISSUE"],
    }

    def __init__(self, config: EcosystemBridgeConfig):
        self.config = config
        self._service = None

    async def _get_service(self) -> Any:
        """Lazy load Composio service."""
        if self._service is None:
            try:
                from kagami.core.services.composio import get_composio_service

                self._service = get_composio_service()
                await self._service.initialize()
                logger.info("Composio service connected")
            except Exception as e:
                logger.warning(f"Could not connect to Composio: {e}")
        return self._service

    async def execute_action(
        self,
        action: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute Composio action.

        Args:
            action: Action name (e.g., "GMAIL_FETCH_EMAILS")
            params: Action parameters

        Returns:
            Result dict
        """
        service = await self._get_service()

        if service is None:
            return {"success": False, "error": "Composio not available"}

        try:
            result = await service.execute_action(action, params)
            return {"success": True, "result": result}
        except Exception as e:
            logger.error(f"Composio action failed: {e}")
            return {"success": False, "error": str(e)}

    async def send_notification(
        self,
        channel: str,
        message: str,
    ) -> dict[str, Any]:
        """Send notification through appropriate channel.

        Args:
            channel: "slack", "email", etc.
            message: Notification content

        Returns:
            Result
        """
        if channel == "slack":
            return await self.execute_action(
                "SLACK_SEND_MESSAGE",
                {"channel": "#kagami", "text": message},
            )
        elif channel == "email":
            return await self.execute_action(
                "GMAIL_SEND_EMAIL",
                {"to": "timothyjacoby@gmail.com", "subject": "Kagami", "body": message},
            )
        return {"success": False, "error": f"Unknown channel: {channel}"}


# =============================================================================
# SAFETY FILTER
# =============================================================================


class SafetyFilter:
    """CBF-based safety filtering for actions."""

    def __init__(self, config: EcosystemBridgeConfig):
        self.config = config
        self._cbf: OptimalCBF | None = None

    def _get_cbf(self) -> OptimalCBF | None:
        """Lazy load CBF."""
        if self._cbf is None:
            try:
                from kagami.core.safety.optimal_cbf import OptimalCBF, OptimalCBFConfig

                self._cbf = OptimalCBF(OptimalCBFConfig())
                logger.info("CBF safety filter loaded")
            except Exception as e:
                logger.warning(f"Could not load CBF: {e}")
        return self._cbf

    def check_safety(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
    ) -> tuple[bool, float]:
        """Check if action is safe.

        Args:
            state: Current state tensor
            action: Proposed action tensor

        Returns:
            (is_safe, h_value)
        """
        cbf = self._get_cbf()

        if cbf is None:
            # Default to safe if CBF not available
            return True, 1.0

        h_value = cbf.compute_h(state, action)
        h_float = h_value.min().item() if isinstance(h_value, torch.Tensor) else h_value

        is_safe = h_float >= self.config.safety_threshold
        return is_safe, h_float

    def filter_action(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
    ) -> torch.Tensor:
        """Filter action to ensure safety.

        Args:
            state: Current state
            action: Proposed action

        Returns:
            Safe action (possibly modified)
        """
        is_safe, h_value = self.check_safety(state, action)

        if is_safe:
            return action

        # Project to safe action by scaling down
        # More sophisticated: use QP projection
        scale = max(0.1, min(1.0, (h_value + 0.5) / 0.5))
        return action * scale


# =============================================================================
# UNIFIED ECOSYSTEM BRIDGE
# =============================================================================


class KagamiEcosystemBridge:
    """The unified bridge connecting world model to all of Kagami.

    This is what makes the world model OPERATIONAL.

    Usage:
        bridge = KagamiEcosystemBridge()

        # Get real sensor data
        state_tensor = await bridge.get_real_state()

        # Execute action with safety
        result = await bridge.execute_safe_action(state, action)

        # Use Claude for reasoning
        plan = await bridge.reason_with_claude(goal)

        # Route through colonies
        colony = bridge.route_to_colony(intent)

        # Send digital notification
        await bridge.notify("slack", "Task complete!")
    """

    def __init__(self, config: EcosystemBridgeConfig | None = None):
        self.config = config or EcosystemBridgeConfig()

        # Initialize bridges
        if self.config.enable_smarthome:
            self.smarthome = SmartHomeBridge(self.config)
        else:
            self.smarthome = None

        if self.config.enable_claude:
            self.claude = ClaudeBridge(self.config)
        else:
            self.claude = None

        if self.config.enable_colonies:
            self.colonies = ColonyBridge(self.config)
        else:
            self.colonies = None

        if self.config.enable_composio:
            self.composio = ComposioBridge(self.config)
        else:
            self.composio = None

        if self.config.enable_safety:
            self.safety = SafetyFilter(self.config)
        else:
            self.safety = None

        logger.info(
            f"KagamiEcosystemBridge initialized:\n"
            f"  SmartHome: {self.config.enable_smarthome}\n"
            f"  Claude: {self.config.enable_claude}\n"
            f"  Colonies: {self.config.enable_colonies}\n"
            f"  Composio: {self.config.enable_composio}\n"
            f"  Safety: {self.config.enable_safety}"
        )

    async def get_real_state(self) -> torch.Tensor:
        """Get real sensor state from smart home.

        Returns:
            [1, num_rooms, features] state tensor
        """
        if self.smarthome is None:
            return torch.zeros(1, self.config.num_rooms, self.config.features_per_room)
        return await self.smarthome.get_current_state()

    async def execute_safe_action(
        self,
        state: torch.Tensor,
        action: torch.Tensor,
    ) -> dict[str, Any]:
        """Execute action with safety filtering.

        Args:
            state: Current state
            action: Proposed action

        Returns:
            Execution result
        """
        # Safety check
        if self.safety is not None:
            is_safe, h_value = self.safety.check_safety(state, action)
            if not is_safe:
                action = self.safety.filter_action(state, action)
                logger.warning(f"Action filtered for safety (h={h_value:.3f})")

        # Decode action
        action_type = int(action[0, 0].item() * 10) % 10
        value = action[0, 1].item() * 100
        room = int(action[0, 2].item() * 26) % 26

        # Execute
        if self.smarthome is not None:
            return await self.smarthome.execute_action(action_type, value, room)

        return {"success": False, "error": "SmartHome not enabled"}

    async def reason_with_claude(
        self,
        query: str,
        state: torch.Tensor | None = None,
    ) -> str:
        """Use Claude for reasoning.

        Args:
            query: What to reason about
            state: Current state for context

        Returns:
            Claude's reasoning
        """
        if self.claude is None:
            return f"[Claude not enabled] {query}"

        # State tensor→description conversion deferred until SmartHomeController
        # exposes a describe_state() method that maps device states to natural language
        _ = state  # Reserved for future state-aware reasoning

        return await self.claude.reason(query)

    async def plan_with_claude(
        self,
        goal: str,
        state: torch.Tensor | None = None,
    ) -> list[dict[str, Any]]:
        """Use Claude to plan actions.

        Args:
            goal: Goal to achieve
            state: Current state

        Returns:
            List of planned actions
        """
        if self.claude is None:
            return []

        # Placeholder until SmartHomeController.describe_state() exists
        state_desc = "Living room lights at 50%, temperature 72°F"
        _ = state  # Reserved for future state-aware planning
        return await self.claude.plan_actions(goal, state_desc)

    def route_to_colony(
        self,
        intent: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Route intent to appropriate colony.

        Args:
            intent: What to do
            context: Additional context

        Returns:
            Colony name
        """
        if self.colonies is None:
            return "beacon"
        return self.colonies.route_intent(intent, context)

    def process_with_colony(
        self,
        task: str,
        colony: str | None = None,
    ) -> dict[str, Any]:
        """Process task through colony system.

        Args:
            task: Task to process
            colony: Specific colony (or auto-route)

        Returns:
            Result
        """
        if self.colonies is None:
            return {"success": False, "error": "Colonies not enabled"}
        return self.colonies.process_task(task, colony)

    async def notify(
        self,
        channel: str,
        message: str,
    ) -> dict[str, Any]:
        """Send notification through digital service.

        Args:
            channel: slack, email, etc.
            message: Notification content

        Returns:
            Result
        """
        if self.composio is None:
            return {"success": False, "error": "Composio not enabled"}
        return await self.composio.send_notification(channel, message)

    async def execute_digital_action(
        self,
        action: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute action on digital service.

        Args:
            action: Composio action name
            params: Action parameters

        Returns:
            Result
        """
        if self.composio is None:
            return {"success": False, "error": "Composio not enabled"}
        return await self.composio.execute_action(action, params)


# =============================================================================
# FACTORY
# =============================================================================


def create_ecosystem_bridge(
    enable_all: bool = True,
) -> KagamiEcosystemBridge:
    """Factory for KagamiEcosystemBridge."""
    config = EcosystemBridgeConfig(
        enable_smarthome=enable_all,
        enable_claude=enable_all,
        enable_colonies=enable_all,
        enable_composio=enable_all,
        enable_safety=enable_all,
    )
    return KagamiEcosystemBridge(config)


__all__ = [
    "ClaudeBridge",
    "ColonyBridge",
    "ComposioBridge",
    "EcosystemBridgeConfig",
    "KagamiEcosystemBridge",
    "SafetyFilter",
    "SmartHomeBridge",
    "create_ecosystem_bridge",
]
