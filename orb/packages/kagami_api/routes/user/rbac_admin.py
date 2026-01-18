from __future__ import annotations

"""RBAC administration API - custom roles and permissions.

Enterprise feature for fine-grained access control.
"""
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from kagami.core.database.connection import get_db
from kagami.core.database.models import Base
from kagami.core.safety.cbf_integration import check_cbf_for_operation
from pydantic import BaseModel
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from kagami_api.audit_logger import AuditEventType, AuditSeverity, audit_event
from kagami_api.routes.user.auth import get_current_user


class RoleCreate(BaseModel):
    """Create custom role."""

    name: str
    description: str | None = None
    permissions: list[str]
    inherits_from: str | None = None


class RoleAssign(BaseModel):
    """Assign role to user."""

    user_id: int
    role_name: str
    expires_days: int | None = None


# SQLAlchemy models defined at module level to avoid redefinition warnings
class CustomRole(Base):
    """Custom role definitions."""

    __tablename__ = "custom_roles"
    __table_args__ = {"extend_existing": True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id = Column(UUID(as_uuid=True), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    permissions = Column(Text, nullable=False)
    inherits_from = Column(String(100), nullable=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserRoleAssignment(Base):
    """User to role assignments."""

    __tablename__ = "user_role_assignments"
    __table_args__ = {"extend_existing": True}
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    role_name = Column(String(100), nullable=False)
    granted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    granted_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/user/rbac", tags=["user", "rbac"])

    @router.post("/roles")
    async def create_role(
        body: RoleCreate,
        user: dict[str, Any] = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Create custom role."""
        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.rbac.create_role",
            action="create",
            target="role",
            params=body.model_dump(),
            metadata={"endpoint": "/api/user/rbac/roles", "role_name": body.name},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        user_id = int(user.get("user_id", 0))
        existing = db.query(CustomRole).filter(CustomRole.name == body.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Role name already exists")

        role = CustomRole(
            name=body.name,
            description=body.description,
            permissions=json.dumps(body.permissions),
            inherits_from=body.inherits_from,
            created_by=user_id,
        )
        db.add(role)
        db.commit()
        db.refresh(role)

        audit_event(
            AuditEventType.ADMIN_ROLE_CHANGE,
            user_id=str(user_id),
            severity=AuditSeverity.HIGH,
            details={
                "action": "create_role",
                "role_name": body.name,
                "permissions": body.permissions,
            },
        )
        return {
            "ok": True,
            "role": {"id": role.id, "name": role.name, "permissions": body.permissions},
        }

    return router
