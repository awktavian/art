"""Privacy Framework for Ambient Intelligence.

Implements privacy-by-design principles for ambient sensing:
- Data classification by sensitivity level
- Retention policies with automatic expiration
- Local-first processing
- Audit logging for transparency
- GDPR-compliant data export/deletion

Design Principles:
1. Minimum necessary data: Only sense what's needed
2. Local first: Process on-device, sync patterns not raw data
3. Temporal limits: Auto-delete after retention period
4. Transparency: User can see what was captured
5. Control: User can pause/delete at any time

Created: December 7, 2025
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DataSensitivity(Enum):
    """Sensitivity levels for ambient data."""

    PUBLIC = "public"  # Time of day, general preferences
    INTERNAL = "internal"  # Activity patterns, device state
    CONFIDENTIAL = "confidential"  # Location, voice transcripts
    RESTRICTED = "restricted"  # Biometrics, health data, video


class DataCategory(Enum):
    """Categories of ambient data collected."""

    PRESENCE = "presence"  # Is user present?
    LOCATION = "location"  # Where is user? (GPS, room)
    ACTIVITY = "activity"  # What is user doing?
    AUDIO = "audio"  # Voice, ambient sound
    VIDEO = "video"  # Camera capture
    BIOMETRIC = "biometric"  # Heart rate, etc.
    DEVICE = "device"  # Battery, screen state
    CONTEXT = "context"  # Derived context (home/work/etc)
    INTERACTION = "interaction"  # User commands, preferences


# Default sensitivity mapping
CATEGORY_SENSITIVITY: dict[DataCategory, DataSensitivity] = {
    DataCategory.PRESENCE: DataSensitivity.INTERNAL,
    DataCategory.LOCATION: DataSensitivity.CONFIDENTIAL,
    DataCategory.ACTIVITY: DataSensitivity.INTERNAL,
    DataCategory.AUDIO: DataSensitivity.CONFIDENTIAL,
    DataCategory.VIDEO: DataSensitivity.RESTRICTED,
    DataCategory.BIOMETRIC: DataSensitivity.RESTRICTED,
    DataCategory.DEVICE: DataSensitivity.PUBLIC,
    DataCategory.CONTEXT: DataSensitivity.INTERNAL,
    DataCategory.INTERACTION: DataSensitivity.INTERNAL,
}

# Default retention periods (hours)
DEFAULT_RETENTION_HOURS: dict[DataSensitivity, int] = {
    DataSensitivity.PUBLIC: 720,  # 30 days
    DataSensitivity.INTERNAL: 168,  # 7 days
    DataSensitivity.CONFIDENTIAL: 24,  # 24 hours
    DataSensitivity.RESTRICTED: 1,  # 1 hour (or immediate processing)
}


@dataclass
class SensorPolicy:
    """Privacy policy for a specific sensor/data type."""

    category: DataCategory
    sensitivity: DataSensitivity
    retention_hours: int
    local_only: bool = True  # Never transmit raw data
    anonymize: bool = True  # Strip PII before any storage
    require_consent: bool = True  # Explicit consent needed
    active: bool = False  # Currently collecting?

    @classmethod
    def default_for_category(cls, category: DataCategory) -> SensorPolicy:
        """Create default policy for a data category."""
        sensitivity = CATEGORY_SENSITIVITY.get(category, DataSensitivity.CONFIDENTIAL)
        retention = DEFAULT_RETENTION_HOURS.get(sensitivity, 24)

        return cls(
            category=category,
            sensitivity=sensitivity,
            retention_hours=retention,
            local_only=sensitivity in (DataSensitivity.CONFIDENTIAL, DataSensitivity.RESTRICTED),
            anonymize=sensitivity != DataSensitivity.PUBLIC,
            require_consent=sensitivity != DataSensitivity.PUBLIC,
        )


@dataclass
class AuditEntry:
    """Audit log entry for data capture."""

    timestamp: float
    category: DataCategory
    action: str  # "capture", "access", "delete", "export"
    description: str
    data_hash: str | None = None  # Hash of data (not data itself)
    retention_until: float | None = None
    consent_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp).isoformat(),
            "category": self.category.value,
            "action": self.action,
            "description": self.description,
            "data_hash": self.data_hash,
            "retention_until": self.retention_until,
            "consent_id": self.consent_id,
        }


@dataclass
class PrivacyConfig:
    """Privacy manager configuration."""

    # Storage paths
    audit_log_path: Path = field(
        default_factory=lambda: Path.home() / ".kagami" / "privacy" / "audit.jsonl"
    )
    data_store_path: Path = field(
        default_factory=lambda: Path.home() / ".kagami" / "privacy" / "data"
    )

    # Global settings
    default_local_only: bool = True
    default_anonymize: bool = True
    audit_retention_days: int = 90  # Keep audit log for 90 days
    enable_audit_log: bool = True

    # Cleanup
    cleanup_interval_hours: float = 1.0  # Run cleanup every hour
    strict_retention: bool = True  # Delete immediately when expired


class PrivacyManager:
    """Manages ambient data privacy.

    Responsibilities:
    - Track what data is being captured
    - Enforce retention policies
    - Provide audit trail
    - Support data export/deletion
    """

    def __init__(self, config: PrivacyConfig | None = None):
        """Initialize privacy manager.

        Args:
            config: Privacy configuration
        """
        self.config = config or PrivacyConfig()

        # Sensor policies
        self._policies: dict[DataCategory, SensorPolicy] = {}
        self._init_default_policies()

        # Audit log (in-memory buffer + file)
        self._audit_buffer: list[AuditEntry] = []
        self._audit_buffer_max = 100

        # Data store (category -> list[Any] of data entries)
        self._data_store: dict[DataCategory, list[dict[str, Any]]] = {}

        # Statistics
        self._stats = {
            "captures": 0,
            "deletions": 0,
            "exports": 0,
            "consent_checks": 0,
            "blocked_captures": 0,
        }

        # Background cleanup task
        self._running = False
        self._cleanup_task: asyncio.Task | None = None

        # Ensure directories exist
        self.config.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.config.data_store_path.mkdir(parents=True, exist_ok=True)

        logger.info("🔐 Privacy manager initialized")

    def _init_default_policies(self) -> None:
        """Initialize default policies for all categories."""
        for category in DataCategory:
            self._policies[category] = SensorPolicy.default_for_category(category)

    # =========================================================================
    # Policy Management
    # =========================================================================

    def get_policy(self, category: DataCategory) -> SensorPolicy:
        """Get policy for a data category.

        Args:
            category: Data category

        Returns:
            Sensor policy
        """
        return self._policies.get(category, SensorPolicy.default_for_category(category))

    def set_policy(self, category: DataCategory, policy: SensorPolicy) -> None:
        """Set policy for a data category.

        Args:
            category: Data category
            policy: New policy
        """
        self._policies[category] = policy
        logger.info(f"🔐 Policy updated for {category.value}: retention={policy.retention_hours}h")

    def set_retention(self, category: DataCategory, hours: int) -> None:
        """Set retention period for a category.

        Args:
            category: Data category
            hours: Retention in hours (0 = no storage)
        """
        policy = self.get_policy(category)
        policy.retention_hours = hours
        self._policies[category] = policy

    def set_local_only(self, category: DataCategory, local_only: bool) -> None:
        """Set local-only flag for a category.

        Args:
            category: Data category
            local_only: If True, never transmit
        """
        policy = self.get_policy(category)
        policy.local_only = local_only
        self._policies[category] = policy

    # =========================================================================
    # Data Capture (with privacy enforcement)
    # =========================================================================

    def can_capture(self, category: DataCategory, consent_granted: bool = False) -> bool:
        """Check if capture is allowed.

        Args:
            category: Data category
            consent_granted: Has user given consent?

        Returns:
            True if capture allowed
        """
        self._stats["consent_checks"] += 1

        policy = self.get_policy(category)

        # Check if category requires consent
        if policy.require_consent and not consent_granted:
            logger.debug(f"🔐 Capture blocked: {category.value} requires consent")
            self._stats["blocked_captures"] += 1
            return False

        # Check if policy allows capture
        if policy.retention_hours == 0:
            logger.debug(f"🔐 Capture blocked: {category.value} has 0 retention")
            self._stats["blocked_captures"] += 1
            return False

        return True

    def record_capture(
        self,
        category: DataCategory,
        data: dict[str, Any],
        consent_id: str | None = None,
        description: str = "",
    ) -> str | None:
        """Record a data capture event.

        Args:
            category: Data category
            data: Captured data (will be anonymized if policy requires)
            consent_id: Associated consent record
            description: Human-readable description

        Returns:
            Data hash if stored, None if rejected
        """
        policy = self.get_policy(category)

        # Anonymize if required
        if policy.anonymize:
            data = self._anonymize_data(data, category)

        # Calculate hash for audit (never store raw sensitive data in audit)
        data_hash = self._hash_data(data)

        # Calculate retention expiry
        retention_until = time.time() + (policy.retention_hours * 3600)

        # Create audit entry
        entry = AuditEntry(
            timestamp=time.time(),
            category=category,
            action="capture",
            description=description or f"Captured {category.value} data",
            data_hash=data_hash,
            retention_until=retention_until,
            consent_id=consent_id,
        )

        self._log_audit(entry)
        self._stats["captures"] += 1

        # Store data if retention > 0
        if policy.retention_hours > 0:
            self._store_data(category, data, retention_until)

        return data_hash

    def _anonymize_data(self, data: dict[str, Any], category: DataCategory) -> dict[str, Any]:
        """Anonymize data by removing/hashing PII.

        Args:
            data: Raw data
            category: Data category

        Returns:
            Anonymized data
        """
        anonymized = data.copy()

        # Remove common PII fields
        pii_fields = [
            "name",
            "email",
            "phone",
            "address",
            "ssn",
            "ip_address",
            "mac_address",
            "device_id",
            "user_id",
        ]

        for field_name in pii_fields:
            if field_name in anonymized:
                # Hash instead of remove (preserves uniqueness without PII)
                anonymized[field_name] = self._hash_value(str(anonymized[field_name]))

        # Category-specific anonymization
        if category == DataCategory.LOCATION:
            # Reduce precision (city-level, not exact)
            if "latitude" in anonymized:
                anonymized["latitude"] = round(anonymized["latitude"], 2)  # ~1km precision
            if "longitude" in anonymized:
                anonymized["longitude"] = round(anonymized["longitude"], 2)

        elif category == DataCategory.AUDIO:
            # Remove raw audio, keep only metadata
            if "audio_data" in anonymized:
                anonymized["audio_data"] = "[REDACTED]"
            if "transcript" in anonymized:
                # Keep length, not content
                anonymized["transcript_length"] = len(anonymized.get("transcript", ""))
                anonymized["transcript"] = "[REDACTED]"

        elif category == DataCategory.VIDEO:
            # Never store raw video
            if "frame_data" in anonymized:
                anonymized["frame_data"] = "[REDACTED]"
            if "faces_detected" in anonymized:
                # Keep count, not identities
                anonymized["face_count"] = len(anonymized.get("faces_detected", []))
                anonymized["faces_detected"] = "[REDACTED]"

        return anonymized

    def _hash_data(self, data: dict[str, Any]) -> str:
        """Create hash of data for audit purposes."""
        serialized = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def _hash_value(self, value: str) -> str:
        """Hash a single value."""
        return hashlib.sha256(value.encode()).hexdigest()[:12]

    def _store_data(
        self, category: DataCategory, data: dict[str, Any], retention_until: float
    ) -> None:
        """Store data with retention metadata.

        Args:
            category: Data category
            data: Data to store
            retention_until: Expiry timestamp
        """
        if category not in self._data_store:
            self._data_store[category] = []

        self._data_store[category].append(
            {
                "data": data,
                "timestamp": time.time(),
                "retention_until": retention_until,
            }
        )

    # =========================================================================
    # Audit Log
    # =========================================================================

    def _log_audit(self, entry: AuditEntry) -> None:
        """Log audit entry.

        Args:
            entry: Audit entry
        """
        if not self.config.enable_audit_log:
            return

        self._audit_buffer.append(entry)

        # Flush to file if buffer full
        if len(self._audit_buffer) >= self._audit_buffer_max:
            self._flush_audit_buffer()

    def _flush_audit_buffer(self) -> None:
        """Flush audit buffer to file."""
        if not self._audit_buffer:
            return

        try:
            with open(self.config.audit_log_path, "a") as f:
                for entry in self._audit_buffer:
                    f.write(json.dumps(entry.to_dict()) + "\n")

            self._audit_buffer.clear()
        except Exception as e:
            logger.error(f"Failed to flush audit log: {e}")

    def get_audit_log(
        self,
        since: datetime | None = None,
        category: DataCategory | None = None,
        limit: int = 100,
    ) -> list[AuditEntry]:
        """Get audit log entries.

        Args:
            since: Only entries after this time
            category: Filter by category
            limit: Max entries to return

        Returns:
            List of audit entries
        """
        entries: list[AuditEntry] = []

        # Include buffer
        entries.extend(self._audit_buffer)

        # Read from file
        if self.config.audit_log_path.exists():
            try:
                with open(self.config.audit_log_path) as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            entry = AuditEntry(
                                timestamp=data["timestamp"],
                                category=DataCategory(data["category"]),
                                action=data["action"],
                                description=data["description"],
                                data_hash=data.get("data_hash"),
                                retention_until=data.get("retention_until"),
                                consent_id=data.get("consent_id"),
                            )
                            entries.append(entry)
                        except (json.JSONDecodeError, KeyError, ValueError):
                            continue
            except Exception as e:
                logger.error(f"Failed to read audit log: {e}")

        # Filter
        if since:
            since_ts = since.timestamp()
            entries = [e for e in entries if e.timestamp >= since_ts]

        if category:
            entries = [e for e in entries if e.category == category]

        # Sort by timestamp descending, limit
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    # =========================================================================
    # Data Export / Deletion (GDPR)
    # =========================================================================

    def export_my_data(self, categories: list[DataCategory] | None = None) -> dict[str, Any]:
        """Export all stored data for user.

        Args:
            categories: Categories to export (None = all)

        Returns:
            Exported data bundle
        """
        self._stats["exports"] += 1

        categories = categories or list(DataCategory)

        export = {
            "export_timestamp": datetime.now().isoformat(),
            "categories": {},
            "audit_log": [],
            "policies": {},
        }

        # Export data by category
        for category in categories:
            if category in self._data_store:
                export["categories"][category.value] = [  # type: ignore[index]
                    {"data": entry["data"], "timestamp": entry["timestamp"]}
                    for entry in self._data_store[category]
                ]

            # Include policy
            policy = self.get_policy(category)
            export["policies"][category.value] = {  # type: ignore[index]
                "sensitivity": policy.sensitivity.value,
                "retention_hours": policy.retention_hours,
                "local_only": policy.local_only,
                "anonymize": policy.anonymize,
            }

        # Include relevant audit entries
        export["audit_log"] = [
            e.to_dict()
            for e in self.get_audit_log(limit=1000)
            if e.category in categories  # type: ignore[misc]
        ]

        # Log the export
        self._log_audit(
            AuditEntry(
                timestamp=time.time(),
                category=DataCategory.INTERACTION,
                action="export",
                description=f"Data export requested for {len(categories)} categories",
            )
        )

        return export

    def delete_my_data(
        self,
        categories: list[DataCategory] | None = None,
        since: datetime | None = None,
    ) -> int:
        """Delete stored data (right to be forgotten).

        Args:
            categories: Categories to delete (None = all)
            since: Only delete data captured after this time

        Returns:
            Number of entries deleted
        """
        categories = categories or list(DataCategory)
        since_ts = since.timestamp() if since else 0

        deleted = 0

        for category in categories:
            if category not in self._data_store:
                continue

            original_len = len(self._data_store[category])

            if since_ts > 0:
                # Delete only entries after since
                self._data_store[category] = [
                    entry for entry in self._data_store[category] if entry["timestamp"] < since_ts
                ]
            else:
                # Delete all
                self._data_store[category] = []

            deleted += original_len - len(self._data_store[category])

        self._stats["deletions"] += deleted

        # Log the deletion
        self._log_audit(
            AuditEntry(
                timestamp=time.time(),
                category=DataCategory.INTERACTION,
                action="delete",
                description=f"Deleted {deleted} entries from {len(categories)} categories",
            )
        )

        logger.info(f"🔐 Deleted {deleted} data entries")
        return deleted

    # =========================================================================
    # Cleanup (Retention Enforcement)
    # =========================================================================

    async def start(self) -> None:
        """Start privacy manager background tasks."""
        if self._running:
            return

        self._running = True

        from kagami.core.async_utils import safe_create_task

        self._cleanup_task = safe_create_task(
            self._cleanup_loop(),
            name="privacy_cleanup",
            error_callback=lambda e: logger.error(f"Privacy cleanup crashed: {e}"),
        )

        logger.info("🔐 Privacy manager started")

    async def stop(self) -> None:
        """Stop privacy manager."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()

        # Flush audit buffer
        self._flush_audit_buffer()

        logger.info("🔐 Privacy manager stopped")

    async def _cleanup_loop(self) -> None:
        """Background cleanup of expired data."""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval_hours * 3600)

                expired = self._cleanup_expired()
                if expired > 0:
                    logger.info(f"🔐 Cleaned up {expired} expired entries")

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    def _cleanup_expired(self) -> int:
        """Remove expired data entries.

        Returns:
            Number of entries removed
        """
        now = time.time()
        removed = 0

        for category in list(self._data_store.keys()):
            original = len(self._data_store[category])

            self._data_store[category] = [
                entry
                for entry in self._data_store[category]
                if entry.get("retention_until", float("inf")) > now
            ]

            removed += original - len(self._data_store[category])

        # Also cleanup old audit entries
        if self.config.audit_log_path.exists():
            now - (self.config.audit_retention_days * 86400)
            # Note: Full audit cleanup would rewrite the file
            # For now, just track in stats

        return removed

    # =========================================================================
    # Statistics & Status
    # =========================================================================

    def get_stats(self) -> dict[str, Any]:
        """Get privacy statistics."""
        total_stored = sum(len(entries) for entries in self._data_store.values())

        return {
            **self._stats,
            "total_stored_entries": total_stored,
            "categories_with_data": len(self._data_store),
            "audit_buffer_size": len(self._audit_buffer),
            "policies": {cat.value: pol.retention_hours for cat, pol in self._policies.items()},
        }

    def get_active_sensors(self) -> list[DataCategory]:
        """Get list[Any] of currently active sensors.

        Returns:
            List of active data categories
        """
        return [cat for cat, policy in self._policies.items() if policy.active]

    def set_sensor_active(self, category: DataCategory, active: bool) -> None:
        """Set sensor active state.

        Args:
            category: Data category
            active: Is sensor currently capturing?
        """
        if category in self._policies:
            self._policies[category].active = active


# =============================================================================
# Global Instance
# =============================================================================

_PRIVACY_MANAGER: PrivacyManager | None = None


async def get_privacy_manager() -> PrivacyManager:
    """Get global privacy manager instance."""
    global _PRIVACY_MANAGER
    if _PRIVACY_MANAGER is None:
        _PRIVACY_MANAGER = PrivacyManager()
        await _PRIVACY_MANAGER.start()
    return _PRIVACY_MANAGER
