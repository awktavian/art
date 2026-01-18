"""Local encrypted backend implementation.

Stores secrets in an encrypted local file. Suitable for development
and testing, NOT for production use.

Secrets are encrypted using Fernet (AES-128 in CBC mode with HMAC).
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

from kagami.core.security.encryption import SecretEncryption, generate_master_key
from kagami.core.security.secrets_manager import (
    SecretBackend,
    SecretBackendType,
    SecretMetadata,
    SecretVersion,
)

logger = logging.getLogger(__name__)


class LocalEncryptedBackend(SecretBackend):
    """Local encrypted file backend (development only)."""

    def __init__(self, config: dict[str, Any]):
        """Initialize local encrypted backend.

        Args:
            config: Configuration dict[str, Any] with keys:
                - storage_path: Path to secrets file
                - master_key_path: Path to master key file
                - auto_generate_key: Auto-generate key if missing (default: True)
        """
        super().__init__(config)

        # Get or create storage directory
        storage_path = config.get(
            "storage_path",
            str(Path.home() / ".kagami" / "secrets" / "secrets.enc"),
        )
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

        # Get or create master key
        master_key_path = config.get(
            "master_key_path",
            str(Path.home() / ".kagami" / "secrets" / "master.key"),
        )
        self.master_key_path = Path(master_key_path)
        self.auto_generate_key = config.get("auto_generate_key", True)

        # Load or generate master key
        self._load_or_generate_master_key()

        # Initialize encryption
        self.encryption = SecretEncryption(master_key=self.master_key)

        # Load secrets from disk
        self._secrets_data: dict[str, Any] = {}
        self._file_lock = RLock()  # Use RLock to allow re-entry from set_secret -> _save_secrets
        self._load_secrets()

        logger.warning(
            "LocalEncryptedBackend initialized - FOR DEVELOPMENT ONLY, NOT FOR PRODUCTION"
        )
        logger.info(f"Secrets storage: {self.storage_path}")
        logger.info(f"Master key: {self.master_key_path}")

    def _load_or_generate_master_key(self) -> None:
        """Load existing master key or generate a new one."""
        if self.master_key_path.exists():
            # Load existing key
            with open(self.master_key_path, "rb") as f:
                self.master_key = f.read()
            logger.info("Loaded existing master key")

        elif self.auto_generate_key:
            # Generate new key
            self.master_key = generate_master_key()

            # Save key to file with restricted permissions
            self.master_key_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.master_key_path, "wb") as f:
                f.write(self.master_key)

            # Set restrictive permissions (owner read/write only)
            os.chmod(self.master_key_path, 0o600)

            logger.warning(f"Generated new master key at {self.master_key_path}")
            logger.warning("KEEP THIS KEY SECURE - Cannot decrypt secrets without it")

        else:
            raise RuntimeError(
                f"Master key not found at {self.master_key_path} and auto_generate_key is disabled"
            )

    def _load_secrets(self) -> None:
        """Load secrets from encrypted file."""
        with self._file_lock:
            if not self.storage_path.exists():
                self._secrets_data = {}
                return

            try:
                # Read encrypted file
                with open(self.storage_path, "rb") as f:
                    encrypted_data = f.read()

                if not encrypted_data:
                    self._secrets_data = {}
                    return

                # Split salt and ciphertext (first 16 bytes is salt)
                salt = encrypted_data[:16]
                ciphertext = encrypted_data[16:]

                # Decrypt
                decrypted = self.encryption.decrypt(ciphertext, salt)

                # Parse JSON
                self._secrets_data = json.loads(decrypted)

                logger.info(f"Loaded {len(self._secrets_data)} secrets from disk")

            except Exception as e:
                logger.error(f"Failed to load secrets file: {e}")
                # Start with empty secrets (don't fail)
                self._secrets_data = {}

    def _save_secrets(self) -> None:
        """Save secrets to encrypted file."""
        with self._file_lock:
            try:
                # Serialize to JSON
                json_data = json.dumps(self._secrets_data, indent=2)

                # Encrypt
                ciphertext, salt = self.encryption.encrypt(json_data)

                # Write to file (salt + ciphertext)
                with open(self.storage_path, "wb") as f:
                    f.write(salt + ciphertext)

                # Set restrictive permissions
                os.chmod(self.storage_path, 0o600)

                logger.debug(f"Saved {len(self._secrets_data)} secrets to disk")

            except Exception as e:
                logger.error(f"Failed to save secrets file: {e}")
                raise

    async def get_secret(self, name: str, version: str | None = None) -> str | None:
        """Get secret from local storage.

        Args:
            name: Secret name
            version: Optional version ID

        Returns:
            Secret value or None if not found
        """
        with self._file_lock:
            if name not in self._secrets_data:
                return None

            secret_entry = self._secrets_data[name]

            if version:
                # Get specific version
                versions = secret_entry.get("versions", [])
                for v in versions:
                    if v["version_id"] == version:
                        return v["value"]
                return None
            else:
                # Get current version
                return secret_entry.get("current_value")

    async def set_secret(
        self,
        name: str,
        value: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Set secret in local storage.

        Args:
            name: Secret name
            value: Secret value
            metadata: Optional metadata

        Returns:
            Version ID of created secret
        """
        with self._file_lock:
            now = datetime.utcnow()

            if name not in self._secrets_data:
                # Create new secret
                self._secrets_data[name] = {
                    "name": name,
                    "current_value": value,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "metadata": metadata or {},
                    "versions": [],
                    "version_counter": 1,
                }
                version_id = "1"

            else:
                # Update existing secret
                secret_entry = self._secrets_data[name]

                # Archive current version
                current_value = secret_entry.get("current_value")
                if current_value:
                    secret_entry["versions"].append(
                        {
                            "version_id": str(secret_entry["version_counter"]),
                            "value": current_value,
                            "created_at": secret_entry.get("updated_at", now.isoformat()),
                        }
                    )

                # Set new version
                secret_entry["version_counter"] += 1
                secret_entry["current_value"] = value
                secret_entry["updated_at"] = now.isoformat()

                if metadata:
                    secret_entry["metadata"].update(metadata)

                version_id = str(secret_entry["version_counter"])

            # Save to disk
            self._save_secrets()

            return version_id

    async def delete_secret(self, name: str) -> bool:
        """Delete secret from local storage.

        Args:
            name: Secret name

        Returns:
            True if deleted successfully
        """
        with self._file_lock:
            if name in self._secrets_data:
                del self._secrets_data[name]
                self._save_secrets()
                return True
            return False

    async def list_secrets(self) -> list[str]:
        """List all secret names.

        Returns:
            List of secret names
        """
        with self._file_lock:
            return list(self._secrets_data.keys())

    async def get_secret_versions(self, name: str) -> list[SecretVersion]:
        """Get all versions of a secret.

        Args:
            name: Secret name

        Returns:
            List of secret versions
        """
        with self._file_lock:
            if name not in self._secrets_data:
                return []

            secret_entry = self._secrets_data[name]
            versions = []

            # Add historical versions
            for v in secret_entry.get("versions", []):
                versions.append(
                    SecretVersion(
                        version_id=v["version_id"],
                        value=v["value"],
                        created_at=datetime.fromisoformat(v["created_at"]),
                        created_by="local",
                        is_active=False,
                    )
                )

            # Add current version
            versions.append(
                SecretVersion(
                    version_id=str(secret_entry.get("version_counter", 1)),
                    value=secret_entry.get("current_value", ""),
                    created_at=datetime.fromisoformat(
                        secret_entry.get("updated_at", datetime.utcnow().isoformat())
                    ),
                    created_by="local",
                    is_active=True,
                )
            )

            return sorted(versions, key=lambda v: int(v.version_id), reverse=True)

    async def get_secret_metadata(self, name: str) -> SecretMetadata | None:
        """Get secret metadata.

        Args:
            name: Secret name

        Returns:
            Secret metadata or None if not found
        """
        with self._file_lock:
            if name not in self._secrets_data:
                return None

            secret_entry = self._secrets_data[name]
            meta = secret_entry.get("metadata", {})

            metadata = SecretMetadata(
                name=name,
                backend=SecretBackendType.LOCAL_ENCRYPTED,
                created_at=datetime.fromisoformat(
                    secret_entry.get("created_at", datetime.utcnow().isoformat())
                ),
                updated_at=datetime.fromisoformat(
                    secret_entry.get("updated_at", datetime.utcnow().isoformat())
                ),
                rotation_enabled=meta.get("rotation_enabled", False),
                rotation_days=meta.get("rotation_days", 90),
                tags=meta,
            )

            return metadata

    def export_secrets(self, output_path: str, include_versions: bool = False) -> None:
        """Export secrets to JSON file (unencrypted - use carefully).

        Args:
            output_path: Path to output file
            include_versions: Include version history

        Warning:
            This exports secrets in plaintext. Use only for backups in secure locations.
        """
        with self._file_lock:
            export_data = {}

            for name, entry in self._secrets_data.items():
                export_entry = {
                    "name": name,
                    "value": entry.get("current_value"),
                    "created_at": entry.get("created_at"),
                    "updated_at": entry.get("updated_at"),
                    "metadata": entry.get("metadata", {}),
                }

                if include_versions:
                    export_entry["versions"] = entry.get("versions", [])

                export_data[name] = export_entry

            # Write to file
            output_path_obj = Path(output_path)
            output_path_obj.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path_obj, "w") as f:
                json.dump(export_data, f, indent=2)

            # Set restrictive permissions
            os.chmod(output_path_obj, 0o600)

            logger.warning(
                f"Exported {len(export_data)} secrets to {output_path} (PLAINTEXT - keep secure)"
            )

    def import_secrets(self, input_path: str, overwrite: bool = False) -> int:
        """Import secrets from JSON file.

        Args:
            input_path: Path to input file
            overwrite: Overwrite existing secrets

        Returns:
            Number of secrets imported
        """
        with self._file_lock:
            with open(input_path) as f:
                import_data = json.load(f)

            imported_count = 0

            for name, entry in import_data.items():
                if name in self._secrets_data and not overwrite:
                    logger.warning(f"Skipping existing secret: {name}")
                    continue

                self._secrets_data[name] = {
                    "name": name,
                    "current_value": entry.get("value"),
                    "created_at": entry.get("created_at", datetime.utcnow().isoformat()),
                    "updated_at": entry.get("updated_at", datetime.utcnow().isoformat()),
                    "metadata": entry.get("metadata", {}),
                    "versions": entry.get("versions", []),
                    "version_counter": len(entry.get("versions", [])) + 1,
                }

                imported_count += 1

            # Save to disk
            self._save_secrets()

            logger.info(f"Imported {imported_count} secrets from {input_path}")
            return imported_count
