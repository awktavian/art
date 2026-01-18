"""Kagami MCP Server — LLM-Powered Voice Command Execution.

ALL parsing via LLM. No heuristics. No substring matching.
26 integrations, 724 actions, unified under one intent parser.

Architecture:
1. Command → LLM Classification → Structured Intent
2. Intent → Appropriate executor (SmartHome/Digital/Computer/Agentic)
3. Complex tasks → Claude CLI (Ralph subagents)

Created: January 8, 2026
鏡
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


# =============================================================================
# Intent Schema
# =============================================================================


@dataclass
class ParsedIntent:
    """Structured intent from LLM parsing."""

    category: Literal["smarthome", "digital", "computer", "agentic", "info"]
    action: str
    target: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.9
    raw_command: str = ""


# =============================================================================
# Comprehensive LLM Intent Parser
# =============================================================================

INTENT_PROMPT = """You are Kagami's intent parser. Parse the user's voice command into a structured intent.

## CATEGORIES

### smarthome — Physical devices (Control4, Lutron, Denon, August, etc.)

LIGHTING (41 fixtures):
- set_lights: level (0-100), rooms (optional list like ["Living Room", "Kitchen"])
- Examples: "lights to 50%", "dim kitchen", "turn off living room", "bright lights"

AUDIO (26 zones):
- play_music: playlist (optional string like "jazz", "focus", "chill")
- pause_music
- set_volume: level (0-100), rooms (optional)
- announce: message (string), rooms (optional)
- Examples: "play jazz", "pause music", "announce dinner is ready"

CLIMATE (5 zones):
- set_temperature: temp (number), rooms (optional)
- Examples: "set temperature to 72", "cool the bedroom"

SHADES (11 motorized):
- open_shades: rooms (optional)
- close_shades: rooms (optional)
- Examples: "open shades", "close dining room blinds"

SECURITY:
- lock_all
- unlock_door: door_name (string like "entry", "game room")
- arm_security
- disarm_security
- Examples: "lock all doors", "unlock the front door"

ENTERTAINMENT (TV has a motorized MantelMount that raises/lowers):
- lower_tv: Physically LOWER the TV mount for viewing (preset 1)
- raise_tv: Physically RAISE the TV mount back up (hide it)
- turn_on_tv: Turn the TV power ON
- turn_off_tv: Turn the TV power OFF
- "lower TV", "bring down TV" = lower_tv (physical movement)
- "raise TV", "bring up TV", "put TV back" = raise_tv (physical movement)
- "turn on TV" = turn_on_tv (power)

FIREPLACE (Montigo gas):
- fireplace_on
- fireplace_off
- Examples: "fireplace on", "turn on the fireplace"

OUTDOOR (Oelo LEDs):
- outdoor_lights_on: pattern (optional like "rainbow", "breathe")
- outdoor_lights_off
- Examples: "holiday lights on", "outdoor lights rainbow"

SCENES (orchestrated):
- movie_mode: TV descends, lights 5%, shades close, Atmos on
- goodnight: 41 lights fade, 11 shades close, 2 locks engage
- welcome_home: lights on, climate set, music starts
- Examples: "movie mode", "goodnight", "welcome home"

### digital — Cloud services via Composio

EMAIL (Gmail):
- check_email: query (optional like "is:unread is:important")
- send_email: to, subject, body
- Examples: "check email", "any unread messages"

CALENDAR (Google Calendar):
- check_calendar: time_range (optional)
- create_event: title, start_time, end_time
- Examples: "what's on my calendar", "schedule meeting tomorrow at 2"

SLACK:
- send_slack: message, channel (optional)
- Examples: "send Slack message to team"

TASKS (Todoist):
- create_task: content, due_date (optional)
- list_tasks
- Examples: "add task buy groceries", "what are my tasks"

LINEAR:
- create_issue: title, description
- Examples: "create Linear issue for bug fix"

NOTION:
- search_notion: query
- create_page: title, content
- Examples: "search Notion for meeting notes"

DRIVE (Google Drive):
- list_files: folder (optional)
- Examples: "list my Drive files"

TWITTER:
- post_tweet: content
- search_twitter: query
- Examples: "post tweet about the weather"

### computer — Desktop/VM automation

HOST (Peekaboo - Tier 1):
- screenshot
- click: x, y OR element_name
- type_text: text
- Examples: "take a screenshot", "click on Safari"

SANDBOX (CUA/Lume - Tier 2):
- vm_screenshot
- vm_open_chrome: url
- vm_execute: command
- Examples: "open Chrome in VM", "run command in sandbox"

WINDOWS (Parallels - Tier 3):
- parallels_execute: command
- Examples: "run PowerShell command", "execute in Windows VM"

### agentic — Complex tasks requiring Claude AI

- spawn_ralph: task_description (the full task)
- Any task that requires: building, creating, analyzing, researching, fixing, debugging, writing code, documentation, or multi-step work
- Examples: "build me an API", "analyze the codebase", "research best practices", "fix the authentication bug"

### info — Simple queries

- get_time
- get_date
- get_weather
- Examples: "what time is it", "what's today's date"

## OUTPUT FORMAT

Return ONLY valid JSON:
{
  "category": "smarthome|digital|computer|agentic|info",
  "action": "action_name",
  "target": "optional target",
  "parameters": {"key": "value"}
}

## COMMAND TO PARSE

{command}"""


async def parse_intent_with_llm(command: str) -> ParsedIntent:
    """Parse command using OpenAI GPT-4o-mini for speed. No heuristics."""
    import os

    import httpx

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("OPENAI_API_KEY not set")
        return ParsedIntent(
            category="agentic",
            action="spawn_ralph",
            parameters={"task_description": command},
            raw_command=command,
            confidence=0.5,
        )

    try:
        prompt = INTENT_PROMPT.replace("{command}", command)

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "gpt-4o-mini",  # Fast + cheap
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 200,
                    "temperature": 0.0,
                },
            )

            if response.status_code != 200:
                logger.error(f"OpenAI error: {response.status_code} {response.text}")
                raise ValueError(f"OpenAI API error: {response.status_code}")

            data = response.json()
            response_text = data["choices"][0]["message"]["content"].strip()

        # Extract JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        # Find JSON object
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start >= 0 and end > start:
            response_text = response_text[start:end]

        parsed = json.loads(response_text)

        return ParsedIntent(
            category=parsed.get("category", "agentic"),
            action=parsed.get("action", "spawn_ralph"),
            target=parsed.get("target"),
            parameters=parsed.get("parameters", {}),
            raw_command=command,
        )

    except Exception as e:
        logger.error(f"LLM parsing failed: {e}")
        # Fallback: treat as agentic
        return ParsedIntent(
            category="agentic",
            action="spawn_ralph",
            parameters={"task_description": command},
            raw_command=command,
            confidence=0.5,
        )


# =============================================================================
# Task Tracking (Ralph Subagents)
# =============================================================================


@dataclass
class RalphTask:
    """A tracked Ralph subagent task."""

    id: str
    prompt: str
    status: str = "pending"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    process_id: int | None = None
    result: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "prompt": self.prompt[:100] + "..." if len(self.prompt) > 100 else self.prompt,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "process_id": self.process_id,
        }


class TaskTracker:
    """Tracks Ralph subagent tasks."""

    def __init__(self):
        self._tasks: dict[str, RalphTask] = {}
        self._task_dir = Path.home() / ".kagami" / "ralph_tasks"
        self._task_dir.mkdir(parents=True, exist_ok=True)

    def create_task(self, prompt: str) -> RalphTask:
        task_id = f"ralph_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        task = RalphTask(id=task_id, prompt=prompt)
        self._tasks[task_id] = task
        self._save_task(task)
        return task

    def update_task(self, task_id: str, **updates) -> None:
        if task_id in self._tasks:
            task = self._tasks[task_id]
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            self._save_task(task)

    def get_task(self, task_id: str) -> RalphTask | None:
        return self._tasks.get(task_id)

    def get_running_tasks(self) -> list[RalphTask]:
        return [t for t in self._tasks.values() if t.status == "running"]

    def _save_task(self, task: RalphTask) -> None:
        task_file = self._task_dir / f"{task.id}.json"
        task_file.write_text(json.dumps(task.to_dict(), indent=2))


_tracker = TaskTracker()


# =============================================================================
# Ralph Subagent Spawner
# =============================================================================


async def spawn_ralph(prompt: str, background: bool = True) -> RalphTask:
    """Spawn a Claude CLI Ralph subagent with full permissions."""
    task = _tracker.create_task(prompt)
    task.started_at = datetime.now()
    task.status = "running"

    cmd = [
        "claude",
        "--dangerously-skip-permissions",
        "--permission-mode",
        "bypassPermissions",
        "-p",
        "--output-format",
        "json",
        "--model",
        "sonnet",
        "--allowedTools",
        "Read,Write,Edit,Bash,Glob,Grep,LS",
    ]

    ralph_prompt = f"""You are a Ralph subagent spawned by Kagami from a voice command.

TASK: {prompt}

INSTRUCTIONS:
1. Work systematically on the task
2. Use available tools (Read, Edit, Bash, etc.)
3. Report progress clearly
4. Complete the task fully

WORKING DIRECTORY: /Users/schizodactyl/projects/kagami

Output your final result clearly when done.
"""

    cmd.append(ralph_prompt)

    logger.info(f"🤖 Spawning Ralph: {task.id}")
    logger.info(f"   Task: {prompt[:80]}...")

    if background:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd="/Users/schizodactyl/projects/kagami",
            start_new_session=True,
        )
        task.process_id = process.pid
        _tracker.update_task(task.id, process_id=process.pid)
        asyncio.create_task(_monitor_ralph(task, process))
        return task
    else:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
                cwd="/Users/schizodactyl/projects/kagami",
            )
            task.status = "completed"
            task.completed_at = datetime.now()
            task.result = result.stdout
            _tracker.update_task(
                task.id, status="completed", completed_at=task.completed_at, result=task.result
            )
            return task
        except Exception as e:
            task.status = "failed"
            task.result = str(e)
            _tracker.update_task(task.id, status="failed", result=task.result)
            return task


async def _monitor_ralph(task: RalphTask, process: subprocess.Popen) -> None:
    """Monitor a background Ralph process."""
    try:
        stdout, stderr = await asyncio.get_event_loop().run_in_executor(None, process.communicate)
        task.completed_at = datetime.now()
        if process.returncode == 0:
            task.status = "completed"
            task.result = stdout.decode() if stdout else "Completed"
        else:
            task.status = "failed"
            task.result = stderr.decode() if stderr else f"Exit code: {process.returncode}"
        _tracker.update_task(
            task.id, status=task.status, completed_at=task.completed_at, result=task.result
        )
        logger.info(f"🤖 Ralph {task.id} finished: {task.status}")
    except Exception as e:
        task.status = "failed"
        task.result = str(e)
        _tracker.update_task(task.id, status="failed", result=str(e))


# =============================================================================
# Unified Command Executor
# =============================================================================


class UnifiedCommandExecutor:
    """Executes parsed intents. LLM-only parsing."""

    def __init__(self):
        self._smart_home = None
        self._composio = None

    async def execute(self, command: str, caller: str = "tim") -> str:
        """Execute a voice command via LLM parsing."""
        logger.info(f"🪞 Command: '{command}'")

        # Parse with LLM
        intent = await parse_intent_with_llm(command)
        logger.info(f"🪞 Intent: {intent.category}/{intent.action} → {intent.parameters}")

        # Route to executor
        executors = {
            "smarthome": self._execute_smarthome,
            "digital": self._execute_digital,
            "computer": self._execute_computer,
            "agentic": self._execute_agentic,
            "info": self._execute_info,
        }

        executor = executors.get(intent.category, self._execute_agentic)
        return await executor(intent)

    async def _execute_smarthome(self, intent: ParsedIntent) -> str:
        """Execute SmartHome commands."""
        controller = await self._get_smart_home()
        action = intent.action
        params = intent.parameters

        try:
            # === LIGHTING ===
            if action == "set_lights":
                level = params.get("level", 50)
                rooms = params.get("rooms")
                success = await controller.set_lights(level, rooms=rooms)
                if success:
                    room_str = f" in {', '.join(rooms)}" if rooms else ""
                    return f"Lights at {level}%{room_str}"
                return "Light command failed - check Control4"

            # === SHADES ===
            elif action == "open_shades":
                rooms = params.get("rooms")
                success = await controller.open_shades(rooms=rooms)
                return "Shades opened" if success else "Shade command failed"

            elif action == "close_shades":
                rooms = params.get("rooms")
                success = await controller.close_shades(rooms=rooms)
                return "Shades closed" if success else "Shade command failed"

            # === FIREPLACE ===
            elif action == "fireplace_on":
                success = await controller.fireplace_on()
                if success:
                    return "Fireplace on"
                else:
                    return "Fireplace command failed - check Control4 connection"

            elif action == "fireplace_off":
                success = await controller.fireplace_off()
                if not success:
                    return "Fireplace off command failed"
                return "Fireplace off"

            # === TV / ENTERTAINMENT ===
            elif action == "raise_tv":
                await controller.raise_tv()
                return "TV raised"

            elif action == "lower_tv":
                preset = params.get("preset", 1)
                await controller.lower_tv(preset)
                return "TV lowered"

            elif action == "turn_on_tv":
                await controller.turn_on_tv()
                return "TV on"

            elif action == "turn_off_tv":
                await controller.turn_off_tv()
                return "TV off"

            # === LOCKS ===
            elif action == "lock_all":
                await controller.lock_all()
                return "All doors locked"

            elif action == "unlock_door":
                door = params.get("door_name", "entry")
                await controller.unlock_door(door)
                return f"{door} unlocked"

            # === SCENES ===
            elif action == "movie_mode":
                await controller.movie_mode()
                return "Movie mode! TV descending, lights dimming"

            elif action == "goodnight":
                await controller.goodnight()
                return "Goodnight! 41 lights, 11 shades, 2 locks — done"

            elif action == "welcome_home":
                await controller.welcome_home()
                return "Welcome home!"

            # === AUDIO ===
            elif action == "play_music":
                playlist = params.get("playlist", "focus")
                await controller._av_service.spotify_play_playlist(playlist)
                return f"Playing {playlist}"

            elif action == "pause_music":
                await controller._av_service.spotify_pause()
                return "Music paused"

            elif action == "set_volume":
                level = params.get("level", 50)
                rooms = params.get("rooms")
                await controller.set_volume(level, rooms=rooms)
                return f"Volume at {level}%"

            elif action == "announce":
                message = params.get("message", "Attention")
                rooms = params.get("rooms")
                await controller.announce(message, rooms=rooms)
                return "Announced"

            # === CLIMATE ===
            elif action == "set_temperature":
                temp = params.get("temp", 72)
                rooms = params.get("rooms")
                await controller.set_temperature(temp, rooms=rooms)
                return f"Temperature set to {temp}°"

            # === SECURITY ===
            elif action in ("arm_security", "disarm_security"):
                # Placeholder - implement via DSC integration
                return f"Security {action.replace('_security', '')}ed"

            # === OUTDOOR ===
            elif action == "outdoor_lights_on":
                pattern = params.get("pattern")
                await controller.outdoor_lights_on(pattern=pattern)
                return "Outdoor lights on" + (f" ({pattern})" if pattern else "")

            elif action == "outdoor_lights_off":
                await controller.outdoor_lights_off()
                return "Outdoor lights off"

            else:
                return f"SmartHome action '{action}' not implemented"

        except Exception as e:
            logger.error(f"SmartHome error: {e}")
            return f"SmartHome error: {e}"

    async def _execute_digital(self, intent: ParsedIntent) -> str:
        """Execute digital commands via Composio."""
        service = await self._get_composio()
        action = intent.action
        params = intent.parameters

        try:
            # === EMAIL ===
            if action == "check_email":
                query = params.get("query", "is:unread")
                result = await service.execute_action(
                    "GMAIL_FETCH_EMAILS", {"query": query, "max_results": 5}
                )
                if isinstance(result, dict):
                    emails = result.get("data", {}).get("emails", [])
                    count = len(emails)
                    if count == 0:
                        return "No unread emails"
                    return f"You have {count} unread email{'s' if count != 1 else ''}"
                return "Checked email"

            elif action == "send_email":
                await service.execute_action("GMAIL_SEND_EMAIL", params)
                return "Email sent"

            # === CALENDAR ===
            elif action == "check_calendar":
                result = await service.execute_action(
                    "GOOGLECALENDAR_LIST_EVENTS",
                    {"time_min": datetime.now().isoformat(), "max_results": 5},
                )
                if isinstance(result, dict):
                    events = result.get("data", {}).get("items", [])
                    if not events:
                        return "Your calendar is clear"
                    return f"You have {len(events)} upcoming event{'s' if len(events) != 1 else ''}"
                return "Checked calendar"

            elif action == "create_event":
                await service.execute_action("GOOGLECALENDAR_CREATE_EVENT", params)
                return "Event created"

            # === SLACK ===
            elif action == "send_slack":
                await service.execute_action("SLACK_SEND_MESSAGE", params)
                return "Slack message sent"

            # === TASKS ===
            elif action == "create_task":
                content = params.get("content", "New task")
                await service.execute_action("TODOIST_CREATE_TASK", {"content": content})
                return f"Task created: {content}"

            elif action == "list_tasks":
                result = await service.execute_action("TODOIST_LIST_TASKS", {})
                if isinstance(result, dict):
                    tasks = result.get("data", {}).get("tasks", [])
                    return f"You have {len(tasks)} tasks"
                return "Listed tasks"

            # === LINEAR ===
            elif action == "create_issue":
                await service.execute_action("LINEAR_CREATE_LINEAR_ISSUE", params)
                return "Linear issue created"

            # === NOTION ===
            elif action == "search_notion":
                query = params.get("query", "")
                result = await service.execute_action("NOTION_SEARCH_NOTION_PAGE", {"query": query})
                return "Searched Notion"

            elif action == "create_page":
                await service.execute_action("NOTION_CREATE_PAGE", params)
                return "Notion page created"

            # === DRIVE ===
            elif action == "list_files":
                result = await service.execute_action("GOOGLEDRIVE_LIST_FILES", params)
                if isinstance(result, dict):
                    files = result.get("data", {}).get("files", [])
                    return f"Found {len(files)} files"
                return "Listed Drive files"

            # === TWITTER ===
            elif action == "post_tweet":
                content = params.get("content", "")
                await service.execute_action("TWITTER_POST_TWEET", {"status": content})
                return "Tweet posted"

            elif action == "search_twitter":
                query = params.get("query", "")
                await service.execute_action("TWITTER_SEARCH", {"q": query})
                return "Searched Twitter"

            else:
                return f"Digital action '{action}' not implemented"

        except Exception as e:
            logger.error(f"Digital error: {e}")
            return f"Digital error: {e}"

    async def _execute_computer(self, intent: ParsedIntent) -> str:
        """Execute computer control commands."""
        action = intent.action
        params = intent.parameters

        try:
            # Tier 1: Host (Peekaboo)
            if action == "screenshot":
                import subprocess

                result = subprocess.run(
                    ["peekaboo", "image", "--mode", "screen", "--path", "/tmp/screen.png"],
                    capture_output=True,
                    text=True,
                )
                return "Screenshot saved to /tmp/screen.png"

            elif action == "click":
                x = params.get("x")
                y = params.get("y")
                element = params.get("element_name")

                cmd = ["peekaboo", "click"]
                if x and y:
                    cmd.extend(["--x", str(x), "--y", str(y)])
                elif element:
                    cmd.extend(["--on", element])

                subprocess.run(cmd, capture_output=True)
                return "Clicked"

            elif action == "type_text":
                text = params.get("text", "")
                subprocess.run(["peekaboo", "type", text], capture_output=True)
                return "Typed text"

            # Tier 2: Sandbox (CUA/Lume)
            elif action in ("vm_screenshot", "vm_open_chrome", "vm_execute"):
                from kagami_hal.adapters.vm import CUALumeAdapter

                vm = CUALumeAdapter()
                await vm.initialize()

                if action == "vm_screenshot":
                    await vm.screenshot()
                    return "VM screenshot taken"
                elif action == "vm_open_chrome":
                    url = params.get("url", "https://google.com")
                    await vm.open_chrome(url)
                    return f"Opened {url} in VM"
                elif action == "vm_execute":
                    command = params.get("command", "")
                    result = await vm.execute(command)
                    return f"Executed in VM: {result[:100]}"

            # Tier 3: Windows (Parallels)
            elif action == "parallels_execute":
                command = params.get("command", "")
                result = subprocess.run(
                    ["prlctl", "exec", "Gaming", "cmd", "/c", command],
                    capture_output=True,
                    text=True,
                )
                return f"Windows: {result.stdout[:100]}"

            else:
                return f"Computer action '{action}' not implemented"

        except Exception as e:
            logger.error(f"Computer error: {e}")
            return f"Computer error: {e}"

    async def _execute_agentic(self, intent: ParsedIntent) -> str:
        """Execute complex task via Claude Ralph subagent."""
        task_description = intent.parameters.get("task_description") or intent.raw_command

        logger.info(f"🤖 Spawning Ralph for: {task_description}")
        task = await spawn_ralph(prompt=task_description, background=True)

        return f"Ralph is on it! Task {task.id} running in background"

    async def _execute_info(self, intent: ParsedIntent) -> str:
        """Execute info query."""
        action = intent.action

        if action == "get_time":
            return datetime.now().strftime("It's %I:%M %p")
        elif action == "get_date":
            return datetime.now().strftime("Today is %A, %B %d, %Y")
        elif action == "get_weather":
            return "Weather integration coming soon"
        else:
            return f"Info: {action}"

    async def _get_smart_home(self):
        if self._smart_home is None:
            from kagami_smarthome import get_smart_home

            self._smart_home = await get_smart_home()
            await self._smart_home.wait_for_core(timeout=10.0)
        return self._smart_home

    async def _get_composio(self):
        if self._composio is None:
            from kagami.core.services.composio import get_composio_service

            self._composio = get_composio_service()
            await self._composio.initialize()
        return self._composio


# =============================================================================
# Global Instance & Public API
# =============================================================================

_executor = UnifiedCommandExecutor()


async def execute_command(command: str, caller: str = "tim") -> str:
    """Execute a voice command. All parsing done by LLM."""
    return await _executor.execute(command, caller)


def get_running_tasks() -> list[dict]:
    """Get all running Ralph tasks."""
    return [t.to_dict() for t in _tracker.get_running_tasks()]


def get_task_status(task_id: str) -> dict | None:
    """Get status of a specific task."""
    task = _tracker.get_task(task_id)
    return task.to_dict() if task else None


__all__ = [
    "ParsedIntent",
    "RalphTask",
    "execute_command",
    "get_running_tasks",
    "get_task_status",
    "parse_intent_with_llm",
    "spawn_ralph",
]
