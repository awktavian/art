from __future__ import annotations

"""Per-tenant quota enforcement middleware.

Disabled by default. When enabled via environment variables, this middleware
reads the caller identity, looks up the current `TenantPlan` and `TenantUsage`,
and attaches quota headers. In hard-enforce mode it returns 429 when caps are
exceeded with an upgrade hint.

Env flags:
- ENFORCE_TENANT_PLAN=1|0           -> enable middleware logic
- ENFORCE_TENANT_PLAN_HARD=1|0      -> 429 at caps (else soft headers only)

Notes:
- Missing/unknown users pass through with policy=off to avoid auth coupling.
- DB errors fail-open but still attach a policy header for observability.
"""
import logging
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

import anyio
from fastapi import Request
from kagami.core.di import try_resolve
from kagami.core.interfaces import DatabaseProvider
from starlette.responses import JSONResponse, Response

try:  # Backwards-compat for tests that monkeypatch this symbol directly
    from kagami.core.database.connection import get_session_factory as _get_session_factory
except Exception:
    _get_session_factory = None  # type: ignore[assignment]

get_session_factory = _get_session_factory

# Default tenant UUID string used by TenantMiddleware fallback.
_DEFAULT_TENANT_UUID_STR = "00000000-0000-0000-0000-000000000000"


def _resolve_user_id_from_headers(request: Request) -> str | None:
    """Best-effort user UUID resolution from Authorization header.

    Prefers the `uid` claim embedded in JWT access tokens (stringified UUID).
    Returns None when not resolvable; middleware remains best-effort.
    """
    try:
        auth_header = request.headers.get("Authorization") or ""
        if not auth_header.lower().startswith("bearer "):
            return None
        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return None
        try:
            from kagami_api.security import get_token_manager  # lazy import

            tm = get_token_manager()
            payload = tm.verify_token(token) if tm else None
            if payload:
                uid = payload.get("uid") or payload.get("user_id")
                if uid:
                    return str(uid)
        except Exception:
            pass
        # Fallback to security framework (raises HTTPException on failure)
        try:
            from kagami_api.security import SecurityFramework

            principal = SecurityFramework.verify_token(token)
            uid = getattr(principal, "user_id", None)
            if uid:
                return str(uid)
            return None
        except Exception:
            return None
    except Exception:
        return None


def _current_month_window(now_dt: datetime) -> tuple[datetime, datetime]:
    """Calculate current month's datetime window (start, end).

    Args:
        now_dt: Current datetime

    Returns:
        Tuple of (month_start, month_end) datetime objects
    """
    month_start = now_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return month_start, next_month


def _get_database_provider() -> DatabaseProvider | None:
    provider = try_resolve(DatabaseProvider)
    if provider and isinstance(provider, DatabaseProvider):
        return provider  # type: ignore[no-any-return]
    return None


async def _fetch_plan_and_usage_with_provider(
    provider: DatabaseProvider, tenant_id: str | None, user_id: str | None
) -> tuple[SimpleNamespace | None, int, int]:
    now_dt = datetime.utcnow()
    month_start, next_month = _current_month_window(now_dt)

    plan_row: dict[str, Any] | None = None
    if tenant_id is not None:
        plan_row = await provider.fetch_one(
            """
            SELECT plan_name, ops_monthly_cap, settlement_monthly_cap
            FROM tenant_plans
            WHERE tenant_id = :tenant_id
            ORDER BY valid_from DESC
            LIMIT 1
            """,
            {"tenant_id": tenant_id},
        )
    elif user_id is not None:
        plan_row = await provider.fetch_one(
            """
            SELECT plan_name, ops_monthly_cap, settlement_monthly_cap
            FROM tenant_plans
            WHERE user_id = :user_id
            ORDER BY valid_from DESC
            LIMIT 1
            """,
            {"user_id": user_id},
        )
    plan_ns = SimpleNamespace(**plan_row) if plan_row else None

    params: dict[str, Any] = {"month_start": month_start, "next_month": next_month}
    settlement_query = [
        "SELECT COUNT(id) AS count",
        "FROM settlement_records",
        "WHERE timestamp >= :month_start AND timestamp < :next_month",
    ]
    if tenant_id is not None:
        settlement_query.append("AND tenant_id = :tenant_id")
        params["tenant_id"] = tenant_id
    elif user_id is not None:
        settlement_query.append("AND user_id = :user_id")
        params["user_id"] = user_id
    settle_row = await provider.fetch_one(" ".join(settlement_query), params)
    settle_cnt = int((settle_row or {}).get("count") or 0)

    # Query ops count from receipts (EXECUTE phase receipts within current month)
    ops_query = [
        "SELECT COUNT(id) AS count",
        "FROM receipts",
        "WHERE ts >= :month_start AND ts < :next_month",
        "AND (phase = 'EXECUTE' OR phase = 'execute')",
    ]
    if tenant_id is not None:
        ops_query.append("AND tenant_id = :tenant_id")
    elif user_id is not None:
        ops_query.append("AND user_id = :user_id")
    ops_row = await provider.fetch_one(" ".join(ops_query), params)
    ops_cnt = int((ops_row or {}).get("count") or 0)

    return plan_ns, ops_cnt, settle_cnt


def _is_quota_enabled() -> bool:
    """Check if quota enforcement is enabled."""
    return os.getenv("ENFORCE_TENANT_PLAN", "0").lower() in ("1", "true", "yes", "on")


def _is_hard_enforce() -> bool:
    """Check if hard quota enforcement is enabled."""
    return os.getenv("ENFORCE_TENANT_PLAN_HARD", "0").lower() in ("1", "true", "yes", "on")


def _is_public_path(path: str) -> bool:
    """Check if path is a public endpoint that bypasses quota."""
    return path.startswith("/metrics") or path.startswith("/health") or path.startswith("/static")


def _set_header_safe(response: Response, key: str, value: str) -> None:
    """Set response header with error handling."""
    try:
        response.headers[key] = value
    except Exception:
        pass


def _resolve_tenant_user(request: Request) -> tuple[str | None, str | None]:
    """Resolve tenant and user IDs from request."""
    tenant_id = None
    try:
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            tenant_id = str(tenant_id)
    except Exception:
        pass
    user_id = _resolve_user_id_from_headers(request)
    # If tenant is the default singleton, prefer per-user quotas to avoid
    # cross-user coupling in single-tenant deployments.
    if tenant_id == _DEFAULT_TENANT_UUID_STR and user_id is not None:
        tenant_id = None
    return tenant_id, user_id


async def _get_cached_quota(
    tenant_id: str | None, user_id: str | None
) -> tuple[dict | None, str | None, Any]:
    """Get quota data from Redis cache.

    Returns:
        Tuple of (cached_data, cache_key, redis_client)
    """
    try:
        from kagami.core.caching.redis import RedisClientFactory

        redis_client = await RedisClientFactory.get_client(
            purpose="default", async_mode=True, decode_responses=True
        )
        now_dt = datetime.utcnow()
        month_key = now_dt.strftime("%Y-%m")

        cache_key = None
        if tenant_id:
            cache_key = f"kagami:quota:tenant:{tenant_id}:{month_key}"
        elif user_id:
            cache_key = f"kagami:quota:user:{user_id}:{month_key}"

        if cache_key:
            cached_json = await redis_client.get(cache_key)
            if cached_json:
                import json

                return json.loads(cached_json), cache_key, redis_client

        return None, cache_key, redis_client
    except Exception as e:
        logging.getLogger(__name__).debug(f"Redis quota cache lookup failed: {e}")
        return None, None, None


async def _cache_quota_data(
    cache_key: str | None, redis_client: Any, plan: Any, ops_cnt: int, settle_cnt: int
) -> None:
    """Cache quota data to Redis."""
    if not cache_key or not redis_client:
        return
    try:
        import json

        cache_data = {
            "plan": {
                "plan_name": getattr(plan, "plan_name", None),
                "ops_monthly_cap": getattr(plan, "ops_monthly_cap", 0) if plan else 0,
                "settlement_monthly_cap": getattr(plan, "settlement_monthly_cap", 0) if plan else 0,
            }
            if plan
            else None,
            "ops_cnt": ops_cnt,
            "settle_cnt": settle_cnt,
        }
        await redis_client.setex(cache_key, 60, json.dumps(cache_data))
    except Exception:
        pass


def _extract_caps(
    plan: Any, ops_cnt: int, settle_cnt: int
) -> tuple[int | None, int | None, int | None, int | None]:
    """Extract quota caps and remaining counts from plan.

    Returns:
        Tuple of (ops_cap, settle_cap, ops_remaining, settle_remaining)
    """
    ops_cap = (
        int(plan.ops_monthly_cap)
        if plan and getattr(plan, "ops_monthly_cap", None) is not None
        else None
    )
    settle_cap = (
        int(plan.settlement_monthly_cap)
        if plan and getattr(plan, "settlement_monthly_cap", None) is not None
        else None
    )
    ops_remaining = None if ops_cap is None else max(0, ops_cap - ops_cnt)
    settle_remaining = None if settle_cap is None else max(0, settle_cap - settle_cnt)
    return ops_cap, settle_cap, ops_remaining, settle_remaining


def _build_quota_exceeded_response(
    plan: Any,
    ops_remaining: int | None,
    settle_remaining: int | None,
    ops_cap: int | None,
    settle_cap: int | None,
) -> JSONResponse:
    """Build 429 response for quota exceeded."""
    payload = {
        "ok": False,
        "error": "quota_exceeded",
        "plan": plan.plan_name if plan else None,
        "ops_remaining": ops_remaining,
        "settlements_remaining": settle_remaining,
        "upgrade_url": "/api/billing/upgrade",
    }
    resp = JSONResponse(payload, status_code=429)
    _set_header_safe(resp, "X-Quota-Policy", "hard")
    if ops_cap is not None:
        _set_header_safe(resp, "X-Quota-Ops-Limit", str(ops_cap))
        _set_header_safe(resp, "X-Quota-Ops-Remaining", str(ops_remaining))
    if settle_cap is not None:
        _set_header_safe(resp, "X-Quota-Settlements-Limit", str(settle_cap))
        _set_header_safe(resp, "X-Quota-Settlements-Remaining", str(settle_remaining))
    return resp


def _attach_quota_headers(
    response: Response,
    plan: Any,
    ops_cap: int | None,
    settle_cap: int | None,
    ops_remaining: int | None,
    settle_remaining: int | None,
) -> None:
    """Attach quota headers to response."""
    _set_header_safe(response, "X-Quota-Policy", "soft")
    if plan and plan.plan_name:
        _set_header_safe(response, "X-Quota-Plan", str(plan.plan_name))
    if ops_cap is not None:
        _set_header_safe(response, "X-Quota-Ops-Limit", str(ops_cap))
        _set_header_safe(response, "X-Quota-Ops-Remaining", str(ops_remaining))
    if settle_cap is not None:
        _set_header_safe(response, "X-Quota-Settlements-Limit", str(settle_cap))
        _set_header_safe(response, "X-Quota-Settlements-Remaining", str(settle_remaining))


async def tenant_quota_middleware(request: Request, call_next: Any) -> Any:
    """Enforce per-tenant quota limits based on TenantPlan and usage."""
    # Fast path: disabled
    if not _is_quota_enabled():
        response: Response = await call_next(request)
        _set_header_safe(response, "X-Quota-Policy", "off")
        return response

    # Skip public endpoints
    if _is_public_path(str(request.url.path)):
        return await call_next(request)

    # Resolve tenant/user
    tenant_id_val, user_id_val = _resolve_tenant_user(request)

    # Unknown user/tenant: pass through
    if user_id_val is None and tenant_id_val is None:
        response = await call_next(request)
        _set_header_safe(response, "X-Quota-Policy", "enabled-unknown-user")
        return response

    try:
        # Fetch quota data (cached or from DB)
        plan, ops_cnt, settle_cnt, _redis_client, _cache_key = await _fetch_quota_data(
            tenant_id_val, user_id_val
        )

        # Extract caps and remaining
        ops_cap, settle_cap, ops_remaining, settle_remaining = _extract_caps(
            plan, ops_cnt, settle_cnt
        )

        # Check hard enforcement
        if _is_hard_enforce():
            over_ops = ops_cap is not None and ops_cnt >= ops_cap
            over_settle = settle_cap is not None and settle_cnt >= settle_cap
            if over_ops or over_settle:
                return _build_quota_exceeded_response(
                    plan, ops_remaining, settle_remaining, ops_cap, settle_cap
                )

        # Soft enforcement: pass through with headers
        response = await call_next(request)
        _attach_quota_headers(response, plan, ops_cap, settle_cap, ops_remaining, settle_remaining)
        return response

    except Exception:
        # Fail-open on middleware errors
        response = await call_next(request)
        _set_header_safe(response, "X-Quota-Policy", "error-fail-open")
        return response


async def _fetch_quota_data(
    tenant_id: str | None, user_id: str | None
) -> tuple[Any, int, int, Any, str | None]:
    """Fetch quota data from cache or database.

    Returns:
        Tuple of (plan, ops_cnt, settle_cnt, redis_client, cache_key)
    """
    # Try cache first
    cached_data, cache_key, redis_client = await _get_cached_quota(tenant_id, user_id)

    if cached_data:
        plan = SimpleNamespace(**cached_data["plan"]) if cached_data.get("plan") else None
        return (
            plan,
            cached_data.get("ops_cnt", 0),
            cached_data.get("settle_cnt", 0),
            redis_client,
            cache_key,
        )

    # Fetch from database
    plan, ops_cnt, settle_cnt = await _fetch_from_database(tenant_id, user_id)

    # Cache result
    await _cache_quota_data(cache_key, redis_client, plan, ops_cnt, settle_cnt)

    return plan, ops_cnt, settle_cnt, redis_client, cache_key


async def _fetch_from_database(tenant_id: str | None, user_id: str | None) -> tuple[Any, int, int]:
    """Fetch plan and usage from database."""
    db_provider = _get_database_provider()

    if db_provider:
        try:
            return await _fetch_plan_and_usage_with_provider(db_provider, tenant_id, user_id)
        except Exception as exc:
            logging.getLogger(__name__).warning("Async DB provider failed, falling back: %s", exc)

    # Legacy fallback
    if get_session_factory is None:
        raise RuntimeError("Database connection helper unavailable")

    return await anyio.to_thread.run_sync(lambda: _compute_plan_and_usage_sync(tenant_id, user_id))


def _compute_plan_and_usage_sync(
    tenant_id: str | None, user_id: str | None
) -> tuple[Any, int, int]:
    """Synchronous plan and usage computation."""
    from uuid import UUID

    from kagami.core.database.models import Receipt, SettlementRecord, TenantPlan
    from sqlalchemy import func

    if get_session_factory is None:
        raise RuntimeError("Database connection helper unavailable")

    # Prefer kagami.core.database.connection.get_db() to preserve test monkeypatching
    # patterns; fall back to get_session_factory for legacy callers.
    db = None
    db_gen = None
    try:
        from kagami.core.database import connection as _connection

        maybe = _connection.get_db()
        if hasattr(maybe, "query"):
            db = maybe
        else:
            db_gen = maybe
            db = next(db_gen)  # type: ignore[assignment]
    except Exception:
        db = None
        db_gen = None
    if db is None:
        if get_session_factory is None:
            raise RuntimeError("Database connection helper unavailable")
        db = get_session_factory()()
    try:
        now_dt = datetime.utcnow()
        month_start, next_month = _current_month_window(now_dt)

        # Coerce user_id (string) to UUID for SQLAlchemy comparisons
        user_uuid = None
        if user_id is not None:
            try:
                user_uuid = UUID(str(user_id))
            except Exception:
                user_uuid = None
        if tenant_id is None and user_id is None:
            # No identity => fail open with zeroed usage
            return None, 0, 0
        user_filter_value: Any = user_uuid if user_uuid is not None else user_id

        # Query plan
        if tenant_id is not None:
            plan = (
                db.query(TenantPlan)
                .filter(TenantPlan.tenant_id == tenant_id)
                .order_by(TenantPlan.valid_from.desc())
                .first()
            )
        else:
            plan = (
                db.query(TenantPlan)
                .filter(TenantPlan.user_id == user_filter_value)
                .order_by(TenantPlan.valid_from.desc())
                .first()
            )

        # Query settlement count
        settle_cnt = 0
        try:
            q = db.query(func.count(SettlementRecord.id)).filter(
                SettlementRecord.timestamp >= month_start,
                SettlementRecord.timestamp < next_month,
            )
            if tenant_id is not None:
                q = q.filter(SettlementRecord.tenant_id == tenant_id)
            elif user_filter_value is not None:
                q = q.filter(SettlementRecord.user_id == user_filter_value)
            if hasattr(q, "scalar"):
                settle_cnt = int(q.scalar() or 0)
        except Exception:
            settle_cnt = 0

        # Query ops count (EXECUTE phase receipts)
        ops_cnt = 0
        try:
            ops_q = db.query(func.count(Receipt.id)).filter(
                Receipt.ts >= month_start,
                Receipt.ts < next_month,
            )
            ops_q = ops_q.filter(func.lower(Receipt.phase) == "execute")
            if tenant_id is not None:
                ops_q = ops_q.filter(Receipt.tenant_id == tenant_id)
            elif user_filter_value is not None:
                ops_q = ops_q.filter(Receipt.user_id == user_filter_value)
            if hasattr(ops_q, "scalar"):
                ops_cnt = int(ops_q.scalar() or 0)
        except Exception:
            ops_cnt = 0

        return plan, ops_cnt, settle_cnt
    finally:
        try:
            if db_gen is not None:
                try:
                    db_gen.close()
                except Exception:
                    pass
            elif hasattr(db, "close"):
                db.close()
        except Exception:
            pass
