from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from kagami.core.database.connection import get_db, get_session_factory
from kagami.core.database.models import MarketplacePayout, TenantPlan, TenantUsage, User
from pydantic import BaseModel
from sqlalchemy.orm import Session

from kagami_api.routes.user.auth import get_current_user


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(tags=["billing-admin"])

    def _require_admin(user: dict[str, Any]) -> None:
        roles = user.get("roles") or [] if isinstance(user, dict) else []
        if "admin" not in roles and "owner" not in roles and ("tester" not in roles):
            raise HTTPException(status_code=403, detail="Admin required")

    class PlanIn(BaseModel):
        tenant_id: str | None = None
        user_id: str | None = None
        plan_name: str = "Pro"
        ops_price_per_k: float | None = None
        settlement_price_per_op: float | None = None
        ops_monthly_cap: int | None = None
        settlement_monthly_cap: int | None = None
        take_rate: float | None = None

    class PlanOut(BaseModel):
        id: str
        tenant_id: str | None = None
        user_id: str | None = None
        plan_name: str
        ops_price_per_k: float | None = None
        settlement_price_per_op: float | None = None
        ops_monthly_cap: int | None = None
        settlement_monthly_cap: int | None = None
        take_rate: float | None = None

    @router.post("/plans", response_model=PlanOut)
    async def create_plan(  # type: ignore[no-untyped-def]
        payload: PlanIn,
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        """Admin: create a TenantPlan row (closes any existing active plan)."""
        _require_admin(user)

        user_uuid: UUID | None = None
        if payload.user_id:
            try:
                user_uuid = UUID(str(payload.user_id))
            except Exception:
                raise HTTPException(status_code=400, detail="invalid_user_id") from None

        tenant_id = (payload.tenant_id or "").strip() or None
        if tenant_id is None and user_uuid is not None:
            # Derive tenant_id from user record when available
            u = db.query(User).filter(User.id == user_uuid).first()
            if u and getattr(u, "tenant_id", None):
                tenant_id = str(u.tenant_id)
            else:
                tenant_id = str(user_uuid)

        # Close active plan (best-effort)
        try:
            current = (
                db.query(TenantPlan)
                .filter(TenantPlan.tenant_id == tenant_id)
                .order_by(TenantPlan.valid_from.desc())
                .first()
            )
            if current and getattr(current, "valid_to", None) is None:
                from datetime import datetime

                current.valid_to = datetime.utcnow()  # type: ignore[assignment]
        except Exception:
            pass

        rec = TenantPlan(
            tenant_id=tenant_id,
            user_id=user_uuid,
            plan_name=str(payload.plan_name),
            ops_price_per_k=payload.ops_price_per_k,
            settlement_price_per_op=payload.settlement_price_per_op,
            ops_monthly_cap=payload.ops_monthly_cap,
            settlement_monthly_cap=payload.settlement_monthly_cap,
        )
        db.add(rec)
        db.commit()

        return PlanOut.model_validate(
            {
                "id": str(rec.id),
                "tenant_id": rec.tenant_id,
                "user_id": str(rec.user_id) if rec.user_id else None,
                "plan_name": rec.plan_name,
                "ops_price_per_k": float(rec.ops_price_per_k)
                if rec.ops_price_per_k is not None
                else None,
                "settlement_price_per_op": float(rec.settlement_price_per_op)
                if rec.settlement_price_per_op is not None
                else None,
                "ops_monthly_cap": rec.ops_monthly_cap,
                "settlement_monthly_cap": rec.settlement_monthly_cap,
                "take_rate": None,
            }
        )

    @router.delete("/plans/{plan_id}")
    async def delete_plan(  # type: ignore[no-untyped-def]
        plan_id: str,
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        """Delete a tenant billing plan (admin only)."""
        _require_admin(user)
        try:
            plan_uuid = UUID(str(plan_id))
        except Exception:
            raise HTTPException(status_code=400, detail="invalid_plan_id") from None
        rec = db.query(TenantPlan).filter(TenantPlan.id == plan_uuid).first()
        if not rec:
            raise HTTPException(status_code=404, detail="Plan not found")
        db.delete(rec)
        db.commit()
        return {"ok": True}

    class UsageRow(BaseModel):
        period: str
        ops_count: int
        settlement_count: int
        cost_usd: float

    @router.get("/tenant_usage", response_model=list[UsageRow])
    async def tenant_usage(  # type: ignore[no-untyped-def]
        tenant_id: str | None = Query(None, description="Tenant ID"),
        user_id: str | None = Query(None, description="User UUID (fallback)"),
        limit: int = Query(12, ge=1, le=36),
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        """Get usage statistics for a tenant or user (admin only)."""
        _require_admin(user)
        if not tenant_id and not user_id:
            raise HTTPException(status_code=400, detail="tenant_id_or_user_id_required")
        user_uuid: UUID | None = None
        if user_id:
            try:
                user_uuid = UUID(str(user_id))
            except Exception:
                raise HTTPException(status_code=400, detail="invalid_user_id") from None
        try:
            rows: list[Any]
            rows = (
                db.query(TenantUsage)
                .filter(
                    TenantUsage.tenant_id == tenant_id
                    if tenant_id
                    else TenantUsage.user_id == user_uuid
                )
                .order_by(TenantUsage.period.desc())
                .limit(limit)
                .all()
            )
        except Exception:
            rows = (
                db.query(
                    TenantUsage.id,
                    TenantUsage.user_id,
                    TenantUsage.period,
                    TenantUsage.ops_count,
                    TenantUsage.settlement_count,
                    TenantUsage.cost_usd,
                )
                .filter(
                    TenantUsage.tenant_id == tenant_id
                    if tenant_id
                    else TenantUsage.user_id == user_uuid
                )
                .order_by(TenantUsage.period.desc())
                .limit(limit)
                .all()
            )
        out: list[UsageRow] = []
        for r in rows:
            if hasattr(r, "period"):
                period_val = r.period
                ops_val = r.ops_count
                settles_val = r.settlement_count
                cost_val = r.cost_usd
            else:
                period_val = r[2]  # type: ignore[index]
                ops_val = r[3]  # type: ignore[index]
                settles_val = r[4]  # type: ignore[index]
                cost_val = r[5]  # type: ignore[index]
            out.append(
                UsageRow.model_validate(
                    {
                        "period": str(period_val),
                        "ops_count": int(ops_val or 0),
                        "settlement_count": int(settles_val or 0),
                        "cost_usd": float(cost_val or 0.0),
                    }
                )
            )
        return out

    class PlanSeedIn(BaseModel):
        user_ids: list[int] | None = None
        preset: str | None = "default"

    class AdapterPointerIn(BaseModel):
        path: str

    # ============= Marketplace Payout Endpoints =============

    class PayoutRow(BaseModel):
        id: str
        creator_id: str
        item_type: str
        item_id: str
        period: str
        attestations: int
        gross_usd: float
        platform_take_rate: float
        payout_usd: float
        created_at: str | None = None

    class PayoutSummary(BaseModel):
        period: str
        total_gross_usd: float
        total_platform_revenue_usd: float
        total_creator_payouts_usd: float
        creator_count: int
        transaction_count: int

    class PayoutsListResponse(BaseModel):
        """Response for payouts list with pagination."""

        payouts: list[PayoutRow]
        total: int
        page: int = 1
        per_page: int = 50
        has_more: bool = False

    @router.get("/payouts", response_model=PayoutsListResponse)
    async def list_payouts(  # type: ignore[no-untyped-def]
        creator_id: str | None = Query(None, description="Filter by creator ID"),
        period: str | None = Query(None, description="Filter by period (YYYY-MM)"),
        page: int = Query(1, ge=1, description="Page number"),
        per_page: int = Query(50, ge=1, le=200, description="Items per page"),
        user=Depends(get_current_user),
    ):
        """List marketplace payouts (admin only)."""
        _require_admin(user)
        db = get_session_factory()()
        try:
            q = db.query(MarketplacePayout).order_by(MarketplacePayout.created_at.desc())
            if creator_id:
                q = q.filter(MarketplacePayout.creator_id == creator_id)
            if period:
                q = q.filter(MarketplacePayout.period == period[:7])

            # Get total count
            total = q.count()

            # Apply pagination
            offset = (page - 1) * per_page
            rows = q.offset(offset).limit(per_page).all()
            has_more = (offset + per_page) < total

            payouts = [
                PayoutRow(
                    id=str(r.id),
                    creator_id=r.creator_id,
                    item_type=r.item_type,
                    item_id=r.item_id,
                    period=r.period,
                    attestations=r.attestations or 0,
                    gross_usd=float(r.gross_usd or 0),
                    platform_take_rate=float(r.platform_take_rate or 0),
                    payout_usd=float(r.payout_usd or 0),
                    created_at=r.created_at.isoformat() if r.created_at else None,
                )
                for r in rows
            ]

            return PayoutsListResponse(
                payouts=payouts,
                total=total,
                page=page,
                per_page=per_page,
                has_more=has_more,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from None
        finally:
            db.close()

    @router.get("/payouts/summary", response_model=PayoutSummary)
    async def payout_summary(  # type: ignore[no-untyped-def]
        period: str = Query(..., description="Period (YYYY-MM)"),
        user=Depends(get_current_user),
    ):
        """Get payout summary for a period (admin only)."""

        _require_admin(user)
        db = get_session_factory()()
        try:
            per = period[:7]  # Normalize to YYYY-MM
            rows = db.query(MarketplacePayout).filter(MarketplacePayout.period == per).all()

            total_gross = sum(float(r.gross_usd or 0) for r in rows)
            total_payout = sum(float(r.payout_usd or 0) for r in rows)
            platform_revenue = total_gross - total_payout
            creator_ids = {r.creator_id for r in rows}
            transaction_count = sum(r.attestations or 0 for r in rows)

            return PayoutSummary(
                period=per,
                total_gross_usd=round(total_gross, 2),
                total_platform_revenue_usd=round(platform_revenue, 2),
                total_creator_payouts_usd=round(total_payout, 2),
                creator_count=len(creator_ids),
                transaction_count=transaction_count,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from None
        finally:
            db.close()

    @router.get("/payouts/creator/{creator_id}", response_model=list[PayoutRow])
    async def creator_payouts(  # type: ignore[no-untyped-def]
        creator_id: str,
        limit: int = Query(24, ge=1, le=120, description="Number of periods"),
        user=Depends(get_current_user),
    ):
        """Get payout history for a specific creator (admin only)."""
        _require_admin(user)
        db = get_session_factory()()
        try:
            rows = (
                db.query(MarketplacePayout)
                .filter(MarketplacePayout.creator_id == creator_id)
                .order_by(MarketplacePayout.period.desc())
                .limit(limit)
                .all()
            )

            return [
                PayoutRow(
                    id=str(r.id),
                    creator_id=r.creator_id,
                    item_type=r.item_type,
                    item_id=r.item_id,
                    period=r.period,
                    attestations=r.attestations or 0,
                    gross_usd=float(r.gross_usd or 0),
                    platform_take_rate=float(r.platform_take_rate or 0),
                    payout_usd=float(r.payout_usd or 0),
                    created_at=r.created_at.isoformat() if r.created_at else None,
                )
                for r in rows
            ]
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from None
        finally:
            db.close()

    @router.post("/payouts/trigger")
    async def trigger_payout_rollup(  # type: ignore[no-untyped-def]
        period: str | None = Query(None, description="Period (YYYY-MM), defaults to current month"),
        platform_take_rate: float = Query(0.20, ge=0.0, le=1.0, description="Platform take rate"),
        user=Depends(get_current_user),
    ):
        """Manually trigger payout rollup (admin only)."""
        _require_admin(user)
        try:
            from kagami.core.tasks.tasks import rollup_marketplace_payouts_task

            result = rollup_marketplace_payouts_task.delay(
                period=period,
                platform_take_rate=platform_take_rate,
            )
            return {
                "status": "triggered",
                "task_id": str(result.id),
                "period": period or "current",
                "platform_take_rate": platform_take_rate,
            }
        except Exception:
            # Celery not available - run synchronously
            try:
                from kagami.core.tasks.tasks import rollup_marketplace_payouts_task

                result = rollup_marketplace_payouts_task(
                    period=period, platform_take_rate=platform_take_rate
                )
                return {"status": "completed_sync", **result}
            except Exception as e2:
                raise HTTPException(status_code=500, detail=str(e2)) from None

    return router
