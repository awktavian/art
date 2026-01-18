"""Cloud storage backend for Kagami persistence (S3/GCS).

CREATED: December 28, 2025
PURPOSE: Archive state to cloud object storage (infinite scale).

Supports:
- AWS S3 (boto3)
- Google Cloud Storage (google-cloud-storage)
- MinIO (S3-compatible)

Features:
- Infinite scalability
- Automatic versioning (S3 native)
- Lifecycle policies for cost optimization
- Multi-region replication
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from kagami.core.persistence.backends.protocol import (
    KeyNotFoundError,
    StorageBackend,
    StorageConfig,
    StorageConnectionError,
)

try:
    import boto3
    from botocore.exceptions import ClientError

    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False


class CloudBackend(StorageBackend):
    """Cloud object storage backend (S3/GCS/MinIO)."""

    def __init__(self, config: StorageConfig):
        """Initialize cloud backend.

        Config params:
            provider: "s3" | "gcs" | "minio"
            bucket: Bucket name (required)
            prefix: Key prefix (optional)
            region: AWS region (default: us-east-1)
            endpoint_url: Custom endpoint for MinIO (optional)
            access_key: Access key ID
            secret_key: Secret access key
        """
        super().__init__(config)

        params = config.params
        self.provider = params.get("provider", "s3")
        self.bucket = params.get("bucket")
        self.prefix = params.get("prefix", "kagami-state")
        self.region = params.get("region", "us-east-1")

        if not self.bucket:
            raise ValueError("bucket required in config.params")

        # Initialize S3 client (works for S3, MinIO, GCS with interop)
        if not HAS_BOTO3:
            raise ImportError("boto3 not installed. pip install boto3")

        try:
            self.s3 = boto3.client(
                "s3",
                region_name=self.region,
                endpoint_url=params.get("endpoint_url"),
                aws_access_key_id=params.get("access_key"),
                aws_secret_access_key=params.get("secret_key"),
            )
            # Test connection
            self.s3.head_bucket(Bucket=self.bucket)
        except Exception as e:
            raise StorageConnectionError(f"Failed to connect to {self.provider}: {e}") from e

    async def save(
        self,
        key: str,
        data: bytes,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Save data to cloud storage."""
        import asyncio

        # Generate version
        version_id = f"v{int(time.time() * 1000000)}"
        checksum = hashlib.sha256(data).hexdigest()

        # Prepare metadata
        metadata = metadata or {}
        metadata.update(
            {
                "version": version_id,
                "checksum": checksum,
                "size": str(len(data)),
                "timestamp": str(time.time()),
            }
        )

        # S3 key
        s3_key = f"{self.prefix}/{key}"
        if self.config.enable_versioning:
            s3_key = f"{s3_key}/{version_id}"

        # Upload to S3 (run in thread pool)
        await asyncio.to_thread(
            self.s3.put_object,
            Bucket=self.bucket,
            Key=s3_key,
            Body=data,
            Metadata=metadata,
            ContentMD5=None,  # S3 computes automatically
        )

        return version_id

    async def load(
        self,
        key: str,
        version: str | None = None,
    ) -> tuple[bytes, dict[str, Any]]:
        """Load data from cloud storage."""
        import asyncio

        s3_key = f"{self.prefix}/{key}"
        if version and self.config.enable_versioning:
            s3_key = f"{s3_key}/{version}"

        try:
            response = await asyncio.to_thread(
                self.s3.get_object,
                Bucket=self.bucket,
                Key=s3_key,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                raise KeyNotFoundError(f"Key not found: {key}") from e
            raise

        data = response["Body"].read()
        metadata = response.get("Metadata", {})

        # Convert string metadata back to proper types
        if "size" in metadata:
            metadata["size"] = int(metadata["size"])
        if "timestamp" in metadata:
            metadata["timestamp"] = float(metadata["timestamp"])

        # Verify checksum
        if "checksum" in metadata:
            actual = hashlib.sha256(data).hexdigest()
            if actual != metadata["checksum"]:
                raise ValueError(f"Checksum mismatch: {key}")

        return data, metadata

    async def delete(self, key: str, version: str | None = None) -> bool:
        """Delete data from cloud storage."""
        import asyncio

        s3_key = f"{self.prefix}/{key}"
        if version:
            s3_key = f"{s3_key}/{version}"

            try:
                await asyncio.to_thread(
                    self.s3.delete_object,
                    Bucket=self.bucket,
                    Key=s3_key,
                )
                return True
            except ClientError:
                return False
        else:
            # Delete all versions (list[Any] then delete)
            try:
                response = await asyncio.to_thread(
                    self.s3.list_objects_v2,
                    Bucket=self.bucket,
                    Prefix=f"{s3_key}/",
                )
                if "Contents" in response:
                    # Delete all objects in parallel
                    await asyncio.gather(
                        *[
                            asyncio.to_thread(
                                self.s3.delete_object,
                                Bucket=self.bucket,
                                Key=obj["Key"],
                            )
                            for obj in response["Contents"]
                        ],
                        return_exceptions=True,
                    )
                    return True
                return False
            except ClientError:
                return False

    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        import asyncio

        s3_key = f"{self.prefix}/{key}"

        try:
            await asyncio.to_thread(
                self.s3.head_object,
                Bucket=self.bucket,
                Key=s3_key,
            )
            return True
        except ClientError:
            # Check for versioned keys
            try:
                response = await asyncio.to_thread(
                    self.s3.list_objects_v2,
                    Bucket=self.bucket,
                    Prefix=f"{s3_key}/",
                    MaxKeys=1,
                )
                return "Contents" in response and len(response["Contents"]) > 0
            except ClientError:
                return False

    async def list_keys(
        self,
        prefix: str | None = None,
        limit: int | None = None,
    ) -> list[str]:
        """List all keys."""

        s3_prefix = f"{self.prefix}/{prefix}" if prefix else self.prefix
        keys = set()

        try:
            paginator = self.s3.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(
                Bucket=self.bucket,
                Prefix=s3_prefix,
                PaginationConfig={"MaxItems": limit} if limit else {},
            )

            for page in page_iterator:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        key = obj["Key"]
                        # Remove prefix and extract base key
                        key = key[len(self.prefix) + 1 :]
                        if "/" in key:
                            base_key = key.split("/")[0]
                        else:
                            base_key = key
                        keys.add(base_key)

        except ClientError:
            pass

        return sorted(keys)

    async def list_versions(self, key: str) -> list[str]:
        """List all versions."""
        import asyncio

        s3_prefix = f"{self.prefix}/{key}/"
        versions = []

        try:
            response = await asyncio.to_thread(
                self.s3.list_objects_v2,
                Bucket=self.bucket,
                Prefix=s3_prefix,
            )

            if "Contents" in response:
                for obj in response["Contents"]:
                    # Extract version from key
                    key_parts = obj["Key"].split("/")
                    if len(key_parts) > 2:
                        version = key_parts[-1]
                        versions.append(version)

        except ClientError:
            pass

        versions.sort(reverse=True)
        return versions

    async def get_metadata(self, key: str, version: str | None = None) -> dict[str, Any]:
        """Get metadata."""
        import asyncio

        s3_key = f"{self.prefix}/{key}"
        if version and self.config.enable_versioning:
            s3_key = f"{s3_key}/{version}"

        try:
            response = await asyncio.to_thread(
                self.s3.head_object,
                Bucket=self.bucket,
                Key=s3_key,
            )
            metadata = response.get("Metadata", {})

            # Convert string metadata
            if "size" in metadata:
                metadata["size"] = int(metadata["size"])
            if "timestamp" in metadata:
                metadata["timestamp"] = float(metadata["timestamp"])

            return metadata

        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                raise KeyNotFoundError(f"Key not found: {key}") from e
            raise

    async def get_size(self, key: str, version: str | None = None) -> int:
        """Get size."""
        import asyncio

        s3_key = f"{self.prefix}/{key}"
        if version and self.config.enable_versioning:
            s3_key = f"{s3_key}/{version}"

        try:
            response = await asyncio.to_thread(
                self.s3.head_object,
                Bucket=self.bucket,
                Key=s3_key,
            )
            return response["ContentLength"]
        except ClientError:
            return 0
