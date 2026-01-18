"""Storage Audit Initialization — Startup Integration for All Fixes.

This module initializes all storage audit improvements at application startup.
Include this in your application boot sequence to enable:

1. OAuth token migration to Keychain
2. PII encryption for sensitive columns
3. Extended receipt TTL with archival
4. Weaviate audit logging
5. Weaviate backup scheduling
6. Secure Redis configuration
7. Time-series analytics
8. Distributed storage

Usage:
    # In your application startup
    from kagami.core.storage.storage_audit_init import initialize_storage_audit

    await initialize_storage_audit()

Created: December 30, 2025
Author: Kagami Storage Audit
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


async def initialize_storage_audit(
    weaviate_client: Any = None,
    skip_migration: bool = False,
) -> dict[str, bool]:
    """Initialize all storage audit improvements.

    Args:
        weaviate_client: Weaviate client for audit logging and backups
        skip_migration: Skip one-time migrations (for testing)

    Returns:
        Dict of component -> success status
    """
    results = {}

    # 1. Migrate OAuth tokens from plaintext to Keychain (P0-1)
    if not skip_migration:
        try:
            from kagami.core.security.secure_credentials import (
                check_and_migrate_all_plaintext_credentials,
            )

            migration_results = check_and_migrate_all_plaintext_credentials()
            results["oauth_migration"] = all(migration_results.values())
            logger.info(f"OAuth migration: {migration_results}")
        except Exception as e:
            logger.error(f"OAuth migration failed: {e}")
            results["oauth_migration"] = False

    # 2. Patch receipt storage for extended TTL (P1-1)
    try:
        from kagami.core.receipts.receipt_archival import (
            patch_receipt_storage_ttl,
            start_receipt_archival,
        )

        patch_receipt_storage_ttl()
        await start_receipt_archival()
        results["receipt_archival"] = True
        logger.info("Receipt archival service started")
    except Exception as e:
        logger.error(f"Receipt archival failed: {e}")
        results["receipt_archival"] = False

    # 3. Initialize Weaviate audit logging (P1-2)
    if weaviate_client:
        try:
            from satellites.integrations.kagami_integrations.elysia.weaviate_audit import (
                initialize_audit_logger,
            )

            await initialize_audit_logger(weaviate_client)
            results["weaviate_audit"] = True
            logger.info("Weaviate audit logging initialized")
        except Exception as e:
            logger.error(f"Weaviate audit logging failed: {e}")
            results["weaviate_audit"] = False

    # 4. Initialize Weaviate backup service (P2-1)
    if weaviate_client:
        try:
            from satellites.integrations.kagami_integrations.elysia.weaviate_backup import (
                initialize_backup_service,
            )

            await initialize_backup_service(weaviate_client)
            results["weaviate_backup"] = True
            logger.info("Weaviate backup service initialized")
        except Exception as e:
            logger.error(f"Weaviate backup service failed: {e}")
            results["weaviate_backup"] = False

    # 5. Patch Redis config for secure credentials (P1-3)
    try:
        from kagami.core.caching.secure_redis_config import (
            migrate_redis_cache_config,
        )

        migrate_redis_cache_config()
        results["secure_redis"] = True
        logger.info("Redis config migrated to secure configuration")
    except Exception as e:
        logger.error(f"Secure Redis config failed: {e}")
        results["secure_redis"] = False

    # 6. Initialize time-series analytics (P2-2)
    try:
        from kagami.core.analytics.timeseries_optimization import get_analytics

        get_analytics()
        results["timeseries_analytics"] = True
        logger.info("Time-series analytics initialized")
    except Exception as e:
        logger.error(f"Time-series analytics failed: {e}")
        results["timeseries_analytics"] = False

    # 7. Initialize distributed storage (P2-3)
    try:
        from kagami.core.persistence.distributed_storage import get_distributed_storage

        storage = get_distributed_storage()
        results["distributed_storage"] = True
        logger.info(f"Distributed storage initialized (backend: {storage.config.backend.value})")
    except Exception as e:
        logger.error(f"Distributed storage failed: {e}")
        results["distributed_storage"] = False

    # Summary
    success_count = sum(1 for v in results.values() if v)
    total_count = len(results)

    logger.info(f"Storage audit initialization complete: {success_count}/{total_count} components")

    return results


def get_storage_audit_status() -> dict[str, Any]:
    """Get current status of storage audit components.

    Returns:
        Dict with status of each component
    """
    status = {}

    # Check each component
    try:
        from kagami.core.security.secure_credentials import get_secure_credentials

        get_secure_credentials()
        status["secure_credentials"] = {"available": True}
    except Exception as e:
        status["secure_credentials"] = {"available": False, "error": str(e)}

    try:
        from kagami.core.receipts.receipt_archival import get_receipt_archival

        archival = get_receipt_archival()
        status["receipt_archival"] = {
            "available": True,
            "stats": archival.get_stats().to_dict(),
        }
    except Exception as e:
        status["receipt_archival"] = {"available": False, "error": str(e)}

    try:
        from kagami.core.caching.secure_redis_config import get_secure_redis_config

        config = get_secure_redis_config()
        status["secure_redis"] = {
            "available": True,
            "config": config.to_dict(),
        }
    except Exception as e:
        status["secure_redis"] = {"available": False, "error": str(e)}

    try:
        from kagami.core.persistence.distributed_storage import get_distributed_storage

        storage = get_distributed_storage()
        status["distributed_storage"] = {
            "available": True,
            "backend": storage.config.backend.value,
        }
    except Exception as e:
        status["distributed_storage"] = {"available": False, "error": str(e)}

    return status


__all__ = [
    "get_storage_audit_status",
    "initialize_storage_audit",
]
