"""Email Monitoring API Routes.

Provides REST endpoints for managing email watch rules and service request tracking.
Integrates with EmailMonitorService for proactive email monitoring.

Endpoints:
- GET  /email/status - Get email monitor status and stats
- GET  /email/rules - List all watch rules
- POST /email/rules - Add a new watch rule
- GET  /email/service-requests - List tracked service requests
- POST /email/service-requests - Track a new service request (primary interface)
- GET  /email/pending - Get service requests awaiting responses

INTENT INTEGRATION:
===================
The TRACK intent verb routes here for email-related tracking:
- "track this email thread" → POST /email/service-requests
- "track responses from coffeephysics.com" → POST /email/rules

Created: January 4, 2026
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from kagami.core.services.email_monitor import (
    EmailMonitorService,
    EmailPriority,
    ServiceRequestCategory,
    WatchRule,
    get_email_monitor,
)
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/email", tags=["email"])


# =============================================================================
# SCHEMAS
# =============================================================================


class WatchRuleCreate(BaseModel):
    """Create a new watch rule."""

    name: str = Field(..., description="Unique name for the rule")
    description: str = Field("", description="Human-readable description")
    from_domains: list[str] = Field(default_factory=list, description="Domains to watch")
    from_addresses: list[str] = Field(default_factory=list, description="Email addresses to watch")
    subject_contains: list[str] = Field(default_factory=list, description="Subject keywords")
    thread_ids: list[str] = Field(default_factory=list, description="Gmail thread IDs to track")
    priority: str = Field("normal", description="Alert priority: low, normal, high, urgent")
    poll_interval_seconds: int = Field(300, description="Seconds between polls")


class ServiceRequestCreate(BaseModel):
    """Create a service request tracker.

    This is the primary interface for tracking vendor/contractor conversations.
    Provide thread IDs from sent emails to monitor for responses.

    Example:
        {
            "name": "lelit_repair",
            "description": "Lelit Bianca espresso machine repair",
            "thread_ids": ["19b8a63dfe6ec714"],
            "category": "appliance_repair",
            "from_domains": ["coffeephysics.com"]
        }
    """

    name: str = Field(..., description="Unique identifier for this service request")
    description: str = Field(..., description="Human-readable description")
    thread_ids: list[str] = Field(..., description="Gmail thread IDs to monitor")
    category: str = Field(
        "general",
        description="Category: appliance_repair, home_contractor, vehicle_service, "
        "furniture, technology, financial, general",
    )
    from_domains: list[str] = Field(
        default_factory=list, description="Expected response domains (optional)"
    )
    subject_keywords: list[str] = Field(
        default_factory=list, description="Subject keywords to match (optional)"
    )
    priority: str = Field("high", description="Alert priority: low, normal, high, urgent")
    poll_interval: int = Field(180, description="Seconds between checks (default 3 min)")


class ServiceRequestStatus(BaseModel):
    """Service request tracking status."""

    name: str
    description: str
    category: str
    thread_count: int
    initiated_date: str
    matches_found: int
    last_response_time: float | None
    enabled: bool


class EmailMonitorStatus(BaseModel):
    """Email monitor service status."""

    running: bool
    rules_count: int
    rules_enabled: int
    polls_total: int
    emails_checked: int
    alerts_generated: int
    errors: int
    last_poll: float
    service_requests_pending: int


# =============================================================================
# DEPENDENCIES
# =============================================================================


def get_monitor() -> EmailMonitorService:
    """Get the email monitor service."""
    return get_email_monitor()


# =============================================================================
# ROUTES
# =============================================================================


@router.get("/status", response_model=EmailMonitorStatus)
async def get_email_status(monitor: EmailMonitorService = Depends(get_monitor)) -> dict[str, Any]:
    """Get email monitor status and statistics.

    Returns running state, rule counts, and polling statistics.
    """
    stats = monitor.stats
    pending = monitor.get_pending_responses()
    return {
        "running": stats.get("running", False),
        "rules_count": stats.get("rules_count", 0),
        "rules_enabled": stats.get("rules_enabled", 0),
        "polls_total": stats.get("polls_total", 0),
        "emails_checked": stats.get("emails_checked", 0),
        "alerts_generated": stats.get("alerts_generated", 0),
        "errors": stats.get("errors", 0),
        "last_poll": stats.get("last_poll", 0.0),
        "service_requests_pending": len(pending),
    }


@router.get("/rules")
async def list_rules(
    enabled_only: bool = Query(False, description="Only return enabled rules"),
    monitor: EmailMonitorService = Depends(get_monitor),
) -> list[dict[str, Any]]:
    """List all watch rules.

    Returns configuration and status of each rule.
    """
    rules = []
    for rule in monitor._rules:
        if enabled_only and not rule.enabled:
            continue
        rules.append(
            {
                "name": rule.name,
                "description": rule.description,
                "from_domains": rule.from_domains,
                "from_addresses": rule.from_addresses,
                "subject_contains": rule.subject_contains,
                "thread_ids": rule.thread_ids,
                "service_category": rule.service_category.value if rule.service_category else None,
                "priority": rule.priority.value,
                "poll_interval_seconds": rule.poll_interval_seconds,
                "enabled": rule.enabled,
                "matches_found": rule.matches_found,
                "last_checked": rule.last_checked,
            }
        )
    return rules


@router.post("/rules")
async def add_rule(
    rule: WatchRuleCreate,
    monitor: EmailMonitorService = Depends(get_monitor),
) -> dict[str, Any]:
    """Add a new watch rule.

    For service request tracking, use POST /email/service-requests instead.
    """
    # Map priority string to enum
    try:
        priority = EmailPriority[rule.priority.upper()]
    except KeyError:
        priority = EmailPriority.NORMAL

    watch_rule = WatchRule(
        name=rule.name,
        description=rule.description,
        from_domains=rule.from_domains,
        from_addresses=rule.from_addresses,
        subject_contains=rule.subject_contains,
        thread_ids=rule.thread_ids,
        priority=priority,
        poll_interval_seconds=rule.poll_interval_seconds,
    )
    monitor.add_rule(watch_rule)

    return {"status": "created", "rule_name": rule.name}


@router.delete("/rules/{rule_name}")
async def delete_rule(
    rule_name: str,
    monitor: EmailMonitorService = Depends(get_monitor),
) -> dict[str, Any]:
    """Delete a watch rule."""
    rule = monitor.get_rule(rule_name)
    if not rule:
        raise HTTPException(status_code=404, detail=f"Rule '{rule_name}' not found")

    monitor.remove_rule(rule_name)
    return {"status": "deleted", "rule_name": rule_name}


@router.get("/service-requests")
async def list_service_requests(
    category: str | None = Query(None, description="Filter by category"),
    pending_only: bool = Query(False, description="Only return requests awaiting response"),
    monitor: EmailMonitorService = Depends(get_monitor),
) -> list[dict[str, Any]]:
    """List tracked service requests.

    Service requests are email threads where Tim initiated contact with a vendor
    or contractor. When they respond, alerts are generated.

    Categories: appliance_repair, home_contractor, vehicle_service, furniture,
                technology, financial, general
    """
    # Parse category if provided
    cat_filter = None
    if category:
        try:
            cat_filter = ServiceRequestCategory[category.upper()]
        except KeyError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Valid: {[c.value for c in ServiceRequestCategory]}",
            ) from e

    if pending_only:
        requests = monitor.get_active_service_requests()
        if cat_filter:
            requests = [r for r in requests if r.service_category == cat_filter]
    else:
        requests = monitor.get_service_requests(cat_filter)

    return [
        {
            "name": r.name,
            "description": r.description,
            "category": r.service_category.value if r.service_category else "unknown",
            "thread_count": len(r.thread_ids),
            "initiated_date": r.initiated_date,
            "matches_found": r.matches_found,
            "last_response_time": r.last_response_time if r.last_response_time > 0 else None,
            "enabled": r.enabled,
        }
        for r in requests
    ]


@router.post("/service-requests")
async def create_service_request(
    request: ServiceRequestCreate,
    monitor: EmailMonitorService = Depends(get_monitor),
) -> dict[str, Any]:
    """Track a new service request.

    This is the primary interface for monitoring vendor/contractor conversations.
    When a response is received, you'll get a proactive alert.

    How to get thread IDs:
    1. Go to the sent email in Gmail
    2. The thread ID is in the URL after #thread/
    3. Or use: GET /email/recent-sent to find recent outgoing emails

    Example:
        POST /email/service-requests
        {
            "name": "lelit_repair",
            "description": "Lelit Bianca espresso machine repair - leaking issue",
            "thread_ids": ["19b8a63dfe6ec714"],
            "category": "appliance_repair",
            "from_domains": ["coffeephysics.com", "seattlecoffeegear.com"]
        }
    """
    # Map category string to enum
    try:
        category = ServiceRequestCategory[request.category.upper()]
    except KeyError:
        category = ServiceRequestCategory.GENERAL

    # Map priority string to enum
    try:
        priority = EmailPriority[request.priority.upper()]
    except KeyError:
        priority = EmailPriority.HIGH

    # Create the service request via the dedicated method
    monitor.add_service_request(
        name=request.name,
        description=request.description,
        thread_ids=request.thread_ids,
        category=category,
        from_domains=request.from_domains or None,
        subject_keywords=request.subject_keywords or None,
        priority=priority,
        poll_interval=request.poll_interval,
    )

    logger.info(f"📧 Service request created via API: {request.name} ({category.value})")

    return {
        "status": "created",
        "name": request.name,
        "description": request.description,
        "category": category.value,
        "thread_count": len(request.thread_ids),
        "poll_interval": request.poll_interval,
    }


@router.get("/pending")
async def get_pending_responses(
    monitor: EmailMonitorService = Depends(get_monitor),
) -> list[dict[str, Any]]:
    """Get service requests awaiting responses.

    Returns a summary of all active service requests that haven't received
    replies yet. Useful for checking what you're waiting on.
    """
    return monitor.get_pending_responses()


@router.post("/poll")
async def trigger_poll(
    monitor: EmailMonitorService = Depends(get_monitor),
) -> dict[str, Any]:
    """Manually trigger a poll cycle.

    Immediately checks all enabled rules for new emails.
    Returns any alerts generated.
    """
    if not monitor._composio:
        raise HTTPException(status_code=503, detail="Email monitor not initialized")

    alerts = await monitor.poll_once()
    return {
        "status": "polled",
        "alerts_count": len(alerts),
        "alerts": [
            {
                "rule": a.rule_name,
                "sender": a.message.sender_email,
                "subject": a.message.subject,
                "priority": a.priority.value,
            }
            for a in alerts
        ],
    }


# =============================================================================
# INTENT HANDLER INTEGRATION
# =============================================================================


async def handle_track_intent(target: str, metadata: dict[str, Any]) -> dict[str, Any]:
    """Handle TRACK intent for email-related targets.

    Called by the intent router when verb=TRACK and target matches email patterns.

    Examples:
        - TRACK email.thread.19b8a63dfe6ec714
        - TRACK responses.from.coffeephysics.com
        - TRACK service-request.lelit-repair
    """
    monitor = get_email_monitor()

    # Parse target to determine what to track
    if target.startswith("email.thread."):
        thread_id = target.replace("email.thread.", "")
        name = metadata.get("name", f"thread_{thread_id[:8]}")
        description = metadata.get("description", f"Tracking thread {thread_id}")

        monitor.add_service_request(
            name=name,
            description=description,
            thread_ids=[thread_id],
            category=ServiceRequestCategory.GENERAL,
        )
        return {"status": "tracking", "type": "thread", "thread_id": thread_id}

    elif target.startswith("responses.from."):
        domain = target.replace("responses.from.", "")
        name = metadata.get("name", f"domain_{domain.split('.')[0]}")
        description = metadata.get("description", f"Tracking responses from {domain}")

        rule = WatchRule(
            name=name,
            description=description,
            from_domains=[domain],
            priority=EmailPriority.HIGH,
        )
        monitor.add_rule(rule)
        return {"status": "tracking", "type": "domain", "domain": domain}

    return {"status": "error", "message": f"Unknown track target: {target}"}


__all__ = ["handle_track_intent", "router"]
