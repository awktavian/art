"""HashiCorp Vault backend implementation.

Integrates with HashiCorp Vault for secret storage.
Supports dynamic secrets, leasing, and renewal.
"""

import logging
from datetime import datetime
from typing import Any

from kagami.core.security.secrets_manager import (
    SecretBackend,
    SecretBackendType,
    SecretMetadata,
    SecretVersion,
)

logger = logging.getLogger(__name__)


class HashiCorpVaultBackend(SecretBackend):
    """HashiCorp Vault backend implementation."""

    def __init__(self, config: dict[str, Any]):
        """Initialize HashiCorp Vault backend.

        Args:
            config: Configuration dict[str, Any] with keys:
                - url: Vault server URL (required)
                - token: Vault token for authentication
                - mount_point: KV mount point (default: secret)
                - kv_version: KV version (1 or 2, default: 2)
                - namespace: Optional Vault namespace
                - prefix: Optional prefix for secret paths
        """
        super().__init__(config)
        self.url = config.get("url", "http://localhost:8200")
        self.token = config.get("token")
        self.mount_point = config.get("mount_point", "secret")
        self.kv_version = config.get("kv_version", 2)
        self.namespace = config.get("namespace")
        self.prefix = config.get("prefix", "kagami/")

        if not self.token:
            raise ValueError("token is required for HashiCorp Vault")

        # Lazy import for optional dependency
        try:
            import hvac

            client_kwargs = {"url": self.url, "token": self.token}

            if self.namespace:
                client_kwargs["namespace"] = self.namespace

            self.client = hvac.Client(**client_kwargs)

            # Verify authentication
            if not self.client.is_authenticated():
                raise RuntimeError("Failed to authenticate with Vault")

            logger.info(
                f"HashiCorp Vault backend initialized "
                f"(url: {self.url}, kv_version: {self.kv_version})"
            )

        except ImportError:
            logger.error("hvac not installed. Install with: pip install hvac")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize HashiCorp Vault: {e}")
            raise

    def _full_path(self, name: str) -> str:
        """Get full secret path with prefix.

        Args:
            name: Base secret name

        Returns:
            Full secret path
        """
        return f"{self.prefix}{name}"

    async def get_secret(self, name: str, version: str | None = None) -> str | None:
        """Get secret from Vault.

        Args:
            name: Secret name
            version: Optional version number (KV v2 only)

        Returns:
            Secret value or None if not found
        """
        try:
            path = self._full_path(name)

            if self.kv_version == 2:
                # KV v2 API
                kwargs = {"path": path, "mount_point": self.mount_point}
                if version:
                    kwargs["version"] = int(version)

                response = self.client.secrets.kv.v2.read_secret_version(**kwargs)
                data = response.get("data", {}).get("data", {})

            else:
                # KV v1 API
                response = self.client.secrets.kv.v1.read_secret(
                    path=path, mount_point=self.mount_point
                )
                data = response.get("data", {})

            # Return the 'value' field or entire data as JSON
            if "value" in data:
                return data["value"]
            elif data:
                import json

                return json.dumps(data)

            return None

        except Exception as e:
            if "Invalid path" in str(e) or "No value found" in str(e):
                logger.debug(f"Secret not found: {name}")
                return None
            logger.error(f"Failed to get secret '{name}': {e}")
            raise

    async def set_secret(
        self,
        name: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Set secret in Vault.

        Args:
            name: Secret name
            value: Secret value
            metadata: Optional metadata (KV v2 custom metadata)

        Returns:
            Version ID of created secret
        """
        try:
            path = self._full_path(name)

            # Prepare secret data
            secret_data = {"value": value}

            if self.kv_version == 2:
                # KV v2 API
                response = self.client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret=secret_data,
                    mount_point=self.mount_point,
                )

                version_id = str(response.get("data", {}).get("version", "1"))

                # Set custom metadata if provided
                if metadata:
                    self.client.secrets.kv.v2.update_metadata(
                        path=path,
                        custom_metadata=metadata,
                        mount_point=self.mount_point,
                    )

            else:
                # KV v1 API (no versioning)
                self.client.secrets.kv.v1.create_or_update_secret(
                    path=path,
                    secret=secret_data,
                    mount_point=self.mount_point,
                )
                version_id = "1"

            logger.info(f"Set secret '{name}' (version: {version_id})")
            return version_id

        except Exception as e:
            logger.error(f"Failed to set[Any] secret '{name}': {e}")
            raise

    async def delete_secret(self, name: str) -> bool:
        """Delete secret from Vault.

        For KV v2, this soft-deletes the latest version.
        For KV v1, this permanently deletes the secret.

        Args:
            name: Secret name

        Returns:
            True if deleted successfully
        """
        try:
            path = self._full_path(name)

            if self.kv_version == 2:
                # KV v2: Delete latest version
                self.client.secrets.kv.v2.delete_latest_version_of_secret(
                    path=path, mount_point=self.mount_point
                )
            else:
                # KV v1: Permanent delete
                self.client.secrets.kv.v1.delete_secret(path=path, mount_point=self.mount_point)

            logger.info(f"Deleted secret: {name}")
            return True

        except Exception as e:
            if "Invalid path" in str(e) or "No value found" in str(e):
                logger.debug(f"Secret not found for deletion: {name}")
                return False
            logger.error(f"Failed to delete secret '{name}': {e}")
            raise

    async def list_secrets(self) -> list[str]:
        """List all secrets in Vault.

        Returns:
            List of secret names (without prefix)
        """
        try:
            secrets = []

            # List secrets at prefix path
            if self.kv_version == 2:
                response = self.client.secrets.kv.v2.list_secrets(
                    path=self.prefix.rstrip("/"),
                    mount_point=self.mount_point,
                )
            else:
                response = self.client.secrets.kv.v1.list_secrets(
                    path=self.prefix.rstrip("/"),
                    mount_point=self.mount_point,
                )

            keys = response.get("data", {}).get("keys", [])

            for key in keys:
                # Remove trailing slash for folders
                key = key.rstrip("/")
                secrets.append(key)

            return secrets

        except Exception as e:
            if "Invalid path" in str(e):
                return []
            logger.error(f"Failed to list[Any] secrets: {e}")
            raise

    async def get_secret_versions(self, name: str) -> list[SecretVersion]:
        """Get all versions of a secret (KV v2 only).

        Args:
            name: Secret name

        Returns:
            List of secret versions
        """
        if self.kv_version != 2:
            logger.warning("Secret versioning only available in KV v2")
            return []

        try:
            path = self._full_path(name)

            response = self.client.secrets.kv.v2.read_secret_metadata(
                path=path, mount_point=self.mount_point
            )

            versions_data = response.get("data", {}).get("versions", {})
            versions = []

            for version_num, version_info in versions_data.items():
                created_time = version_info.get("created_time")
                if created_time:
                    # Parse ISO format timestamp
                    created_at = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                else:
                    created_at = datetime.utcnow()

                versions.append(
                    SecretVersion(
                        version_id=str(version_num),
                        value="<not fetched>",  # Don't fetch in list[Any] operation
                        created_at=created_at,
                        created_by="vault",
                        is_active=not version_info.get("deletion_time"),
                    )
                )

            return sorted(versions, key=lambda v: int(v.version_id), reverse=True)

        except Exception as e:
            if "Invalid path" in str(e):
                return []
            logger.error(f"Failed to get versions for '{name}': {e}")
            raise

    async def get_secret_metadata(self, name: str) -> SecretMetadata | None:
        """Get secret metadata from Vault.

        Args:
            name: Secret name

        Returns:
            Secret metadata or None if not found
        """
        try:
            path = self._full_path(name)

            if self.kv_version == 2:
                response = self.client.secrets.kv.v2.read_secret_metadata(
                    path=path, mount_point=self.mount_point
                )

                data = response.get("data", {})
                custom_meta = data.get("custom_metadata", {})

                created_time = data.get("created_time")
                updated_time = data.get("updated_time")

                metadata = SecretMetadata(
                    name=name,
                    backend=SecretBackendType.HASHICORP_VAULT,
                    created_at=(
                        datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                        if created_time
                        else datetime.utcnow()
                    ),
                    updated_at=(
                        datetime.fromisoformat(updated_time.replace("Z", "+00:00"))
                        if updated_time
                        else datetime.utcnow()
                    ),
                    rotation_enabled=bool(custom_meta.get("rotation_enabled", False)),
                    rotation_days=int(custom_meta.get("rotation_days", 90)),
                    tags=custom_meta,
                )

                return metadata

            else:
                # KV v1 has no metadata API
                return SecretMetadata(
                    name=name,
                    backend=SecretBackendType.HASHICORP_VAULT,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )

        except Exception as e:
            if "Invalid path" in str(e):
                return None
            logger.error(f"Failed to get metadata for '{name}': {e}")
            raise

    async def destroy_secret_versions(self, name: str, versions: list[int]) -> bool:
        """Permanently destroy specific versions (KV v2 only).

        Args:
            name: Secret name
            versions: List of version numbers to destroy

        Returns:
            True if destroyed successfully
        """
        if self.kv_version != 2:
            logger.warning("Version destruction only available in KV v2")
            return False

        try:
            path = self._full_path(name)

            self.client.secrets.kv.v2.destroy_secret_versions(
                path=path,
                versions=versions,
                mount_point=self.mount_point,
            )

            logger.info(f"Destroyed versions {versions} of secret: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to destroy versions of '{name}': {e}")
            raise
