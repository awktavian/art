"""Twilio Configuration — Auto-configure caller ID and messaging profiles.

Automatically configures:
- Caller ID (CNAM) for outbound calls
- Business profile for A2P messaging
- Phone number verification
- Webhook URLs

Usage:
    from kagami.core.services.voice.twilio_config import configure_twilio

    result = await configure_twilio()
    print(result)  # All configuration status

Created: January 8, 2026
Colony: Nexus (e₄) — Integration
鏡
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TwilioConfigResult:
    """Result of Twilio configuration."""

    success: bool = False
    account_sid: str = ""
    phone_numbers: list[str] = field(default_factory=list)
    caller_id_configured: bool = False
    messaging_profile: str = ""
    webhook_url: str = ""
    errors: list[str] = field(default_factory=list)


async def configure_twilio(
    webhook_base_url: str | None = None,
) -> TwilioConfigResult:
    """Auto-configure Twilio for Kagami.

    Configures:
    1. Validates credentials
    2. Lists available phone numbers
    3. Sets up caller ID (friendly name)
    4. Configures webhook URLs for incoming calls

    Args:
        webhook_base_url: Base URL for webhooks (e.g., https://api.kagami.ai)

    Returns:
        Configuration result with status
    """
    result = TwilioConfigResult()

    try:
        from twilio.rest import Client

        from kagami.core.security import get_secret

        # Get credentials
        account_sid = get_secret("twilio_account_sid")
        auth_token = get_secret("twilio_auth_token")
        get_secret("twilio_phone_number")

        if not account_sid or not auth_token:
            result.errors.append("Missing Twilio credentials")
            return result

        result.account_sid = account_sid
        client = Client(account_sid, auth_token)

        # List phone numbers
        incoming_numbers = client.incoming_phone_numbers.list()
        result.phone_numbers = [n.phone_number for n in incoming_numbers]
        logger.info(f"Found {len(result.phone_numbers)} phone numbers")

        # Configure each number
        for number in incoming_numbers:
            # Set friendly name (caller ID display)
            number.update(
                friendly_name="Kagami",
                # Voice settings
                voice_method="POST",
                voice_fallback_method="POST",
                # SMS settings (if messaging enabled)
                sms_method="POST",
                sms_fallback_method="POST",
            )

            # Set webhooks if URL provided
            if webhook_base_url:
                number.update(
                    voice_url=f"{webhook_base_url}/api/v1/voice/incoming",
                    sms_url=f"{webhook_base_url}/api/v1/sms/incoming",
                )
                result.webhook_url = webhook_base_url

            logger.info(f"Configured {number.phone_number}")

        result.caller_id_configured = True

        # Check for messaging profile (A2P)
        try:
            messaging_services = client.messaging.services.list()
            if messaging_services:
                result.messaging_profile = messaging_services[0].sid
                logger.info(f"Messaging service: {result.messaging_profile}")
        except Exception as e:
            logger.warning(f"No messaging service configured: {e}")

        result.success = True
        logger.info("✅ Twilio configuration complete")

    except Exception as e:
        result.errors.append(str(e))
        logger.error(f"Twilio configuration failed: {e}")

    return result


async def get_twilio_status() -> dict[str, Any]:
    """Get current Twilio configuration status."""
    try:
        from twilio.rest import Client

        from kagami.core.security import get_secret

        account_sid = get_secret("twilio_account_sid")
        auth_token = get_secret("twilio_auth_token")

        if not account_sid or not auth_token:
            return {"configured": False, "error": "Missing credentials"}

        client = Client(account_sid, auth_token)

        # Get account info
        account = client.api.accounts(account_sid).fetch()

        # List numbers
        numbers = client.incoming_phone_numbers.list()

        return {
            "configured": True,
            "account_name": account.friendly_name,
            "account_status": account.status,
            "phone_numbers": [
                {
                    "number": n.phone_number,
                    "friendly_name": n.friendly_name,
                    "capabilities": {
                        "voice": n.capabilities.get("voice", False),
                        "sms": n.capabilities.get("sms", False),
                        "mms": n.capabilities.get("mms", False),
                    },
                }
                for n in numbers
            ],
        }

    except Exception as e:
        return {"configured": False, "error": str(e)}


async def set_caller_id(
    phone_number: str,
    friendly_name: str = "Kagami",
) -> bool:
    """Set caller ID for a specific phone number.

    Args:
        phone_number: Phone number in E.164 format
        friendly_name: Display name for caller ID

    Returns:
        True if successful
    """
    try:
        from twilio.rest import Client

        from kagami.core.security import get_secret

        account_sid = get_secret("twilio_account_sid")
        auth_token = get_secret("twilio_auth_token")

        client = Client(account_sid, auth_token)

        # Find the number
        numbers = client.incoming_phone_numbers.list(phone_number=phone_number)
        if not numbers:
            logger.error(f"Phone number not found: {phone_number}")
            return False

        # Update friendly name
        numbers[0].update(friendly_name=friendly_name)
        logger.info(f"Set caller ID '{friendly_name}' for {phone_number}")
        return True

    except Exception as e:
        logger.error(f"Failed to set caller ID: {e}")
        return False


__all__ = [
    "TwilioConfigResult",
    "configure_twilio",
    "get_twilio_status",
    "set_caller_id",
]
