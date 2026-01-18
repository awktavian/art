from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from kagami.core.database.connection import get_db_session as get_db
from kagami.core.database.models import AppData
from pydantic import BaseModel
from sqlalchemy.orm import Session

from kagami_api.routes.user.auth import get_current_user


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(tags=["billing-experience"])

    # Use canonical require_admin from security module

    def _user_id_from(user: Any) -> int | None:
        if isinstance(user, dict):
            raw = user.get("user_id")
            if raw is None:
                return None
            try:
                return int(str(raw))
            except Exception:
                try:
                    return int(str(raw).split("-")[-1])
                except Exception:
                    return None
        return None

    class TrialStatus(BaseModel):
        active: bool
        trial_end: str | None = None
        days_remaining: int = 0
        length_days: int = 0

    @router.get("/trial", response_model=TrialStatus)
    async def get_trial_status(  # type: ignore[no-untyped-def]
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> TrialStatus:
        """Get the current user's trial status and remaining days."""
        uid = _user_id_from(user)
        if not uid:
            return TrialStatus(active=False, days_remaining=0, length_days=0)
        rec = (
            db.query(AppData)
            .filter(
                AppData.app_name == "billing",
                AppData.data_type == "trial",
                AppData.data_id == f"user:{uid}",
            )
            .first()
        )
        if not rec:
            return TrialStatus(active=False, days_remaining=0, length_days=0)
        data: dict[str, Any] = rec.data if isinstance(rec.data, dict) else {}  # type: ignore[unreachable]
        end_str = data.get("trial_end")
        try:
            end_dt = datetime.fromisoformat(end_str) if end_str else None
        except Exception:
            end_dt = None
        now = datetime.utcnow()
        active = bool(end_dt and end_dt > now)
        days_remaining = max(0, (end_dt - now).days) if end_dt else 0
        return TrialStatus(
            active=active,
            trial_end=end_dt.isoformat() if end_dt else None,
            days_remaining=days_remaining,
            length_days=int(data.get("length_days") or 0),
        )

    class PlanStatus(BaseModel):
        plan_name: str | None = None
        valid_from: str | None = None
        valid_to: str | None = None

    class WalletOut(BaseModel):
        balance_usd: float
        updated_at: str | None = None

    @router.get("/wallet", response_model=WalletOut)
    async def get_wallet(  # type: ignore[no-untyped-def]
        user=Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> WalletOut:
        """Get the current user's wallet balance."""
        uid = _user_id_from(user)
        if not uid:
            return WalletOut(balance_usd=0.0)
        rec = (
            db.query(AppData)
            .filter(
                AppData.app_name == "billing",
                AppData.data_type == "wallet",
                AppData.data_id == f"user:{uid}",
            )
            .first()
        )
        data: dict[str, Any] = {}
        if rec and isinstance(rec.data, dict):  # type: ignore[unreachable]
            data = rec.data  # type: ignore[unreachable]
        return WalletOut(
            balance_usd=float(data.get("balance_usd", 0.0)),
            updated_at=str(data.get("updated_at")) if data.get("updated_at") else None,
        )

    class WalletTopupIn(BaseModel):
        amount_usd: float

    class UpgradeOut(BaseModel):
        suggestion: str
        checkout_url: str | None = None
        portal_url: str | None = None

    class ForecastOut(BaseModel):
        period: str
        cost_usd: float
        projected_cost_usd: float
        days_elapsed: int
        days_in_month: int

    return router
