"""Email Helper — High-quality email operations with validation.

This module wraps Composio Gmail actions with proper validation,
draft review workflow, and tracking for important threads.

Created: January 7, 2026
Fixes: Blank email bug, CC parameter validation, missing priority searches
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class EmailDraft:
    """Email draft for review before sending."""

    to: str
    subject: str
    body: str
    cc: list[str] = field(default_factory=list)
    bcc: list[str] = field(default_factory=list)
    reply_to_thread: str | None = None

    def validate(self) -> list[str]:
        """Validate the draft and return list of errors."""
        errors = []

        # Required fields
        if not self.to or not self.to.strip():
            errors.append("Recipient email is required")
        elif not self._is_valid_email(self.to):
            errors.append(f"Invalid recipient email: {self.to}")

        if not self.subject or not self.subject.strip():
            errors.append("Subject is required")

        if not self.body or not self.body.strip():
            errors.append("Email body is empty - this will send a BLANK email!")
        elif len(self.body.strip()) < 10:
            errors.append(f"Email body suspiciously short ({len(self.body)} chars)")

        # Validate CC/BCC emails
        for email in self.cc:
            if not self._is_valid_email(email):
                errors.append(f"Invalid CC email: {email}")

        for email in self.bcc:
            if not self._is_valid_email(email):
                errors.append(f"Invalid BCC email: {email}")

        return errors

    def is_valid(self) -> bool:
        """Check if draft is valid for sending."""
        return len(self.validate()) == 0

    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Basic email validation."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email.strip()))

    def preview(self) -> str:
        """Generate a preview of the email for review."""
        lines = [
            "=" * 60,
            "📧 EMAIL DRAFT PREVIEW",
            "=" * 60,
            f"TO: {self.to}",
        ]
        if self.cc:
            lines.append(f"CC: {', '.join(self.cc)}")
        if self.bcc:
            lines.append(f"BCC: {', '.join(self.bcc)}")
        lines.extend(
            [
                f"SUBJECT: {self.subject}",
                "-" * 60,
                self.body,
                "=" * 60,
            ]
        )
        return "\n".join(lines)


@dataclass
class EmailSearchResult:
    """Structured email search result."""

    message_id: str
    sender: str
    subject: str
    date: str
    snippet: str
    labels: list[str]
    is_unread: bool
    is_starred: bool
    is_important: bool

    @classmethod
    def from_api_response(cls, msg: dict[str, Any]) -> EmailSearchResult:
        """Create from Composio API response."""
        labels = msg.get("labelIds", [])
        sender = msg.get("sender", "Unknown")
        # Clean up sender
        if "<" in sender:
            sender = sender.split("<")[0].strip()

        return cls(
            message_id=msg.get("messageId", ""),
            sender=sender[:50],
            subject=msg.get("subject", "(no subject)")[:80],
            date=msg.get("messageTimestamp", ""),
            snippet=msg.get("messageText", "")[:200],
            labels=labels,
            is_unread="UNREAD" in labels,
            is_starred="STARRED" in labels,
            is_important="IMPORTANT" in labels,
        )


# =============================================================================
# EMAIL HELPER SERVICE
# =============================================================================


class EmailHelper:
    """High-quality email operations with validation and tracking.

    Usage:
        helper = EmailHelper()
        await helper.initialize()

        # Check email (starred first!)
        results = await helper.check_email()

        # Draft and review before sending
        draft = helper.create_draft(
            to="bobby@example.com",
            subject="Re: Topic",
            body="Hello...",
            cc=["ryan@example.com"]
        )
        print(draft.preview())  # Review first!
        if draft.is_valid():
            await helper.send(draft)
    """

    def __init__(self) -> None:
        self._service = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize the email helper."""
        from kagami.core.services.composio import get_composio_service

        self._service = get_composio_service()
        self._initialized = await self._service.initialize()
        return self._initialized

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
        cc: list[str] | str | None = None,
        bcc: list[str] | str | None = None,
        reply_to_thread: str | None = None,
    ) -> EmailDraft:
        """Create an email draft for review.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body text
            cc: CC recipients (string or list)
            bcc: BCC recipients (string or list)
            reply_to_thread: Thread ID if this is a reply

        Returns:
            EmailDraft object for review before sending
        """
        # Normalize CC/BCC to lists
        cc_list = self._normalize_recipients(cc)
        bcc_list = self._normalize_recipients(bcc)

        return EmailDraft(
            to=to.strip(),
            subject=subject.strip(),
            body=body,
            cc=cc_list,
            bcc=bcc_list,
            reply_to_thread=reply_to_thread,
        )

    @staticmethod
    def _normalize_recipients(recipients: list[str] | str | None) -> list[str]:
        """Normalize recipients to a list."""
        if recipients is None:
            return []
        if isinstance(recipients, str):
            return [recipients.strip()] if recipients.strip() else []
        return [r.strip() for r in recipients if r.strip()]

    async def send(self, draft: EmailDraft, force: bool = False) -> dict[str, Any]:
        """Send an email after validation.

        Args:
            draft: EmailDraft object (must be valid)
            force: If True, send even with validation warnings

        Returns:
            Result dict with success status and message ID
        """
        if not self._initialized:
            return {"success": False, "error": "Email helper not initialized"}

        # Validate
        errors = draft.validate()
        if errors and not force:
            return {
                "success": False,
                "error": "Validation failed",
                "validation_errors": errors,
                "hint": "Review draft.preview() and fix issues, or use force=True",
            }

        # Build parameters
        params: dict[str, Any] = {
            "recipient_email": draft.to,
            "subject": draft.subject,
            "body": draft.body,
        }

        # CC/BCC must be lists (Composio API requirement)
        if draft.cc:
            params["cc"] = draft.cc
        if draft.bcc:
            params["bcc"] = draft.bcc

        # Execute
        try:
            result = await self._service.execute_action("GMAIL_SEND_EMAIL", params)

            if result.get("success"):
                logger.info(f"✅ Email sent to {draft.to}: {draft.subject}")
                return {
                    "success": True,
                    "message_id": result.get("result", {}).get("data", {}).get("id"),
                    "thread_id": result.get("result", {}).get("data", {}).get("threadId"),
                }
            else:
                logger.error(f"❌ Email send failed: {result}")
                return {"success": False, "error": result.get("error", "Unknown error")}

        except Exception as e:
            logger.exception("Email send exception")
            return {"success": False, "error": str(e)}

    async def check_email(self, max_results: int = 10) -> dict[str, list[EmailSearchResult]]:
        """Check email using priority-ordered searches.

        Returns emails in priority order:
        1. Starred (explicit priority markers)
        2. Important (non-promo)
        3. Unread (filtered)

        Returns:
            Dict with 'starred', 'important', 'unread' keys
        """
        if not self._initialized:
            return {"starred": [], "important": [], "unread": []}

        results = {}

        # Priority searches in order
        searches = [
            ("starred", "is:starred"),
            ("important", "is:important -category:promotions"),
            ("unread", "is:unread -category:promotions -category:social"),
        ]

        for key, query in searches:
            try:
                response = await self._service.execute_action(
                    "GMAIL_FETCH_EMAILS",
                    {"query": query, "max_results": max_results},
                )

                if response.get("success"):
                    messages = response.get("result", {}).get("data", {}).get("messages", [])
                    results[key] = [EmailSearchResult.from_api_response(msg) for msg in messages]
                else:
                    results[key] = []
            except Exception as e:
                logger.warning(f"Email search '{key}' failed: {e}")
                results[key] = []

        return results

    async def search(self, query: str, max_results: int = 10) -> list[EmailSearchResult]:
        """Search emails with a custom query.

        Args:
            query: Gmail search query
            max_results: Maximum results to return

        Returns:
            List of EmailSearchResult objects
        """
        if not self._initialized:
            return []

        try:
            response = await self._service.execute_action(
                "GMAIL_FETCH_EMAILS",
                {"query": query, "max_results": max_results},
            )

            if response.get("success"):
                messages = response.get("result", {}).get("data", {}).get("messages", [])
                return [EmailSearchResult.from_api_response(msg) for msg in messages]
            return []
        except Exception as e:
            logger.warning(f"Email search failed: {e}")
            return []

    async def get_thread(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        """Get full email thread details.

        Args:
            query: Gmail search query to find the thread
            max_results: Maximum messages to return

        Returns:
            List of full message dicts with body content
        """
        if not self._initialized:
            return []

        try:
            response = await self._service.execute_action(
                "GMAIL_FETCH_EMAILS",
                {"query": query, "max_results": max_results},
            )

            if response.get("success"):
                return response.get("result", {}).get("data", {}).get("messages", [])
            return []
        except Exception as e:
            logger.warning(f"Get thread failed: {e}")
            return []


# =============================================================================
# SINGLETON
# =============================================================================

_email_helper: EmailHelper | None = None


def get_email_helper() -> EmailHelper:
    """Get the singleton EmailHelper instance."""
    global _email_helper
    if _email_helper is None:
        _email_helper = EmailHelper()
    return _email_helper


__all__ = [
    "EmailDraft",
    "EmailHelper",
    "EmailSearchResult",
    "get_email_helper",
]
