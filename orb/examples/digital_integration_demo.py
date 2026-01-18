#!/usr/bin/env python3
"""Digital Integration Demo — 500 Tools via Composio.

Kagami integrates with 500+ digital tools through Composio:
Gmail, Slack, Calendar, Todoist, Linear, Notion, and more.

WHAT YOU'LL LEARN:
==================
1. Initialize Composio service
2. Gmail — Fetch unread, send email
3. Google Calendar — Get/create events
4. Slack — Send messages
5. Todoist — Create/manage tasks
6. Cross-service workflows

RATE LIMITING CONSIDERATIONS:
=============================
Composio applies rate limits per action and per account. This demo uses
conservative defaults but production use should consider:

- Per-action QPS limits (default: 10 QPS, configurable via COMPOSIO_QPS_DEFAULT)
- Circuit breaker protection (opens after 5 failures, resets after 60s)
- Response caching for read operations (30s TTL)
- Async batching with asyncio.gather() for parallel calls
- Exponential backoff on retries (handled by call_with_resilience_async)

Environment variables for tuning:
- COMPOSIO_QPS_DEFAULT: Max requests per second per action (default: 10)
- COMPOSIO_TOOL_TIMEOUT_MS: Timeout per API call (default: 5000ms)
- COMPOSIO_RETRY_ATTEMPTS: Retry count on failure (default: 3)
- COMPOSIO_CB_FAILURE_THRESHOLD: Failures before circuit opens (default: 5)
- COMPOSIO_CB_RESET_SECONDS: Circuit breaker reset time (default: 60)

Created: December 31, 2025
Colony: Nexus (e₄) — The Bridge
"""

from __future__ import annotations

import argparse
import asyncio
import html
import logging
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Add paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "packages"))
sys.path.insert(0, str(Path(__file__).parent))

from common.output import (
    print_header,
    print_section,
    print_success,
    print_warning,
    print_info,
    print_metrics,
    print_footer,
    print_separator,
    print_table,
)
from common.metrics import Timer, MetricsCollector

if TYPE_CHECKING:
    from kagami.core.services.composio import ComposioIntegrationService

# Configure logging
logger = logging.getLogger(__name__)


# =============================================================================
# INPUT SANITIZATION
# =============================================================================


def sanitize_query(query: str, max_length: int = 500) -> str:
    """Sanitize a search query string for safe API usage.

    Args:
        query: Raw query string from user input
        max_length: Maximum allowed length (default: 500)

    Returns:
        Sanitized query string safe for API calls
    """
    if not query:
        return ""

    # Strip whitespace and limit length
    sanitized = query.strip()[:max_length]

    # Remove potentially dangerous characters (shell injection, SQL injection patterns)
    # Keep alphanumeric, spaces, and common search operators
    sanitized = re.sub(r'[;\'"\\`$(){}|<>]', "", sanitized)

    # Escape HTML entities to prevent XSS if displayed
    sanitized = html.escape(sanitized)

    # Normalize whitespace
    sanitized = re.sub(r"\s+", " ", sanitized)

    return sanitized


def sanitize_params(params: dict[str, Any]) -> dict[str, Any]:
    """Sanitize all string parameters in a dictionary.

    Args:
        params: Dictionary of parameters to sanitize

    Returns:
        New dictionary with sanitized string values
    """
    sanitized: dict[str, Any] = {}
    for key, value in params.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_query(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_params(value)
        elif isinstance(value, list):
            sanitized[key] = [sanitize_query(v) if isinstance(v, str) else v for v in value]
        else:
            sanitized[key] = value
    return sanitized


# =============================================================================
# COMMON API CALL HELPER
# =============================================================================


async def execute_api_call(
    service: ComposioIntegrationService | None,
    action_name: str,
    params: dict[str, Any],
    metrics: MetricsCollector,
    *,
    simulated_result: Any = None,
    sanitize: bool = True,
) -> tuple[Any, bool]:
    """Execute a Composio API call with consistent error handling.

    This helper centralizes:
    - Input sanitization
    - Timing measurement
    - Error handling
    - Metrics tracking
    - Simulation mode fallback

    Args:
        service: Composio service instance or None for simulation
        action_name: The Composio action to execute (e.g., "GMAIL_FETCH_EMAILS")
        params: Parameters for the action
        metrics: Metrics collector for tracking
        simulated_result: Result to return when service is None
        sanitize: Whether to sanitize input params (default: True)

    Returns:
        Tuple of (result, is_real) where is_real indicates if the call was live
    """
    # Sanitize parameters if requested
    safe_params = sanitize_params(params) if sanitize else params

    logger.debug("Executing %s with params: %s", action_name, safe_params)

    with Timer() as t:
        try:
            if service:
                result = await service.execute_action(action_name, safe_params)
                metrics.increment("api_calls")
                logger.info(
                    "API call %s completed in %.2fms",
                    action_name,
                    t.elapsed_ms,
                )
                return result, True
            else:
                # Simulation mode
                metrics.increment("simulated")
                logger.debug("Simulated %s (no service)", action_name)
                return simulated_result, False
        except Exception as e:
            metrics.increment("errors")
            logger.warning("API call %s failed: %s", action_name, e)
            raise


async def execute_batch(
    service: ComposioIntegrationService | None,
    calls: list[tuple[str, dict[str, Any]]],
    metrics: MetricsCollector,
    *,
    sanitize: bool = True,
) -> list[tuple[Any, bool]]:
    """Execute multiple API calls concurrently with asyncio.gather.

    This enables efficient batching of independent API calls, reducing
    total latency when multiple services need to be queried.

    Args:
        service: Composio service instance or None for simulation
        calls: List of (action_name, params) tuples
        metrics: Metrics collector for tracking
        sanitize: Whether to sanitize input params (default: True)

    Returns:
        List of (result, is_real) tuples in the same order as input

    Example:
        results = await execute_batch(service, [
            ("GMAIL_FETCH_EMAILS", {"query": "is:unread"}),
            ("GOOGLECALENDAR_LIST_EVENTS", {"date": "2025-12-31"}),
            ("TODOIST_GET_TODAY", {}),
        ], metrics)
    """
    logger.info("Executing batch of %d API calls", len(calls))

    tasks = [
        execute_api_call(
            service,
            action_name,
            params,
            metrics,
            simulated_result={"simulated": True},
            sanitize=sanitize,
        )
        for action_name, params in calls
    ]

    # Use return_exceptions to prevent one failure from canceling others
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Convert exceptions to (None, False) tuples
    processed: list[tuple[Any, bool]] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Batch call failed: %s", result)
            processed.append((None, False))
        else:
            processed.append(result)  # type: ignore[arg-type]

    return processed


# =============================================================================
# SECTION 1: INITIALIZE COMPOSIO
# =============================================================================


async def section_1_initialize(
    metrics: MetricsCollector,
) -> ComposioIntegrationService | None:
    """Initialize the Composio service.

    Args:
        metrics: Metrics collector for tracking initialization timing

    Returns:
        Initialized ComposioIntegrationService or None if unavailable
    """
    print_section(1, "Initializing Composio Service")
    logger.info("Starting Composio service initialization")

    try:
        from kagami.core.services.composio import get_composio_service

        with Timer() as t:
            service = get_composio_service()
            await service.initialize()

        metrics.record_timing("init", t.elapsed)

        # Show available services
        print_success("Composio initialized", f"{t.elapsed_ms:.0f}ms")
        logger.info("Composio initialized successfully in %.2fms", t.elapsed_ms)
        print()

        print_table(
            headers=["Service", "Tools", "Key Actions"],
            rows=[
                ["Slack", "130", "SLACK_SEND_MESSAGE, SLACK_CREATE_CHANNEL"],
                ["Twitter", "75", "TWITTER_POST_TWEET, TWITTER_SEARCH"],
                ["Google Drive", "56", "GOOGLEDRIVE_LIST_FILES"],
                ["Google Calendar", "44", "GOOGLECALENDAR_CREATE_EVENT"],
                ["Todoist", "44", "TODOIST_CREATE_TASK"],
                ["Notion", "42", "NOTION_SEARCH_NOTION_PAGE"],
                ["Google Sheets", "40", "GOOGLESHEETS_GET_SPREADSHEET_INFO"],
                ["Gmail", "37", "GMAIL_FETCH_EMAILS, GMAIL_SEND_EMAIL"],
                ["Linear", "26", "LINEAR_CREATE_LINEAR_ISSUE"],
                ["Discord", "6", "DISCORD_GET_MY_USER"],
            ],
            title="Connected Services (10 total, 500 tools)",
        )

        return service

    except Exception as e:
        logger.warning("Composio not available: %s", e, exc_info=True)
        print_warning(f"Composio not available: {e}")
        print_info("Running in simulation mode")
        return None


# =============================================================================
# SECTION 2: GMAIL
# =============================================================================


async def section_2_gmail(
    service: ComposioIntegrationService | None,
    metrics: MetricsCollector,
) -> None:
    """Demonstrate Gmail integration.

    Args:
        service: Composio service instance or None for simulation
        metrics: Metrics collector for tracking
    """
    print_separator()
    print_section(2, "Gmail Integration")
    logger.info("Starting Gmail integration demo")

    # Fetch unread emails using the helper
    print("   Fetching unread emails...")
    with Timer() as t:
        try:
            result, is_real = await execute_api_call(
                service,
                "GMAIL_FETCH_EMAILS",
                {"query": "is:unread is:important"},
                metrics,
                simulated_result={
                    "emails": [
                        {"subject": "Q4 Planning", "from": "team@example.com"},
                        {"subject": "PR Review", "from": "github@example.com"},
                        {"subject": "Weekly Update", "from": "newsletter@example.com"},
                    ]
                },
            )
            email_count = len(result.get("emails", [])) if result else 0
            mode = "" if is_real else " (simulated)"
            print_success(
                f"Found {email_count} unread important emails{mode}",
                f"{t.elapsed_ms:.0f}ms",
            )
        except Exception as e:
            logger.error("Gmail fetch failed: %s", e)
            print_warning(f"Gmail fetch failed: {e}")

    # Show sample email data
    print()
    print("   Sample response:")
    print("      {")
    print('         "emails": [')
    print('            {"subject": "Q4 Planning", "from": "team@example.com"},')
    print('            {"subject": "PR Review", "from": "github@example.com"}')
    print("         ]")
    print("      }")

    # Send email example
    print()
    print("   Send email action:")
    print(
        """
      await service.execute_action("GMAIL_SEND_EMAIL", {
         "to": "tim@example.com",
         "subject": "Kagami Update",
         "body": "System status: All green."
      })
"""
    )

    metrics.record_timing("gmail", t.elapsed)


# =============================================================================
# SECTION 3: GOOGLE CALENDAR
# =============================================================================


async def section_3_calendar(
    service: ComposioIntegrationService | None,
    metrics: MetricsCollector,
) -> None:
    """Demonstrate Calendar integration.

    Args:
        service: Composio service instance or None for simulation
        metrics: Metrics collector for tracking
    """
    print_separator()
    print_section(3, "Google Calendar Integration")
    logger.info("Starting Calendar integration demo")

    # Fetch today's events using the helper
    print("   Fetching today's events...")
    today = datetime.now().strftime("%Y-%m-%d")

    with Timer() as t:
        try:
            result, is_real = await execute_api_call(
                service,
                "GOOGLECALENDAR_LIST_EVENTS",
                {"date": today},
                metrics,
                simulated_result={
                    "events": [
                        {"title": "Morning standup", "time": "09:00"},
                        {"title": "Code review", "time": "11:00"},
                        {"title": "Q4 Planning", "time": "14:00"},
                        {"title": "Gym", "time": "16:00"},
                    ]
                },
            )
            event_count = len(result.get("events", [])) if result else 0
            mode = "" if is_real else " (simulated)"
            print_success(f"Found {event_count} events today{mode}", f"{t.elapsed_ms:.0f}ms")
        except Exception as e:
            logger.error("Calendar fetch failed: %s", e)
            print_warning(f"Calendar fetch failed: {e}")

    # Show sample calendar data
    print()
    print("   Today's schedule:")
    print("      09:00  Morning standup")
    print("      11:00  Code review")
    print("      14:00  Q4 Planning")
    print("      16:00  Gym (personal)")

    # Create event example
    print()
    print("   Create event action:")
    tomorrow = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    print(
        f"""
      await service.execute_action("GOOGLECALENDAR_CREATE_EVENT", {{
         "title": "Demo Meeting",
         "start": "{tomorrow}T10:00:00",
         "end": "{tomorrow}T11:00:00",
         "description": "Kagami demo for stakeholders"
      }})
"""
    )

    metrics.record_timing("calendar", t.elapsed)


# =============================================================================
# SECTION 4: SLACK
# =============================================================================


async def section_4_slack(
    service: ComposioIntegrationService | None,
    metrics: MetricsCollector,
) -> None:
    """Demonstrate Slack integration.

    Args:
        service: Composio service instance or None for simulation
        metrics: Metrics collector for tracking
    """
    print_separator()
    print_section(4, "Slack Integration")
    logger.info("Starting Slack integration demo")

    # Send message example using the helper
    print("   Sending Slack message...")
    with Timer() as t:
        try:
            _result, is_real = await execute_api_call(
                service,
                "SLACK_SEND_MESSAGE",
                {
                    "channel": "#general",
                    "text": "Kagami status: Online",
                },
                metrics,
                simulated_result={"ok": True, "ts": "1234567890.123456"},
            )
            mode = "" if is_real else " (simulated)"
            print_success(f"Message sent to #general{mode}", f"{t.elapsed_ms:.0f}ms")
        except Exception as e:
            logger.error("Slack send failed: %s", e)
            print_warning(f"Slack send failed: {e}")

    # Show available Slack actions
    print()
    print("   Available Slack actions:")
    print("      - SLACK_SEND_MESSAGE: Send to channel/DM")
    print("      - SLACK_CREATE_CHANNEL: Create new channel")
    print("      - SLACK_LIST_CHANNELS: Get all channels")
    print("      - SLACK_GET_USER_INFO: Lookup user details")
    print("      - SLACK_SET_STATUS: Update your status")

    metrics.record_timing("slack", t.elapsed)


# =============================================================================
# SECTION 5: TODOIST
# =============================================================================


async def section_5_todoist(
    service: ComposioIntegrationService | None,
    metrics: MetricsCollector,
) -> None:
    """Demonstrate Todoist integration.

    Args:
        service: Composio service instance or None for simulation
        metrics: Metrics collector for tracking
    """
    print_separator()
    print_section(5, "Todoist Integration")
    logger.info("Starting Todoist integration demo")

    # Create task example using the helper
    print("   Creating task...")
    with Timer() as t:
        try:
            result, is_real = await execute_api_call(
                service,
                "TODOIST_CREATE_TASK",
                {
                    "content": "Review Kagami examples",
                    "priority": 2,
                    "due_string": "tomorrow",
                },
                metrics,
                simulated_result={"id": "12345", "content": "Review Kagami examples"},
            )
            task_id = result.get("id", "simulated") if result else "simulated"
            mode = "" if is_real else " (simulated)"
            print_success(f"Task created{mode}", f"id={task_id}")
        except Exception as e:
            logger.error("Todoist create failed: %s", e)
            print_warning(f"Todoist create failed: {e}")

    # Get today's tasks
    print()
    print("   Today's tasks:")
    print("      [ ] Review Kagami examples (P2)")
    print("      [ ] Update documentation (P3)")
    print("      [x] Morning workout (completed)")

    # Task management examples
    print()
    print("   Task management actions:")
    print("      - TODOIST_CREATE_TASK: Create new task")
    print("      - TODOIST_COMPLETE_TASK: Mark complete")
    print("      - TODOIST_GET_TODAY: Get today's tasks")
    print("      - TODOIST_UPDATE_TASK: Modify task")

    metrics.record_timing("todoist", t.elapsed)


# =============================================================================
# SECTION 6: CROSS-SERVICE WORKFLOW
# =============================================================================


async def section_6_workflow(
    service: ComposioIntegrationService | None,
    metrics: MetricsCollector,
) -> None:
    """Demonstrate cross-service workflow with async batching.

    This section shows how to use execute_batch() for parallel API calls,
    significantly reducing total latency when fetching from multiple services.

    Args:
        service: Composio service instance or None for simulation
        metrics: Metrics collector for tracking
    """
    print_separator()
    print_section(6, "Cross-Service Workflow")
    logger.info("Starting cross-service workflow demo")

    print(
        """
   Kagami can orchestrate actions across services:

   EXAMPLE: Morning briefing workflow (with async batching)
   ────────────────────────────────────────────────────────
   1. Fetch unread important emails (Gmail)     |
   2. Get today's calendar events (Calendar)    | <- These run in PARALLEL
   3. Get today's tasks (Todoist)               |
   4. Post summary to Slack (Slack)             <- Sequential (needs results)
"""
    )

    print("   Executing morning briefing with async batching...")
    today = datetime.now().strftime("%Y-%m-%d")

    with Timer() as t:
        # Use execute_batch for parallel fetching (the key pattern!)
        batch_calls: list[tuple[str, dict[str, Any]]] = [
            ("GMAIL_FETCH_EMAILS", {"query": "is:unread is:important"}),
            ("GOOGLECALENDAR_LIST_EVENTS", {"date": today}),
            ("TODOIST_GET_TODAY", {}),
        ]

        logger.info("Starting parallel batch of %d API calls", len(batch_calls))
        results = await execute_batch(service, batch_calls, metrics)

        # Process results
        email_result, email_real = results[0]
        calendar_result, calendar_real = results[1]
        todoist_result, todoist_real = results[2]

        email_count = len(email_result.get("emails", [])) if email_result else 3
        event_count = len(calendar_result.get("events", [])) if calendar_result else 4
        task_count = len(todoist_result.get("tasks", [])) if todoist_result else 5

        # Display results
        mode = "(live)" if all([email_real, calendar_real, todoist_real]) else "(simulated)"
        print(f"      + Gmail: Fetch unread -> {email_count} emails {mode}")
        print(f"      + Calendar: Today's events -> {event_count} meetings {mode}")
        print(f"      + Todoist: Today's tasks -> {task_count} tasks {mode}")

        # Post summary to Slack (sequential, depends on above results)
        summary = (
            f"Morning briefing: {email_count} emails, {event_count} meetings, {task_count} tasks"
        )
        _, slack_real = await execute_api_call(
            service,
            "SLACK_SEND_MESSAGE",
            {"channel": "#daily-briefing", "text": summary},
            metrics,
            simulated_result={"ok": True},
        )
        slack_mode = "(live)" if slack_real else "(simulated)"
        print(f"      + Slack: Post summary -> #daily-briefing {slack_mode}")

    print_success("Morning briefing complete", f"{t.elapsed:.2f}s total")
    logger.info("Workflow completed in %.2fs", t.elapsed)

    # Show workflow code with batching pattern
    print()
    print("   Async batching pattern:")
    print(
        """
      # Morning briefing with parallel fetching
      from digital_integration_demo import execute_batch, execute_api_call

      # Fetch from multiple services in PARALLEL (reduces latency)
      results = await execute_batch(service, [
          ("GMAIL_FETCH_EMAILS", {"query": "is:unread is:important"}),
          ("GOOGLECALENDAR_LIST_EVENTS", {"date": "2025-12-31"}),
          ("TODOIST_GET_TODAY", {}),
      ], metrics)

      emails, events, tasks = [r[0] for r in results]

      # Post summary (sequential, depends on above)
      summary = format_briefing(emails, events, tasks)
      await execute_api_call(service, "SLACK_SEND_MESSAGE", {
          "channel": "#daily-briefing",
          "text": summary
      }, metrics)
"""
    )

    metrics.record_timing("workflow", t.elapsed)


# =============================================================================
# SERVICE REGISTRY
# =============================================================================

# Map of service names to their demo functions
SERVICE_DEMOS: dict[str, Any] = {
    "gmail": section_2_gmail,
    "calendar": section_3_calendar,
    "slack": section_4_slack,
    "todoist": section_5_todoist,
    "workflow": section_6_workflow,
}

AVAILABLE_SERVICES = list(SERVICE_DEMOS.keys())


# =============================================================================
# CLI ARGUMENT PARSER
# =============================================================================


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Digital Integration Demo - 500 Tools via Composio",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                     Run all service demos
  %(prog)s --service gmail     Run only Gmail demo
  %(prog)s --service workflow  Run only the workflow demo
  %(prog)s -s slack -s todoist Run Slack and Todoist demos
  %(prog)s --verbose           Enable debug logging
  %(prog)s --list              List available services

Environment Variables:
  COMPOSIO_API_KEY             Required for live API calls
  COMPOSIO_QPS_DEFAULT         Max requests/second (default: 10)
  COMPOSIO_TOOL_TIMEOUT_MS     API timeout in ms (default: 5000)
  KAGAMI_DISABLE_COMPOSIO      Set to 1 to force simulation mode
        """,
    )

    parser.add_argument(
        "-s",
        "--service",
        action="append",
        dest="services",
        choices=AVAILABLE_SERVICES,
        metavar="SERVICE",
        help=f"Run specific service demo (choices: {', '.join(AVAILABLE_SERVICES)}). "
        "Can be specified multiple times.",
    )

    parser.add_argument(
        "-l",
        "--list",
        action="store_true",
        help="List available services and exit",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress INFO logging (only show warnings and errors)",
    )

    return parser.parse_args()


def setup_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Configure logging based on CLI flags.

    Args:
        verbose: If True, set level to DEBUG
        quiet: If True, set level to WARNING
    """
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.WARNING
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# =============================================================================
# MAIN
# =============================================================================


async def main(services: list[str] | None = None) -> None:
    """Run Digital Integration demonstration.

    Args:
        services: Optional list of specific services to demo.
                  If None or empty, runs all services.
    """
    print_header("DIGITAL INTEGRATION DEMO", "[+]")
    logger.info("Starting Digital Integration demo")

    metrics = MetricsCollector("digital_integration")

    with Timer() as total_timer:
        # Section 1: Initialize (always run)
        service = await section_1_initialize(metrics)

        # Determine which demos to run
        demos_to_run = services if services else AVAILABLE_SERVICES

        # Run selected service demos
        for demo_name in demos_to_run:
            if demo_name in SERVICE_DEMOS:
                logger.info("Running %s demo", demo_name)
                await SERVICE_DEMOS[demo_name](service, metrics)
            else:
                logger.warning("Unknown service: %s", demo_name)

    print_metrics(
        {
            "Total time": f"{total_timer.elapsed:.2f}s",
            "API calls": metrics.counters.get("api_calls", 0),
            "Simulated": metrics.counters.get("simulated", 0),
            "Errors": metrics.counters.get("errors", 0),
            "Services demoed": len(demos_to_run),
            "Total available tools": 500,
        }
    )

    print_footer(
        message="Digital Integration demo complete!",
        next_steps=[
            "Run cross_domain_triggers_demo.py for digital->physical",
            "Run smarthome_demo.py for home control",
            "See docs/03_DIGITAL_LIFE.md for full service list",
        ],
    )

    logger.info("Demo completed in %.2fs", total_timer.elapsed)


def cli() -> None:
    """CLI entry point."""
    args = parse_args()

    # Handle --list flag
    if args.list:
        print("Available services:")
        for svc in AVAILABLE_SERVICES:
            print(f"  - {svc}")
        sys.exit(0)

    # Setup logging
    setup_logging(verbose=args.verbose, quiet=args.quiet)

    # Run the demo
    asyncio.run(main(services=args.services))


if __name__ == "__main__":
    cli()
