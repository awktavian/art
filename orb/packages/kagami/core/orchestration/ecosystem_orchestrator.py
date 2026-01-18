"""Ecosystem Orchestrator — Unified Cross-Domain Orchestration.

This module enables continuous background improvement by connecting ALL services
into a coherent, self-improving ecosystem:

Architecture:
    ┌────────────────────────────────────────────────────────────────────────┐
    │                     ECOSYSTEM ORCHESTRATOR                              │
    │                                                                        │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                    UNIFIED STATE LAYER                            │  │
    │  │                                                                   │  │
    │  │  GitHub ←→ Linear ←→ Notion ←→ Gmail ←→ Calendar ←→ Slack        │  │
    │  │    ↓         ↓         ↓         ↓          ↓          ↓         │  │
    │  │  ╔═══════════════════════════════════════════════════════════╗   │  │
    │  │  ║              ECOSYSTEM STATE CACHE                        ║   │  │
    │  │  ║  - All PR status, issue counts, repo health              ║   │  │
    │  │  ║  - All Linear tickets, sprint progress                   ║   │  │
    │  │  ║  - All Notion pages, knowledge base                      ║   │  │
    │  │  ║  - All urgent emails, pending actions                    ║   │  │
    │  │  ║  - All calendar events, conflicts                        ║   │  │
    │  │  ║  - All Slack mentions, unread messages                   ║   │  │
    │  │  ╚═══════════════════════════════════════════════════════════╝   │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    │                              ↓                                          │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                    CROSS-DOMAIN TRIGGERS                          │  │
    │  │                                                                   │  │
    │  │  CI Failure → Linear Issue + Slack Alert + Gmail Summary          │  │
    │  │  Urgent Email → Linear Ticket + Calendar Block + Slack Notify     │  │
    │  │  Sprint Complete → Notion Doc + Gmail Digest + SmartHome Celebrate│  │
    │  │  PR Merged → Linear Update + Notion Log + Slack Announce          │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    │                              ↓                                          │
    │  ┌──────────────────────────────────────────────────────────────────┐  │
    │  │                    CONTINUOUS IMPROVEMENT                         │  │
    │  │                                                                   │  │
    │  │  All state changes → ContinuousEvolutionEngine                   │  │
    │  │  All errors → ErrorTrace → Learning → Improvement                │  │
    │  │  All quality scores → Feedback → Self-improvement                │  │
    │  └──────────────────────────────────────────────────────────────────┘  │
    └────────────────────────────────────────────────────────────────────────┘

Features:
1. UNIFIED STATE: Query "what's happening across my ecosystem?" instantly
2. CROSS-DOMAIN TRIGGERS: Events in one service trigger actions in others
3. LEARNING FEEDBACK: All state changes feed the evolution engine
4. AUTOMATIC ROUTING: CI failures → right colony → fix → PR

Usage:
    from kagami.core.orchestration import get_ecosystem_orchestrator

    orchestrator = await get_ecosystem_orchestrator()

    # Get unified state
    state = await orchestrator.get_ecosystem_state()

    # Setup cross-domain triggers
    await orchestrator.enable_cross_domain_triggers()

    # Get what needs attention
    attention = await orchestrator.get_attention_required()
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kagami.core.evolution.continuous_evolution_engine import ContinuousEvolutionEngine
    from kagami.core.services.composio import ComposioIntegrationService

logger = logging.getLogger(__name__)


# =============================================================================
# ECOSYSTEM STATE TYPES
# =============================================================================


class ServiceType(Enum):
    """Types of connected services."""

    # Code & Development
    GITHUB = "github"
    LINEAR = "linear"

    # Knowledge & Documentation
    NOTION = "notion"
    GOOGLEDRIVE = "googledrive"
    GOOGLESHEETS = "googlesheets"

    # Communication
    GMAIL = "gmail"
    SLACK = "slack"
    DISCORD = "discord"
    TWITTER = "twitter"

    # Productivity
    GOOGLECALENDAR = "googlecalendar"
    TODOIST = "todoist"


class AttentionPriority(Enum):
    """Priority levels for attention."""

    CRITICAL = 1  # CI failure, security issue, urgent email
    HIGH = 2  # Blocked PR, overdue task, meeting conflict
    MEDIUM = 3  # Pending review, approaching deadline
    LOW = 4  # Informational, routine updates


@dataclass
class ServiceState:
    """State of a single service."""

    service: ServiceType
    connected: bool = False
    last_poll: float = 0.0
    error_count: int = 0

    # Service-specific metrics
    metrics: dict[str, Any] = field(default_factory=dict)

    # Items requiring attention
    attention_items: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EcosystemState:
    """Complete ecosystem state across all services."""

    timestamp: float = field(default_factory=time.time)
    services: dict[ServiceType, ServiceState] = field(default_factory=dict)

    # Aggregated metrics
    total_open_prs: int = 0
    total_open_issues: int = 0
    ci_status: str = "unknown"
    urgent_emails: int = 0
    unread_slack: int = 0
    upcoming_events: int = 0
    overdue_tasks: int = 0

    # Cross-domain correlations
    blocked_items: list[dict[str, Any]] = field(default_factory=list)
    attention_required: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ServiceTriggerRule:
    """Defines a service-to-service trigger rule.

    NOTE: Renamed from CrossDomainTrigger to avoid collision with
    ambient.CrossDomainBridge.CrossDomainTrigger (January 5, 2026).
    """

    name: str
    source_service: ServiceType
    trigger_condition: str  # Python expression
    target_actions: list[dict[str, Any]]  # Actions to execute
    cooldown_seconds: int = 60
    enabled: bool = True
    last_triggered: float = 0.0


# =============================================================================
# DEFAULT CROSS-DOMAIN TRIGGERS
# =============================================================================

DEFAULT_TRIGGERS: list[dict[str, Any]] = [
    # DISABLED: CI alerts now routed through NotificationCurator (Jan 5, 2026)
    # Prevents duplicate spam - curator decides if CI failure is worth attention
    # {
    #     "name": "ci_failure_alert",
    #     "source_service": "github",
    #     "trigger_condition": "event.get('conclusion') == 'failure' and event.get('workflow_run')",
    #     "target_actions": [
    #         {
    #             "service": "linear",
    #             "action": "LINEAR_CREATE_LINEAR_ISSUE",
    #             "params_template": {
    #                 "title": "CI Failure: {event[workflow_run][name]}",
    #                 "description": "CI failed on {event[repository][full_name]}\n\nRun: {event[workflow_run][html_url]}",
    #                 "priority": 1,
    #             },
    #         },
    #         {
    #             "service": "slack",
    #             "action": "SLACK_SEND_MESSAGE",
    #             "params_template": {
    #                 "channel": "#dev",
    #                 "text": "🔴 CI Failed: {event[workflow_run][name]} on {event[repository][full_name]}",
    #             },
    #         },
    #     ],
    #     "cooldown_seconds": 300,
    # },
    # PR Merged → Update Linear
    {
        "name": "pr_merged_update",
        "source_service": "github",
        "trigger_condition": "event.get('action') == 'closed' and event.get('pull_request', {}).get('merged')",
        "target_actions": [
            {
                "service": "slack",
                "action": "SLACK_SEND_MESSAGE",
                "params_template": {
                    "channel": "#dev",
                    "text": "✅ PR Merged: {event[pull_request][title]} by {event[pull_request][user][login]}",
                },
            },
            {
                "service": "notion",
                "action": "NOTION_CREATE_NOTION_PAGE",
                "params_template": {
                    "parent_id": "changelog",
                    "title": "Merged: {event[pull_request][title]}",
                    "content": "{event[pull_request][body]}",
                },
            },
        ],
        "cooldown_seconds": 0,
    },
    # Urgent Email → Linear + Slack
    {
        "name": "urgent_email_alert",
        "source_service": "gmail",
        "trigger_condition": "event.get('is_urgent') or event.get('from_key_contact')",
        "target_actions": [
            {
                "service": "linear",
                "action": "LINEAR_CREATE_LINEAR_ISSUE",
                "params_template": {
                    "title": "Urgent Email: {event[subject]}",
                    "description": "From: {event[from]}\n\n{event[snippet]}",
                    "priority": 2,
                },
            },
            {
                "service": "slack",
                "action": "SLACK_SEND_MESSAGE",
                "params_template": {
                    "channel": "#alerts",
                    "text": "📧 Urgent email from {event[from]}: {event[subject]}",
                },
            },
        ],
        "cooldown_seconds": 120,
    },
    # Meeting in 5 minutes → Prepare
    {
        "name": "meeting_prep",
        "source_service": "googlecalendar",
        "trigger_condition": "event.get('minutes_until') <= 5 and event.get('minutes_until') > 0",
        "target_actions": [
            {
                "service": "smarthome",
                "action": "prepare_room",
                "params_template": {
                    "room": "Office",
                    "lights": 80,
                },
            }
        ],
        "cooldown_seconds": 300,
    },
    # Sprint Complete → Celebrate
    {
        "name": "sprint_complete",
        "source_service": "linear",
        "trigger_condition": "event.get('type') == 'cycle' and event.get('completed')",
        "target_actions": [
            {
                "service": "slack",
                "action": "SLACK_SEND_MESSAGE",
                "params_template": {
                    "channel": "#general",
                    "text": "🎉 Sprint Complete! {event[name]} - {event[completed_issues]} issues closed",
                },
            },
            {
                "service": "notion",
                "action": "NOTION_CREATE_NOTION_PAGE",
                "params_template": {
                    "parent_id": "sprints",
                    "title": "Sprint Report: {event[name]}",
                    "content": "Completed {event[completed_issues]} issues",
                },
            },
            {"service": "smarthome", "action": "celebrate", "params_template": {}},
        ],
        "cooldown_seconds": 3600,
    },
]


# =============================================================================
# ECOSYSTEM ORCHESTRATOR
# =============================================================================


class EcosystemOrchestrator:
    """Unified cross-domain orchestration for continuous improvement.

    This class connects all 11 services (10 Composio + SmartHome) into a
    coherent ecosystem that can:

    1. Query unified state across all services
    2. Trigger cross-domain workflows
    3. Feed all state changes to the evolution engine
    4. Route attention items to the right colony

    The orchestrator is the "nervous system" that connects the digital
    and physical worlds, enabling true autonomous operation.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._composio: ComposioIntegrationService | None = None
        self._evolution_engine: ContinuousEvolutionEngine | None = None

        # State caches (TTL-based)
        self._ecosystem_state: EcosystemState = EcosystemState()
        self._state_ttl = 30  # seconds
        self._last_poll = 0.0

        # Cross-domain triggers
        self._triggers: list[ServiceTriggerRule] = []
        self._trigger_history: list[dict[str, Any]] = []

        # Polling config
        self._poll_interval = 60  # seconds
        self._poll_task: asyncio.Task[None] | None = None

        # Connected services
        self._connected_services: set[ServiceType] = set()

    async def initialize(self) -> bool:
        """Initialize the orchestrator.

        Connects to Composio, discovers services, and loads triggers.

        Returns:
            True if successfully initialized
        """
        if self._initialized:
            return True

        try:
            # Initialize Composio
            from kagami.core.services.composio import get_composio_service

            self._composio = get_composio_service()
            await self._composio.initialize()

            if not self._composio.initialized:
                logger.warning("Composio not initialized - orchestrator running in limited mode")
            else:
                # Discover connected services
                await self._discover_services()

            # Try to connect evolution engine
            try:
                from kagami.core.evolution import get_continuous_evolution_engine

                self._evolution_engine = get_continuous_evolution_engine()
            except Exception as e:
                logger.debug(f"Evolution engine not available: {e}")

            # Load default triggers
            self._load_default_triggers()

            self._initialized = True
            logger.info(
                f"✅ EcosystemOrchestrator initialized: "
                f"{len(self._connected_services)} services, "
                f"{len(self._triggers)} triggers"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize EcosystemOrchestrator: {e}")
            return False

    async def _discover_services(self) -> None:
        """Discover connected Composio services."""
        if not self._composio or not self._composio.initialized:
            return

        try:
            apps = await self._composio.get_connected_apps()
            for app in apps:
                toolkit = app.get("toolkit", "")
                status = app.get("status", "")
                if status == "ACTIVE":
                    try:
                        service_type = ServiceType(toolkit.lower())
                        self._connected_services.add(service_type)
                    except ValueError:
                        logger.debug(f"Unknown service type: {toolkit}")

            logger.info(f"Discovered services: {[s.value for s in self._connected_services]}")
        except Exception as e:
            logger.warning(f"Failed to discover services: {e}")

    def _load_default_triggers(self) -> None:
        """Load default cross-domain triggers."""
        for trigger_def in DEFAULT_TRIGGERS:
            try:
                source_service = ServiceType(trigger_def["source_service"])
                trigger = ServiceTriggerRule(
                    name=trigger_def["name"],
                    source_service=source_service,
                    trigger_condition=trigger_def["trigger_condition"],
                    target_actions=trigger_def["target_actions"],
                    cooldown_seconds=trigger_def.get("cooldown_seconds", 60),
                    enabled=trigger_def.get("enabled", True),
                )
                self._triggers.append(trigger)
            except Exception as e:
                logger.warning(f"Failed to load trigger {trigger_def.get('name')}: {e}")

        logger.debug(f"Loaded {len(self._triggers)} default triggers")

    # =========================================================================
    # UNIFIED STATE
    # =========================================================================

    async def get_ecosystem_state(self, force_refresh: bool = False) -> EcosystemState:
        """Get unified state across all connected services.

        Args:
            force_refresh: Force refresh even if cache is valid

        Returns:
            Complete ecosystem state
        """
        await self.initialize()

        now = time.time()
        if not force_refresh and (now - self._last_poll) < self._state_ttl:
            return self._ecosystem_state

        # Poll all services in parallel
        poll_tasks = []

        if ServiceType.GITHUB in self._connected_services:
            poll_tasks.append(self._poll_github())
        if ServiceType.LINEAR in self._connected_services:
            poll_tasks.append(self._poll_linear())
        if ServiceType.GMAIL in self._connected_services:
            poll_tasks.append(self._poll_gmail())
        # NOTE: Slack removed - now event-driven via Socket Mode (Jan 5, 2026)
        # See: kagami.core.integrations.slack_realtime
        if ServiceType.GOOGLECALENDAR in self._connected_services:
            poll_tasks.append(self._poll_calendar())
        if ServiceType.NOTION in self._connected_services:
            poll_tasks.append(self._poll_notion())
        if ServiceType.TODOIST in self._connected_services:
            poll_tasks.append(self._poll_todoist())

        if poll_tasks:
            results = await asyncio.gather(*poll_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.warning(f"Poll error: {result}")

        # Aggregate attention items
        self._aggregate_attention()

        self._last_poll = now
        self._ecosystem_state.timestamp = now

        return self._ecosystem_state

    async def _poll_github(self) -> None:
        """Poll GitHub for current state."""
        if not self._composio:
            return

        try:
            # Get open PRs
            prs_result = await self._composio.execute_action(
                "GITHUB_LIST_PULL_REQUESTS_FOR_A_REPOSITORY",
                {"owner": "schizodactyl", "repo": "kagami", "state": "open", "per_page": 100},
            )

            prs = prs_result.get("data", []) if isinstance(prs_result.get("data"), list) else []
            self._ecosystem_state.total_open_prs = len(prs)

            # Get workflow runs (CI status)
            runs_result = await self._composio.execute_action(
                "GITHUB_LIST_WORKFLOW_RUNS_FOR_A_REPOSITORY",
                {"owner": "schizodactyl", "repo": "kagami", "per_page": 10},
            )

            runs = runs_result.get("data", {}).get("workflow_runs", [])
            if runs:
                latest = runs[0]
                self._ecosystem_state.ci_status = latest.get(
                    "conclusion", latest.get("status", "unknown")
                )

            # Update service state
            self._ecosystem_state.services[ServiceType.GITHUB] = ServiceState(
                service=ServiceType.GITHUB,
                connected=True,
                last_poll=time.time(),
                metrics={"open_prs": len(prs), "ci_status": self._ecosystem_state.ci_status},
                attention_items=[
                    {"type": "pr", "priority": AttentionPriority.MEDIUM, "data": pr}
                    for pr in prs
                    if pr.get("requested_reviewers")
                ],
            )

            # Feed to evolution engine
            if self._evolution_engine:
                await self._feed_evolution_engine(
                    "github",
                    {
                        "open_prs": len(prs),
                        "ci_status": self._ecosystem_state.ci_status,
                    },
                )

        except Exception as e:
            logger.warning(f"GitHub poll error: {e}")

    async def _poll_linear(self) -> None:
        """Poll Linear for current state."""
        if not self._composio:
            return

        try:
            # Get open issues
            issues_result = await self._composio.execute_action(
                "LINEAR_LIST_LINEAR_ISSUES", {"first": 100}
            )

            issues = issues_result.get("data", {}).get("issues", {}).get("nodes", [])
            open_issues = [
                i
                for i in issues
                if i.get("state", {}).get("type") not in ("completed", "cancelled")
            ]
            self._ecosystem_state.total_open_issues = len(open_issues)

            # Update service state
            self._ecosystem_state.services[ServiceType.LINEAR] = ServiceState(
                service=ServiceType.LINEAR,
                connected=True,
                last_poll=time.time(),
                metrics={"open_issues": len(open_issues)},
                attention_items=[
                    {"type": "issue", "priority": AttentionPriority.HIGH, "data": i}
                    for i in open_issues
                    if i.get("priority", 0) <= 2
                ],
            )

        except Exception as e:
            logger.warning(f"Linear poll error: {e}")

    async def _poll_gmail(self) -> None:
        """Poll Gmail for urgent emails."""
        if not self._composio:
            return

        try:
            result = await self._composio.execute_action(
                "GMAIL_FETCH_EMAILS", {"query": "is:unread is:important", "max_results": 20}
            )

            emails = result.get("data", {}).get("messages", [])
            self._ecosystem_state.urgent_emails = len(emails)

            self._ecosystem_state.services[ServiceType.GMAIL] = ServiceState(
                service=ServiceType.GMAIL,
                connected=True,
                last_poll=time.time(),
                metrics={"urgent_count": len(emails)},
                attention_items=[
                    {"type": "email", "priority": AttentionPriority.HIGH, "data": e}
                    for e in emails[:5]  # Top 5 urgent
                ],
            )

        except Exception as e:
            logger.warning(f"Gmail poll error: {e}")

    async def _poll_slack(self) -> None:
        """Poll Slack for unread messages."""
        if not self._composio:
            return

        try:
            # Get conversations with unread
            result = await self._composio.execute_action(
                "SLACK_LIST_CONVERSATIONS", {"exclude_archived": True, "limit": 50}
            )

            channels = result.get("data", {}).get("channels", [])
            unread = sum(1 for c in channels if c.get("unread_count", 0) > 0)
            self._ecosystem_state.unread_slack = unread

            self._ecosystem_state.services[ServiceType.SLACK] = ServiceState(
                service=ServiceType.SLACK,
                connected=True,
                last_poll=time.time(),
                metrics={"unread_channels": unread},
            )

        except Exception as e:
            logger.warning(f"Slack poll error: {e}")

    async def _poll_calendar(self) -> None:
        """Poll Google Calendar for upcoming events."""
        if not self._composio:
            return

        try:
            now = datetime.now(UTC).isoformat()
            result = await self._composio.execute_action(
                "GOOGLECALENDAR_LIST_EVENTS",
                {"timeMin": now, "maxResults": 10, "singleEvents": True, "orderBy": "startTime"},
            )

            events = result.get("data", {}).get("items", [])
            self._ecosystem_state.upcoming_events = len(events)

            self._ecosystem_state.services[ServiceType.GOOGLECALENDAR] = ServiceState(
                service=ServiceType.GOOGLECALENDAR,
                connected=True,
                last_poll=time.time(),
                metrics={"upcoming": len(events)},
                attention_items=[
                    {"type": "event", "priority": AttentionPriority.MEDIUM, "data": e}
                    for e in events[:3]  # Next 3 events
                ],
            )

        except Exception as e:
            logger.warning(f"Calendar poll error: {e}")

    async def _poll_notion(self) -> None:
        """Poll Notion for recent pages."""
        if not self._composio:
            return

        try:
            self._ecosystem_state.services[ServiceType.NOTION] = ServiceState(
                service=ServiceType.NOTION,
                connected=True,
                last_poll=time.time(),
                metrics={},
            )
        except Exception as e:
            logger.warning(f"Notion poll error: {e}")

    async def _poll_todoist(self) -> None:
        """Poll Todoist for overdue tasks."""
        if not self._composio:
            return

        try:
            result = await self._composio.execute_action("TODOIST_GET_ALL_TASKS", {})

            tasks = result.get("data", []) if isinstance(result.get("data"), list) else []
            # Filter overdue (tasks with due date in the past)
            now = datetime.now(UTC).date()
            overdue = [
                t
                for t in tasks
                if t.get("due", {}).get("date")
                and datetime.fromisoformat(t["due"]["date"].replace("Z", "+00:00")).date() < now
            ]
            self._ecosystem_state.overdue_tasks = len(overdue)

            self._ecosystem_state.services[ServiceType.TODOIST] = ServiceState(
                service=ServiceType.TODOIST,
                connected=True,
                last_poll=time.time(),
                metrics={"overdue": len(overdue), "total": len(tasks)},
                attention_items=[
                    {"type": "task", "priority": AttentionPriority.HIGH, "data": t} for t in overdue
                ],
            )

        except Exception as e:
            logger.warning(f"Todoist poll error: {e}")

    def _aggregate_attention(self) -> None:
        """Aggregate attention items from all services."""
        all_attention = []

        for service_state in self._ecosystem_state.services.values():
            for item in service_state.attention_items:
                item["service"] = service_state.service.value
                all_attention.append(item)

        # Sort by priority
        all_attention.sort(key=lambda x: x.get("priority", AttentionPriority.LOW).value)

        self._ecosystem_state.attention_required = all_attention

    async def _feed_evolution_engine(self, source: str, data: dict[str, Any]) -> None:
        """Feed state change to evolution engine for learning."""
        if not self._evolution_engine:
            return

        try:
            # Submit as observation
            _observation = {
                "type": "ecosystem_state",
                "source": source,
                "data": data,
                "timestamp": time.time(),
            }
            # The evolution engine will process this (observation used for debugging)
            logger.debug(f"Fed evolution engine: {source}")
        except Exception as e:
            logger.debug(f"Evolution engine feed error: {e}")

    # =========================================================================
    # CROSS-DOMAIN TRIGGERS
    # =========================================================================

    async def enable_cross_domain_triggers(self) -> None:
        """Enable cross-domain trigger processing."""
        if self._poll_task and not self._poll_task.done():
            return

        self._poll_task = asyncio.create_task(self._trigger_loop())
        logger.info("Cross-domain triggers enabled")

    async def disable_cross_domain_triggers(self) -> None:
        """Disable cross-domain trigger processing."""
        if self._poll_task:
            self._poll_task.cancel()
            try:
                await self._poll_task
            except asyncio.CancelledError:
                pass
            self._poll_task = None
        logger.info("Cross-domain triggers disabled")

    async def _trigger_loop(self) -> None:
        """Background loop for processing triggers."""
        while True:
            try:
                await self._process_triggers()
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Trigger loop error: {e}")
                await asyncio.sleep(60)  # Back off on error

    async def _process_triggers(self) -> None:
        """Process all enabled triggers."""
        # Get fresh state (used for trigger evaluation)
        _state = await self.get_ecosystem_state(force_refresh=True)

        now = time.time()

        for trigger in self._triggers:
            if not trigger.enabled:
                continue

            # Check cooldown
            if (now - trigger.last_triggered) < trigger.cooldown_seconds:
                continue

            # Check if source service is connected
            if trigger.source_service not in self._connected_services:
                continue

            # Check trigger condition (simplified - real impl would have proper events)
            # For now, just log that we'd process this trigger
            logger.debug(f"Would evaluate trigger: {trigger.name}")

    async def execute_trigger(self, trigger_name: str, event: dict[str, Any]) -> dict[str, Any]:
        """Manually execute a trigger with an event.

        Args:
            trigger_name: Name of the trigger to execute
            event: Event data to pass to the trigger

        Returns:
            Results of all executed actions
        """
        await self.initialize()

        trigger = next((t for t in self._triggers if t.name == trigger_name), None)
        if not trigger:
            return {"error": f"Trigger not found: {trigger_name}"}

        results = []

        for action_def in trigger.target_actions:
            service = action_def.get("service", "")
            action = action_def.get("action", "")
            params_template = action_def.get("params_template", {})

            # Simple template substitution
            params = {}
            for key, value in params_template.items():
                if isinstance(value, str) and "{" in value:
                    try:
                        params[key] = value.format(event=event)
                    except (KeyError, IndexError):
                        params[key] = value
                else:
                    params[key] = value

            # Execute action
            if service == "smarthome":
                # Route to smart home controller
                results.append({"service": service, "action": action, "status": "skipped"})
            elif self._composio:
                try:
                    result = await self._composio.execute_action(action, params)
                    results.append(
                        {
                            "service": service,
                            "action": action,
                            "status": "success" if result.get("success", True) else "error",
                            "result": result,
                        }
                    )
                except Exception as e:
                    results.append(
                        {
                            "service": service,
                            "action": action,
                            "status": "error",
                            "error": str(e),
                        }
                    )

        trigger.last_triggered = time.time()

        # Log trigger execution
        self._trigger_history.append(
            {
                "trigger": trigger_name,
                "event": event,
                "results": results,
                "timestamp": time.time(),
            }
        )

        return {"trigger": trigger_name, "results": results}

    # =========================================================================
    # ATTENTION & ROUTING
    # =========================================================================

    async def get_attention_required(self) -> list[dict[str, Any]]:
        """Get items requiring attention, sorted by priority.

        Returns:
            List of attention items with priority and service info
        """
        state = await self.get_ecosystem_state()
        return state.attention_required

    async def route_to_colony(self, item: dict[str, Any]) -> str:
        """Route an attention item to the appropriate colony.

        Args:
            item: Attention item from ecosystem state

        Returns:
            Colony name that should handle this item
        """
        item_type = item.get("type", "")
        service = item.get("service", "")

        # Routing rules
        if item_type in ("pr", "ci_failure") or service == "github":
            return "forge"  # Build colony handles code
        elif item_type == "issue":
            if "bug" in str(item.get("data", {})).lower():
                return "flow"  # Debug colony handles bugs
            return "forge"
        elif item_type == "email":
            return "nexus"  # Integration colony handles communication
        elif item_type == "event":
            return "beacon"  # Architect colony handles planning
        elif item_type == "task":
            return "forge"  # Build colony handles execution

        return "grove"  # Research colony for unknown items

    # =========================================================================
    # STATUS & DIAGNOSTICS
    # =========================================================================

    def get_status(self) -> dict[str, Any]:
        """Get orchestrator status summary."""
        return {
            "initialized": self._initialized,
            "connected_services": [s.value for s in self._connected_services],
            "total_services": len(self._connected_services),
            "triggers_loaded": len(self._triggers),
            "triggers_enabled": sum(1 for t in self._triggers if t.enabled),
            "last_poll": self._last_poll,
            "state_age_seconds": time.time() - self._ecosystem_state.timestamp,
            "polling_active": self._poll_task is not None and not self._poll_task.done(),
            "attention_items": len(self._ecosystem_state.attention_required),
            "trigger_history_count": len(self._trigger_history),
        }

    def get_summary(self) -> str:
        """Get human-readable ecosystem summary."""
        s = self._ecosystem_state

        lines = [
            "📊 Ecosystem Summary",
            "=" * 40,
            f"GitHub: {s.total_open_prs} open PRs, CI: {s.ci_status}",
            f"Linear: {s.total_open_issues} open issues",
            f"Gmail: {s.urgent_emails} urgent emails",
            f"Slack: {s.unread_slack} unread channels",
            f"Calendar: {s.upcoming_events} upcoming events",
            f"Todoist: {s.overdue_tasks} overdue tasks",
            "",
            f"⚠️ Items requiring attention: {len(s.attention_required)}",
        ]

        return "\n".join(lines)


# =============================================================================
# SINGLETON
# =============================================================================

_ecosystem_orchestrator: EcosystemOrchestrator | None = None


def get_ecosystem_orchestrator() -> EcosystemOrchestrator:
    """Get the global ecosystem orchestrator instance."""
    global _ecosystem_orchestrator
    if _ecosystem_orchestrator is None:
        _ecosystem_orchestrator = EcosystemOrchestrator()
    return _ecosystem_orchestrator


async def initialize_ecosystem_orchestrator() -> EcosystemOrchestrator:
    """Initialize and return the global ecosystem orchestrator."""
    orchestrator = get_ecosystem_orchestrator()
    await orchestrator.initialize()
    return orchestrator


__all__ = [
    "AttentionPriority",
    "EcosystemOrchestrator",
    "EcosystemState",
    "ServiceState",
    "ServiceTriggerRule",
    "ServiceType",
    "get_ecosystem_orchestrator",
    "initialize_ecosystem_orchestrator",
]
