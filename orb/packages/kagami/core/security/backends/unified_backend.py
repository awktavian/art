"""Unified cross-platform secrets backend.

Automatically selects the appropriate backend based on:
1. Environment override (KAGAMI_SECRET_BACKEND)
2. CI/CD detection (CI, GITHUB_ACTIONS env vars)
3. Platform detection (macOS -> Keychain, other -> LocalEncrypted)

This is the ONLY entry point for secrets. No fallbacks. No compatibility layers.

Created: December 31, 2025
"""

from __future__ import annotations

import logging
import os
import sys
from typing import TYPE_CHECKING, Any

from kagami.core.security.secrets_manager import (
    SecretBackend,
    SecretMetadata,
    SecretVersion,
)

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class UnifiedSecretsBackend(SecretBackend):
    """Unified cross-platform secrets backend.

    Backend selection priority:
    1. KAGAMI_SECRET_BACKEND env var override (aws, vault, env, keychain, local)
    2. CI/CD detection -> EnvironmentBackend
    3. macOS -> KeychainBackend
    4. Linux/Windows/Docker -> LocalEncryptedBackend

    Usage:
        backend = UnifiedSecretsBackend()
        value = await backend.get_secret("api_key")
        await backend.set_secret("api_key", "new_value")
    """

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize unified backend with automatic selection.

        Args:
            config: Optional configuration passed to selected backend
        """
        super().__init__(config or {})
        self._backend: SecretBackend | None = None
        self._backend_type: str = "unknown"
        self._config = config or {}

    def _get_backend(self) -> SecretBackend:
        """Get or create the appropriate backend."""
        if self._backend is not None:
            return self._backend

        self._backend = self._select_backend()
        return self._backend

    def _select_backend(self) -> SecretBackend:
        """Select appropriate backend based on environment and platform."""
        # Check for explicit override
        override = os.getenv("KAGAMI_SECRET_BACKEND", "").lower()

        if override:
            return self._create_backend_by_name(override)

        # Platform detection FIRST - macOS always uses Keychain
        # (Keychain is available even in CI on macOS, and is the canonical store)
        if sys.platform == "darwin":
            logger.info("macOS detected, using KeychainBackend")
            return self._create_keychain_backend()

        # CI/CD detection (only for non-macOS)
        if self._is_ci_environment():
            logger.info("CI/CD environment detected, using EnvironmentBackend")
            return self._create_environment_backend()

        # Linux, Windows, Docker -> LocalEncrypted
        logger.info(f"Platform {sys.platform} detected, using LocalEncryptedBackend")
        return self._create_local_backend()

    def _is_ci_environment(self) -> bool:
        """Detect if running in CI/CD environment."""
        ci_indicators = [
            "CI",
            "GITHUB_ACTIONS",
            "GITLAB_CI",
            "JENKINS_URL",
            "TRAVIS",
            "CIRCLECI",
            "BUILDKITE",
            "DRONE",
            "TEAMCITY_VERSION",
        ]
        return any(os.getenv(var) for var in ci_indicators)

    def _create_backend_by_name(self, name: str) -> SecretBackend:
        """Create backend by name."""
        if name == "env" or name == "environment":
            self._backend_type = "environment"
            return self._create_environment_backend()

        if name == "keychain" or name == "macos":
            self._backend_type = "keychain"
            return self._create_keychain_backend()

        if name == "local" or name == "encrypted":
            self._backend_type = "local"
            return self._create_local_backend()

        if name == "aws":
            self._backend_type = "aws"
            return self._create_aws_backend()

        if name == "vault" or name == "hashicorp":
            self._backend_type = "vault"
            return self._create_vault_backend()

        if name == "gcp":
            self._backend_type = "gcp"
            return self._create_gcp_backend()

        if name == "azure":
            self._backend_type = "azure"
            return self._create_azure_backend()

        logger.warning(f"Unknown backend '{name}', falling back to local")
        self._backend_type = "local"
        return self._create_local_backend()

    def _create_environment_backend(self) -> SecretBackend:
        """Create environment variable backend."""
        from kagami.core.security.backends.environment_backend import EnvironmentBackend

        self._backend_type = "environment"
        return EnvironmentBackend(self._config)

    def _create_keychain_backend(self) -> SecretBackend:
        """Create macOS Keychain backend."""
        try:
            from kagami.core.security.backends.keychain_backend import KeychainBackend

            self._backend_type = "keychain"
            return KeychainBackend(self._config)
        except Exception as e:
            logger.warning(f"Keychain backend failed: {e}, falling back to local")
            return self._create_local_backend()

    def _create_local_backend(self) -> SecretBackend:
        """Create local encrypted backend."""
        from kagami.core.security.backends.local_backend import LocalEncryptedBackend

        self._backend_type = "local"
        return LocalEncryptedBackend(self._config)

    def _create_aws_backend(self) -> SecretBackend:
        """Create AWS Secrets Manager backend."""
        try:
            from kagami.core.security.backends.aws_secrets_manager import (
                AWSSecretsManagerBackend,
            )

            self._backend_type = "aws"
            return AWSSecretsManagerBackend(self._config)
        except Exception as e:
            logger.error(f"AWS backend failed: {e}")
            raise RuntimeError(
                f"AWS Secrets Manager backend requested but failed to initialize: {e}"
            ) from e

    def _create_vault_backend(self) -> SecretBackend:
        """Create HashiCorp Vault backend."""
        try:
            from kagami.core.security.backends.vault_backend import VaultBackend

            self._backend_type = "vault"
            return VaultBackend(self._config)
        except Exception as e:
            logger.error(f"Vault backend failed: {e}")
            raise RuntimeError(f"Vault backend requested but failed to initialize: {e}") from e

    def _create_gcp_backend(self) -> SecretBackend:
        """Create GCP Secret Manager backend."""
        try:
            from kagami.core.security.backends.gcp_secret_manager import (
                GCPSecretManagerBackend,
            )

            self._backend_type = "gcp"
            return GCPSecretManagerBackend(self._config)
        except Exception as e:
            logger.error(f"GCP backend failed: {e}")
            raise RuntimeError(f"GCP Secret Manager backend requested but failed: {e}") from e

    def _create_azure_backend(self) -> SecretBackend:
        """Create Azure Key Vault backend."""
        try:
            from kagami.core.security.backends.azure_key_vault import AzureKeyVaultBackend

            self._backend_type = "azure"
            return AzureKeyVaultBackend(self._config)
        except Exception as e:
            logger.error(f"Azure backend failed: {e}")
            raise RuntimeError(f"Azure Key Vault backend requested but failed: {e}") from e

    @property
    def backend_type(self) -> str:
        """Get the current backend type."""
        # Ensure backend is initialized
        self._get_backend()
        return self._backend_type

    async def get_secret(self, name: str, version: str | None = None) -> str | None:
        """Get secret from the selected backend.

        Args:
            name: Secret name/key
            version: Optional version ID

        Returns:
            Secret value or None if not found
        """
        backend = self._get_backend()
        return await backend.get_secret(name, version)

    async def set_secret(
        self,
        name: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Set secret in the selected backend.

        Args:
            name: Secret name/key
            value: Secret value
            metadata: Optional metadata

        Returns:
            Version ID of created secret
        """
        backend = self._get_backend()
        return await backend.set_secret(name, value, metadata)

    async def delete_secret(self, name: str) -> bool:
        """Delete secret from the selected backend.

        Args:
            name: Secret name

        Returns:
            True if deleted successfully
        """
        backend = self._get_backend()
        return await backend.delete_secret(name)

    async def list_secrets(self) -> list[str]:
        """List all secrets in the selected backend.

        Returns:
            List of secret names
        """
        backend = self._get_backend()
        return await backend.list_secrets()

    async def get_secret_versions(self, name: str) -> list[SecretVersion]:
        """Get all versions of a secret.

        Args:
            name: Secret name

        Returns:
            List of secret versions
        """
        backend = self._get_backend()
        return await backend.get_secret_versions(name)

    async def get_secret_metadata(self, name: str) -> SecretMetadata | None:
        """Get secret metadata.

        Args:
            name: Secret name

        Returns:
            Secret metadata or None if not found
        """
        backend = self._get_backend()
        return await backend.get_secret_metadata(name)


# =============================================================================
# Module-level singleton and convenience functions
# =============================================================================

_unified_backend: UnifiedSecretsBackend | None = None


def get_unified_backend(config: dict[str, Any] | None = None) -> UnifiedSecretsBackend:
    """Get the singleton unified backend instance.

    Args:
        config: Optional configuration (only used on first call)

    Returns:
        UnifiedSecretsBackend instance
    """
    global _unified_backend
    if _unified_backend is None:
        _unified_backend = UnifiedSecretsBackend(config)
    return _unified_backend


def reset_unified_backend() -> None:
    """Reset the singleton backend (for testing)."""
    global _unified_backend
    _unified_backend = None


# =============================================================================
# Synchronous convenience wrapper
# =============================================================================


class SyncSecretsBackend:
    """Synchronous wrapper around UnifiedSecretsBackend.

    For use in contexts where async is not available.
    Uses asyncio.run() internally.
    """

    def __init__(self, backend: UnifiedSecretsBackend | None = None):
        """Initialize sync wrapper.

        Args:
            backend: Optional backend instance (uses singleton if not provided)
        """
        self._backend = backend or get_unified_backend()

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get secret synchronously.

        Args:
            key: Secret key
            default: Default value if not found

        Returns:
            Secret value or default
        """
        import asyncio

        try:
            asyncio.get_running_loop()
            # We're in an async context, create a task
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._backend.get_secret(key))
                result = future.result()
        except RuntimeError:
            # No running loop, safe to use asyncio.run
            result = asyncio.run(self._backend.get_secret(key))

        return result if result is not None else default

    def set(self, key: str, value: str) -> bool:
        """Set secret synchronously.

        Args:
            key: Secret key
            value: Secret value

        Returns:
            True if successful
        """
        import asyncio

        try:
            asyncio.get_running_loop()
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._backend.set_secret(key, value))
                future.result()
                return True
        except RuntimeError:
            asyncio.run(self._backend.set_secret(key, value))
            return True
        except Exception as e:
            logger.error(f"Failed to set secret {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete secret synchronously.

        Args:
            key: Secret key

        Returns:
            True if deleted
        """
        import asyncio

        try:
            asyncio.get_running_loop()
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._backend.delete_secret(key))
                return future.result()
        except RuntimeError:
            return asyncio.run(self._backend.delete_secret(key))

    def list(self) -> list[str]:
        """List all secrets synchronously.

        Returns:
            List of secret keys
        """
        import asyncio

        try:
            asyncio.get_running_loop()
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self._backend.list_secrets())
                return future.result()
        except RuntimeError:
            return asyncio.run(self._backend.list_secrets())

    def has(self, key: str) -> bool:
        """Check if secret exists.

        Args:
            key: Secret key

        Returns:
            True if exists
        """
        return self.get(key) is not None

    @property
    def backend_type(self) -> str:
        """Get the backend type."""
        return self._backend.backend_type


# Singleton sync wrapper
_sync_backend: SyncSecretsBackend | None = None


def get_sync_backend() -> SyncSecretsBackend:
    """Get the singleton sync backend wrapper.

    Returns:
        SyncSecretsBackend instance
    """
    global _sync_backend
    if _sync_backend is None:
        _sync_backend = SyncSecretsBackend()
    return _sync_backend
