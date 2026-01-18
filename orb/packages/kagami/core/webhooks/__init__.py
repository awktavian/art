"""Webhook handlers for external service events.

This module provides FastAPI-compatible webhook handlers for receiving
real-time events from external services:
- Figma: File updates, comments
- GitHub: Push, PR, workflow events
- Linear: Issue, comment, cycle events

Architecture:
- Webhook handlers validate signatures and parse events
- Events are published to the UnifiedE8Bus for colony routing
- Auto-triggers process events for cross-domain actions

Created: January 5, 2026
"""

from kagami.core.webhooks.figma_webhook import (
    FigmaWebhookHandler,
    handle_figma_webhook,
)

__all__ = [
    "FigmaWebhookHandler",
    "handle_figma_webhook",
]
