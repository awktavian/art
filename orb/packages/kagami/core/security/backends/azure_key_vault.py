"""Azure Key Vault backend implementation.

Integrates with Azure Key Vault for production secret storage.
Supports automatic rotation, versioning, and Azure AD authentication.
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


class AzureKeyVaultBackend(SecretBackend):
    """Azure Key Vault backend implementation."""

    def __init__(self, config: dict[str, Any]):
        """Initialize Azure Key Vault backend.

        Args:
            config: Configuration dict[str, Any] with keys:
                - vault_url: Azure Key Vault URL (required)
                - tenant_id: Optional Azure AD tenant ID
                - client_id: Optional service principal client ID
                - client_secret: Optional service principal secret
                - prefix: Optional prefix for secret names
        """
        super().__init__(config)
        self.vault_url = config.get("vault_url")
        if not self.vault_url:
            raise ValueError("vault_url is required for Azure Key Vault")

        self.prefix = config.get("prefix", "kagami-")

        # Lazy import for optional dependency
        try:
            from azure.identity import ClientSecretCredential, DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            # Initialize credentials
            if all(k in config for k in ["tenant_id", "client_id", "client_secret"]):
                credential = ClientSecretCredential(
                    tenant_id=config["tenant_id"],
                    client_id=config["client_id"],
                    client_secret=config["client_secret"],
                )
            else:
                # Use default credential chain
                credential = DefaultAzureCredential()

            self.client = SecretClient(vault_url=self.vault_url, credential=credential)

            logger.info(f"Azure Key Vault backend initialized (vault: {self.vault_url})")

        except ImportError:
            logger.error(
                "azure-keyvault-secrets not installed. "
                "Install with: pip install azure-keyvault-secrets azure-identity"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to initialize Azure Key Vault: {e}")
            raise

    def _full_name(self, name: str) -> str:
        """Get full secret name with prefix.

        Azure Key Vault has naming restrictions:
        - Only alphanumeric and hyphens
        - Must start with letter
        - Max 127 characters

        Args:
            name: Base secret name

        Returns:
            Full secret name with prefix
        """
        # Sanitize name for Azure
        sanitized = name.replace("_", "-").replace("/", "-").lower()
        full_name = f"{self.prefix}{sanitized}"

        # Ensure starts with letter
        if not full_name[0].isalpha():
            full_name = f"s-{full_name}"

        return full_name[:127]

    async def get_secret(self, name: str, version: str | None = None) -> str | None:
        """Get secret from Azure Key Vault.

        Args:
            name: Secret name
            version: Optional version ID

        Returns:
            Secret value or None if not found
        """
        try:
            full_name = self._full_name(name)

            if version:
                secret = self.client.get_secret(name=full_name, version=version)
            else:
                secret = self.client.get_secret(name=full_name)

            return secret.value

        except Exception as e:
            if "SecretNotFound" in str(e) or "not found" in str(e).lower():
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
        """Set secret in Azure Key Vault.

        Args:
            name: Secret name
            value: Secret value
            metadata: Optional metadata (stored as tags)

        Returns:
            Version ID of created secret
        """
        try:
            full_name = self._full_name(name)

            # Prepare tags from metadata
            tags = {}
            if metadata:
                for key, val in metadata.items():
                    tags[key] = str(val)

            # Set secret (creates new version if exists)
            kwargs = {"name": full_name, "value": value}
            if tags:
                kwargs["tags"] = tags

            secret = self.client.set_secret(**kwargs)

            version_id = secret.properties.version

            logger.info(f"Set secret '{name}' (version: {version_id})")
            return version_id

        except Exception as e:
            logger.error(f"Failed to set[Any] secret '{name}': {e}")
            raise

    async def delete_secret(self, name: str) -> bool:
        """Delete secret from Azure Key Vault.

        Note: Secrets are soft-deleted and can be recovered.

        Args:
            name: Secret name

        Returns:
            True if deleted successfully
        """
        try:
            full_name = self._full_name(name)

            # Begin delete operation
            poller = self.client.begin_delete_secret(name=full_name)
            poller.wait()  # Wait for deletion to complete

            logger.info(f"Deleted secret: {name} (soft-deleted, can be recovered)")
            return True

        except Exception as e:
            if "SecretNotFound" in str(e) or "not found" in str(e).lower():
                logger.debug(f"Secret not found for deletion: {name}")
                return False
            logger.error(f"Failed to delete secret '{name}': {e}")
            raise

    async def list_secrets(self) -> list[str]:
        """List all secrets in Azure Key Vault.

        Returns:
            List of secret names (without prefix)
        """
        try:
            secrets = []

            for secret_properties in self.client.list_properties_of_secrets():
                secret_name = secret_properties.name

                if secret_name.startswith(self.prefix):
                    # Remove prefix and restore original format
                    original = secret_name[len(self.prefix) :]
                    secrets.append(original)

            return secrets

        except Exception as e:
            logger.error(f"Failed to list[Any] secrets: {e}")
            raise

    async def get_secret_versions(self, name: str) -> list[SecretVersion]:
        """Get all versions of a secret.

        Args:
            name: Secret name

        Returns:
            List of secret versions
        """
        try:
            full_name = self._full_name(name)
            versions = []

            for props in self.client.list_properties_of_secret_versions(name=full_name):
                versions.append(
                    SecretVersion(
                        version_id=props.version,
                        value="<not fetched>",  # Don't fetch in list[Any] operation
                        created_at=props.created_on or datetime.utcnow(),
                        created_by="azure",
                        is_active=props.enabled,
                        metadata={
                            "updated_on": props.updated_on,
                            "content_type": props.content_type,
                        },
                    )
                )

            return versions

        except Exception as e:
            if "SecretNotFound" in str(e) or "not found" in str(e).lower():
                return []
            logger.error(f"Failed to get versions for '{name}': {e}")
            raise

    async def get_secret_metadata(self, name: str) -> SecretMetadata | None:
        """Get secret metadata from Azure.

        Args:
            name: Secret name

        Returns:
            Secret metadata or None if not found
        """
        try:
            full_name = self._full_name(name)
            secret = self.client.get_secret(name=full_name)
            props = secret.properties

            # Parse tags for metadata
            tags = dict(props.tags) if props.tags else {}

            metadata = SecretMetadata(
                name=name,
                backend=SecretBackendType.AZURE_KEY_VAULT,
                created_at=props.created_on or datetime.utcnow(),
                updated_at=props.updated_on or datetime.utcnow(),
                rotation_enabled=bool(tags.get("rotation_enabled", False)),
                rotation_days=int(tags.get("rotation_days", 90)),
                tags=tags,
            )

            return metadata

        except Exception as e:
            if "SecretNotFound" in str(e) or "not found" in str(e).lower():
                return None
            logger.error(f"Failed to get metadata for '{name}': {e}")
            raise

    async def backup_secret(self, name: str) -> bytes:
        """Backup a secret (Azure-specific feature).

        Args:
            name: Secret name

        Returns:
            Backup blob

        Raises:
            Exception: If backup fails
        """
        try:
            full_name = self._full_name(name)
            backup_blob = self.client.backup_secret(name=full_name)

            logger.info(f"Backed up secret: {name}")
            return backup_blob

        except Exception as e:
            logger.error(f"Failed to backup secret '{name}': {e}")
            raise

    async def restore_secret(self, backup_blob: bytes) -> str:
        """Restore a secret from backup (Azure-specific feature).

        Args:
            backup_blob: Backup blob from backup_secret()

        Returns:
            Name of restored secret

        Raises:
            Exception: If restore fails
        """
        try:
            secret = self.client.restore_secret_backup(backup=backup_blob)
            name = secret.name

            logger.info(f"Restored secret: {name}")
            return name

        except Exception as e:
            logger.error(f"Failed to restore secret: {e}")
            raise

    async def purge_deleted_secret(self, name: str) -> bool:
        """Permanently delete a soft-deleted secret.

        Args:
            name: Secret name

        Returns:
            True if purged successfully
        """
        try:
            full_name = self._full_name(name)
            self.client.purge_deleted_secret(name=full_name)

            logger.info(f"Purged deleted secret: {name}")
            return True

        except Exception as e:
            logger.error(f"Failed to purge secret '{name}': {e}")
            raise
