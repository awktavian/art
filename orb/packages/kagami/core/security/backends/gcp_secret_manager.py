"""Google Cloud Secret Manager backend implementation.

Integrates with GCP Secret Manager for production secret storage.
Supports automatic rotation, versioning, and IAM-based access control.
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


class GCPSecretManagerBackend(SecretBackend):
    """Google Cloud Secret Manager backend implementation."""

    def __init__(self, config: dict[str, Any]):
        """Initialize GCP Secret Manager backend.

        Args:
            config: Configuration dict[str, Any] with keys:
                - project_id: GCP project ID (required)
                - credentials_path: Optional path to service account JSON
                - prefix: Optional prefix for secret names
        """
        super().__init__(config)
        self.project_id = config.get("project_id")
        if not self.project_id:
            raise ValueError("project_id is required for GCP Secret Manager")

        self.prefix = config.get("prefix", "kagami-")

        # Lazy import for optional dependency
        try:
            from google.cloud import secretmanager

            # Initialize client
            client_kwargs = {}
            if "credentials_path" in config:
                from google.oauth2 import service_account

                credentials = service_account.Credentials.from_service_account_file(
                    config["credentials_path"]
                )
                client_kwargs["credentials"] = credentials

            self.client = secretmanager.SecretManagerServiceClient(**client_kwargs)
            self.project_path = f"projects/{self.project_id}"

            logger.info(f"GCP Secret Manager backend initialized (project: {self.project_id})")

        except ImportError:
            logger.error(
                "google-cloud-secret-manager not installed. "
                "Install with: pip install google-cloud-secret-manager"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to initialize GCP Secret Manager: {e}")
            raise

    def _full_name(self, name: str) -> str:
        """Get full secret name with prefix.

        Args:
            name: Base secret name

        Returns:
            Full secret name with prefix
        """
        return f"{self.prefix}{name}"

    def _secret_path(self, name: str) -> str:
        """Get full secret path.

        Args:
            name: Secret name

        Returns:
            Full GCP secret path
        """
        return f"{self.project_path}/secrets/{self._full_name(name)}"

    def _version_path(self, name: str, version: str) -> str:
        """Get full version path.

        Args:
            name: Secret name
            version: Version ID or 'latest'

        Returns:
            Full GCP version path
        """
        return f"{self._secret_path(name)}/versions/{version}"

    async def get_secret(self, name: str, version: str | None = None) -> str | None:
        """Get secret from GCP Secret Manager.

        Args:
            name: Secret name
            version: Optional version ID (defaults to 'latest')

        Returns:
            Secret value or None if not found
        """
        try:
            version_id = version or "latest"
            version_path = self._version_path(name, version_id)

            response = self.client.access_secret_version(name=version_path)
            return response.payload.data.decode("utf-8")

        except Exception as e:
            if "NOT_FOUND" in str(e):
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
        """Set secret in GCP Secret Manager.

        Args:
            name: Secret name
            value: Secret value
            metadata: Optional metadata (stored as labels)

        Returns:
            Version ID of created secret
        """
        try:
            full_name = self._full_name(name)
            secret_path = self._secret_path(name)

            # Prepare labels from metadata
            labels = {}
            if metadata:
                for key, val in metadata.items():
                    # GCP labels have restrictions
                    label_key = key.lower().replace("_", "-")[:63]
                    label_val = str(val).lower().replace("_", "-")[:63]
                    labels[label_key] = label_val

            # Try to get existing secret
            try:
                self.client.get_secret(name=secret_path)
                secret_exists = True
            except Exception:
                secret_exists = False

            # Create secret if it doesn't exist
            if not secret_exists:
                from google.cloud import secretmanager

                secret = secretmanager.Secret(
                    replication=secretmanager.Replication(
                        automatic=secretmanager.Replication.Automatic()
                    ),
                    labels=labels,
                )

                self.client.create_secret(
                    parent=self.project_path,
                    secret_id=full_name,
                    secret=secret,
                )

                logger.info(f"Created secret: {name}")

            # Add secret version
            response = self.client.add_secret_version(
                parent=secret_path,
                payload={"data": value.encode("utf-8")},
            )

            # Extract version number from path
            version_id = response.name.split("/")[-1]

            logger.info(f"Set secret '{name}' (version: {version_id})")
            return version_id

        except Exception as e:
            logger.error(f"Failed to set[Any] secret '{name}': {e}")
            raise

    async def delete_secret(self, name: str) -> bool:
        """Delete secret from GCP Secret Manager.

        Args:
            name: Secret name

        Returns:
            True if deleted successfully
        """
        try:
            secret_path = self._secret_path(name)
            self.client.delete_secret(name=secret_path)

            logger.info(f"Deleted secret: {name}")
            return True

        except Exception as e:
            if "NOT_FOUND" in str(e):
                logger.debug(f"Secret not found for deletion: {name}")
                return False
            logger.error(f"Failed to delete secret '{name}': {e}")
            raise

    async def list_secrets(self) -> list[str]:
        """List all secrets in GCP Secret Manager.

        Returns:
            List of secret names (without prefix)
        """
        try:
            secrets = []
            for secret in self.client.list_secrets(parent=self.project_path):
                # Extract secret name from path
                secret_name = secret.name.split("/")[-1]

                if secret_name.startswith(self.prefix):
                    # Remove prefix
                    secrets.append(secret_name[len(self.prefix) :])

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
            secret_path = self._secret_path(name)
            versions = []

            for version in self.client.list_secret_versions(parent=secret_path):
                version_id = version.name.split("/")[-1]

                # Determine if active
                is_active = version.state == 1  # ENABLED state

                versions.append(
                    SecretVersion(
                        version_id=version_id,
                        value="<not fetched>",  # Don't fetch in list[Any] operation
                        created_at=(
                            version.create_time.ToDatetime()
                            if hasattr(version, "create_time")
                            else datetime.utcnow()
                        ),
                        created_by="gcp",
                        is_active=is_active,
                    )
                )

            return versions

        except Exception as e:
            if "NOT_FOUND" in str(e):
                return []
            logger.error(f"Failed to get versions for '{name}': {e}")
            raise

    async def get_secret_metadata(self, name: str) -> SecretMetadata | None:
        """Get secret metadata from GCP.

        Args:
            name: Secret name

        Returns:
            Secret metadata or None if not found
        """
        try:
            secret_path = self._secret_path(name)
            secret = self.client.get_secret(name=secret_path)

            # Parse labels for metadata
            labels = dict(secret.labels) if secret.labels else {}

            # Check if rotation is configured
            rotation_enabled = secret.rotation and secret.rotation.next_rotation_time

            metadata = SecretMetadata(
                name=name,
                backend=SecretBackendType.GCP_SECRET_MANAGER,
                created_at=(
                    secret.create_time.ToDatetime()
                    if hasattr(secret, "create_time")
                    else datetime.utcnow()
                ),
                updated_at=datetime.utcnow(),  # GCP doesn't track update time
                rotation_enabled=bool(rotation_enabled),
                rotation_days=int(labels.get("rotation-days", 90)),
                tags=labels,
            )

            return metadata

        except Exception as e:
            if "NOT_FOUND" in str(e):
                return None
            logger.error(f"Failed to get metadata for '{name}': {e}")
            raise

    async def disable_secret_version(self, name: str, version: str) -> bool:
        """Disable a specific secret version.

        Args:
            name: Secret name
            version: Version ID to disable

        Returns:
            True if disabled successfully
        """
        try:
            version_path = self._version_path(name, version)
            self.client.disable_secret_version(name=version_path)

            logger.info(f"Disabled secret version: {name}:{version}")
            return True

        except Exception as e:
            logger.error(f"Failed to disable version '{name}:{version}': {e}")
            raise
