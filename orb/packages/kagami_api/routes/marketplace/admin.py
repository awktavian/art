import logging
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from kagami.core.database.connection import get_session_factory
from kagami.core.database.models import MarketplacePlugin
from kagami.core.safety import enforce_tier1
from pydantic import BaseModel, Field
from sqlalchemy import func

from kagami_api.rbac import require_admin
from kagami_api.security import Principal

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/admin/marketplace", tags=["admin_marketplace"])

    class HighRiskToolsPolicy(BaseModel):
        tools: list[str] = Field(default_factory=list)

    def _deps_admin() -> None:
        """Return a dependency that enforces admin in runtime, with test bypass.

        - Under pytest (or echo test mode), bypass auth and return an admin principal.
        - Otherwise, delegate to RBAC's require_admin(), resolved at call-time to
          avoid stale imports across module reloads.
        """
        from kagami_api.rbac import require_admin as _require_admin

        return _require_admin()

    class PluginExposureUpdate(BaseModel):
        visibility: str | None = Field(default=None)
        allowed_orgs: list[str] | None = Field(default=None)
        exposure_percent: int | None = Field(default=None, ge=0, le=100)
        release_channel: str | None = Field(default=None)

    class ToolParamWhitelist(BaseModel):
        allowed: list[str] = Field(default_factory=list)

    # Admin endpoints for marketplace management
    @router.post("/policies/high-risk-tools")
    async def set_high_risk_tools_policy(  # type: ignore[no-untyped-def]
        policy: HighRiskToolsPolicy,
        admin: Principal = Depends(require_admin),
    ):
        """Set high-risk tools policy (admin only)."""
        from kagami_api.audit_logger import AuditEventType, AuditSeverity, audit_event

        audit_event(
            AuditEventType.APP_SETTINGS_CHANGE,
            user_id=admin.sub,
            severity=AuditSeverity.HIGH,
            details={"action": "set_high_risk_tools_policy", "tools": policy.tools},
        )
        return {"status": "ok", "policy": policy.model_dump()}

    @router.post("/policies/tool-param-whitelist/{tool_name}")
    async def set_tool_param_whitelist(  # type: ignore[no-untyped-def]
        tool_name: str,
        whitelist: ToolParamWhitelist,
        admin: Principal = Depends(require_admin),
    ):
        """Set parameter whitelist for a tool (admin only)."""
        from kagami_api.audit_logger import AuditEventType, AuditSeverity, audit_event

        audit_event(
            AuditEventType.APP_SETTINGS_CHANGE,
            user_id=admin.sub,
            severity=AuditSeverity.HIGH,
            details={
                "action": "set_tool_param_whitelist",
                "tool_name": tool_name,
                "allowed": whitelist.allowed,
            },
        )
        return {"status": "ok", "tool": tool_name, "whitelist": whitelist.model_dump()}

    @router.post("/plugins/{plugin_id}/exposure")
    async def update_plugin_exposure(  # type: ignore[no-untyped-def]
        plugin_id: str,
        update: PluginExposureUpdate,
        admin: Principal = Depends(require_admin),
    ):
        """Update plugin exposure settings (admin only)."""
        from kagami_api.audit_logger import AuditEventType, AuditSeverity, audit_event

        audit_event(
            AuditEventType.APP_SETTINGS_CHANGE,
            user_id=admin.sub,
            severity=AuditSeverity.HIGH,
            details={
                "action": "update_plugin_exposure",
                "plugin_id": plugin_id,
                "update": update.model_dump(),
            },
        )
        return {"status": "ok", "plugin_id": plugin_id, "update": update.model_dump()}

    # ============= Plugin Approval/Rejection Endpoints =============

    class PluginRejection(BaseModel):
        """Rejection reason for a plugin."""

        reason: str = Field(..., min_length=10, max_length=1000)
        notes: dict[str, Any] = Field(default_factory=dict)

    @router.get("/plugins/pending")
    async def list_pending_plugins(  # type: ignore[no-untyped-def]
        page: int = 1,
        page_size: int = 20,
        admin: Principal = Depends(require_admin),
    ):
        """List plugins awaiting approval (admin only)."""
        db = get_session_factory()()
        try:
            total = (
                db.query(func.count(MarketplacePlugin.id))
                .filter(MarketplacePlugin.status == "pending")
                .scalar()
                or 0
            )

            offset = (page - 1) * page_size
            plugins = (
                db.query(MarketplacePlugin)
                .filter(MarketplacePlugin.status == "pending")
                .order_by(MarketplacePlugin.submitted_at.asc())  # FIFO
                .offset(offset)
                .limit(page_size)
                .all()
            )

            return {
                "plugins": [
                    {
                        "id": str(p.id),
                        "name": p.name,
                        "description": p.description[:200] + "..."
                        if len(p.description) > 200
                        else p.description,
                        "category": p.category,
                        "version": p.version,
                        "pricing_model": p.pricing_model,
                        "price_usd": p.price_usd,
                        "author_id": p.author_id,
                        "author_name": p.author_name,
                        "repository_url": p.repository_url,
                        "submitted_at": p.submitted_at.isoformat() if p.submitted_at else None,
                        "required_permissions": p.required_permissions or [],
                    }
                    for p in plugins
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": (total + page_size - 1) // page_size if total else 0,
            }
        except Exception as e:
            logger.error(f"Failed to list pending plugins: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list pending plugins") from None
        finally:
            db.close()

    @router.post("/plugins/{plugin_id}/approve")
    @enforce_tier1("rate_limit")
    async def approve_plugin(  # type: ignore[no-untyped-def]
        plugin_id: str,
        admin: Principal = Depends(require_admin),
    ):
        """Approve a pending plugin (admin only).

        Changes status to 'approved' and sets approved_at timestamp.
        """
        from kagami_api.audit_logger import AuditEventType, AuditSeverity, audit_event

        db = get_session_factory()()
        try:
            plugin_uuid = UUID(plugin_id)
            plugin = db.query(MarketplacePlugin).filter(MarketplacePlugin.id == plugin_uuid).first()

            if not plugin:
                raise HTTPException(status_code=404, detail="Plugin not found")

            if plugin.status == "approved":
                return {"status": "already_approved", "plugin_id": plugin_id}

            if plugin.status == "rejected":
                raise HTTPException(
                    status_code=400,
                    detail="Plugin was previously rejected. Author must resubmit.",
                )

            plugin.status = "approved"
            plugin.approved_at = datetime.utcnow()
            plugin.rejection_reason = None
            db.commit()

            audit_event(
                AuditEventType.APP_SETTINGS_CHANGE,
                user_id=admin.sub,
                severity=AuditSeverity.MEDIUM,
                details={
                    "action": "approve_plugin",
                    "plugin_id": plugin_id,
                    "plugin_name": plugin.name,
                    "author_id": plugin.author_id,
                },
            )

            return {
                "status": "approved",
                "plugin_id": plugin_id,
                "plugin_name": plugin.name,
                "approved_at": plugin.approved_at.isoformat(),
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to approve plugin: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to approve plugin") from None
        finally:
            db.close()

    @router.post("/plugins/{plugin_id}/reject")
    @enforce_tier1("rate_limit")
    async def reject_plugin(  # type: ignore[no-untyped-def]
        plugin_id: str,
        rejection: PluginRejection,
        admin: Principal = Depends(require_admin),
    ):
        """Reject a pending plugin (admin only).

        Changes status to 'rejected' and records the rejection reason.
        """
        from kagami_api.audit_logger import AuditEventType, AuditSeverity, audit_event

        db = get_session_factory()()
        try:
            plugin_uuid = UUID(plugin_id)
            plugin = db.query(MarketplacePlugin).filter(MarketplacePlugin.id == plugin_uuid).first()

            if not plugin:
                raise HTTPException(status_code=404, detail="Plugin not found")

            if plugin.status == "approved":
                raise HTTPException(
                    status_code=400,
                    detail="Cannot reject an approved plugin. Use 'unpublish' instead.",
                )

            plugin.status = "rejected"
            plugin.rejected_at = datetime.utcnow()
            plugin.rejection_reason = rejection.reason
            plugin.moderation_notes = {
                **(plugin.moderation_notes or {}),
                "rejected_by": admin.sub,
                "rejected_at": datetime.utcnow().isoformat(),
                **rejection.notes,
            }
            db.commit()

            audit_event(
                AuditEventType.APP_SETTINGS_CHANGE,
                user_id=admin.sub,
                severity=AuditSeverity.MEDIUM,
                details={
                    "action": "reject_plugin",
                    "plugin_id": plugin_id,
                    "plugin_name": plugin.name,
                    "author_id": plugin.author_id,
                    "reason": rejection.reason,
                },
            )

            return {
                "status": "rejected",
                "plugin_id": plugin_id,
                "plugin_name": plugin.name,
                "rejected_at": plugin.rejected_at.isoformat(),
                "reason": rejection.reason,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to reject plugin: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to reject plugin") from None
        finally:
            db.close()

    @router.post("/plugins/{plugin_id}/unpublish")
    @enforce_tier1("rate_limit")
    async def unpublish_plugin(  # type: ignore[no-untyped-def]
        plugin_id: str,
        admin: Principal = Depends(require_admin),
    ):
        """Unpublish an approved plugin (admin only).

        Changes status back to 'pending' for re-review.
        """
        from kagami_api.audit_logger import AuditEventType, AuditSeverity, audit_event

        db = get_session_factory()()
        try:
            plugin_uuid = UUID(plugin_id)
            plugin = db.query(MarketplacePlugin).filter(MarketplacePlugin.id == plugin_uuid).first()

            if not plugin:
                raise HTTPException(status_code=404, detail="Plugin not found")

            if plugin.status != "approved":
                raise HTTPException(
                    status_code=400,
                    detail=f"Plugin is '{plugin.status}', not 'approved'. Cannot unpublish.",
                )

            plugin.status = "pending"
            plugin.moderation_notes = {
                **(plugin.moderation_notes or {}),
                "unpublished_by": admin.sub,
                "unpublished_at": datetime.utcnow().isoformat(),
            }
            db.commit()

            audit_event(
                AuditEventType.APP_SETTINGS_CHANGE,
                user_id=admin.sub,
                severity=AuditSeverity.HIGH,
                details={
                    "action": "unpublish_plugin",
                    "plugin_id": plugin_id,
                    "plugin_name": plugin.name,
                    "author_id": plugin.author_id,
                },
            )

            return {
                "status": "unpublished",
                "plugin_id": plugin_id,
                "plugin_name": plugin.name,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to unpublish plugin: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to unpublish plugin") from None
        finally:
            db.close()

    return router
