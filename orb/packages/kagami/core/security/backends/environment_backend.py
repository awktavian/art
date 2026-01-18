"""Environment variable backend for secrets management.

Used in CI/CD environments where secrets are injected via environment variables.
Simple, read-only (get only), no persistence.

Created: December 31, 2025
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from kagami.core.security.secrets_manager import (
    SecretBackend,
    SecretBackendType,
    SecretMetadata,
    SecretVersion,
)

logger = logging.getLogger(__name__)


class EnvironmentBackend(SecretBackend):
    """Environment variable backend for CI/CD.

    Reads secrets from environment variables. Keys are normalized:
    - Lowercase key becomes UPPERCASE env var
    - Underscores preserved
    - Dots converted to underscores

    Example:
        get_secret("unifi_password") -> os.getenv("UNIFI_PASSWORD")
        get_secret("api.key") -> os.getenv("API_KEY")
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize environment backend.

        Args:
            config: Optional configuration (not used, for interface compatibility)
        """
        super().__init__(config or {})
        logger.info("EnvironmentBackend initialized (CI/CD mode)")

    def _normalize_key(self, key: str) -> str:
        """Normalize key to environment variable name."""
        # Convert to uppercase, replace dots with underscores
        return key.upper().replace(".", "_").replace("-", "_")

    async def get_secret(self, name: str, version: str | None = None) -> str | None:
        """Get secret from environment variable.

        Args:
            name: Secret name (will be uppercased)
            version: Ignored (no versioning in env vars)

        Returns:
            Environment variable value or None
        """
        env_key = self._normalize_key(name)
        value = os.getenv(env_key)

        if value:
            logger.debug(f"Found secret in env var: {env_key}")
        else:
            logger.debug(f"Secret not found in env: {env_key}")

        return value

    async def set_secret(
        self,
        name: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Set secret - NOT SUPPORTED in environment backend.

        Environment variables are read-only in this context.
        They should be set externally (CI/CD config, Docker, etc.)

        Raises:
            RuntimeError: Always, as env vars cannot be set from code
        """
        raise RuntimeError(
            "EnvironmentBackend is read-only. "
            "Set secrets via CI/CD configuration, Docker secrets, or shell environment."
        )

    async def delete_secret(self, name: str) -> bool:
        """Delete secret - NOT SUPPORTED in environment backend.

        Raises:
            RuntimeError: Always
        """
        raise RuntimeError("EnvironmentBackend is read-only. Cannot delete secrets.")

    async def list_secrets(self) -> list[str]:
        """List all KAGAMI-related environment variables.

        Returns:
            List of environment variable names that match Kagami patterns
        """
        # Look for common Kagami secret patterns
        prefixes = [
            "KAGAMI_",
            "UNIFI_",
            "CONTROL4_",
            "EIGHT_SLEEP_",
            "AUGUST_",
            "TESLA_",
            "DSC_",
            "JWT_",
            "CSRF_",
            "ANTHROPIC_",
            "OPENAI_",
            "COMPOSIO_",
            "DATABASE_",
            "REDIS_",
        ]

        secrets = []
        for key in os.environ:
            for prefix in prefixes:
                if key.startswith(prefix):
                    secrets.append(key.lower())
                    break

        return secrets

    async def get_secret_versions(self, name: str) -> list[SecretVersion]:
        """Get secret versions - only current value available.

        Args:
            name: Secret name

        Returns:
            List with single current version if secret exists
        """
        value = await self.get_secret(name)
        if not value:
            return []

        return [
            SecretVersion(
                version_id="env",
                value="[CURRENT]",
                created_at=datetime.utcnow(),
                created_by="environment",
                is_active=True,
            )
        ]

    async def get_secret_metadata(self, name: str) -> SecretMetadata | None:
        """Get secret metadata.

        Args:
            name: Secret name

        Returns:
            Basic metadata if secret exists
        """
        value = await self.get_secret(name)
        if not value:
            return None

        return SecretMetadata(
            name=name,
            backend=SecretBackendType.LOCAL_ENCRYPTED,  # No specific type for env
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            rotation_enabled=False,
            rotation_days=0,
            tags={"source": "environment"},
        )
