"""Database module for K OS - Optimized for CockroachDB.

REWRITTEN: December 2, 2025

This module provides:
- Sync and async database connections
- ORM models optimized for CockroachDB
- Connection pooling with CockroachDB-specific settings
- UUID-based primary keys (no sequential hotspots)
"""

# Connection management
# Async connection management
from .async_connection import (
    get_async_db_session,
    get_async_engine,
    get_async_session,
    init_async_db,
    reset_async_engine,
)

# Base class for all models
from .base import Base
from .connection import (
    check_connection,
    get_db,
    get_db_session,
    get_session,
    get_session_factory,
    get_session_generator,
    init_db,
    init_db_sync,
    resolve_database_url,
)

# Core models
from .models import (
    APIKey,
    # Generic
    AppData,
    AuditLogEntry,
    CalibrationPoint,
    ExpectedFreeEnergy,
    # Goals
    Goal,
    IdempotencyKey,
    IntegrationMeasurement,
    MarketplacePayout,
    MarketplacePlugin,
    MarketplacePluginReview,
    MarketplacePurchase,
    Plan,
    PlanTask,
    PrivacyAuditLog,
    ProceduralWorkflow,
    # Receipts
    Receipt,
    # Learning
    RewardSignal,
    # Safety
    SafetyStateSnapshot,
    Session,
    SettlementRecord,
    # Billing
    TenantPlan,
    TenantUsage,
    ThreatClassification,
    TICRecord,
    # Core
    User,
    # Privacy
    UserConsent,
    UserSettings,
    VerificationToken,
    WorldModelPrediction,
    # Utilities
    generate_uuid,
)

__all__ = [
    "APIKey",
    # Generic
    "AppData",
    "AuditLogEntry",
    # Base
    "Base",
    "CalibrationPoint",
    "ExpectedFreeEnergy",
    # Goals
    "Goal",
    "IdempotencyKey",
    "IntegrationMeasurement",
    "MarketplacePayout",
    "MarketplacePlugin",
    "MarketplacePluginReview",
    "MarketplacePurchase",
    "Plan",
    "PlanTask",
    "PrivacyAuditLog",
    "ProceduralWorkflow",
    # Receipts
    "Receipt",
    # Learning
    "RewardSignal",
    # Safety
    "SafetyStateSnapshot",
    "Session",
    "SettlementRecord",
    "TICRecord",
    # Billing
    "TenantPlan",
    "TenantUsage",
    "ThreatClassification",
    # Core Models
    "User",
    # Privacy
    "UserConsent",
    "UserSettings",
    "VerificationToken",
    "WorldModelPrediction",
    "check_connection",
    # Utilities
    "generate_uuid",
    # Async Connection
    "get_async_db_session",
    "get_async_engine",
    "get_async_session",
    # Connection
    "get_db",
    "get_db_session",
    "get_session",
    "get_session_factory",
    "get_session_generator",
    "init_async_db",
    "init_db",
    "init_db_sync",
    "reset_async_engine",
    "resolve_database_url",
]
