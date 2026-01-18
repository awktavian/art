"""Public marketplace for K os plugins and extensions.

Allows developers to:
- Submit plugins for review
- Browse available plugins
- Install plugins
- Rate and review plugins
- Earn revenue from paid plugins
"""

import logging
import os
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from kagami.core.database.connection import get_db_session, get_session_factory
from kagami.core.database.models import (
    MarketplacePlugin,
    MarketplacePluginReview,
    MarketplacePurchase,
)
from kagami.core.safety import enforce_tier1
from kagami.core.safety.cbf_integration import check_cbf_for_operation
from pydantic import BaseModel, Field
from sqlalchemy import func, text

from kagami_api.security import Principal, optional_auth, require_auth

logger = logging.getLogger(__name__)


def get_router() -> APIRouter:
    """Create and configure the API router.

    Factory function for lazy router instantiation.
    Router is not created until this function is called.
    """
    router = APIRouter(tags=["marketplace"])

    # Stripe plugin checkout URL (env or computed)
    STRIPE_PLUGIN_CHECKOUT_URL = os.getenv(
        "STRIPE_PLUGIN_CHECKOUT_URL", "/api/billing/plugin_checkout"
    )

    class PluginSubmission(BaseModel):
        """Plugin submission for review."""

        name: str = Field(..., min_length=3, max_length=100)
        description: str = Field(..., min_length=20, max_length=1000)
        category: str = Field(..., pattern="^(agent|integration|tool|ui|theme)$")
        version: str = Field(..., pattern="^\\d+\\.\\d+\\.\\d+$")
        repository_url: str | None = None
        documentation_url: str | None = None
        homepage_url: str | None = None
        pricing_model: str = Field("free", pattern="^(free|paid|freemium)$")
        price_usd: float | None = Field(None, ge=0, le=10000)
        kagami_min_version: str | None = None
        required_permissions: list[str] = []
        external_dependencies: list[str] = []
        icon_url: str | None = None
        screenshot_urls: list[str] = []
        video_url: str | None = None
        tags: list[str] = []
        license: str = "MIT"

    class PluginReview(BaseModel):
        """User review of a plugin."""

        rating: int = Field(..., ge=1, le=5)
        title: str = Field(..., min_length=3, max_length=100)
        comment: str = Field(..., min_length=10, max_length=2000)

    @router.get("/plugins")
    async def list_plugins(
        query: str | None = None,
        category: str | None = None,
        pricing: str | None = None,
        min_rating: float | None = None,
        sort_by: str = "popular",
        page: int = 1,
        page_size: int = 20,
        user: Principal | None = Depends(optional_auth),
    ) -> dict:
        """List available plugins with filtering and pagination.

        Public endpoint - no auth required.
        """
        try:
            async with get_db_session() as db:
                conditions = ["status = 'approved'"]
                params: dict[str, Any] = {}
                if query:
                    conditions.append("(name ILIKE :query OR description ILIKE :query)")
                    params["query"] = f"%{query}%"
                if category:
                    conditions.append("category = :category")
                    params["category"] = category
                if pricing:
                    conditions.append("pricing_model = :pricing")
                    params["pricing"] = pricing
                if min_rating:
                    conditions.append("average_rating >= :min_rating")
                    params["min_rating"] = min_rating
                where_clause = " AND ".join(conditions)
                order_map = {
                    "popular": "install_count DESC",
                    "recent": "submitted_at DESC",
                    "rating": "average_rating DESC",
                    "name": "name ASC",
                }
                order_by = order_map.get(sort_by, "install_count DESC")
                # Use sqlalchemy.text() for parameterized queries - prevents SQL injection
                # Note: where_clause uses only controlled strings + bound params
                # order_by uses whitelist validation via order_map
                count_query = text(f"SELECT COUNT(*) FROM marketplace_plugins WHERE {where_clause}")
                count_result = db.execute(count_query, params)
                total = int(count_result.scalar() or 0)
                offset = (page - 1) * page_size
                params["limit"] = page_size
                params["offset"] = offset
                select_query = text(
                    f"""
                    SELECT
                        id, name, description, category, version,
                        pricing_model, price_usd, icon_url,
                        author_id, author_name, install_count,
                        average_rating, review_count,
                        submitted_at, approved_at
                    FROM marketplace_plugins
                    WHERE {where_clause}
                    ORDER BY {order_by}
                    LIMIT :limit OFFSET :offset
                """
                )
                result = db.execute(select_query, params)
                plugins = [dict(row) for row in result.fetchall()]
                return {
                    "plugins": plugins,
                    "total": total,
                    "page": page,
                    "page_size": page_size,
                    "pages": (total + page_size - 1) // page_size,
                }
        except Exception as e:
            logger.error(f"Failed to list plugins: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e)) from None

    @router.post("/plugins/submit")
    @enforce_tier1("rate_limit")
    async def submit_plugin(  # type: ignore[no-untyped-def]
        submission: PluginSubmission,
        user: Principal = Depends(require_auth),
    ):
        """Submit a plugin for review.

        Requires authentication. The plugin enters 'pending' status and awaits admin approval.
        """
        # CBF safety check
        cbf_result = await check_cbf_for_operation(
            operation="api.marketplace.submit_plugin",
            action="submit",
            target="plugin",
            params=submission.model_dump(),
            metadata={"endpoint": "/api/marketplace/plugins/submit", "name": submission.name},
            source="api",
        )
        if not cbf_result.safe:
            raise HTTPException(
                status_code=403,
                detail=f"Safety check failed: {cbf_result.reason}",
            )

        db = get_session_factory()()
        try:
            # Check for duplicate name by same author
            existing = (
                db.query(MarketplacePlugin)
                .filter(MarketplacePlugin.name == submission.name)
                .filter(MarketplacePlugin.author_id == user.sub)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=f"You already have a plugin named '{submission.name}'. Update it instead.",
                )

            plugin = MarketplacePlugin(
                name=submission.name,
                description=submission.description,
                category=submission.category,
                version=submission.version,
                repository_url=submission.repository_url,
                documentation_url=submission.documentation_url,
                homepage_url=submission.homepage_url,
                pricing_model=submission.pricing_model,
                price_usd=submission.price_usd if submission.pricing_model != "free" else None,
                kagami_min_version=submission.kagami_min_version,
                required_permissions=submission.required_permissions,
                external_dependencies=submission.external_dependencies,
                icon_url=submission.icon_url,
                screenshot_urls=submission.screenshot_urls,
                video_url=submission.video_url,
                tags=submission.tags,
                license=submission.license,
                status="pending",
                author_id=user.sub,
                author_name=getattr(user, "name", None) or user.sub,
                submitted_at=datetime.utcnow(),
            )
            db.add(plugin)
            db.commit()
            db.refresh(plugin)

            return {
                "id": str(plugin.id),
                "name": plugin.name,
                "status": plugin.status,
                "message": "Plugin submitted for review. You'll be notified when approved.",
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to submit plugin: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to submit plugin") from None
        finally:
            db.close()

    @router.get("/plugins/{plugin_id}")
    async def get_plugin_details(  # type: ignore[no-untyped-def]
        plugin_id: str,
        user: Principal | None = Depends(optional_auth),
    ):
        """Get detailed information about a plugin.

        Public for approved plugins. Shows pending plugins only to their author.
        """
        db = get_session_factory()()
        try:
            plugin_uuid = UUID(plugin_id)
            plugin = db.query(MarketplacePlugin).filter(MarketplacePlugin.id == plugin_uuid).first()
            if not plugin:
                raise HTTPException(status_code=404, detail="Plugin not found")

            # Only show non-approved plugins to their author
            if plugin.status != "approved":
                if not user or user.sub != plugin.author_id:
                    raise HTTPException(status_code=404, detail="Plugin not found")

            # Check if current user has installed this plugin
            is_installed = False
            if user:
                try:
                    user_uuid = UUID(user.sub) if user.sub else None
                    if user_uuid:
                        purchase = (
                            db.query(MarketplacePurchase)
                            .filter(
                                MarketplacePurchase.user_id == user_uuid,
                                MarketplacePurchase.item_type == "plugin",
                                MarketplacePurchase.item_id == plugin_id,
                                MarketplacePurchase.status == "active",
                            )
                            .first()
                        )
                        is_installed = purchase is not None
                except Exception:
                    pass

            return {
                "id": str(plugin.id),
                "name": plugin.name,
                "description": plugin.description,
                "category": plugin.category,
                "version": plugin.version,
                "repository_url": plugin.repository_url,
                "documentation_url": plugin.documentation_url,
                "homepage_url": plugin.homepage_url,
                "pricing_model": plugin.pricing_model,
                "price_usd": plugin.price_usd,
                "kagami_min_version": plugin.kagami_min_version,
                "required_permissions": plugin.required_permissions or [],
                "external_dependencies": plugin.external_dependencies or [],
                "icon_url": plugin.icon_url,
                "screenshot_urls": plugin.screenshot_urls or [],
                "video_url": plugin.video_url,
                "tags": plugin.tags or [],
                "license": plugin.license,
                "status": plugin.status,
                "author_id": plugin.author_id,
                "author_name": plugin.author_name,
                "install_count": plugin.install_count,
                "average_rating": plugin.average_rating,
                "review_count": plugin.review_count,
                "submitted_at": plugin.submitted_at.isoformat() if plugin.submitted_at else None,
                "approved_at": plugin.approved_at.isoformat() if plugin.approved_at else None,
                "is_installed": is_installed,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to get plugin details: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to get plugin details") from None
        finally:
            db.close()

    @router.post("/plugins/{plugin_id}/install")
    @enforce_tier1("process")
    async def install_plugin(  # type: ignore[no-untyped-def]
        plugin_id: str,
        user: Principal = Depends(require_auth),
    ):
        """Install a plugin.

        For paid plugins, user must have completed purchase via Stripe.
        For free plugins, creates an entitlement immediately.
        """
        db = get_session_factory()()
        try:
            plugin_uuid = UUID(plugin_id)
            user_uuid = UUID(user.sub)

            plugin = db.query(MarketplacePlugin).filter(MarketplacePlugin.id == plugin_uuid).first()
            if not plugin:
                raise HTTPException(status_code=404, detail="Plugin not found")
            if plugin.status != "approved":
                raise HTTPException(
                    status_code=400, detail="Plugin is not available for installation"
                )

            # Check if already installed
            existing = (
                db.query(MarketplacePurchase)
                .filter(
                    MarketplacePurchase.user_id == user_uuid,
                    MarketplacePurchase.item_type == "plugin",
                    MarketplacePurchase.item_id == plugin_id,
                    MarketplacePurchase.status == "active",
                )
                .first()
            )
            if existing:
                return {"status": "already_installed", "plugin_id": plugin_id}

            # For paid plugins, require prior purchase or redirect to checkout
            if plugin.pricing_model == "paid" and plugin.price_usd and plugin.price_usd > 0:
                # Check for completed purchase record (from Stripe webhook)
                purchase_record = (
                    db.query(MarketplacePurchase)
                    .filter(
                        MarketplacePurchase.user_id == user_uuid,
                        MarketplacePurchase.item_type == "plugin",
                        MarketplacePurchase.item_id == plugin_id,
                    )
                    .first()
                )
                if not purchase_record:
                    # Need to purchase first
                    raise HTTPException(
                        status_code=402,
                        detail={
                            "message": "Purchase required",
                            "checkout_url": f"{STRIPE_PLUGIN_CHECKOUT_URL}?plugin_id={plugin_id}",
                            "price_usd": plugin.price_usd,
                        },
                    )
                # Reactivate if previously cancelled
                purchase_record.status = "active"

                purchase_record.started_at = datetime.utcnow()

                db.commit()
            else:
                # Free plugin - create entitlement
                entitlement = MarketplacePurchase(
                    user_id=user_uuid,
                    item_type="plugin",
                    item_id=plugin_id,
                    price_model=plugin.pricing_model,
                    status="active",
                    started_at=datetime.utcnow(),
                    purchase_metadata={"version_installed": plugin.version},
                )
                db.add(entitlement)

            # Increment install count
            plugin.install_count = (plugin.install_count or 0) + 1

            db.commit()

            return {"status": "installed", "plugin_id": plugin_id, "version": plugin.version}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to install plugin: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to install plugin") from None
        finally:
            db.close()

    @router.delete("/plugins/{plugin_id}/install")
    @enforce_tier1("process")
    async def uninstall_plugin(  # type: ignore[no-untyped-def]
        plugin_id: str,
        user: Principal = Depends(require_auth),
    ):
        """Uninstall a plugin.

        Marks the entitlement as 'cancelled'. Does not decrement install_count.
        """
        db = get_session_factory()()
        try:
            user_uuid = UUID(user.sub)

            entitlement = (
                db.query(MarketplacePurchase)
                .filter(
                    MarketplacePurchase.user_id == user_uuid,
                    MarketplacePurchase.item_type == "plugin",
                    MarketplacePurchase.item_id == plugin_id,
                    MarketplacePurchase.status == "active",
                )
                .first()
            )
            if not entitlement:
                raise HTTPException(status_code=404, detail="Plugin not installed")

            entitlement.status = "cancelled"

            db.commit()

            return {"status": "uninstalled", "plugin_id": plugin_id}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to uninstall plugin: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to uninstall plugin") from None
        finally:
            db.close()

    @router.post("/plugins/{plugin_id}/reviews")
    async def review_plugin(  # type: ignore[no-untyped-def]
        plugin_id: str,
        review: PluginReview,
        user: Principal = Depends(require_auth),
    ):
        """Submit or update a review for a plugin.

        User must have the plugin installed. One review per user per plugin.
        """
        db = get_session_factory()()
        try:
            plugin_uuid = UUID(plugin_id)
            user_uuid = UUID(user.sub)

            plugin = db.query(MarketplacePlugin).filter(MarketplacePlugin.id == plugin_uuid).first()
            if not plugin:
                raise HTTPException(status_code=404, detail="Plugin not found")
            if plugin.status != "approved":
                raise HTTPException(status_code=400, detail="Cannot review unapproved plugins")

            # Check if user has the plugin installed
            entitlement = (
                db.query(MarketplacePurchase)
                .filter(
                    MarketplacePurchase.user_id == user_uuid,
                    MarketplacePurchase.item_type == "plugin",
                    MarketplacePurchase.item_id == plugin_id,
                )
                .first()
            )
            if not entitlement:
                raise HTTPException(
                    status_code=403, detail="You must install the plugin before reviewing"
                )

            # Create or update review
            existing_review = (
                db.query(MarketplacePluginReview)
                .filter(
                    MarketplacePluginReview.plugin_id == plugin_uuid,
                    MarketplacePluginReview.user_id == user_uuid,
                )
                .first()
            )
            is_new = existing_review is None
            if existing_review:
                existing_review.rating = review.rating

                existing_review.title = review.title

                existing_review.comment = review.comment

                existing_review.updated_at = datetime.utcnow()

            else:
                new_review = MarketplacePluginReview(
                    plugin_id=plugin_uuid,
                    user_id=user_uuid,
                    rating=review.rating,
                    title=review.title,
                    comment=review.comment,
                    status="active",
                )
                db.add(new_review)

            # Recompute average rating and review count
            stats = (
                db.query(
                    func.count(MarketplacePluginReview.id),
                    func.avg(MarketplacePluginReview.rating),
                )
                .filter(
                    MarketplacePluginReview.plugin_id == plugin_uuid,
                    MarketplacePluginReview.status == "active",
                )
                .first()
            )
            review_count_result: int = int(stats[0]) if stats[0] else 0
            avg_rating_result: float = float(stats[1]) if stats[1] else 0.0
            # If this is a new review, count includes it already after commit; adjust for pre-commit
            if is_new:
                # Recalc manually since not committed yet
                total_rating = avg_rating_result * review_count_result + review.rating
                review_count_result += 1
                avg_rating_result = (
                    total_rating / review_count_result if review_count_result else 0.0
                )

            plugin.review_count = review_count_result

            plugin.average_rating = round(avg_rating_result, 2)

            db.commit()

            return {
                "status": "created" if is_new else "updated",
                "plugin_id": plugin_id,
                "rating": review.rating,
                "average_rating": plugin.average_rating,
                "review_count": plugin.review_count,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to submit review: {e}", exc_info=True)
            db.rollback()
            raise HTTPException(status_code=500, detail="Failed to submit review") from None
        finally:
            db.close()

    @router.get("/plugins/{plugin_id}/reviews")
    async def list_plugin_reviews(  # type: ignore[no-untyped-def]
        plugin_id: str,
        page: int = 1,
        page_size: int = 20,
        user: Principal | None = Depends(optional_auth),
    ):
        """List reviews for a plugin with pagination."""
        db = get_session_factory()()
        try:
            plugin_uuid = UUID(plugin_id)

            plugin = db.query(MarketplacePlugin).filter(MarketplacePlugin.id == plugin_uuid).first()
            if not plugin or plugin.status != "approved":
                raise HTTPException(status_code=404, detail="Plugin not found")

            total = (
                db.query(func.count(MarketplacePluginReview.id))
                .filter(
                    MarketplacePluginReview.plugin_id == plugin_uuid,
                    MarketplacePluginReview.status == "active",
                )
                .scalar()
                or 0
            )

            offset = (page - 1) * page_size
            reviews = (
                db.query(MarketplacePluginReview)
                .filter(
                    MarketplacePluginReview.plugin_id == plugin_uuid,
                    MarketplacePluginReview.status == "active",
                )
                .order_by(MarketplacePluginReview.created_at.desc())
                .offset(offset)
                .limit(page_size)
                .all()
            )

            return {
                "reviews": [
                    {
                        "id": str(r.id),
                        "user_id": str(r.user_id),
                        "rating": r.rating,
                        "title": r.title,
                        "comment": r.comment,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in reviews
                ],
                "total": total,
                "page": page,
                "page_size": page_size,
                "pages": (total + page_size - 1) // page_size if total else 0,
            }
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to list reviews: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to list reviews") from None
        finally:
            db.close()

    return router
