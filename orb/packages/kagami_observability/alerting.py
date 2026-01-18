"""Unified alerting for Kagami - PagerDuty and Slack integration.

Routes alerts based on severity:
- CRITICAL → PagerDuty (pages on-call)
- WARNING → Slack (team notification)
- INFO → Logged only

Configuration via environment variables:
- PAGERDUTY_API_KEY: PagerDuty Events API v2 integration key
- SLACK_WEBHOOK_URL: Slack incoming webhook URL
- ALERTS_ENABLED: Enable/disable alerting (default: true)

Created: December 27, 2025
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    """Alert payload."""

    severity: AlertSeverity
    title: str
    description: str
    source: str  # Component name
    timestamp: float
    metadata: dict[str, Any] | None = None


# =============================================================================
# PAGERDUTY INTEGRATION
# =============================================================================


class PagerDutyClient:
    """PagerDuty Events API v2 client.

    Sends incidents to PagerDuty for CRITICAL alerts.
    Uses the Events API v2: https://developer.pagerduty.com/docs/events-api-v2/
    """

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize PagerDuty client.

        Args:
            api_key: PagerDuty integration key (Events API v2).
                     Defaults to PAGERDUTY_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("PAGERDUTY_API_KEY")
        self.enabled = bool(self.api_key)

        if not self.enabled:
            logger.warning("PagerDuty not configured (PAGERDUTY_API_KEY not set)")

    def send_alert(self, alert: Alert) -> bool:
        """Send alert to PagerDuty.

        Args:
            alert: Alert to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("PagerDuty disabled, skipping alert: %s", alert.title)
            return False

        try:
            import httpx
        except ImportError:
            logger.error("httpx not installed, cannot send PagerDuty alerts")
            return False

        # Build PagerDuty event payload
        # https://developer.pagerduty.com/docs/events-api-v2/trigger-events/
        payload = {
            "routing_key": self.api_key,
            "event_action": "trigger",
            "payload": {
                "summary": alert.title,
                "severity": self._map_severity(alert.severity),
                "source": alert.source,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(alert.timestamp)),
                "custom_details": {
                    "description": alert.description,
                    **(alert.metadata or {}),
                },
            },
        }

        try:
            response = httpx.post(
                "https://events.pagerduty.com/v2/enqueue",
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()

            logger.info(
                "PagerDuty alert sent: %s (dedup_key=%s)",
                alert.title,
                response.json().get("dedup_key", "unknown"),
            )
            return True

        except Exception as e:
            logger.error("Failed to send PagerDuty alert: %s", e, exc_info=True)
            return False

    @staticmethod
    def _map_severity(severity: AlertSeverity) -> str:
        """Map AlertSeverity to PagerDuty severity.

        PagerDuty severities: critical, error, warning, info
        """
        mapping = {
            AlertSeverity.CRITICAL: "critical",
            AlertSeverity.WARNING: "warning",
            AlertSeverity.INFO: "info",
        }
        return mapping.get(severity, "error")


# =============================================================================
# SLACK INTEGRATION
# =============================================================================


class SlackClient:
    """Slack webhook client.

    Sends notifications to Slack for WARNING and INFO alerts.
    Uses Incoming Webhooks: https://api.slack.com/messaging/webhooks
    """

    def __init__(self, webhook_url: str | None = None) -> None:
        """Initialize Slack client.

        Args:
            webhook_url: Slack incoming webhook URL.
                        Defaults to SLACK_WEBHOOK_URL env var.
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)

        if not self.enabled:
            logger.warning("Slack not configured (SLACK_WEBHOOK_URL not set)")

    def send_alert(self, alert: Alert) -> bool:
        """Send alert to Slack.

        Args:
            alert: Alert to send

        Returns:
            True if sent successfully, False otherwise
        """
        if not self.enabled:
            logger.debug("Slack disabled, skipping alert: %s", alert.title)
            return False

        try:
            import httpx
        except ImportError:
            logger.error("httpx not installed, cannot send Slack alerts")
            return False

        # Build Slack message with Block Kit
        # https://api.slack.com/messaging/composing/layouts
        color = self._get_color(alert.severity)
        emoji = self._get_emoji(alert.severity)

        payload = {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"{emoji} {alert.title}",
                            },
                        },
                        {
                            "type": "section",
                            "fields": [
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Severity:*\n{alert.severity.value.upper()}",
                                },
                                {
                                    "type": "mrkdwn",
                                    "text": f"*Source:*\n{alert.source}",
                                },
                            ],
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*Description:*\n{alert.description}",
                            },
                        },
                    ],
                }
            ]
        }

        # Add metadata if present
        if alert.metadata:
            metadata_text = "\n".join(f"• *{k}:* {v}" for k, v in alert.metadata.items())
            payload["attachments"][0]["blocks"].append(  # type: ignore[attr-defined]
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Metadata:*\n{metadata_text}",
                    },
                }
            )

        try:
            response = httpx.post(
                self.webhook_url,  # type: ignore[arg-type]
                json=payload,
                timeout=10.0,
            )
            response.raise_for_status()

            logger.info("Slack alert sent: %s", alert.title)
            return True

        except Exception as e:
            logger.error("Failed to send Slack alert: %s", e, exc_info=True)
            return False

    @staticmethod
    def _get_color(severity: AlertSeverity) -> str:
        """Get Slack attachment color for severity."""
        mapping = {
            AlertSeverity.CRITICAL: "#FF0000",  # Red
            AlertSeverity.WARNING: "#FFA500",  # Orange
            AlertSeverity.INFO: "#36A64F",  # Green
        }
        return mapping.get(severity, "#808080")  # Gray default

    @staticmethod
    def _get_emoji(severity: AlertSeverity) -> str:
        """Get emoji for severity."""
        mapping = {
            AlertSeverity.CRITICAL: "🚨",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.INFO: "ℹ️",
        }
        return mapping.get(severity, "📢")


# =============================================================================
# UNIFIED ALERT ROUTER
# =============================================================================


class AlertRouter:
    """Routes alerts to appropriate channels based on severity.

    Routing rules:
    - CRITICAL → PagerDuty (pages on-call)
    - WARNING → Slack (team notification)
    - INFO → Logged only (no external alert)
    """

    def __init__(
        self,
        pagerduty_client: PagerDutyClient | None = None,
        slack_client: SlackClient | None = None,
        enabled: bool | None = None,
    ) -> None:
        """Initialize alert router.

        Args:
            pagerduty_client: PagerDuty client (default: auto-create)
            slack_client: Slack client (default: auto-create)
            enabled: Enable/disable alerting (default: ALERTS_ENABLED env var or True)
        """
        self.pagerduty = pagerduty_client or PagerDutyClient()
        self.slack = slack_client or SlackClient()

        if enabled is None:
            enabled = os.getenv("ALERTS_ENABLED", "true").lower() in ("1", "true", "yes", "on")
        self.enabled = enabled

        if not self.enabled:
            logger.warning("Alert routing DISABLED (ALERTS_ENABLED=false)")

    def send_alert(
        self,
        severity: AlertSeverity,
        title: str,
        description: str,
        source: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Send alert via appropriate channel(s).

        Args:
            severity: Alert severity
            title: Short alert title
            description: Detailed description
            source: Source component
            metadata: Optional metadata dict

        Returns:
            True if alert sent successfully (or logging-only), False if failed
        """
        if not self.enabled:
            logger.debug("Alerting disabled, skipping: %s", title)
            return True

        alert = Alert(
            severity=severity,
            title=title,
            description=description,
            source=source,
            timestamp=time.time(),
            metadata=metadata,
        )

        # Route based on severity
        if severity == AlertSeverity.CRITICAL:
            # CRITICAL → PagerDuty (pages on-call)
            logger.critical(
                "CRITICAL ALERT: %s - %s (source=%s)",
                title,
                description,
                source,
            )
            return self.pagerduty.send_alert(alert)

        elif severity == AlertSeverity.WARNING:
            # WARNING → Slack (team notification)
            logger.warning(
                "WARNING ALERT: %s - %s (source=%s)",
                title,
                description,
                source,
            )
            return self.slack.send_alert(alert)

        else:  # INFO
            # INFO → Log only
            logger.info(
                "INFO ALERT: %s - %s (source=%s)",
                title,
                description,
                source,
            )
            return True


# =============================================================================
# FACTORY & SINGLETON
# =============================================================================

_default_router: AlertRouter | None = None


def get_alert_router() -> AlertRouter:
    """Get or create default alert router singleton.

    Returns:
        Default AlertRouter instance
    """
    global _default_router
    if _default_router is None:
        _default_router = AlertRouter()
    return _default_router


def send_critical_alert(
    title: str,
    description: str,
    source: str = "kagami",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Send CRITICAL alert (convenience function).

    Args:
        title: Alert title
        description: Alert description
        source: Source component
        metadata: Optional metadata

    Returns:
        True if sent successfully
    """
    return get_alert_router().send_alert(
        AlertSeverity.CRITICAL,
        title,
        description,
        source,
        metadata,
    )


def send_warning_alert(
    title: str,
    description: str,
    source: str = "kagami",
    metadata: dict[str, Any] | None = None,
) -> bool:
    """Send WARNING alert (convenience function).

    Args:
        title: Alert title
        description: Alert description
        source: Source component
        metadata: Optional metadata

    Returns:
        True if sent successfully
    """
    return get_alert_router().send_alert(
        AlertSeverity.WARNING,
        title,
        description,
        source,
        metadata,
    )


__all__ = [
    "Alert",
    "AlertRouter",
    "AlertSeverity",
    "PagerDutyClient",
    "SlackClient",
    "get_alert_router",
    "send_critical_alert",
    "send_warning_alert",
]
