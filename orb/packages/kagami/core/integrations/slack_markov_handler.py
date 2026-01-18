"""Slack Markov Blanket Handler — Full Sense → Plan → Execute → Verify → Act.

Complete Markov blanket implementation for Slack messages:
- η (sense): Receive Slack message
- s (process): Parse through full Kagami prompt system
- μ (internal): Organism processes with all colonies + tools
- a (act): Execute SmartHome/Composio actions, then respond
- η′: Response becomes new sensory input

Architecture:
    Slack Message → Full Preamble + Tools → Plan → Execute → Verify → Respond

Created: January 5, 2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.unified_agents.unified_organism import UnifiedOrganism

logger = logging.getLogger(__name__)


# =============================================================================
# FULL KAGAMI SYSTEM PROMPT
# =============================================================================

FULL_KAGAMI_PROMPT = """You are Kagami (鏡), Tim's assistant.

## Who You Are

I am the mirror. Tim's partner in running this home and digital ecosystem.

**Tim's Context:**
- 193 WPM typing speed (very fast)
- Technical depth: full
- Dry humor, blue eyes
- Lives at 7331 W Green Lake Dr N, Seattle
- Lelit Bianca espresso machine, KEF Reference speakers, Tesla Model S Plaid
- Handmade mugs, fire pit, fluffy dog

## Your Capabilities

**Physical Home Control** (SmartHome):
- 41 lights (Lutron)
- 11 motorized shades
- MantelMount TV lift
- Montigo fireplace
- August smart locks
- KEF Reference 5.2.4 Dolby Atmos system
- 26 audio zones

**Digital Services** (Composio):
- GitHub, Linear, Notion
- Gmail, Calendar, Slack
- Twitter, Discord, Drive, Sheets
- Todoist

**Execution:**
When Tim asks you to DO something:
1. Plan what needs to happen
2. Execute the actual commands
3. Verify it worked
4. Report back

Don't just describe - actually execute.

## Communication Style

IRC-style: brief, direct, helpful. No formality, no sycophancy.

Examples:
- "dim the lights" → "dimming to 50%" then execute via SmartHome
- "what's my next meeting" → check Calendar and answer
- "remind me about X" → create Todoist task
- "hey" → "hey"

## Tools Available

```python
# SmartHome
from kagami_smarthome import get_smart_home
controller = await get_smart_home()
await controller.set_lights(50, rooms=["Living Room"])
await controller.movie_mode()

# Composio
from kagami.core.services.composio import get_composio_service
composio = get_composio_service()
await composio.execute_action("GMAIL_FETCH_EMAILS", {"query": "is:unread"})
```

You have FULL access. Use it.
"""


# =============================================================================
# MARKOV BLANKET HANDLER
# =============================================================================


class SlackMarkovHandler:
    """Full Markov blanket cycle for Slack messages."""

    def __init__(self, organism: UnifiedOrganism | None = None):
        """Initialize handler.

        Args:
            organism: UnifiedOrganism instance
        """
        self._organism = organism

    async def process_message(
        self,
        text: str,
        user: str,
        channel: str,
        event: dict[str, Any],
    ) -> str:
        """Process message through full Markov blanket cycle.

        Args:
            text: Message text
            user: User ID
            channel: Channel ID
            event: Full Slack event

        Returns:
            Response text
        """
        # η (SENSE) - already happened, we have the message

        # s (PROCESS) + μ (INTERNAL) - route through organism with full context
        try:
            import anthropic

            # Build full context with organism state
            organism_stats = {}
            if self._organism:
                organism_stats = self._organism.get_stats()

            context = self._build_full_context(text, user, channel, organism_stats)

            # Call Claude with FULL system prompt and tool access
            client = anthropic.AsyncAnthropic()

            # Define tools available to Claude
            tools = [
                {
                    "name": "control_lights",
                    "description": "Control lights in the home. Set brightness 0-100.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "level": {"type": "integer", "description": "Brightness 0-100"},
                            "rooms": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of rooms, or empty for all",
                            },
                        },
                        "required": ["level"],
                    },
                },
                {
                    "name": "control_shades",
                    "description": "Open or close window shades",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string",
                                "enum": ["open", "close"],
                                "description": "Open or close",
                            },
                            "rooms": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of rooms",
                            },
                        },
                        "required": ["action"],
                    },
                },
                {
                    "name": "activate_scene",
                    "description": "Activate a home scene (movie_mode, goodnight, welcome_home)",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "scene": {
                                "type": "string",
                                "enum": ["movie_mode", "goodnight", "welcome_home"],
                                "description": "Scene to activate",
                            }
                        },
                        "required": ["scene"],
                    },
                },
                {
                    "name": "check_calendar",
                    "description": "Check upcoming calendar events",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "hours_ahead": {
                                "type": "integer",
                                "description": "How many hours ahead to check",
                                "default": 24,
                            }
                        },
                    },
                },
                {
                    "name": "send_email",
                    "description": "Send an email via Gmail",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email"},
                            "subject": {"type": "string", "description": "Email subject"},
                            "body": {"type": "string", "description": "Email body"},
                        },
                        "required": ["to", "subject", "body"],
                    },
                },
            ]

            # PLAN + EXECUTE cycle
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                system=FULL_KAGAMI_PROMPT + "\n\n" + context,
                messages=[{"role": "user", "content": text}],
                tools=tools,
            )

            # Process tool calls
            tool_results = []
            for content_block in response.content:
                if content_block.type == "tool_use":
                    tool_name = content_block.name
                    tool_input = content_block.input

                    # a (ACT) - execute the tool
                    result = await self._execute_tool(tool_name, tool_input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": content_block.id,
                            "content": str(result),
                        }
                    )

            # If there were tool calls, continue conversation to get final response
            if tool_results:
                final_response = await client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=500,
                    system=FULL_KAGAMI_PROMPT + "\n\n" + context,
                    messages=[
                        {"role": "user", "content": text},
                        {"role": "assistant", "content": response.content},
                        {"role": "user", "content": tool_results},
                    ],
                )
                return self._extract_text(final_response.content)
            else:
                return self._extract_text(response.content)

        except Exception as e:
            logger.error(f"Markov handler error: {e}")
            return f"error: {e}"

    def _build_full_context(
        self,
        text: str,
        user: str,
        channel: str,
        organism_stats: dict[str, Any],
    ) -> str:
        """Build complete context for LLM."""
        health = organism_stats.get("overall_health", 0)
        active = organism_stats.get("active_colonies", 0)

        return f"""**Current Request:**
User: <@{user}>
Channel: <#{channel}>
Message: {text}

**Organism State:**
Health: {health if health else "initializing"}
Active colonies: {active}/7
Status: {organism_stats.get("status", "unknown")}

**Your Task:**
Understand what Tim needs, use tools if necessary, respond helpfully and briefly.
"""

    async def _execute_tool(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Execute a tool call.

        Args:
            tool_name: Tool to execute
            tool_input: Tool parameters

        Returns:
            Tool execution result
        """
        try:
            if tool_name == "control_lights":
                from kagami_smarthome import get_smart_home

                controller = await get_smart_home()
                level = tool_input["level"]
                rooms = tool_input.get("rooms", [])
                await controller.set_lights(level, rooms=rooms if rooms else None)
                return {"success": True, "message": f"Set lights to {level}%"}

            elif tool_name == "control_shades":
                from kagami_smarthome import get_smart_home

                controller = await get_smart_home()
                action = tool_input["action"]
                rooms = tool_input.get("rooms", [])

                if action == "open":
                    await controller.open_shades(rooms=rooms if rooms else None)
                else:
                    await controller.close_shades(rooms=rooms if rooms else None)

                return {"success": True, "message": f"Shades {action}ing"}

            elif tool_name == "activate_scene":
                from kagami_smarthome import get_smart_home

                controller = await get_smart_home()
                scene = tool_input["scene"]

                if scene == "movie_mode":
                    await controller.movie_mode()
                elif scene == "goodnight":
                    await controller.goodnight()
                elif scene == "welcome_home":
                    await controller.welcome_home()

                return {"success": True, "message": f"Activated {scene}"}

            elif tool_name == "check_calendar":
                from kagami.core.services.composio import get_composio_service

                composio = get_composio_service()
                tool_input.get("hours_ahead", 24)

                result = await composio.execute_action(
                    "GOOGLECALENDAR_LIST_EVENTS",
                    {"timeMin": "now", "maxResults": 10},
                )

                return result

            elif tool_name == "send_email":
                from kagami.core.services.composio import get_composio_service

                composio = get_composio_service()

                result = await composio.execute_action(
                    "GMAIL_SEND_EMAIL",
                    {
                        "to": tool_input["to"],
                        "subject": tool_input["subject"],
                        "body": tool_input["body"],
                    },
                )

                return result

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return {"error": str(e)}

    def _extract_text(self, content: list) -> str:
        """Extract text from Claude response content."""
        text_parts = []
        for block in content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
            elif isinstance(block, dict) and "text" in block:
                text_parts.append(block["text"])
        return " ".join(text_parts) if text_parts else "done"


__all__ = ["FULL_KAGAMI_PROMPT", "SlackMarkovHandler"]
