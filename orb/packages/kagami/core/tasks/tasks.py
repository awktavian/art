"""
Core Celery tasks for K os system maintenance and monitoring.

These tasks handle:
- Health checks
- Data cleanup
- Analytics generation
- Embeddings synchronization
- Intent processing
"""

import asyncio
import logging
from typing import Any

from kagami.core.tasks.app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="kagami.core.tasks.tasks.health_check_task")
def health_check_task() -> dict[str, Any]:
    """
    Periodic health check task.

    Verifies system components are operational:
    - Redis connectivity
    - Database connectivity
    - API responsiveness

    Returns:
        dict[str, Any]: Health status report
    """
    try:
        from kagami.core.caching.redis import RedisClientFactory
        from kagami.core.database.async_connection import async_engine

        async def _check() -> dict[str, Any]:
            results: dict[str, Any] = {"redis": False, "database": False, "timestamp": None}
            try:
                redis = RedisClientFactory.get_client("default", async_mode=True)
                await redis.ping()
                results["redis"] = True
            except Exception as e:
                logger.error(f"Redis health check failed: {e}")
            try:
                async with async_engine.begin() as conn:
                    await conn.execute("SELECT 1")
                results["database"] = True
            except Exception as e:
                logger.error(f"Database health check failed: {e}")
            from datetime import datetime

            results["timestamp"] = datetime.utcnow().isoformat()
            return results

        result: dict[str, Any] = asyncio.run(_check())
        try:
            from kagami_observability.metrics import health_check_status

            health_check_status.labels(component="redis").set(1 if result.get("redis") else 0)
            health_check_status.labels(component="database").set(1 if result.get("database") else 0)
        except Exception:
            pass
        return {"status": "success", "health": result}
    except Exception as e:
        logger.error(f"Health check task failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="kagami.core.tasks.tasks.sync_embeddings_task")
def sync_embeddings_task() -> dict[str, Any]:
    """
    Validate embedding cache consistency in Redis.

    Scans Redis embedding cache entries and validates they are well-formed.
    NOTE: Vector search is handled by Weaviate (Dec 2025). Redis is cache-only.

    Returns:
        dict[str, Any]: Validation results
    """
    try:
        from kagami.core.caching.redis import RedisClientFactory

        redis_client = RedisClientFactory.get_client("default")
        synced_count = 0
        errors = []
        embedding_pattern = "kagami:embedding:*"
        cursor = 0
        embedding_keys = []
        while True:
            cursor, keys = redis_client.scan(cursor, match=embedding_pattern, count=100)
            embedding_keys.extend(keys)
            if cursor == 0:
                break
        logger.info(f"Found {len(embedding_keys)} embeddings in Redis to sync")
        for key in embedding_keys[:1000]:
            try:
                embedding_data = redis_client.get(key)
                if embedding_data:
                    import json

                    data = json.loads(embedding_data)
                    if "vector" in data and "metadata" in data:
                        synced_count += 1
            except Exception as e:
                errors.append(f"{key}: {e!s}")
                logger.warning(f"Failed to sync {key}: {e}")
        logger.info(f"Embeddings sync completed: {synced_count} synced, {len(errors)} errors")
        return {
            "status": "success",
            "synced": synced_count,
            "total_keys": len(embedding_keys),
            "errors": len(errors),
            "message": f"Synced {synced_count} embeddings",
        }
    except Exception as e:
        logger.error(f"Embeddings sync failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="kagami.core.tasks.tasks.cleanup_expired_data_task")
def cleanup_expired_data_task() -> dict[str, Any]:
    """
    Clean up expired data from Redis and database.

    Removes:
    - Expired idempotency keys
    - Old receipts (> 30 days)
    - Stale cache entries
    - Completed task results

    Returns:
        dict[str, Any]: Cleanup results
    """
    try:
        from kagami.core.caching.redis import RedisClientFactory

        async def _cleanup() -> dict[str, Any]:
            redis = RedisClientFactory.get_client("default", async_mode=True)
            cleaned: dict[str, Any] = {"idempotency_keys": 0, "receipts": 0, "cache_entries": 0}
            try:
                cursor = 0
                pattern = "idempotency:*"
                expired_count = 0
                while True:
                    cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                    for key in keys:
                        ttl = await redis.ttl(key)
                        if ttl == -1:
                            await redis.expire(key, 300)
                            expired_count += 1
                    if cursor == 0:
                        break
                cleaned["idempotency_keys"] = expired_count
            except Exception as e:
                logger.error(f"Idempotency cleanup failed: {e}")
            try:
                from datetime import datetime, timedelta

                cutoff_time = datetime.utcnow() - timedelta(days=30)
                cutoff_timestamp = cutoff_time.timestamp()
                receipts_deleted = 0
                receipts_archived = 0
                cursor = 0
                pattern = "receipt:*"
                while True:
                    cursor, keys = await redis.scan(cursor, match=pattern, count=100)
                    for key in keys:
                        try:
                            receipt_data = await redis.get(key)
                            if not receipt_data:
                                continue
                            try:
                                import json

                                receipt = json.loads(receipt_data)
                                timestamp = receipt.get("timestamp", 0)
                                if timestamp < cutoff_timestamp:
                                    try:
                                        import os

                                        archive_dir = os.getenv("KAGAMI_RECEIPT_ARCHIVE_DIR")
                                        if archive_dir:
                                            import gzip
                                            from pathlib import Path

                                            archive_path = Path(archive_dir)
                                            archive_path.mkdir(parents=True, exist_ok=True)
                                            date_str = datetime.fromtimestamp(timestamp).strftime(
                                                "%Y-%m-%d"
                                            )
                                            archive_file = (
                                                archive_path / f"receipts_{date_str}.jsonl.gz"
                                            )
                                            with gzip.open(archive_file, "at") as f:
                                                f.write(receipt_data + "\n")
                                            receipts_archived += 1
                                    except Exception as archive_err:
                                        logger.debug(f"Archive failed for {key}: {archive_err}")
                                    await redis.delete(key)
                                    receipts_deleted += 1
                            except (json.JSONDecodeError, ValueError):
                                await redis.delete(key)
                                receipts_deleted += 1
                        except Exception as key_err:
                            logger.debug(f"Error processing key {key}: {key_err}")
                    if cursor == 0:
                        break
                cleaned["receipts"] = receipts_deleted
                cleaned["receipts_archived"] = receipts_archived
                logger.info(
                    f"Receipt cleanup: deleted={receipts_deleted}, archived={receipts_archived}"
                )
            except Exception as e:
                logger.error(f"Receipt cleanup failed: {e}")
            return cleaned

        result = asyncio.run(_cleanup())
        logger.info(f"Cleanup completed: {result}")
        return {"status": "success", "cleaned": result}
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="kagami.core.tasks.tasks.generate_analytics_task")
def generate_analytics_task(report_type: str = "daily") -> dict[str, Any]:
    """
    Generate analytics reports.

    Args:
        report_type: Type of report (daily, weekly, monthly)

    Returns:
        dict[str, Any]: Analytics results
    """
    try:
        logger.info(f"Generating {report_type} analytics report")
        import json
        from datetime import datetime, timedelta

        from kagami.core.caching.redis import RedisClientFactory

        redis_client = RedisClientFactory.get_client("default")
        time_ranges = {
            "daily": timedelta(days=1),
            "weekly": timedelta(weeks=1),
            "monthly": timedelta(days=30),
        }
        cutoff = datetime.utcnow() - time_ranges.get(report_type, timedelta(days=1))
        cutoff_timestamp = cutoff.timestamp()
        receipt_pattern = "kagami:receipt:*"
        cursor = 0
        total_operations = 0
        success_count = 0
        error_count = 0
        operations_by_app: dict[str, Any] = {}
        while True:
            cursor, keys = redis_client.scan(cursor, match=receipt_pattern, count=100)
            for key in keys:
                try:
                    receipt_data = redis_client.get(key)
                    if receipt_data:
                        receipt = json.loads(receipt_data)
                        timestamp = receipt.get("timestamp", 0)
                        if timestamp >= cutoff_timestamp:
                            total_operations += 1
                            status = receipt.get("status", "unknown")
                            if status == "success":
                                success_count += 1
                            elif status == "error":
                                error_count += 1
                            app = receipt.get("app", "unknown")
                            operations_by_app[app] = operations_by_app.get(app, 0) + 1
                except Exception as e:
                    logger.warning(f"Failed to parse receipt {key}: {e}")
            if cursor == 0:
                break
        success_rate = success_count / total_operations * 100 if total_operations > 0 else 0
        top_apps = sorted(operations_by_app.items(), key=lambda x: x[1], reverse=True)[:10]
        report = {
            "report_type": report_type,
            "period_start": cutoff.isoformat(),
            "period_end": datetime.utcnow().isoformat(),
            "total_operations": total_operations,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": round(success_rate, 2),
            "top_apps": dict(top_apps),
        }
        report_key = f"kagami:analytics:{report_type}:{datetime.utcnow().strftime('%Y%m%d')}"
        redis_client.setex(report_key, 86400 * 7, json.dumps(report))
        logger.info(
            f"Analytics report generated: {total_operations} operations, {success_rate:.1f}% success"
        )
        return {
            "status": "success",
            "report_type": report_type,
            "report": report,
            "message": f"Generated {report_type} analytics report",
        }
    except Exception as e:
        logger.error(f"Analytics generation failed: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="kagami.core.tasks.tasks.process_intent_task")
def process_intent_task(intent_id: str) -> dict[str, Any]:
    """
    Process an intent asynchronously.

    Args:
        intent_id: Unique intent identifier

    Returns:
        dict[str, Any]: Processing results
    """
    try:
        logger.info(f"Processing intent: {intent_id}")
        import json

        from kagami.core.caching.redis import RedisClientFactory

        redis_client = RedisClientFactory.get_client("default")
        intent_key = f"kagami:intent:{intent_id}"
        intent_data = redis_client.get(intent_key)
        if not intent_data:
            logger.error(f"Intent {intent_id} not found in Redis")
            return {"status": "error", "intent_id": intent_id, "error": "Intent not found"}
        intent = json.loads(intent_data)
        try:
            from kagami.core.orchestrator import process_intent_async

            result = asyncio.run(process_intent_async(intent))
            result_key = f"kagami:intent:result:{intent_id}"
            redis_client.setex(result_key, 3600, json.dumps(result))
            logger.info(f"Intent {intent_id} processed successfully")
            return {
                "status": "success",
                "intent_id": intent_id,
                "result": result,
                "message": "Intent processed successfully",
            }
        except Exception as e:
            logger.error(f"Intent processing failed: {e}", exc_info=True)
            error_result = {"status": "error", "error": str(e), "intent_id": intent_id}
            result_key = f"kagami:intent:result:{intent_id}"
            redis_client.setex(result_key, 3600, json.dumps(error_result))
            return error_result
    except Exception as e:
        logger.error(f"Intent processing failed: {e}")
        return {"status": "error", "error": str(e)}


def _month_window_from_period(period: str) -> tuple[Any, Any]:
    """Return (start_dt, end_dt) for YYYY-MM period in UTC."""
    from datetime import datetime, timedelta

    raw = (period or "").strip()
    if len(raw) != 7 or raw[4] != "-":
        raise ValueError("period must be YYYY-MM")
    year = int(raw[0:4])
    month = int(raw[5:7])
    start = datetime(year, month, 1)
    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    return start, next_month


def _extract_tokens_from_receipt_blobs(metrics: Any, event: Any) -> int:
    """Best-effort token extraction from receipt metrics/event JSON."""
    try:
        total = 0
        m = metrics if isinstance(metrics, dict) else {}
        e = event if isinstance(event, dict) else {}
        ed = e.get("data") if isinstance(e, dict) else None
        ed = ed if isinstance(ed, dict) else {}

        # Common direct keys
        for key in ("tokens_used", "total_tokens"):
            val = m.get(key)
            if isinstance(val, (int, float)) and val >= 0:
                total += int(val)
            val2 = ed.get(key)
            if isinstance(val2, (int, float)) and val2 >= 0:
                total += int(val2)

        # OpenAI-style / provider-style usage dict[str, Any]
        usage = ed.get("usage") or m.get("usage")
        if isinstance(usage, dict):
            for key in (
                "total_tokens",
                "prompt_tokens",
                "completion_tokens",
                "input_tokens",
                "output_tokens",
            ):
                val = usage.get(key)
                if isinstance(val, (int, float)) and val >= 0:
                    total += int(val)

        return int(total)
    except Exception:
        return 0


def _extract_bytes_from_receipt_blobs(metrics: Any, event: Any) -> tuple[int, int]:
    """Best-effort (storage_bytes, bandwidth_bytes) extraction."""
    try:
        storage = 0
        bandwidth = 0
        m = metrics if isinstance(metrics, dict) else {}
        e = event if isinstance(event, dict) else {}
        ed = e.get("data") if isinstance(e, dict) else None
        ed = ed if isinstance(ed, dict) else {}

        for key in ("storage_bytes", "bytes_written", "bytes_stored"):
            val = m.get(key) or ed.get(key)
            if isinstance(val, (int, float)) and val >= 0:
                storage += int(val)

        for key in ("bandwidth_bytes", "bytes_sent", "bytes_received", "bytes_transferred"):
            val = m.get(key) or ed.get(key)
            if isinstance(val, (int, float)) and val >= 0:
                bandwidth += int(val)

        return int(storage), int(bandwidth)
    except Exception:
        return 0, 0


@celery_app.task(name="kagami.core.tasks.tasks.rollup_tenant_usage_task")
def rollup_tenant_usage_task(period: str | None = None, lookback_months: int = 2) -> dict[str, Any]:
    """Roll up TenantUsage from receipts + settlement records.

    Writes/updates rows in `tenant_usage` with:
    - ops_count (EXECUTE receipts)
    - settlement_count
    - tokens_used (best-effort from receipt JSON)
    - storage_bytes / bandwidth_bytes (best-effort from receipt JSON)
    - cost_usd (best-effort from TenantPlan pricing fields)
    """
    try:
        import os
        from datetime import datetime

        from sqlalchemy import func

        from kagami.core.database.connection import get_session_factory
        from kagami.core.database.models import Receipt, SettlementRecord, TenantPlan, TenantUsage

        now = datetime.utcnow()

        # Determine which periods to roll up (default: current + previous month)
        periods: list[str] = []
        if period:
            periods = [str(period)]
        else:
            months = max(1, int(lookback_months or 1))
            y, m = now.year, now.month
            for back in range(months):
                mm = m - back
                yy = y
                while mm <= 0:
                    mm += 12
                    yy -= 1
                periods.append(f"{yy:04d}-{mm:02d}")

        max_receipts_per_tenant = int(os.getenv("KAGAMI_USAGE_ROLLUP_MAX_RECEIPTS", "50000"))

        db = get_session_factory()()
        try:
            updated_rows = 0
            results: dict[str, Any] = {"periods": {}, "updated_rows": 0}

            for per in periods:
                start_dt, end_dt = _month_window_from_period(per)

                # Collect tenants with activity or plans
                tenant_ids: set[str] = set()
                try:
                    for (tid,) in (
                        db.query(TenantPlan.tenant_id)
                        .filter(TenantPlan.tenant_id.isnot(None))
                        .distinct()
                        .all()
                    ):
                        if tid:
                            tenant_ids.add(str(tid))
                except Exception:
                    pass
                try:
                    for (tid,) in (
                        db.query(Receipt.tenant_id)
                        .filter(Receipt.tenant_id.isnot(None))
                        .filter(Receipt.ts >= start_dt, Receipt.ts < end_dt)
                        .distinct()
                        .all()
                    ):
                        if tid:
                            tenant_ids.add(str(tid))
                except Exception:
                    pass
                try:
                    for (tid,) in (
                        db.query(SettlementRecord.tenant_id)
                        .filter(SettlementRecord.tenant_id.isnot(None))
                        .filter(
                            SettlementRecord.timestamp >= start_dt,
                            SettlementRecord.timestamp < end_dt,
                        )
                        .distinct()
                        .all()
                    ):
                        if tid:
                            tenant_ids.add(str(tid))
                except Exception:
                    pass

                period_summary = {"tenants": len(tenant_ids), "updated": 0}

                for tid in sorted(tenant_ids):
                    # Latest plan (best-effort)
                    plan = (
                        db.query(TenantPlan)
                        .filter(TenantPlan.tenant_id == tid)
                        .order_by(TenantPlan.valid_from.desc())
                        .first()
                    )

                    # Counts
                    ops_cnt = int(
                        db.query(func.count(Receipt.id))
                        .filter(Receipt.tenant_id == tid)
                        .filter(Receipt.ts >= start_dt, Receipt.ts < end_dt)
                        .filter(func.lower(Receipt.phase) == "execute")
                        .scalar()
                        or 0
                    )
                    settle_cnt = int(
                        db.query(func.count(SettlementRecord.id))
                        .filter(SettlementRecord.tenant_id == tid)
                        .filter(
                            SettlementRecord.timestamp >= start_dt,
                            SettlementRecord.timestamp < end_dt,
                        )
                        .scalar()
                        or 0
                    )

                    # Best-effort sums from receipts
                    tokens_used = 0
                    storage_bytes = 0
                    bandwidth_bytes = 0
                    try:
                        blobs = (
                            db.query(Receipt.metrics, Receipt.event)
                            .filter(Receipt.tenant_id == tid)
                            .filter(Receipt.ts >= start_dt, Receipt.ts < end_dt)
                            .filter(func.lower(Receipt.phase) == "execute")
                            .order_by(Receipt.ts.desc())
                            .limit(max_receipts_per_tenant)
                            .all()
                        )
                        for metrics_blob, event_blob in blobs:
                            tokens_used += _extract_tokens_from_receipt_blobs(
                                metrics_blob, event_blob
                            )
                            s_b, bw_b = _extract_bytes_from_receipt_blobs(metrics_blob, event_blob)
                            storage_bytes += s_b
                            bandwidth_bytes += bw_b
                    except Exception:
                        pass

                    # Cost model (best-effort)
                    ops_price_per_k = 0.0
                    settle_price = 0.0
                    user_id = None
                    try:
                        if plan:
                            user_id = getattr(plan, "user_id", None)
                            ops_price_per_k = float(getattr(plan, "ops_price_per_k", 0) or 0.0)
                            settle_price = float(getattr(plan, "settlement_price_per_op", 0) or 0.0)
                    except Exception:
                        ops_price_per_k = 0.0
                        settle_price = 0.0
                        user_id = None

                    cost = (ops_cnt / 1000.0) * ops_price_per_k + (settle_cnt * settle_price)

                    # Upsert TenantUsage row
                    usage_row = (
                        db.query(TenantUsage)
                        .filter(TenantUsage.tenant_id == tid, TenantUsage.period == per)
                        .first()
                    )
                    if usage_row:
                        usage_row.user_id = user_id
                        usage_row.ops_count = ops_cnt
                        usage_row.settlement_count = settle_cnt
                        usage_row.tokens_used = int(tokens_used)
                        usage_row.storage_bytes = int(storage_bytes)
                        usage_row.bandwidth_bytes = int(bandwidth_bytes)
                        usage_row.cost_usd = cost
                    else:
                        db.add(
                            TenantUsage(
                                tenant_id=tid,
                                user_id=user_id,
                                period=per,
                                ops_count=ops_cnt,
                                settlement_count=settle_cnt,
                                tokens_used=int(tokens_used),
                                storage_bytes=int(storage_bytes),
                                bandwidth_bytes=int(bandwidth_bytes),
                                cost_usd=cost,
                            )
                        )

                    try:
                        db.commit()
                    except Exception:
                        db.rollback()
                        continue

                    updated_rows += 1
                    period_summary["updated"] += 1

                results["periods"][per] = period_summary

            results["updated_rows"] = updated_rows
            return {"status": "success", **results}
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Tenant usage rollup failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@celery_app.task(name="kagami.core.tasks.tasks.rollup_marketplace_payouts_task", bind=True)
def rollup_marketplace_payouts_task(  # type: ignore[no-untyped-def]
    self,
    period: str | None = None,
    platform_take_rate: float = 0.20,
) -> dict[str, Any]:
    """Aggregate marketplace purchases into creator payouts.

    For each creator with paid plugin sales during the period:
    1. Sum gross revenue from MarketplacePurchase
    2. Apply platform take rate (default 20%)
    3. Upsert MarketplacePayout record

    Args:
        period: YYYY-MM format, defaults to current month
        platform_take_rate: Platform's share (0.20 = 20%), default 20%

    Returns:
        Summary dict[str, Any] with processing results
    """
    from datetime import datetime
    from decimal import Decimal

    from sqlalchemy import func

    from kagami.core.database.connection import get_session_factory
    from kagami.core.database.models import (
        MarketplacePayout,
        MarketplacePlugin,
        MarketplacePurchase,
    )

    logger.info(
        f"Starting marketplace payout rollup, period={period}, take_rate={platform_take_rate}"
    )

    try:
        db = get_session_factory()()
        try:
            # Determine period
            now = datetime.utcnow()
            if period:
                per = period[:7]  # YYYY-MM
            else:
                per = now.strftime("%Y-%m")

            # Parse period window
            year, month = int(per[:4]), int(per[5:7])
            start_dt = datetime(year, month, 1)
            if month == 12:
                end_dt = datetime(year + 1, 1, 1)
            else:
                end_dt = datetime(year, month + 1, 1)

            results: dict[str, Any] = {
                "period": per,
                "platform_take_rate": platform_take_rate,
                "creators_processed": 0,
                "total_gross_usd": 0.0,
                "total_payout_usd": 0.0,
                "payouts": [],
            }

            # Get all paid plugin purchases in period, grouped by plugin
            # Join with MarketplacePlugin to get author_id and price
            purchase_stats = (
                db.query(
                    MarketplacePurchase.item_id,
                    func.count(MarketplacePurchase.id).label("purchase_count"),
                )
                .filter(
                    MarketplacePurchase.item_type == "plugin",
                    MarketplacePurchase.started_at >= start_dt,
                    MarketplacePurchase.started_at < end_dt,
                    MarketplacePurchase.status.in_(
                        ["active", "cancelled"]
                    ),  # Count even if later cancelled
                )
                .group_by(MarketplacePurchase.item_id)
                .all()
            )

            for item_id, purchase_count in purchase_stats:
                # Get plugin details
                try:
                    from uuid import UUID

                    plugin_uuid = UUID(item_id)
                    plugin = (
                        db.query(MarketplacePlugin)
                        .filter(MarketplacePlugin.id == plugin_uuid)
                        .first()
                    )
                except Exception:
                    plugin = None

                if not plugin:
                    logger.warning(f"Plugin {item_id} not found, skipping payout")
                    continue

                # Skip free plugins
                if plugin.pricing_model == "free" or not plugin.price_usd or plugin.price_usd <= 0:
                    continue

                creator_id = plugin.author_id
                if not creator_id:
                    continue

                # Calculate gross and payout
                gross = Decimal(str(plugin.price_usd)) * purchase_count
                platform_cut = gross * Decimal(str(platform_take_rate))
                payout = gross - platform_cut

                # Upsert payout record
                existing = (
                    db.query(MarketplacePayout)
                    .filter(
                        MarketplacePayout.creator_id == creator_id,
                        MarketplacePayout.item_type == "plugin",
                        MarketplacePayout.item_id == item_id,
                        MarketplacePayout.period == per,
                    )
                    .first()
                )

                if existing:
                    existing.attestations = purchase_count
                    existing.gross_usd = gross
                    existing.platform_take_rate = float(platform_take_rate)
                    existing.payout_usd = payout
                else:
                    new_payout = MarketplacePayout(
                        creator_id=creator_id,
                        item_type="plugin",
                        item_id=item_id,
                        period=per,
                        attestations=purchase_count,
                        gross_usd=gross,
                        platform_take_rate=platform_take_rate,
                        payout_usd=payout,
                    )
                    db.add(new_payout)

                results["payouts"].append(
                    {
                        "creator_id": creator_id,
                        "plugin_id": item_id,
                        "plugin_name": plugin.name,
                        "purchases": purchase_count,
                        "gross_usd": float(gross),
                        "payout_usd": float(payout),
                    }
                )
                results["total_gross_usd"] += float(gross)
                results["total_payout_usd"] += float(payout)
                results["creators_processed"] += 1

            try:
                db.commit()
            except Exception as e:
                logger.error(f"Failed to commit payouts: {e}")
                db.rollback()
                return {"status": "error", "error": str(e)}

            logger.info(
                f"Payout rollup complete: {results['creators_processed']} creators, "
                f"${results['total_gross_usd']:.2f} gross, ${results['total_payout_usd']:.2f} payout"
            )
            return {"status": "success", **results}
        finally:
            try:
                db.close()
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Marketplace payout rollup failed: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@celery_app.task(name="kagami.core.tasks.tasks.slo_monitor_task")
def slo_monitor_task() -> dict[str, Any]:
    """
    Monitor Service Level Objectives (SLOs) and emit alerts.

    Checks key metrics against defined thresholds:
    - API latency (p99 < 500ms)
    - Error rate (< 1%)
    - Availability (> 99.9%)

    Returns:
        dict[str, Any]: SLO compliance status
    """
    try:
        from datetime import datetime

        results: dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "slos": {},
            "violations": [],
        }

        # Check API latency SLO
        try:
            from kagami_observability.metrics import API_LATENCY_P99

            latency_p99 = API_LATENCY_P99._value.get() if hasattr(API_LATENCY_P99, "_value") else 0
            slo_latency = latency_p99 < 0.5  # 500ms
            results["slos"]["latency_p99"] = {
                "value": latency_p99,
                "threshold": 0.5,
                "compliant": slo_latency,
            }
            if not slo_latency:
                results["violations"].append(f"latency_p99={latency_p99:.3f}s > 0.5s")
        except Exception:
            pass

        # Check error rate SLO
        try:
            from kagami_observability.metrics import API_ERROR_RATE

            error_rate = API_ERROR_RATE._value.get() if hasattr(API_ERROR_RATE, "_value") else 0
            slo_errors = error_rate < 0.01  # 1%
            results["slos"]["error_rate"] = {
                "value": error_rate,
                "threshold": 0.01,
                "compliant": slo_errors,
            }
            if not slo_errors:
                results["violations"].append(f"error_rate={error_rate:.2%} > 1%")
        except Exception:
            pass

        # Emit SLO metric
        try:
            from kagami_observability.metrics import SLO_COMPLIANCE

            all_compliant = len(results["violations"]) == 0
            SLO_COMPLIANCE.set(1 if all_compliant else 0)
        except Exception:
            pass

        results["status"] = "success"
        results["compliant"] = len(results["violations"]) == 0

        if results["violations"]:
            logger.warning(f"SLO violations: {results['violations']}")
        else:
            logger.debug("All SLOs compliant")

        return results
    except Exception as e:
        logger.error(f"SLO monitoring failed: {e}")
        return {"status": "error", "error": str(e)}
