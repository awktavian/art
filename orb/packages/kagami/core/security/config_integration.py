"""Backend configuration helpers for secrets manager.

This module provides utilities for configuring secrets backends based on
environment variables. For actual secret access, use:

    from kagami.core.security import get_secret, set_secret

Created: December 2025
Updated: December 31, 2025 - Removed deprecated SecretConfigProvider
"""

import logging
import os
from pathlib import Path
from typing import Any

from kagami.core.security.secrets_manager import (
    SecretBackendType,
    create_secrets_manager,
)

logger = logging.getLogger(__name__)


def get_backend_config(backend_type: str | None = None) -> dict[str, Any]:
    """Get configuration for a secrets backend from environment variables.

    Args:
        backend_type: Backend type (local, aws, gcp, azure, vault).
                     Defaults to KAGAMI_SECRET_BACKEND env var or "local".

    Returns:
        Backend configuration dictionary
    """
    if backend_type is None:
        backend_type = os.getenv("KAGAMI_SECRET_BACKEND", "local")

    return _load_backend_config_from_env(backend_type.lower())


def create_configured_secrets_manager(
    backend_type: str | None = None,
    backend_config: dict[str, Any] | None = None,
) -> Any:
    """Create a secrets manager with configuration from environment.

    Args:
        backend_type: Backend type (local, aws, gcp, azure, vault)
        backend_config: Optional override configuration

    Returns:
        SecretsManager instance
    """
    if backend_type is None:
        backend_type = os.getenv("KAGAMI_SECRET_BACKEND", "local")

    backend_type_map = {
        "local": SecretBackendType.LOCAL_ENCRYPTED,
        "aws": SecretBackendType.AWS_SECRETS_MANAGER,
        "gcp": SecretBackendType.GCP_SECRET_MANAGER,
        "azure": SecretBackendType.AZURE_KEY_VAULT,
        "vault": SecretBackendType.HASHICORP_VAULT,
    }

    backend_enum = backend_type_map.get(backend_type.lower())
    if not backend_enum:
        raise ValueError(f"Invalid backend type: {backend_type}")

    if backend_config is None:
        backend_config = _load_backend_config_from_env(backend_type)

    return create_secrets_manager(
        backend_type=backend_enum,
        config=backend_config,
        enable_cache=True,
        cache_ttl_seconds=int(os.getenv("KAGAMI_SECRET_CACHE_TTL", "300")),
    )


def _load_backend_config_from_env(backend_type: str) -> dict[str, Any]:
    """Load backend configuration from environment variables.

    Args:
        backend_type: Backend type

    Returns:
        Backend configuration dictionary
    """
    if backend_type == "local":
        return {
            "storage_path": os.getenv(
                "KAGAMI_SECRET_STORAGE_PATH",
                str(Path.home() / ".kagami" / "secrets" / "secrets.enc"),
            ),
            "master_key_path": os.getenv(
                "KAGAMI_SECRET_MASTER_KEY_PATH",
                str(Path.home() / ".kagami" / "secrets" / "master.key"),
            ),
            "auto_generate_key": True,
        }

    elif backend_type == "aws":
        return {
            "region_name": os.getenv("AWS_REGION", "us-east-1"),
            "prefix": os.getenv("KAGAMI_SECRET_PREFIX", "kagami/"),
        }

    elif backend_type == "gcp":
        project_id = os.getenv("GCP_PROJECT_ID")
        if not project_id:
            raise ValueError("GCP_PROJECT_ID required for GCP backend")

        config = {
            "project_id": project_id,
            "prefix": os.getenv("KAGAMI_SECRET_PREFIX", "kagami-"),
        }

        if os.getenv("GCP_CREDENTIALS_PATH"):
            config["credentials_path"] = os.getenv("GCP_CREDENTIALS_PATH")

        return config

    elif backend_type == "azure":
        vault_url = os.getenv("AZURE_KEY_VAULT_URL")
        if not vault_url:
            raise ValueError("AZURE_KEY_VAULT_URL required for Azure backend")

        config = {
            "vault_url": vault_url,
            "prefix": os.getenv("KAGAMI_SECRET_PREFIX", "kagami-"),
        }

        if all(os.getenv(k) for k in ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"]):
            config.update(
                {
                    "tenant_id": os.getenv("AZURE_TENANT_ID"),
                    "client_id": os.getenv("AZURE_CLIENT_ID"),
                    "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
                }
            )

        return config

    elif backend_type == "vault":
        vault_url = os.getenv("VAULT_ADDR", "http://localhost:8200")
        vault_token = os.getenv("VAULT_TOKEN")

        if not vault_token:
            raise ValueError("VAULT_TOKEN required for Vault backend")

        return {
            "url": vault_url,
            "token": vault_token,
            "mount_point": os.getenv("VAULT_MOUNT_POINT", "secret"),
            "kv_version": int(os.getenv("VAULT_KV_VERSION", "2")),
            "prefix": os.getenv("KAGAMI_SECRET_PREFIX", "kagami/"),
        }

    else:
        raise ValueError(f"Unknown backend type: {backend_type}")
