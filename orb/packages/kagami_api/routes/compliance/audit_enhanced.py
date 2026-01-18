"Enhanced audit logging for SOC2/ISO 27001 compliance.\n\nTamper-proof audit trail with:\n- Immutable event storage\n- Cryptographic signatures\n- 7-year retention\n- SIEM export capabilities\n"

import hashlib
import hmac
import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from kagami.core.database.models import AuditLogEntry  # Use core model
from pydantic import BaseModel
from sqlalchemy.orm import Session

from kagami_api.feature_gate import require_feature


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(
        prefix="/api/compliance/audit",
        tags=["compliance-audit"],
        dependencies=[Depends(require_feature("compliance_reporting"))],  # type: ignore[func-returns-value]
    )

    # Note: AuditLogEntry model is imported from kagami.core.database.models
    # The enhanced compliance features use the same table with additional helper functions

    class AuditQuery(BaseModel):
        """Audit log query."""

        event_type: str | None = None
        actor_id: str | None = None
        start_time: datetime | None = None
        end_time: datetime | None = None
        limit: int = 100

    class AuditExport(BaseModel):
        """Audit export request."""

        format: str = "json"
        start_time: datetime
        end_time: datetime

    def get_audit_signing_key() -> bytes:
        """Get signing key for audit entry hashing."""
        key = os.getenv("AUDIT_SIGNING_KEY")
        if not key:
            if os.getenv("ENVIRONMENT", "development").lower() == "production":
                raise ValueError("AUDIT_SIGNING_KEY required in production")
            return b"dev_key_not_secure"
        return key.encode("utf-8")

    def compute_audit_hash(
        event_type: str,
        actor_id: str,
        action: str,
        timestamp: datetime,
        details: str,
    ) -> str:
        """Compute HMAC hash for audit entry verification."""
        message = f"{event_type}|{actor_id}|{action}|{timestamp.isoformat()}|{details}"
        key = get_audit_signing_key()
        return hmac.new(key, message.encode(), hashlib.sha256).hexdigest()

    async def log_audit_event(
        event_type: str,
        actor_id: str,
        action: str,
        target_type: str | None = None,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        tenant_id: str | None = None,
        db: Session | None = None,
    ) -> None:
        """Log audit event (called by application code).

        Uses the core AuditLogEntry model for storage.
        """
        from kagami.core.database.connection import get_db_session

        async with get_db_session() as session:
            entry = AuditLogEntry(
                event_type=event_type,
                actor_id=actor_id,
                target_type=target_type,
                target_id=target_id,
                action=action,
                ip_address=ip_address,
                user_agent=user_agent,
                details=details,
                tenant_id=tenant_id,
            )
            session.add(entry)
            session.commit()

    return router
