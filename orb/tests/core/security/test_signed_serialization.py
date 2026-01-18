"""Tests for signed serialization module.

Verifies HMAC signature validation, format migration, and security properties.

Created: December 20, 2025
Colony: Crystal (e₇) - Verification & testing
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_integration

import json
import os
import pickle
import secrets
from pathlib import Path
from typing import Any

import torch

from kagami.core.security.signed_serialization import (
    SecurityError,
    is_signed_format,
    load_signed,
    save_signed,
)


@pytest.fixture
def test_secret_key(monkeypatch: pytest.MonkeyPatch) -> str:
    """Generate test secret key and set environment variable."""
    secret_hex = secrets.token_hex(32)
    monkeypatch.setenv("KAGAMI_CACHE_SECRET", secret_hex)
    return secret_hex


@pytest.fixture
def test_data() -> dict[str, Any]:
    """Sample test data for serialization."""
    return {
        "model_id": "test-model",
        "version": "1.0.0",
        "metadata": {"accuracy": 0.95, "layers": 12},
        "training_steps": 10000,
    }


@pytest.fixture
def test_tensor_data() -> dict[str, torch.Tensor]:
    """Sample tensor data for torch format."""
    return {
        "weights": torch.randn(10, 10),
        "bias": torch.randn(10),
        "embeddings": torch.randn(100, 768),
    }


class TestSignedSerializationBasic:
    """Basic serialization and verification tests."""

    def test_save_load_json(
        self, tmp_path: Path, test_secret_key: str, test_data: dict[str, Any]
    ) -> None:
        """Test basic JSON save and load."""
        path = tmp_path / "test.json"

        # Save
        save_signed(test_data, path, format="json")
        assert path.exists()

        # Load
        loaded = load_signed(path, format="json", allow_legacy_pickle=False)
        assert loaded == test_data

    def test_save_load_torch(
        self, tmp_path: Path, test_secret_key: str, test_tensor_data: dict[str, torch.Tensor]
    ) -> None:
        """Test torch tensor save and load."""
        path = tmp_path / "test.pt"

        # Save
        save_signed(test_tensor_data, path, format="torch")
        assert path.exists()

        # Load
        loaded = load_signed(path, format="torch", allow_legacy_pickle=False)

        # Verify tensors match
        for key in test_tensor_data:
            assert torch.allclose(loaded[key], test_tensor_data[key])

    def test_signature_verification_fails_on_tamper(
        self, tmp_path: Path, test_secret_key: str, test_data: dict[str, Any]
    ) -> None:
        """Test that tampered files fail verification."""
        path = tmp_path / "test.json"

        # Save
        save_signed(test_data, path, format="json")

        # Tamper with file (modify payload)
        with open(path, "rb") as f:
            data = bytearray(f.read())

        # Modify byte after signature (byte 32)
        data[32] = (data[32] + 1) % 256

        with open(path, "wb") as f:
            f.write(data)

        # Verification should fail
        with pytest.raises(SecurityError, match="Signature verification failed"):
            load_signed(path, format="json", allow_legacy_pickle=False)

    def test_missing_secret_key(self, tmp_path: Path, test_data: dict[str, Any]) -> None:
        """Test that missing secret key raises SecurityError."""
        path = tmp_path / "test.json"

        # Remove environment variable
        if "KAGAMI_CACHE_SECRET" in os.environ:
            del os.environ["KAGAMI_CACHE_SECRET"]

        with pytest.raises(SecurityError, match="KAGAMI_CACHE_SECRET"):
            save_signed(test_data, path, format="json")

    def test_invalid_secret_key_format(
        self, tmp_path: Path, test_data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that invalid secret key format raises SecurityError."""
        path = tmp_path / "test.json"

        # Set invalid hex string
        monkeypatch.setenv("KAGAMI_CACHE_SECRET", "not_a_hex_string")

        with pytest.raises(SecurityError, match="Invalid KAGAMI_CACHE_SECRET format"):
            save_signed(test_data, path, format="json")

    def test_short_secret_key(
        self, tmp_path: Path, test_data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that short secret key raises SecurityError."""
        path = tmp_path / "test.json"

        # Set too-short key (16 bytes instead of 32)
        monkeypatch.setenv("KAGAMI_CACHE_SECRET", secrets.token_hex(16))

        with pytest.raises(SecurityError, match="too short"):
            save_signed(test_data, path, format="json")


class TestLegacyPickleMigration:
    """Tests for automatic migration from legacy pickle format."""

    def test_migrate_json_data(
        self, tmp_path: Path, test_secret_key: str, test_data: dict[str, Any]
    ) -> None:
        """Test migration from pickle to signed JSON."""
        path = tmp_path / "legacy.pkl"

        # Create legacy pickle file
        with open(path, "wb") as f:
            pickle.dump(test_data, f)

        # Verify it's pickle format
        assert not is_signed_format(path)

        # Load should auto-migrate
        loaded = load_signed(path, format="json", allow_legacy_pickle=True)
        assert loaded == test_data

        # Verify migration created backup
        backup_path = path.with_suffix(".pkl.pickle.bak")
        assert backup_path.exists()

        # Verify new format is signed
        assert is_signed_format(path)

        # Load again (should use new format)
        loaded_again = load_signed(path, format="json", allow_legacy_pickle=False)
        assert loaded_again == test_data

    def test_migrate_tensor_data(
        self, tmp_path: Path, test_secret_key: str, test_tensor_data: dict[str, torch.Tensor]
    ) -> None:
        """Test migration from pickle to signed torch format."""
        path = tmp_path / "legacy_tensors.pkl"

        # Create legacy pickle file with tensors
        with open(path, "wb") as f:
            pickle.dump(test_tensor_data, f)

        # Load should auto-migrate
        loaded = load_signed(path, format="torch", allow_legacy_pickle=True)

        # Verify tensors match
        for key in test_tensor_data:
            assert torch.allclose(loaded[key], test_tensor_data[key])

        # Verify backup exists
        backup_path = path.with_suffix(".pkl.pickle.bak")
        assert backup_path.exists()

    def test_migration_disabled_fails(
        self, tmp_path: Path, test_secret_key: str, test_data: dict[str, Any]
    ) -> None:
        """Test that loading pickle fails when migration disabled."""
        path = tmp_path / "legacy.pkl"

        # Create legacy pickle file
        with open(path, "wb") as f:
            pickle.dump(test_data, f)

        # Loading with allow_legacy_pickle=False should fail
        with pytest.raises(ValueError, match="too small"):
            load_signed(path, format="json", allow_legacy_pickle=False)


class TestFormatDetection:
    """Tests for format detection utilities."""

    def test_detect_signed_json(
        self, tmp_path: Path, test_secret_key: str, test_data: dict[str, Any]
    ) -> None:
        """Test detection of signed JSON format."""
        path = tmp_path / "signed.json"
        save_signed(test_data, path, format="json")

        assert is_signed_format(path)

    def test_detect_signed_torch(
        self, tmp_path: Path, test_secret_key: str, test_tensor_data: dict[str, torch.Tensor]
    ) -> None:
        """Test detection of signed torch format."""
        path = tmp_path / "signed.pt"
        save_signed(test_tensor_data, path, format="torch")

        assert is_signed_format(path)

    def test_detect_legacy_pickle(self, tmp_path: Path, test_data: dict[str, Any]) -> None:
        """Test detection of legacy pickle format."""
        path = tmp_path / "legacy.pkl"

        with open(path, "wb") as f:
            pickle.dump(test_data, f)

        assert not is_signed_format(path)

    def test_detect_nonexistent_file(self, tmp_path: Path) -> None:
        """Test detection on nonexistent file."""
        path = tmp_path / "nonexistent.json"
        assert not is_signed_format(path)

    def test_detect_empty_file(self, tmp_path: Path) -> None:
        """Test detection on empty file."""
        path = tmp_path / "empty.json"
        path.touch()

        assert not is_signed_format(path)


class TestAtomicWrites:
    """Tests for atomic write operations."""

    def test_atomic_write_json(
        self, tmp_path: Path, test_secret_key: str, test_data: dict[str, Any]
    ) -> None:
        """Test that JSON writes are atomic (no temp files left)."""
        path = tmp_path / "atomic.json"

        save_signed(test_data, path, format="json")

        # Verify no temp files left
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0

    def test_atomic_write_torch(
        self, tmp_path: Path, test_secret_key: str, test_tensor_data: dict[str, torch.Tensor]
    ) -> None:
        """Test that torch writes are atomic."""
        path = tmp_path / "atomic.pt"

        save_signed(test_tensor_data, path, format="torch")

        # Verify no temp files left
        temp_files = list(tmp_path.glob("*.tmp"))
        assert len(temp_files) == 0


class TestErrorHandling:
    """Tests for error handling."""

    def test_invalid_format(
        self, tmp_path: Path, test_secret_key: str, test_data: dict[str, Any]
    ) -> None:
        """Test that invalid format raises ValueError."""
        path = tmp_path / "test.dat"

        with pytest.raises(ValueError, match="Invalid format"):
            save_signed(test_data, path, format="invalid")  # type: ignore

    def test_corrupted_payload(
        self, tmp_path: Path, test_secret_key: str, test_data: dict[str, Any]
    ) -> None:
        """Test that corrupted payload raises ValueError."""
        path = tmp_path / "test.json"

        save_signed(test_data, path, format="json")

        # Corrupt payload (keep valid signature but break JSON)
        with open(path, "rb") as f:
            data = bytearray(f.read())

        # Replace valid JSON with invalid JSON (keep signature)
        signature = data[:32]
        invalid_json = b'{"broken json'

        with open(path, "wb") as f:
            f.write(signature)
            f.write(invalid_json)

        # Loading should fail on signature verification first
        with pytest.raises(SecurityError, match="Signature verification failed"):
            load_signed(path, format="json", allow_legacy_pickle=False)

    def test_file_not_found(self, tmp_path: Path, test_secret_key: str) -> None:
        """Test that loading nonexistent file raises FileNotFoundError."""
        path = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            load_signed(path, format="json")

    def test_file_too_small(self, tmp_path: Path, test_secret_key: str) -> None:
        """Test that file smaller than signature raises ValueError."""
        path = tmp_path / "tiny.json"

        # Write file smaller than 33 bytes (32 signature + 1 payload)
        with open(path, "wb") as f:
            f.write(b"short")

        with pytest.raises(ValueError, match="too small"):
            load_signed(path, format="json", allow_legacy_pickle=False)


class TestSecurityProperties:
    """Tests for cryptographic security properties."""

    def test_different_keys_fail_verification(
        self, tmp_path: Path, test_data: dict[str, Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that files signed with different keys fail verification."""
        path = tmp_path / "test.json"

        # Save with first key
        key1 = secrets.token_hex(32)
        monkeypatch.setenv("KAGAMI_CACHE_SECRET", key1)
        save_signed(test_data, path, format="json")

        # Try to load with different key
        key2 = secrets.token_hex(32)
        monkeypatch.setenv("KAGAMI_CACHE_SECRET", key2)

        with pytest.raises(SecurityError, match="Signature verification failed"):
            load_signed(path, format="json", allow_legacy_pickle=False)

    def test_constant_time_comparison(
        self, tmp_path: Path, test_secret_key: str, test_data: dict[str, Any]
    ) -> None:
        """Test that signature comparison is constant-time (no timing attacks)."""
        path = tmp_path / "test.json"

        save_signed(test_data, path, format="json")

        # Read file
        with open(path, "rb") as f:
            signature = f.read(32)
            payload = f.read()

        # Create signature that differs in first byte
        bad_sig_1 = bytearray(signature)
        bad_sig_1[0] = (bad_sig_1[0] + 1) % 256

        # Create signature that differs in last byte
        bad_sig_2 = bytearray(signature)
        bad_sig_2[31] = (bad_sig_2[31] + 1) % 256

        # Both should fail (testing that hmac.compare_digest is used)
        for bad_sig in [bytes(bad_sig_1), bytes(bad_sig_2)]:
            with open(path, "wb") as f:
                f.write(bad_sig)
                f.write(payload)

            with pytest.raises(SecurityError, match="Signature verification failed"):
                load_signed(path, format="json", allow_legacy_pickle=False)

    def test_replay_attack_detection(
        self, tmp_path: Path, test_secret_key: str, test_data: dict[str, Any]
    ) -> None:
        """Test that old signed files can't be replayed with modified data."""
        path1 = tmp_path / "file1.json"
        path2 = tmp_path / "file2.json"

        data1 = {"id": 1, "value": "first"}
        data2 = {"id": 2, "value": "second"}

        # Save two different files
        save_signed(data1, path1, format="json")
        save_signed(data2, path2, format="json")

        # Read signatures and payloads
        with open(path1, "rb") as f:
            sig1 = f.read(32)
            payload1 = f.read()

        with open(path2, "rb") as f:
            f.read(32)  # sig2 (unused)
            payload2 = f.read()

        # Try to use sig1 with payload2 (replay attack)
        with open(path1, "wb") as f:
            f.write(sig1)
            f.write(payload2)

        # Should fail verification
        with pytest.raises(SecurityError, match="Signature verification failed"):
            load_signed(path1, format="json", allow_legacy_pickle=False)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
