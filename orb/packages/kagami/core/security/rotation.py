"""Automatic secret rotation system.

Handles automatic rotation of secrets based on policies,
with grace periods and rollback capabilities.
"""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from kagami.core.security.encryption import generate_secret
from kagami.core.security.secrets_manager import SecretsManager

logger = logging.getLogger(__name__)


class RotationStatus(Enum):
    """Status of a rotation operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class RotationPolicy:
    """Policy for automatic secret rotation."""

    secret_name: str
    rotation_days: int
    grace_period_seconds: int = 300  # 5 minutes
    auto_generate: bool = True
    generation_length: int = 32
    notify_on_rotation: bool = True
    rollback_on_failure: bool = True


@dataclass
class RotationEvent:
    """Event representing a rotation operation."""

    secret_name: str
    timestamp: datetime
    status: RotationStatus
    old_version: str | None = None
    new_version: str | None = None
    error: str | None = None
    triggered_by: str = "system"


class SecretRotator:
    """Handles automatic secret rotation."""

    def __init__(
        self,
        secrets_manager: SecretsManager,
        policies: list[RotationPolicy] | None = None,
    ):
        """Initialize secret rotator.

        Args:
            secrets_manager: SecretsManager instance
            policies: List of rotation policies
        """
        self.secrets_manager = secrets_manager
        self.policies: dict[str, RotationPolicy] = {}
        self.rotation_history: list[RotationEvent] = []
        self._notification_callbacks: list[Callable[[RotationEvent], None]] = []

        if policies:
            for policy in policies:
                self.add_policy(policy)

    def add_policy(self, policy: RotationPolicy) -> None:
        """Add or update rotation policy.

        Args:
            policy: Rotation policy to add
        """
        self.policies[policy.secret_name] = policy
        logger.info(
            f"Added rotation policy for '{policy.secret_name}' "
            f"(rotate every {policy.rotation_days} days)"
        )

    def remove_policy(self, secret_name: str) -> None:
        """Remove rotation policy.

        Args:
            secret_name: Name of secret to stop rotating
        """
        if secret_name in self.policies:
            del self.policies[secret_name]
            logger.info(f"Removed rotation policy for '{secret_name}'")

    def add_notification_callback(self, callback: Callable[[RotationEvent], None]) -> None:
        """Add callback for rotation notifications.

        Args:
            callback: Function to call on rotation events
        """
        self._notification_callbacks.append(callback)

    async def rotate_secret(
        self,
        secret_name: str,
        new_value: str | None = None,
        user: str = "system",
    ) -> RotationEvent:
        """Rotate a single secret.

        Args:
            secret_name: Name of secret to rotate
            new_value: New value (auto-generated if not provided)
            user: User triggering rotation

        Returns:
            RotationEvent with rotation details
        """
        event = RotationEvent(
            secret_name=secret_name,
            timestamp=datetime.utcnow(),
            status=RotationStatus.IN_PROGRESS,
            triggered_by=user,
        )

        try:
            # Get current version
            old_value = await self.secrets_manager.get_secret(secret_name, user=user)
            if not old_value:
                raise ValueError(f"Secret '{secret_name}' not found")

            metadata = await self.secrets_manager.backend.get_secret_metadata(secret_name)
            if metadata:
                event.old_version = str(metadata.access_count)

            # Generate new value if not provided
            if new_value is None:
                policy = self.policies.get(secret_name)
                if policy and policy.auto_generate:
                    new_value = generate_secret(length=policy.generation_length, use_symbols=True)
                else:
                    raise ValueError(
                        f"No new value provided and auto-generation disabled for '{secret_name}'"
                    )

            # Get grace period
            policy = self.policies.get(secret_name)
            grace_period = policy.grace_period_seconds if policy else 300

            # Perform rotation
            new_version = await self.secrets_manager.rotate_secret(
                name=secret_name,
                new_value=new_value,
                user=user,
                grace_period_seconds=grace_period,
            )

            event.new_version = new_version
            event.status = RotationStatus.SUCCESS

            logger.info(
                f"Successfully rotated secret '{secret_name}' "
                f"(old: {event.old_version}, new: {new_version})"
            )

        except Exception as e:
            event.status = RotationStatus.FAILED
            event.error = str(e)
            logger.error(f"Failed to rotate secret '{secret_name}': {e}")

            # Attempt rollback if policy allows
            policy = self.policies.get(secret_name)
            if policy and policy.rollback_on_failure:
                try:
                    await self._rollback_rotation(secret_name, event)
                except Exception as rollback_error:
                    logger.error(f"Rollback failed for '{secret_name}': {rollback_error}")

        # Record event
        self.rotation_history.append(event)

        # Notify callbacks
        if self.policies.get(secret_name, RotationPolicy("", 0)).notify_on_rotation:
            self._notify(event)

        return event

    async def rotate_all_due(self, user: str = "system") -> list[RotationEvent]:
        """Rotate all secrets that are due for rotation.

        Args:
            user: User triggering rotation

        Returns:
            List of rotation events
        """
        due_secrets = await self.secrets_manager.get_secrets_needing_rotation()
        events = []

        logger.info(f"Found {len(due_secrets)} secrets due for rotation")

        for secret_name in due_secrets:
            try:
                event = await self.rotate_secret(secret_name, user=user)
                events.append(event)

                # Small delay between rotations to avoid overwhelming backend
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error rotating '{secret_name}': {e}")
                events.append(
                    RotationEvent(
                        secret_name=secret_name,
                        timestamp=datetime.utcnow(),
                        status=RotationStatus.FAILED,
                        error=str(e),
                        triggered_by=user,
                    )
                )

        return events

    async def check_and_rotate(self, user: str = "system") -> list[RotationEvent]:
        """Check policies and rotate secrets as needed.

        Args:
            user: User triggering rotation

        Returns:
            List of rotation events
        """
        events = []

        for secret_name, policy in self.policies.items():
            try:
                # Get secret metadata
                metadata = await self.secrets_manager.backend.get_secret_metadata(secret_name)

                if not metadata:
                    logger.warning(f"Secret '{secret_name}' not found for rotation check")
                    continue

                # Check if rotation is due
                if metadata.last_rotated:
                    time_since_rotation = datetime.utcnow() - metadata.last_rotated
                    days_since_rotation = time_since_rotation.days
                else:
                    # Never rotated, use created date
                    time_since_creation = datetime.utcnow() - metadata.created_at
                    days_since_rotation = time_since_creation.days

                if days_since_rotation >= policy.rotation_days:
                    logger.info(
                        f"Secret '{secret_name}' is due for rotation "
                        f"({days_since_rotation} days since last rotation)"
                    )
                    event = await self.rotate_secret(secret_name, user=user)
                    events.append(event)

                    # Small delay between rotations
                    await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Error checking rotation for '{secret_name}': {e}")

        return events

    async def _rollback_rotation(self, secret_name: str, failed_event: RotationEvent) -> None:
        """Rollback a failed rotation.

        Args:
            secret_name: Name of secret to rollback
            failed_event: Failed rotation event
        """
        logger.warning(f"Attempting rollback for '{secret_name}'")

        # Get previous version
        versions = await self.secrets_manager.backend.get_secret_versions(secret_name)

        if len(versions) < 2:
            logger.error(f"Cannot rollback '{secret_name}' - no previous version")
            return

        # Get second-to-last version (last is the failed new one)
        previous_version = versions[1]

        # Restore previous version
        previous_value = await self.secrets_manager.backend.get_secret(
            secret_name, version=previous_version.version_id
        )

        if previous_value:
            await self.secrets_manager.set_secret(
                name=secret_name,
                value=previous_value,
                user="system-rollback",
            )

            failed_event.status = RotationStatus.ROLLED_BACK
            logger.info(f"Rolled back '{secret_name}' to version {previous_version.version_id}")

    def _notify(self, event: RotationEvent) -> None:
        """Notify callbacks of rotation event.

        Args:
            event: Rotation event to notify
        """
        for callback in self._notification_callbacks:
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Notification callback failed: {e}")

    def get_rotation_history(
        self,
        secret_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        status: RotationStatus | None = None,
    ) -> list[RotationEvent]:
        """Get rotation history with optional filters.

        Args:
            secret_name: Filter by secret name
            start_time: Filter by start time
            end_time: Filter by end time
            status: Filter by status

        Returns:
            List of rotation events
        """
        events = self.rotation_history

        if secret_name:
            events = [e for e in events if e.secret_name == secret_name]

        if start_time:
            events = [e for e in events if e.timestamp >= start_time]

        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        if status:
            events = [e for e in events if e.status == status]

        return events

    def get_rotation_summary(self) -> dict[str, Any]:
        """Get summary of rotation operations.

        Returns:
            Dictionary with rotation statistics
        """
        total = len(self.rotation_history)
        successful = len([e for e in self.rotation_history if e.status == RotationStatus.SUCCESS])
        failed = len([e for e in self.rotation_history if e.status == RotationStatus.FAILED])
        rolled_back = len(
            [e for e in self.rotation_history if e.status == RotationStatus.ROLLED_BACK]
        )

        # Get last rotation time for each secret
        last_rotations = {}
        for event in reversed(self.rotation_history):
            if event.secret_name not in last_rotations and event.status == RotationStatus.SUCCESS:
                last_rotations[event.secret_name] = event.timestamp

        return {
            "total_rotations": total,
            "successful": successful,
            "failed": failed,
            "rolled_back": rolled_back,
            "success_rate": successful / total if total > 0 else 0.0,
            "policies_count": len(self.policies),
            "last_rotations": last_rotations,
        }


class RotationScheduler:
    """Schedules and runs automatic secret rotation."""

    def __init__(
        self,
        rotator: SecretRotator,
        check_interval_seconds: int = 3600,  # Check every hour
    ):
        """Initialize rotation scheduler.

        Args:
            rotator: SecretRotator instance
            check_interval_seconds: Interval between rotation checks
        """
        self.rotator = rotator
        self.check_interval_seconds = check_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the rotation scheduler."""
        if self._running:
            logger.warning("Rotation scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"Started rotation scheduler (check interval: {self.check_interval_seconds}s)")

    async def stop(self) -> None:
        """Stop the rotation scheduler."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Stopped rotation scheduler")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                logger.debug("Running scheduled rotation check")
                events = await self.rotator.check_and_rotate(user="scheduler")

                if events:
                    successful = len([e for e in events if e.status == RotationStatus.SUCCESS])
                    failed = len([e for e in events if e.status == RotationStatus.FAILED])
                    logger.info(
                        f"Rotation check complete: {successful} successful, {failed} failed"
                    )

            except Exception as e:
                logger.error(f"Error in rotation scheduler: {e}")

            # Wait for next check
            await asyncio.sleep(self.check_interval_seconds)


def create_default_policies() -> list[RotationPolicy]:
    """Create default rotation policies for common secrets.

    Returns:
        List of default rotation policies
    """
    return [
        RotationPolicy(
            secret_name="JWT_SECRET",
            rotation_days=90,
            grace_period_seconds=3600,  # 1 hour for JWT rotation
            auto_generate=True,
            generation_length=64,
        ),
        RotationPolicy(
            secret_name="KAGAMI_API_KEY",
            rotation_days=90,
            grace_period_seconds=3600,
            auto_generate=True,
            generation_length=48,
        ),
        RotationPolicy(
            secret_name="CSRF_SECRET",
            rotation_days=30,
            grace_period_seconds=300,
            auto_generate=True,
            generation_length=32,
        ),
        RotationPolicy(
            secret_name="SESSION_SECRET",
            rotation_days=30,
            grace_period_seconds=300,
            auto_generate=True,
            generation_length=32,
        ),
    ]
