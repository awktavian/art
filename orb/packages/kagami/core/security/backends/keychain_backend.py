"""macOS Keychain backend for secrets management.

Uses the system Keychain for secure credential storage.
Ideal for local development and single-user deployments.

Features:
- Uses macOS Security framework via `security` command
- Automatic secret versioning via metadata
- Audit logging
- Cross-app access control

Requirements:
- macOS (uses `security` command-line tool)

Created: December 29, 2025
"""

from __future__ import annotations

import json
import logging
import subprocess
import uuid
from datetime import datetime
from typing import Any

from kagami.core.security.secrets_manager import (
    SecretAuditEntry,
    SecretBackend,
    SecretBackendType,
    SecretMetadata,
    SecretVersion,
)

logger = logging.getLogger(__name__)


class KeychainBackend(SecretBackend):
    """macOS Keychain backend for secrets.

    Stores secrets in the system Keychain using the `security` CLI.
    Each secret has:
    - Main entry: The actual secret value
    - Metadata entry: JSON metadata including versions

    Config options:
        service_name: Keychain service name (default: "kagami")
        access_group: Optional access group for shared secrets
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.service_name = config.get("service_name", "kagami")
        self.access_group = config.get("access_group")

        # In-memory version tracking (synced with keychain metadata)
        self._versions: dict[str, list[SecretVersion]] = {}
        self._metadata: dict[str, SecretMetadata] = {}

        # Verify keychain is available
        self._verify_keychain()

    def _verify_keychain(self) -> None:
        """Verify keychain is available."""
        try:
            result = subprocess.run(
                ["security", "help"],
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                logger.warning("KeychainBackend: security command not available")
        except FileNotFoundError:
            logger.warning("KeychainBackend: Not running on macOS, keychain unavailable")

    def _run_security(self, args: list[str], check: bool = True) -> subprocess.CompletedProcess:
        """Run security command."""
        return subprocess.run(
            ["security", *args],
            capture_output=True,
            text=True,
            check=check,
        )

    def _get_keychain_value(self, account: str) -> str | None:
        """Get value from keychain."""
        try:
            result = self._run_security(
                [
                    "find-generic-password",
                    "-s",
                    self.service_name,
                    "-a",
                    account,
                    "-w",
                ],
                check=True,
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def _set_keychain_value(self, account: str, value: str) -> bool:
        """Set value in keychain."""
        try:
            # Delete existing (if any)
            self._run_security(
                [
                    "delete-generic-password",
                    "-s",
                    self.service_name,
                    "-a",
                    account,
                ],
                check=False,
            )

            # Add new
            self._run_security(
                [
                    "add-generic-password",
                    "-s",
                    self.service_name,
                    "-a",
                    account,
                    "-w",
                    value,
                    "-U",
                ],
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Keychain set failed: {e}")
            return False

    def _delete_keychain_value(self, account: str) -> bool:
        """Delete value from keychain."""
        try:
            self._run_security(
                [
                    "delete-generic-password",
                    "-s",
                    self.service_name,
                    "-a",
                    account,
                ],
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _get_metadata_key(self, name: str) -> str:
        """Get metadata key for a secret."""
        return f"_meta_{name}"

    def _load_metadata(self, name: str) -> dict[str, Any] | None:
        """Load metadata from keychain."""
        meta_key = self._get_metadata_key(name)
        meta_json = self._get_keychain_value(meta_key)
        if meta_json:
            try:
                return json.loads(meta_json)
            except json.JSONDecodeError:
                pass
        return None

    def _save_metadata(self, name: str, metadata: dict[str, Any]) -> bool:
        """Save metadata to keychain."""
        meta_key = self._get_metadata_key(name)
        return self._set_keychain_value(meta_key, json.dumps(metadata))

    async def get_secret(self, name: str, version: str | None = None) -> str | None:
        """Get secret from keychain."""
        self._log_audit(
            SecretAuditEntry(
                timestamp=datetime.utcnow(),
                secret_name=name,
                action="read",
                user="system",
                success=True,
            )
        )

        # If specific version requested, check metadata
        if version:
            meta = self._load_metadata(name)
            if meta and "versions" in meta:
                for v in meta["versions"]:
                    if v.get("version_id") == version:
                        return v.get("value")
            return None

        # Get current value
        return self._get_keychain_value(name)

    async def set_secret(
        self,
        name: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Set secret in keychain with versioning."""
        version_id = str(uuid.uuid4())[:8]
        now = datetime.utcnow()

        # Load existing metadata
        existing_meta = self._load_metadata(name) or {
            "name": name,
            "created_at": now.isoformat(),
            "versions": [],
        }

        # Add new version to history (keep last 5)
        old_value = self._get_keychain_value(name)
        if old_value:
            existing_meta["versions"].append(
                {
                    "version_id": existing_meta.get("current_version", "v0"),
                    "created_at": existing_meta.get("updated_at", now.isoformat()),
                    "value": old_value,  # Store old value in metadata for versioning
                }
            )
            # Keep only last 5 versions
            existing_meta["versions"] = existing_meta["versions"][-5:]

        # Update metadata
        existing_meta["updated_at"] = now.isoformat()
        existing_meta["current_version"] = version_id
        if metadata:
            existing_meta["user_metadata"] = metadata

        # Save to keychain
        if not self._set_keychain_value(name, value):
            raise RuntimeError(f"Failed to set secret '{name}' in keychain")

        self._save_metadata(name, existing_meta)

        self._log_audit(
            SecretAuditEntry(
                timestamp=now,
                secret_name=name,
                action="write",
                user="system",
                success=True,
            )
        )

        return version_id

    async def delete_secret(self, name: str) -> bool:
        """Delete secret from keychain."""
        # Delete main secret
        self._delete_keychain_value(name)

        # Delete metadata
        self._delete_keychain_value(self._get_metadata_key(name))

        self._log_audit(
            SecretAuditEntry(
                timestamp=datetime.utcnow(),
                secret_name=name,
                action="delete",
                user="system",
                success=True,
            )
        )

        return True

    async def list_secrets(self) -> list[str]:
        """List all secrets in keychain for this service."""
        try:
            # Use security dump-keychain and parse for our service
            result = self._run_security(
                [
                    "dump-keychain",
                ],
                check=False,
            )

            secrets = []
            current_service = None

            for line in result.stdout.split("\n"):
                line = line.strip()
                if '"svce"' in line and self.service_name in line:
                    current_service = self.service_name
                elif '"acct"' in line and current_service:
                    # Extract account name
                    import re

                    match = re.search(r'"acct"<blob>="([^"]+)"', line)
                    if match:
                        account = match.group(1)
                        # Skip metadata entries
                        if not account.startswith("_meta_"):
                            secrets.append(account)
                    current_service = None

            return secrets

        except Exception as e:
            logger.error(f"Failed to list keychain secrets: {e}")
            return []

    async def get_secret_versions(self, name: str) -> list[SecretVersion]:
        """Get all versions of a secret."""
        meta = self._load_metadata(name)
        if not meta:
            return []

        versions = []

        # Add historical versions
        for v in meta.get("versions", []):
            versions.append(
                SecretVersion(
                    version_id=v["version_id"],
                    value="[REDACTED]",  # Don't expose old values
                    created_at=datetime.fromisoformat(v["created_at"]),
                    created_by="system",
                    is_active=False,
                )
            )

        # Add current version
        current_value = self._get_keychain_value(name)
        if current_value:
            versions.append(
                SecretVersion(
                    version_id=meta.get("current_version", "v0"),
                    value="[CURRENT]",
                    created_at=datetime.fromisoformat(
                        meta.get("updated_at", meta.get("created_at"))
                    ),
                    created_by="system",
                    is_active=True,
                )
            )

        return versions

    async def get_secret_metadata(self, name: str) -> SecretMetadata | None:
        """Get secret metadata."""
        meta = self._load_metadata(name)
        if not meta:
            return None

        return SecretMetadata(
            name=name,
            backend=SecretBackendType.LOCAL_ENCRYPTED,  # Use LOCAL as proxy
            created_at=datetime.fromisoformat(meta.get("created_at")),
            updated_at=datetime.fromisoformat(meta.get("updated_at", meta.get("created_at"))),
            rotation_enabled=meta.get("rotation_enabled", False),
            rotation_days=meta.get("rotation_days", 90),
            last_rotated=datetime.fromisoformat(meta["last_rotated"])
            if meta.get("last_rotated")
            else None,
            access_count=meta.get("access_count", 0),
        )


# =============================================================================
# Convenience functions for simple usage
# =============================================================================


class HalKeychain:
    """Simple keychain interface for Kagami (HAL).

    NOTE: Do not use this class directly. Use the unified API instead:

        from kagami.core.security import get_secret, set_secret

        # Retrieve
        value = get_secret("api_key")

        # Store
        set_secret("api_key", "secret_value")

        # List
        from kagami.core.security import list_secrets
        keys = list_secrets()
    """

    def __init__(self, service: str = "kagami"):
        self.service = service
        self._cache: dict[str, str] = {}

    def get(self, key: str, default: str | None = None) -> str | None:
        """Get secret from keychain."""
        if key in self._cache:
            return self._cache[key]

        try:
            result = subprocess.run(
                ["security", "find-generic-password", "-s", self.service, "-a", key, "-w"],
                capture_output=True,
                text=True,
                check=True,
            )
            value = result.stdout.strip()
            if value:
                self._cache[key] = value
                return value
        except subprocess.CalledProcessError:
            pass
        except FileNotFoundError:
            logger.debug("Keychain not available (not macOS)")

        return default

    def set(self, key: str, value: str) -> bool:
        """Store secret in keychain."""
        try:
            # Delete existing
            subprocess.run(
                ["security", "delete-generic-password", "-s", self.service, "-a", key],
                capture_output=True,
                check=False,
            )

            # Add new
            subprocess.run(
                [
                    "security",
                    "add-generic-password",
                    "-s",
                    self.service,
                    "-a",
                    key,
                    "-w",
                    value,
                    "-U",
                ],
                capture_output=True,
                check=True,
            )

            self._cache[key] = value
            logger.debug(f"Stored {key} in keychain")
            return True

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to store {key}: {e}")
            return False
        except FileNotFoundError:
            logger.error("Keychain not available (not macOS)")
            return False

    def delete(self, key: str) -> bool:
        """Delete secret from keychain."""
        try:
            subprocess.run(
                ["security", "delete-generic-password", "-s", self.service, "-a", key],
                capture_output=True,
                check=True,
            )
            self._cache.pop(key, None)
            return True
        except subprocess.CalledProcessError:
            return False

    def has(self, key: str) -> bool:
        """Check if key exists."""
        return self.get(key) is not None

    def list(self) -> list[str]:
        """List all stored keys."""
        # This is expensive - parse keychain dump
        try:
            result = subprocess.run(
                ["security", "dump-keychain"],
                capture_output=True,
                text=True,
                check=False,
            )

            import re

            keys = []
            in_kagami = False

            for line in result.stdout.split("\n"):
                if f'"{self.service}"' in line and "svce" in line:
                    in_kagami = True
                elif in_kagami and '"acct"' in line:
                    match = re.search(r'"acct"<blob>="([^"]+)"', line)
                    if match:
                        key = match.group(1)
                        if not key.startswith("_"):
                            keys.append(key)
                    in_kagami = False

            return keys
        except Exception:
            return []

    def clear_cache(self) -> None:
        """Clear in-memory cache."""
        self._cache.clear()


# NOTE: Global instances and setup functions removed (Dec 31, 2025)
# Use the unified API instead:
#   from kagami.core.security import get_secret, set_secret
#   value = get_secret("key")
#   set_secret("key", "value")
#
# For setup, use:
#   python -m scripts.security.setup_secrets
