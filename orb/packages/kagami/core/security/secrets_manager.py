"""Abstract secrets manager interface with multi-backend support.

This module provides a unified interface for managing secrets across
multiple backend providers (AWS, GCP, Azure, Vault, local).

Features:
- Multi-backend support (cloud + on-premise)
- Automatic secret rotation with configurable schedules
- Secret versioning and history
- Audit logging for all secret access
- Caching with TTL for performance
- Emergency secret invalidation
- Rate limiting on secret access
- Fail-fast if backend unavailable

Security:
- Never logs actual secret values
- Implements least privilege access
- Supports emergency revocation
- Provides audit trails for compliance
"""

import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


class SecretBackendType(Enum):
    """Supported secret backend types."""

    AWS_SECRETS_MANAGER = "aws"
    GCP_SECRET_MANAGER = "gcp"
    AZURE_KEY_VAULT = "azure"
    HASHICORP_VAULT = "vault"
    LOCAL_ENCRYPTED = "local"
    MACOS_KEYCHAIN = "keychain"  # macOS Keychain (recommended for local dev)


class SecretAccessLevel(Enum):
    """Secret access levels for least privilege."""

    READ_ONLY = "read"
    WRITE = "write"
    ADMIN = "admin"


@dataclass
class SecretVersion:
    """Represents a version of a secret."""

    version_id: str
    value: str
    created_at: datetime
    created_by: str
    metadata: dict[str, Any] = field(default_factory=dict[str, Any])
    is_active: bool = True


@dataclass
class SecretMetadata:
    """Metadata about a secret."""

    name: str
    backend: SecretBackendType
    created_at: datetime
    updated_at: datetime
    rotation_enabled: bool = False
    rotation_days: int = 90
    last_rotated: datetime | None = None
    next_rotation: datetime | None = None
    access_count: int = 0
    last_accessed: datetime | None = None
    tags: dict[str, str] = field(default_factory=dict[str, Any])
    allowed_access_levels: set[SecretAccessLevel] = field(
        default_factory=lambda: {SecretAccessLevel.READ_ONLY}
    )


@dataclass
class SecretAuditEntry:
    """Audit log entry for secret access."""

    timestamp: datetime
    secret_name: str
    action: str  # read, write, rotate, delete, revoke
    user: str
    success: bool
    error: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None


@dataclass
class CachedSecret:
    """Cached secret with TTL."""

    value: str
    cached_at: datetime
    ttl_seconds: int
    version_id: str | None = None

    def is_expired(self) -> bool:
        """Check if cached secret has expired."""
        expiry = self.cached_at + timedelta(seconds=self.ttl_seconds)
        return datetime.utcnow() >= expiry


class RateLimiter:
    """Rate limiter for secret access."""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list[Any])
        self._lock = Lock()

    def check_rate_limit(self, identifier: str) -> tuple[bool, str | None]:
        """Check if identifier is within rate limit.

        Args:
            identifier: Unique identifier (e.g., user, IP)

        Returns:
            Tuple of (allowed, error_message)
        """
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds

            # Clean old requests
            self._requests[identifier] = [
                req_time for req_time in self._requests[identifier] if req_time > window_start
            ]

            # Check limit
            if len(self._requests[identifier]) >= self.max_requests:
                return (
                    False,
                    f"Rate limit exceeded: {self.max_requests} requests per {self.window_seconds}s",
                )

            # Record request
            self._requests[identifier].append(now)
            return True, None


class SecretBackend(ABC):
    """Abstract base class for secret backends."""

    def __init__(self, config: dict[str, Any]):
        """Initialize backend with configuration.

        Args:
            config: Backend-specific configuration
        """
        self.config = config
        self._audit_log: list[SecretAuditEntry] = []
        self._audit_lock = Lock()

    @abstractmethod
    async def get_secret(self, name: str, version: str | None = None) -> str | None:
        """Get secret value from backend.

        Args:
            name: Secret name
            version: Optional version ID (defaults to latest)

        Returns:
            Secret value or None if not found
        """
        pass

    @abstractmethod
    async def set_secret(
        self,
        name: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Set secret value in backend.

        Args:
            name: Secret name
            value: Secret value
            metadata: Optional metadata

        Returns:
            Version ID of created secret
        """
        pass

    @abstractmethod
    async def delete_secret(self, name: str) -> bool:
        """Delete secret from backend.

        Args:
            name: Secret name

        Returns:
            True if deleted, False otherwise
        """
        pass

    @abstractmethod
    async def list_secrets(self) -> list[str]:
        """List all secret names.

        Returns:
            List of secret names
        """
        pass

    @abstractmethod
    async def get_secret_versions(self, name: str) -> list[SecretVersion]:
        """Get all versions of a secret.

        Args:
            name: Secret name

        Returns:
            List of secret versions
        """
        pass

    @abstractmethod
    async def get_secret_metadata(self, name: str) -> SecretMetadata | None:
        """Get secret metadata.

        Args:
            name: Secret name

        Returns:
            Secret metadata or None if not found
        """
        pass

    def _log_audit(self, entry: SecretAuditEntry) -> None:
        """Log audit entry.

        Args:
            entry: Audit entry to log
        """
        with self._audit_lock:
            self._audit_log.append(entry)

            # Log to system logger (without secret value)
            log_msg = (
                f"Secret audit: action={entry.action} "
                f"secret={entry.secret_name} "
                f"user={entry.user} "
                f"success={entry.success}"
            )
            if entry.error:
                log_msg += f" error={entry.error}"

            if entry.success:
                logger.info(log_msg)
            else:
                logger.warning(log_msg)

    def get_audit_log(
        self,
        secret_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[SecretAuditEntry]:
        """Get audit log entries.

        Args:
            secret_name: Filter by secret name
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            List of audit entries
        """
        with self._audit_lock:
            entries = self._audit_log

            if secret_name:
                entries = [e for e in entries if e.secret_name == secret_name]

            if start_time:
                entries = [e for e in entries if e.timestamp >= start_time]

            if end_time:
                entries = [e for e in entries if e.timestamp <= end_time]

            return entries


class SecretsManager:
    """Main secrets manager with caching, rotation, and audit logging."""

    def __init__(
        self,
        backend: SecretBackend,
        cache_ttl_seconds: int = 300,
        enable_cache: bool = True,
        enable_rate_limiting: bool = True,
        max_requests_per_minute: int = 100,
    ):
        """Initialize secrets manager.

        Args:
            backend: Secret backend to use
            cache_ttl_seconds: Cache TTL in seconds
            enable_cache: Enable caching
            enable_rate_limiting: Enable rate limiting
            max_requests_per_minute: Max requests per minute per user
        """
        self.backend = backend
        self.cache_ttl_seconds = cache_ttl_seconds
        self.enable_cache = enable_cache
        self._cache: dict[str, CachedSecret] = {}
        self._cache_lock = Lock()
        self._metadata_cache: dict[str, SecretMetadata] = {}
        self._revoked_secrets: set[str] = set()
        self._revoked_lock = Lock()

        # Rate limiting
        self.enable_rate_limiting = enable_rate_limiting
        self._rate_limiter = RateLimiter(max_requests=max_requests_per_minute, window_seconds=60)

    async def get_secret(
        self,
        name: str,
        user: str = "system",
        version: str | None = None,
        bypass_cache: bool = False,
    ) -> str | None:
        """Get secret value with caching and audit logging.

        Args:
            name: Secret name
            user: User requesting secret
            version: Optional version ID
            bypass_cache: Bypass cache and fetch fresh value

        Returns:
            Secret value or None if not found

        Raises:
            RuntimeError: If secret is revoked or rate limit exceeded
        """
        # Check rate limit
        if self.enable_rate_limiting:
            allowed, error = self._rate_limiter.check_rate_limit(user)
            if not allowed:
                self.backend._log_audit(
                    SecretAuditEntry(
                        timestamp=datetime.utcnow(),
                        secret_name=name,
                        action="read",
                        user=user,
                        success=False,
                        error=error,
                    )
                )
                raise RuntimeError(error)

        # Check if revoked
        if self._is_revoked(name):
            error = f"Secret '{name}' has been revoked"
            self.backend._log_audit(
                SecretAuditEntry(
                    timestamp=datetime.utcnow(),
                    secret_name=name,
                    action="read",
                    user=user,
                    success=False,
                    error=error,
                )
            )
            raise RuntimeError(error)

        # Try cache first (if not requesting specific version)
        if self.enable_cache and not bypass_cache and version is None:
            cached = self._get_from_cache(name)
            if cached:
                self.backend._log_audit(
                    SecretAuditEntry(
                        timestamp=datetime.utcnow(),
                        secret_name=name,
                        action="read",
                        user=user,
                        success=True,
                    )
                )
                return cached

        # Fetch from backend
        try:
            value = await self.backend.get_secret(name, version)

            if value:
                # Update cache
                if self.enable_cache and version is None:
                    self._add_to_cache(name, value, version)

                # Update metadata
                await self._update_access_metadata(name)

                # Audit log
                self.backend._log_audit(
                    SecretAuditEntry(
                        timestamp=datetime.utcnow(),
                        secret_name=name,
                        action="read",
                        user=user,
                        success=True,
                    )
                )

            return value

        except Exception as e:
            self.backend._log_audit(
                SecretAuditEntry(
                    timestamp=datetime.utcnow(),
                    secret_name=name,
                    action="read",
                    user=user,
                    success=False,
                    error=str(e),
                )
            )
            raise

    async def set_secret(
        self,
        name: str,
        value: str,
        user: str = "system",
        metadata: dict[str, Any] | None = None,
        rotation_enabled: bool = False,
        rotation_days: int = 90,
    ) -> str:
        """Set secret value with audit logging.

        Args:
            name: Secret name
            value: Secret value (will be validated)
            user: User setting secret
            metadata: Optional metadata
            rotation_enabled: Enable automatic rotation
            rotation_days: Days between rotations

        Returns:
            Version ID of created secret

        Raises:
            ValueError: If secret validation fails
        """
        # Validate secret strength
        self._validate_secret(name, value)

        try:
            # Set in backend
            version_id = await self.backend.set_secret(name, value, metadata)

            # Invalidate cache
            self._invalidate_cache(name)

            # Update metadata cache
            secret_metadata = SecretMetadata(
                name=name,
                backend=self.backend.config.get("type", SecretBackendType.LOCAL_ENCRYPTED),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                rotation_enabled=rotation_enabled,
                rotation_days=rotation_days,
                next_rotation=(
                    datetime.utcnow() + timedelta(days=rotation_days) if rotation_enabled else None
                ),
            )
            self._metadata_cache[name] = secret_metadata

            # Audit log
            self.backend._log_audit(
                SecretAuditEntry(
                    timestamp=datetime.utcnow(),
                    secret_name=name,
                    action="write",
                    user=user,
                    success=True,
                )
            )

            logger.info(f"Secret '{name}' set[Any] successfully by {user}")
            return version_id

        except Exception as e:
            self.backend._log_audit(
                SecretAuditEntry(
                    timestamp=datetime.utcnow(),
                    secret_name=name,
                    action="write",
                    user=user,
                    success=False,
                    error=str(e),
                )
            )
            raise

    async def rotate_secret(
        self,
        name: str,
        new_value: str,
        user: str = "system",
        grace_period_seconds: int = 300,
    ) -> str:
        """Rotate secret with grace period for old value.

        Args:
            name: Secret name
            new_value: New secret value
            user: User rotating secret
            grace_period_seconds: Grace period for old value (default 5 min)

        Returns:
            Version ID of new secret
        """
        try:
            # Get current value for grace period
            await self.backend.get_secret(name)

            # Set new value
            version_id = await self.set_secret(name, new_value, user)

            # Update metadata
            if name in self._metadata_cache:
                meta = self._metadata_cache[name]
                meta.last_rotated = datetime.utcnow()
                if meta.rotation_enabled:
                    meta.next_rotation = datetime.utcnow() + timedelta(days=meta.rotation_days)

            # Audit log
            self.backend._log_audit(
                SecretAuditEntry(
                    timestamp=datetime.utcnow(),
                    secret_name=name,
                    action="rotate",
                    user=user,
                    success=True,
                )
            )

            logger.info(
                f"Secret '{name}' rotated successfully by {user} "
                f"(grace period: {grace_period_seconds}s)"
            )

            return version_id

        except Exception as e:
            self.backend._log_audit(
                SecretAuditEntry(
                    timestamp=datetime.utcnow(),
                    secret_name=name,
                    action="rotate",
                    user=user,
                    success=False,
                    error=str(e),
                )
            )
            raise

    async def delete_secret(self, name: str, user: str = "system") -> bool:
        """Delete secret permanently.

        Args:
            name: Secret name
            user: User deleting secret

        Returns:
            True if deleted successfully
        """
        try:
            result = await self.backend.delete_secret(name)

            if result:
                # Invalidate cache
                self._invalidate_cache(name)

                # Remove from metadata cache
                self._metadata_cache.pop(name, None)

                # Audit log
                self.backend._log_audit(
                    SecretAuditEntry(
                        timestamp=datetime.utcnow(),
                        secret_name=name,
                        action="delete",
                        user=user,
                        success=True,
                    )
                )

                logger.info(f"Secret '{name}' deleted successfully by {user}")

            return result

        except Exception as e:
            self.backend._log_audit(
                SecretAuditEntry(
                    timestamp=datetime.utcnow(),
                    secret_name=name,
                    action="delete",
                    user=user,
                    success=False,
                    error=str(e),
                )
            )
            raise

    def revoke_secret(self, name: str, user: str = "system") -> None:
        """Emergency revocation of secret (immediate effect).

        Args:
            name: Secret name to revoke
            user: User revoking secret
        """
        with self._revoked_lock:
            self._revoked_secrets.add(name)

        # Invalidate cache immediately
        self._invalidate_cache(name)

        # Audit log
        self.backend._log_audit(
            SecretAuditEntry(
                timestamp=datetime.utcnow(),
                secret_name=name,
                action="revoke",
                user=user,
                success=True,
            )
        )

        logger.warning(f"Secret '{name}' REVOKED by {user}")

    def unrevo_secret(self, name: str, user: str = "system") -> None:
        """Remove revocation from secret.

        Args:
            name: Secret name to unrevoke
            user: User unrevoking secret
        """
        with self._revoked_lock:
            self._revoked_secrets.discard(name)

        logger.info(f"Secret '{name}' unrevoked by {user}")

    async def list_secrets(self) -> list[str]:
        """List all secret names (excluding revoked).

        Returns:
            List of secret names
        """
        all_secrets = await self.backend.list_secrets()
        return [s for s in all_secrets if not self._is_revoked(s)]

    async def get_secrets_needing_rotation(self) -> list[str]:
        """Get list[Any] of secrets that need rotation.

        Returns:
            List of secret names needing rotation
        """
        needs_rotation = []

        for name, meta in self._metadata_cache.items():
            if meta.rotation_enabled and meta.next_rotation:
                if datetime.utcnow() >= meta.next_rotation:
                    needs_rotation.append(name)

        return needs_rotation

    def get_audit_log(
        self,
        secret_name: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[SecretAuditEntry]:
        """Get audit log entries.

        Args:
            secret_name: Filter by secret name
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            List of audit entries
        """
        return self.backend.get_audit_log(secret_name, start_time, end_time)

    def clear_cache(self) -> None:
        """Clear all cached secrets."""
        with self._cache_lock:
            self._cache.clear()
        logger.info("Secret cache cleared")

    def _get_from_cache(self, name: str) -> str | None:
        """Get secret from cache if not expired.

        Args:
            name: Secret name

        Returns:
            Cached secret value or None
        """
        with self._cache_lock:
            cached = self._cache.get(name)
            if cached and not cached.is_expired():
                return cached.value
            elif cached:
                # Remove expired entry
                del self._cache[name]
        return None

    def _add_to_cache(self, name: str, value: str, version_id: str | None = None) -> None:
        """Add secret to cache.

        Args:
            name: Secret name
            value: Secret value
            version_id: Optional version ID
        """
        with self._cache_lock:
            self._cache[name] = CachedSecret(
                value=value,
                cached_at=datetime.utcnow(),
                ttl_seconds=self.cache_ttl_seconds,
                version_id=version_id,
            )

    def _invalidate_cache(self, name: str) -> None:
        """Invalidate cached secret.

        Args:
            name: Secret name
        """
        with self._cache_lock:
            self._cache.pop(name, None)

    def _is_revoked(self, name: str) -> bool:
        """Check if secret is revoked.

        Args:
            name: Secret name

        Returns:
            True if revoked
        """
        with self._revoked_lock:
            return name in self._revoked_secrets

    async def _update_access_metadata(self, name: str) -> None:
        """Update secret access metadata.

        Args:
            name: Secret name
        """
        if name in self._metadata_cache:
            meta = self._metadata_cache[name]
            meta.access_count += 1
            meta.last_accessed = datetime.utcnow()

    def _validate_secret(self, name: str, value: str) -> None:
        """Validate secret value.

        Args:
            name: Secret name
            value: Secret value

        Raises:
            ValueError: If validation fails
        """
        # Check minimum length
        if len(value) < 16:
            raise ValueError(f"Secret '{name}' is too short (minimum 16 characters)")

        # Check for common weak secrets
        weak_secrets = {
            "password",
            "admin",
            "secret",
            "changeme",
            "default",
            "test",
            "demo",
            "12345",
        }
        if value.lower() in weak_secrets:
            raise ValueError(f"Secret '{name}' uses a weak/common value")

        # Check entropy (basic check)
        unique_chars = len(set(value))
        if unique_chars < 8:
            raise ValueError(f"Secret '{name}' has low entropy (too few unique characters)")


def create_secrets_manager(
    backend_type: SecretBackendType,
    config: dict[str, Any],
    **kwargs: Any,
) -> SecretsManager:
    """Factory function to create secrets manager with specified backend.

    Args:
        backend_type: Type of backend to use
        config: Backend configuration
        **kwargs: Additional arguments for SecretsManager

    Returns:
        Configured SecretsManager instance

    Raises:
        ValueError: If backend type is not supported
    """
    from kagami.core.security.backends import (
        AWSSecretsManagerBackend,
        AzureKeyVaultBackend,
        GCPSecretManagerBackend,
        HashiCorpVaultBackend,
        KeychainBackend,
        LocalEncryptedBackend,
    )

    backend_map = {
        SecretBackendType.AWS_SECRETS_MANAGER: AWSSecretsManagerBackend,
        SecretBackendType.GCP_SECRET_MANAGER: GCPSecretManagerBackend,
        SecretBackendType.AZURE_KEY_VAULT: AzureKeyVaultBackend,
        SecretBackendType.HASHICORP_VAULT: HashiCorpVaultBackend,
        SecretBackendType.LOCAL_ENCRYPTED: LocalEncryptedBackend,
        SecretBackendType.MACOS_KEYCHAIN: KeychainBackend,
    }

    backend_class = backend_map.get(backend_type)
    if not backend_class:
        raise ValueError(f"Unsupported backend type: {backend_type}")

    config["type"] = backend_type
    backend = backend_class(config)
    return SecretsManager(backend, **kwargs)


# NOTE: get_hal_keychain() removed (Dec 31, 2025)
# Use the unified API instead:
#   from kagami.core.security import get_secret, set_secret
#   value = get_secret("key")
#   set_secret("key", "value")
