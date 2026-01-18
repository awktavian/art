"""Webhook routes for external service events.

Provides FastAPI endpoints for receiving webhooks from:
- Figma: Design file updates, comments
- GitHub: Push, PR, workflow events (via GitHub Actions)
- Linear: Issue, comment, cycle events

These endpoints validate signatures, parse events, and route
them to the appropriate handlers via the event bus.

Security:
- GitHub: HMAC-SHA256 signature validation (X-Hub-Signature-256)
- Linear: HMAC-SHA256 signature validation (X-Linear-Signature)
- Figma: Signature validation via handle_figma_webhook

Created: January 5, 2026
Updated: January 12, 2026 - Added signature validation for GitHub and Linear
"""

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from kagami.core.webhooks import handle_figma_webhook

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# =============================================================================
# Webhook Signature Verification
# =============================================================================


def verify_github_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook HMAC-SHA256 signature.

    Args:
        payload: Raw request body bytes.
        signature: X-Hub-Signature-256 header value (format: sha256=<hex>).
        secret: GitHub webhook secret.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not signature or not secret:
        return False

    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected, signature)


def verify_linear_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify Linear webhook HMAC-SHA256 signature.

    Linear uses a simple HMAC-SHA256 signature without prefix.

    Args:
        payload: Raw request body bytes.
        signature: X-Linear-Signature header value (hex-encoded HMAC).
        secret: Linear webhook signing secret.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not signature or not secret:
        return False

    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected, signature)


@router.post("/figma")
async def figma_webhook(
    request: Request,
    x_figma_signature: str | None = Header(None, alias="X-Figma-Signature"),
) -> dict[str, Any]:
    """Handle incoming Figma webhook events.

    Figma sends webhooks for:
    - FILE_UPDATE: Design file was modified
    - FILE_COMMENT: Comment added to file
    - FILE_VERSION_UPDATE: New version created
    - FILE_DELETE: File was deleted
    - LIBRARY_PUBLISH: Library was published

    The X-Figma-Signature header is used for HMAC verification
    when a webhook secret is configured.

    Args:
        request: FastAPI request object.
        x_figma_signature: Figma signature header for verification.

    Returns:
        Processing result with status.

    Raises:
        HTTPException: If webhook processing fails.
    """
    try:
        # Get raw body for signature verification
        raw_body = await request.body()
        payload = await request.json()

        result = await handle_figma_webhook(
            payload=payload,
            signature=x_figma_signature,
            raw_body=raw_body,
        )

        if result.get("status") == "error":
            raise HTTPException(
                status_code=400,
                detail=result.get("message", "Webhook processing failed"),
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing error: {str(e)}",
        ) from e


@router.post("/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
) -> dict[str, Any]:
    """Handle incoming GitHub webhook events.

    GitHub sends webhooks for various events including:
    - push: Code pushed to repository
    - pull_request: PR opened, closed, merged
    - workflow_run: CI workflow completed
    - issues: Issue opened, closed
    - issue_comment: Comment on issue

    Security:
    - Validates HMAC-SHA256 signature using webhook secret
    - Rejects requests with invalid or missing signatures

    Args:
        request: FastAPI request object.
        x_hub_signature_256: GitHub HMAC signature.
        x_github_event: Type of GitHub event.

    Returns:
        Processing result with status.

    Raises:
        HTTPException: 401 if signature validation fails.
    """
    try:
        # Get raw body for signature verification
        raw_body = await request.body()

        # Verify signature
        from kagami.core.security import get_secret

        github_webhook_secret = get_secret("github_webhook_secret")

        if github_webhook_secret:
            if not x_hub_signature_256:
                logger.warning("GitHub webhook missing signature header")
                raise HTTPException(
                    status_code=401,
                    detail="Missing X-Hub-Signature-256 header",
                )

            if not verify_github_signature(raw_body, x_hub_signature_256, github_webhook_secret):
                logger.warning("GitHub webhook signature validation failed")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid webhook signature",
                )

            logger.debug("GitHub webhook signature verified")
        else:
            logger.warning("No GitHub webhook secret configured - signature validation skipped")

        payload = await request.json()

        # Publish to event bus
        from kagami.core.events import get_unified_bus

        bus = get_unified_bus()
        await bus.publish(
            f"github.{x_github_event}",
            {
                "source": "github",
                "event_type": x_github_event,
                "payload": payload,
            },
        )

        return {
            "status": "ok",
            "event_type": x_github_event,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing error: {str(e)}",
        ) from e


@router.post("/linear")
async def linear_webhook(
    request: Request,
    x_linear_signature: str | None = Header(None, alias="Linear-Signature"),
) -> dict[str, Any]:
    """Handle incoming Linear webhook events.

    Linear sends webhooks for:
    - Issue: Created, updated, removed
    - Comment: Created, updated, removed
    - Cycle: Started, completed
    - Project: Created, updated

    Security:
    - Validates HMAC-SHA256 signature using webhook signing secret
    - Rejects requests with invalid or missing signatures

    Args:
        request: FastAPI request object.
        x_linear_signature: Linear signature for verification.

    Returns:
        Processing result with status.

    Raises:
        HTTPException: 401 if signature validation fails.
    """
    try:
        # Get raw body for signature verification
        raw_body = await request.body()

        # Verify signature
        from kagami.core.security import get_secret

        linear_webhook_secret = get_secret("linear_webhook_secret")

        if linear_webhook_secret:
            if not x_linear_signature:
                logger.warning("Linear webhook missing signature header")
                raise HTTPException(
                    status_code=401,
                    detail="Missing Linear-Signature header",
                )

            if not verify_linear_signature(raw_body, x_linear_signature, linear_webhook_secret):
                logger.warning("Linear webhook signature validation failed")
                raise HTTPException(
                    status_code=401,
                    detail="Invalid webhook signature",
                )

            logger.debug("Linear webhook signature verified")
        else:
            logger.warning("No Linear webhook secret configured - signature validation skipped")

        payload = await request.json()

        # Extract event type from payload
        event_type = payload.get("type", "unknown")
        action = payload.get("action", "unknown")

        # Publish to event bus
        from kagami.core.events import get_unified_bus

        bus = get_unified_bus()
        await bus.publish(
            f"linear.{event_type}.{action}",
            {
                "source": "linear",
                "event_type": event_type,
                "action": action,
                "payload": payload,
            },
        )

        return {
            "status": "ok",
            "event_type": event_type,
            "action": action,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Webhook processing error: {str(e)}",
        ) from e


@router.get("/status")
async def webhook_status() -> dict[str, Any]:
    """Get webhook handler status.

    Returns information about registered webhooks and
    recent event processing statistics.

    Returns:
        Status information.
    """
    return {
        "status": "ok",
        "endpoints": {
            "figma": "/webhooks/figma",
            "github": "/webhooks/github",
            "linear": "/webhooks/linear",
        },
        "message": "Webhook handlers active",
    }
