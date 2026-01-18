from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from kagami.core.events import get_unified_bus
from kagami.core.safety.cbf_integration import check_cbf_for_operation
from pydantic import BaseModel, Field

from kagami_api.routes.user.auth import get_current_user


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(prefix="/api/policy", tags=["policy"])

    class RuleUpsertRequest(BaseModel):
        topic_prefix: str
        condition: dict[str, Any] | None = None
        lang_template: str
        risk: str = Field(default="low")
        priority: int | None = Field(default=None)
        expires_at: str | None = Field(default=None)
        user_id: str | None = Field(default=None)

    @router.post("/rules/upsert")
    async def upsert_rule(
        req: RuleUpsertRequest, user: Any = Depends(get_current_user)
    ) -> dict[str, Any]:
        """Create or update a policy rule with CBF safety verification."""
        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.policy.upsert_rule",
            action="upsert",
            target="policy_rule",
            params=req.model_dump(),
            metadata={"endpoint": "/api/policy/rules/upsert", "topic_prefix": req.topic_prefix},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        try:
            bus = get_unified_bus()
            orchestrator = getattr(bus, "_cross_domain_orchestrator", None)
            if orchestrator is None:
                raise RuntimeError("orchestrator unavailable")
            orchestrator.policy.rules.upsert_rule(
                topic_prefix=req.topic_prefix,
                condition=req.condition,
                lang_template=req.lang_template,
                risk=req.risk,
                user_id=req.user_id,
            )
            return {"status": "ok"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from None

    class FeedbackRequest(BaseModel):
        topic: str
        lang: str
        reward: float = Field(ge=-1.0, le=1.0)
        user_id: str | None = Field(default=None)

    @router.get("/rules")
    async def list_rules(  # type: ignore[no-untyped-def]
        page: int = 1,
        per_page: int = 20,
        user=Depends(get_current_user),
    ):
        """List all policy rules in the system with pagination."""
        try:
            bus = get_unified_bus()
            orchestrator = getattr(bus, "_cross_domain_orchestrator", None)
            if orchestrator is None:
                raise RuntimeError("orchestrator unavailable")
            all_rules = orchestrator.policy.rules.list_rules()

            # Apply pagination
            total = len(all_rules)
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            paginated_rules = all_rules[start_idx:end_idx]
            has_more = end_idx < total

            return {
                "rules": paginated_rules,
                "total": total,
                "page": page,
                "per_page": per_page,
                "has_more": has_more,
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from None

    @router.get("/stats")
    async def list_stats(user: Any = Depends(get_current_user)) -> dict[str, Any]:
        """Get policy enforcement statistics."""
        try:
            bus = get_unified_bus()
            orchestrator = getattr(bus, "_cross_domain_orchestrator", None)
            if orchestrator is None:
                raise RuntimeError("orchestrator unavailable") from None
            return {"stats": orchestrator.policy.rules.list_stats()}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from None

    return router
