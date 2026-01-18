"""🪞 Kagami Intent Processor — Natural language → Colony execution E2E.

Routes all natural language through:
1. FanoActionRouter (select best colony based on text)
2. Colony Agent (process the request)
3. SmartHome/Composio (execute effectors)
4. Response generation

NO LOCAL PARSING. Kagami decides.

Created: January 5, 2026
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def process_intent(text: str, source: str = "slack") -> dict[str, Any]:
    """Process natural language intent through full Kagami pipeline.

    Args:
        text: Natural language input from user
        source: Origin of the request (slack, voice, api, etc.)

    Returns:
        Dict with:
        - response: Text response for user
        - colony: Colony that processed it
        - action: Action taken (if any)
        - success: Whether it succeeded
    """
    try:
        # Get the router
        from kagami.core.unified_agents.fano_action_router import get_fano_router

        router = get_fano_router()

        # Determine best colony for this text
        context = {"source": source, "text": text}
        best_colony_idx = router._get_best_colony(text, context)
        colony_name = router.COLONY_NAMES.get(best_colony_idx, "forge")

        logger.info(f"🎯 Routing to {colony_name}: {text[:40]}")

        # Execute based on colony
        result = await _execute_colony_action(colony_name, text, context)

        return {
            "response": result.get("response", "done ✓"),
            "colony": colony_name,
            "action": result.get("action"),
            "success": result.get("success", True),
        }

    except Exception as e:
        logger.error(f"Intent processing failed: {e}")
        return {
            "response": f"err: {e}",
            "colony": None,
            "action": None,
            "success": False,
        }


async def _execute_colony_action(colony: str, text: str, context: dict) -> dict[str, Any]:
    """Execute action through the appropriate colony.

    Routes to:
    - nexus: SmartHome, integrations
    - forge: Build, implement
    - flow: Debug, heal
    - spark: Create, ideate
    - beacon: Plan, organize
    - grove: Research, explore
    - crystal: Verify, test
    """
    text_lower = text.lower()

    # Nexus handles smart home and integrations
    if colony == "nexus" or _is_smarthome_request(text_lower):
        return await _handle_smarthome(text_lower, context)

    # Beacon handles planning and scheduling
    if colony == "beacon" or _is_planning_request(text_lower):
        return await _handle_planning(text, context)

    # Grove handles research
    if colony == "grove" or _is_research_request(text_lower):
        return await _handle_research(text, context)

    # Default: Use LLM for conversation
    return await _handle_conversation(text, context, colony)


def _is_smarthome_request(text: str) -> bool:
    """Check if text is a smart home request."""
    keywords = [
        "light",
        "shade",
        "blind",
        "tv",
        "fireplace",
        "lock",
        "door",
        "movie",
        "goodnight",
        "welcome",
        "dim",
        "bright",
        "turn on",
        "turn off",
        "close",
        "open",
        "lower",
        "raise",
        "set",
    ]
    return any(kw in text for kw in keywords)


def _is_planning_request(text: str) -> bool:
    """Check if text is a planning/calendar request."""
    keywords = ["schedule", "calendar", "meeting", "remind", "todo", "task", "plan"]
    return any(kw in text for kw in keywords)


def _is_research_request(text: str) -> bool:
    """Check if text is a research request."""
    keywords = ["search", "find", "look up", "research", "what is", "who is", "how do"]
    return any(kw in text for kw in keywords)


async def _handle_smarthome(text: str, context: dict) -> dict[str, Any]:
    """Handle smart home requests through kagami_smarthome."""
    try:
        import sys

        sys.path.insert(0, "packages")
        from kagami_smarthome import get_smart_home

        controller = await get_smart_home()

        # Room extraction
        rooms = None
        room_map = {
            "living room": "Living Room",
            "kitchen": "Kitchen",
            "bedroom": "Primary Bed",
            "primary": "Primary Bed",
            "office": "Office",
            "dining": "Dining",
            "bathroom": "Primary Bath",
            "game room": "Game Room",
            "gym": "Gym",
        }
        for pattern, room_name in room_map.items():
            if pattern in text:
                rooms = [room_name]
                break

        # Shades
        if any(x in text for x in ["close shade", "lower shade", "shut shade", "close blind"]):
            await controller.close_shades(rooms=rooms)
            room_str = f" in {rooms[0]}" if rooms else ""
            return {
                "response": f"shades closed{room_str} ✓",
                "action": "close_shades",
                "success": True,
            }

        if any(x in text for x in ["open shade", "raise shade", "open blind"]):
            await controller.open_shades(rooms=rooms)
            room_str = f" in {rooms[0]}" if rooms else ""
            return {
                "response": f"shades open{room_str} ✓",
                "action": "open_shades",
                "success": True,
            }

        # Lights with level
        import re

        light_match = re.search(r"lights?\s*(?:to\s*)?(\d+)%?", text)
        if light_match:
            level = int(light_match.group(1))
            await controller.set_lights(level, rooms=rooms)
            room_str = f" in {rooms[0]}" if rooms else ""
            return {
                "response": f"lights → {level}%{room_str} ✓",
                "action": "set_lights",
                "success": True,
            }

        if any(x in text for x in ["lights on", "turn on light"]):
            await controller.set_lights(100, rooms=rooms)
            room_str = f" in {rooms[0]}" if rooms else ""
            return {"response": f"lights on{room_str} ✓", "action": "set_lights", "success": True}

        if any(x in text for x in ["lights off", "turn off light", "dim"]):
            await controller.set_lights(0, rooms=rooms)
            room_str = f" in {rooms[0]}" if rooms else ""
            return {"response": f"lights off{room_str} ✓", "action": "set_lights", "success": True}

        # TV
        if any(x in text for x in ["lower tv", "tv down"]):
            await controller.lower_tv(1)
            return {"response": "tv lowered ✓", "action": "lower_tv", "success": True}

        if any(x in text for x in ["raise tv", "tv up", "hide tv"]):
            await controller.raise_tv()
            return {"response": "tv raised ✓", "action": "raise_tv", "success": True}

        # Fireplace
        if any(x in text for x in ["fireplace on", "start fire", "light fire"]):
            await controller.fireplace_on()
            return {"response": "🔥 fireplace on ✓", "action": "fireplace_on", "success": True}

        if any(x in text for x in ["fireplace off", "stop fire"]):
            await controller.fireplace_off()
            return {"response": "fireplace off ✓", "action": "fireplace_off", "success": True}

        # Locks
        if any(x in text for x in ["lock door", "lock up", "lock all"]):
            await controller.lock_all()
            return {"response": "🔒 locked ✓", "action": "lock_all", "success": True}

        # Scenes
        if "movie mode" in text:
            await controller.movie_mode()
            return {"response": "🎬 movie mode ✓", "action": "movie_mode", "success": True}

        if "goodnight" in text:
            await controller.goodnight()
            return {"response": "🌙 goodnight ✓", "action": "goodnight", "success": True}

        if "welcome home" in text:
            await controller.welcome_home()
            return {"response": "🏠 welcome home ✓", "action": "welcome_home", "success": True}

        # Status
        if any(x in text for x in ["status", "state", "report"]):
            state = controller.get_organism_state()
            lights_on = sum(1 for k, v in state.items() if "light" in k.lower() and v > 0)
            return {"response": f"lights: {lights_on} on ✓", "action": "status", "success": True}

        # Not recognized as smart home command
        return {"response": None, "action": None, "success": False}

    except Exception as e:
        logger.error(f"SmartHome error: {e}")
        return {"response": f"err: {e}", "action": None, "success": False}


async def _handle_planning(text: str, context: dict) -> dict[str, Any]:
    """Handle planning/calendar requests through Composio."""
    try:
        from kagami.core.services.composio import get_composio_service

        service = get_composio_service()
        await service.initialize()

        # Calendar queries
        if "calendar" in text or "schedule" in text:
            result = await service.execute_action("GOOGLECALENDAR_LIST_EVENTS", {"max_results": 5})
            events = result.get("data", [])
            if events:
                summary = ", ".join(e.get("summary", "?")[:20] for e in events[:3])
                return {"response": f"📅 {summary}", "action": "calendar", "success": True}
            return {"response": "📅 no events", "action": "calendar", "success": True}

        # Tasks
        if "task" in text or "todo" in text:
            result = await service.execute_action("TODOIST_LIST_TASKS", {"limit": 5})
            tasks = result.get("data", [])
            if tasks:
                summary = ", ".join(t.get("content", "?")[:20] for t in tasks[:3])
                return {"response": f"📋 {summary}", "action": "tasks", "success": True}
            return {"response": "📋 no tasks", "action": "tasks", "success": True}

        return {"response": None, "action": None, "success": False}

    except Exception as e:
        logger.error(f"Planning error: {e}")
        return {"response": f"err: {e}", "action": None, "success": False}


async def _handle_research(text: str, context: dict) -> dict[str, Any]:
    """Handle research requests."""
    # For now, fall back to conversation
    return {"response": None, "action": None, "success": False}


async def _handle_conversation(text: str, context: dict, colony: str) -> dict[str, Any]:
    """Handle general conversation through LLM."""
    try:
        import anthropic

        client = anthropic.AsyncAnthropic()

        system = f"""You are Kagami (鏡), Tim's AI assistant.
Currently routed to {colony} colony.

STYLE — IRC culture:
- Brief. 1-2 lines max.
- Lowercase preferred.
- No sycophancy.
- Action over explanation.

If you can execute something, say you're doing it.
If you need clarification, ask briefly."""

        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=100,
            system=system,
            messages=[{"role": "user", "content": text}],
        )

        result = response.content[0].text.strip()
        if result.lower() in ["nothing", "n/a", "", "."]:
            return {"response": None, "action": None, "success": True}

        return {"response": result, "action": "conversation", "success": True}

    except Exception as e:
        logger.error(f"Conversation error: {e}")
        return {"response": f"err: {e}", "action": None, "success": False}


# Singleton for caching router
_router = None


def get_router():
    """Get cached router."""
    global _router
    if _router is None:
        from kagami.core.unified_agents.fano_action_router import get_fano_router

        _router = get_fano_router()
    return _router
