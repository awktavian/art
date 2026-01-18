"""AWS Secrets Manager backend implementation.

Integrates with AWS Secrets Manager for production secret storage.
Supports automatic rotation, versioning, and cross-region replication.
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


class AWSSecretsManagerBackend(SecretBackend):
    """AWS Secrets Manager backend implementation."""

    def __init__(self, config: dict[str, Any]):
        """Initialize AWS Secrets Manager backend.

        Args:
            config: Configuration dict[str, Any] with keys:
                - region_name: AWS region (default: us-east-1)
                - aws_access_key_id: Optional AWS access key
                - aws_secret_access_key: Optional AWS secret key
                - prefix: Optional prefix for secret names
                - kms_key_id: Optional KMS key for encryption
        """
        super().__init__(config)
        self.region_name = config.get("region_name", "us-east-1")
        self.prefix = config.get("prefix", "kagami/")
        self.kms_key_id = config.get("kms_key_id")

        # Lazy import for optional dependency
        try:
            import boto3

            session_kwargs = {}
            if "aws_access_key_id" in config:
                session_kwargs["aws_access_key_id"] = config["aws_access_key_id"]
            if "aws_secret_access_key" in config:
                session_kwargs["aws_secret_access_key"] = config["aws_secret_access_key"]

            self.client = boto3.client(
                "secretsmanager", region_name=self.region_name, **session_kwargs
            )
            logger.info(f"AWS Secrets Manager backend initialized (region: {self.region_name})")

        except ImportError:
            logger.error("boto3 not installed. Install with: pip install boto3")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize AWS Secrets Manager: {e}")
            raise

    def _full_name(self, name: str) -> str:
        """Get full secret name with prefix.

        Args:
            name: Base secret name

        Returns:
            Full secret name with prefix
        """
        return f"{self.prefix}{name}"

    async def get_secret(self, name: str, version: str | None = None) -> str | None:
        """Get secret from AWS Secrets Manager.

        Args:
            name: Secret name
            version: Optional version ID or version stage

        Returns:
            Secret value or None if not found
        """
        try:
            kwargs = {"SecretId": self._full_name(name)}

            if version:
                # Check if it's a version ID or stage
                if version.startswith("AWSCURRENT") or version.startswith("AWSPREVIOUS"):
                    kwargs["VersionStage"] = version
                else:
                    kwargs["VersionId"] = version

            response = self.client.get_secret_value(**kwargs)

            # Return string value or parse JSON
            if "SecretString" in response:
                return response["SecretString"]
            elif "SecretBinary" in response:
                return response["SecretBinary"].decode("utf-8")

            return None

        except self.client.exceptions.ResourceNotFoundException:
            logger.debug(f"Secret not found: {name}")
            return None
        except Exception as e:
            logger.error(f"Failed to get secret '{name}': {e}")
            raise

    async def set_secret(
        self,
        name: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Set secret in AWS Secrets Manager.

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
            tags = []
            if metadata:
                for key, val in metadata.items():
                    tags.append({"Key": key, "Value": str(val)})

            # Try to update existing secret
            try:
                kwargs = {"SecretId": full_name, "SecretString": value}

                if self.kms_key_id:
                    kwargs["KmsKeyId"] = self.kms_key_id

                response = self.client.update_secret(**kwargs)
                version_id = response["VersionId"]

                # Update tags if provided
                if tags:
                    self.client.tag_resource(SecretId=full_name, Tags=tags)

                logger.info(f"Updated secret: {name} (version: {version_id})")
                return version_id

            except self.client.exceptions.ResourceNotFoundException:
                # Create new secret
                kwargs = {"Name": full_name, "SecretString": value}

                if self.kms_key_id:
                    kwargs["KmsKeyId"] = self.kms_key_id

                if tags:
                    kwargs["Tags"] = tags

                response = self.client.create_secret(**kwargs)
                version_id = response["VersionId"]

                logger.info(f"Created secret: {name} (version: {version_id})")
                return version_id

        except Exception as e:
            logger.error(f"Failed to set[Any] secret '{name}': {e}")
            raise

    async def delete_secret(self, name: str) -> bool:
        """Delete secret from AWS Secrets Manager.

        Note: Secrets are soft-deleted with a recovery window.

        Args:
            name: Secret name

        Returns:
            True if deleted successfully
        """
        try:
            self.client.delete_secret(
                SecretId=self._full_name(name),
                ForceDeleteWithoutRecovery=False,  # Allow recovery
                RecoveryWindowInDays=7,
            )
            logger.info(f"Deleted secret: {name} (7-day recovery window)")
            return True

        except self.client.exceptions.ResourceNotFoundException:
            logger.debug(f"Secret not found for deletion: {name}")
            return False
        except Exception as e:
            logger.error(f"Failed to delete secret '{name}': {e}")
            raise

    async def list_secrets(self) -> list[str]:
        """List all secrets in AWS Secrets Manager.

        Returns:
            List of secret names (without prefix)
        """
        try:
            secrets = []
            paginator = self.client.get_paginator("list_secrets")

            for page in paginator.paginate():
                for secret in page["SecretList"]:
                    name = secret["Name"]
                    if name.startswith(self.prefix):
                        # Remove prefix
                        secrets.append(name[len(self.prefix) :])

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
            response = self.client.list_secret_version_ids(
                SecretId=self._full_name(name), IncludeDeprecated=True
            )

            versions = []
            for version_id, stages_info in response.get("Versions", {}).items():
                # Note: We don't fetch actual values for security
                versions.append(
                    SecretVersion(
                        version_id=version_id,
                        value="<not fetched>",  # Don't fetch in list[Any] operation
                        created_at=stages_info.get("CreatedDate", datetime.utcnow()),
                        created_by="aws",
                        is_active="AWSCURRENT" in stages_info.get("VersionStages", []),
                    )
                )

            return versions

        except self.client.exceptions.ResourceNotFoundException:
            return []
        except Exception as e:
            logger.error(f"Failed to get versions for '{name}': {e}")
            raise

    async def get_secret_metadata(self, name: str) -> SecretMetadata | None:
        """Get secret metadata from AWS.

        Args:
            name: Secret name

        Returns:
            Secret metadata or None if not found
        """
        try:
            response = self.client.describe_secret(SecretId=self._full_name(name))

            # Parse tags for metadata
            tags = {tag["Key"]: tag["Value"] for tag in response.get("Tags", [])}

            rotation_enabled = response.get("RotationEnabled", False)

            metadata = SecretMetadata(
                name=name,
                backend=SecretBackendType.AWS_SECRETS_MANAGER,
                created_at=response.get("CreatedDate", datetime.utcnow()),
                updated_at=response.get("LastChangedDate", datetime.utcnow()),
                rotation_enabled=rotation_enabled,
                rotation_days=int(tags.get("rotation_days", 90)),
                last_rotated=response.get("LastRotatedDate"),
                tags=tags,
            )

            return metadata

        except self.client.exceptions.ResourceNotFoundException:
            return None
        except Exception as e:
            logger.error(f"Failed to get metadata for '{name}': {e}")
            raise

    async def enable_rotation(
        self,
        name: str,
        rotation_lambda_arn: str,
        rotation_days: int = 30,
    ) -> bool:
        """Enable automatic rotation for a secret.

        Args:
            name: Secret name
            rotation_lambda_arn: ARN of rotation Lambda function
            rotation_days: Days between rotations

        Returns:
            True if rotation enabled successfully
        """
        try:
            self.client.rotate_secret(
                SecretId=self._full_name(name),
                RotationLambdaARN=rotation_lambda_arn,
                RotationRules={"AutomaticallyAfterDays": rotation_days},
            )

            logger.info(f"Enabled rotation for secret '{name}' (every {rotation_days} days)")
            return True

        except Exception as e:
            logger.error(f"Failed to enable rotation for '{name}': {e}")
            raise
