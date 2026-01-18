"""Tests for encryption utilities."""

import pytest

from kagami.core.security.encryption import (
    SecretEncryption,
    SecretValidator,
    compare_secrets_constant_time,
    generate_master_key,
    generate_secret,
    hash_secret,
    validate_secret_strength,
)


class TestSecretEncryption:
    """Test secret encryption."""

    def test_encrypt_decrypt(self):
        """Test basic encryption and decryption."""
        master_key = generate_master_key()
        encryption = SecretEncryption(master_key=master_key)

        plaintext = "my_secret_value_12345"
        ciphertext, salt = encryption.encrypt(plaintext)

        # Decrypt
        decrypted = encryption.decrypt(ciphertext, salt)

        assert decrypted == plaintext

    def test_different_salts(self):
        """Test encryption with different salts."""
        master_key = generate_master_key()
        encryption1 = SecretEncryption(master_key=master_key)
        encryption2 = SecretEncryption(master_key=master_key)

        plaintext = "test_secret_123456"

        # Encrypt with both instances
        ciphertext1, salt1 = encryption1.encrypt(plaintext)
        ciphertext2, salt2 = encryption2.encrypt(plaintext)

        # Different salts should produce different ciphertexts
        assert ciphertext1 != ciphertext2
        assert salt1 != salt2

        # But both should decrypt correctly
        assert encryption1.decrypt(ciphertext1, salt1) == plaintext
        assert encryption2.decrypt(ciphertext2, salt2) == plaintext

    def test_wrong_key(self):
        """Test decryption with wrong key fails."""
        master_key1 = generate_master_key()
        master_key2 = generate_master_key()

        encryption1 = SecretEncryption(master_key=master_key1)
        encryption2 = SecretEncryption(master_key=master_key2)

        plaintext = "secret_value_12345"
        ciphertext, salt = encryption1.encrypt(plaintext)

        # Try to decrypt with wrong key
        with pytest.raises(RuntimeError, match="Decryption failed"):
            encryption2.decrypt(ciphertext, salt)

    def test_key_rotation(self):
        """Test key rotation."""
        old_key = generate_master_key()
        new_key = generate_master_key()

        old_encryption = SecretEncryption(master_key=old_key)
        new_encryption = old_encryption.rotate_key(new_key)

        plaintext = "test_rotation_12345"

        # Encrypt with old key
        old_ciphertext, old_salt = old_encryption.encrypt(plaintext)

        # Re-encrypt with new key
        new_ciphertext, new_salt = old_encryption.re_encrypt(
            old_ciphertext, old_salt, new_encryption
        )

        # Should decrypt with new key
        decrypted = new_encryption.decrypt(new_ciphertext, new_salt)
        assert decrypted == plaintext


class TestSecretGeneration:
    """Test secret generation."""

    def test_generate_secret(self):
        """Test generating secrets."""
        secret = generate_secret(length=32, use_symbols=True)

        assert len(secret) >= 32
        assert isinstance(secret, str)

    def test_generate_secret_without_symbols(self):
        """Test generating secrets without symbols."""
        secret = generate_secret(length=32, use_symbols=False)

        assert len(secret) >= 16  # Hex is shorter
        assert isinstance(secret, str)
        # Should only contain hex characters
        assert all(c in "0123456789abcdef" for c in secret)

    def test_secrets_are_unique(self):
        """Test that generated secrets are unique."""
        secrets = [generate_secret() for _ in range(100)]

        # All should be unique
        assert len(set(secrets)) == 100


class TestSecretValidation:
    """Test secret validation."""

    def test_valid_secret(self):
        """Test validating a strong secret."""
        secret = "Str0ng!P@ssw0rd#With$Many%Ch@rs"

        is_valid, error = validate_secret_strength(secret)

        assert is_valid is True
        assert error is None

    def test_too_short(self):
        """Test validation fails for short secrets."""
        secret = "short"

        is_valid, error = validate_secret_strength(secret, min_length=16)

        assert is_valid is False
        assert "too short" in error.lower()

    def test_low_entropy(self):
        """Test validation fails for low entropy."""
        secret = "aaaaaaaaaaaaaaaa"

        is_valid, error = validate_secret_strength(secret)

        assert is_valid is False
        assert "entropy" in error.lower()

    def test_weak_pattern(self):
        """Test validation fails for weak patterns."""
        secret = "my_password_is_password"

        is_valid, error = validate_secret_strength(secret)

        assert is_valid is False
        assert "weak pattern" in error.lower()

    def test_insufficient_variety(self):
        """Test validation fails for insufficient character variety."""
        secret = "alllowercaseletters"

        is_valid, error = validate_secret_strength(secret)

        assert is_valid is False
        assert "character types" in error.lower()


class TestSecretValidator:
    """Test secret validator."""

    def test_default_policy(self):
        """Test validation with default policy."""
        validator = SecretValidator()

        # Strong secret should pass
        is_valid, error = validator.validate("Str0ng!P@ss#12345678", "test_secret")
        assert is_valid is True

        # Weak secret should fail
        is_valid, error = validator.validate("weak", "test_secret")
        assert is_valid is False

    def test_custom_policy(self):
        """Test validation with custom policy."""
        validator = SecretValidator(
            min_length=32,
            min_entropy_bits=100,
        )

        # Even moderately strong secret should fail with strict policy
        is_valid, error = validator.validate("Str0ng!P@ss#12345", "test_secret")
        assert is_valid is False
        assert "entropy" in error.lower()

    def test_entropy_calculation(self):
        """Test entropy calculation."""
        validator = SecretValidator()

        # All same characters = low entropy
        low_entropy = validator._calculate_entropy("aaaaaaaaaaaaaaaa")

        # Random characters = high entropy
        high_entropy = validator._calculate_entropy("Kj9$mP#zQ2!xR@8v")

        assert high_entropy > low_entropy


class TestSecretHashing:
    """Test secret hashing."""

    def test_hash_secret_sha256(self):
        """Test hashing with SHA-256."""
        secret = "my_secret_value"
        hash1 = hash_secret(secret, algorithm="sha256")
        hash2 = hash_secret(secret, algorithm="sha256")

        # Same input should produce same hash
        assert hash1 == hash2

        # Hash should be hex string
        assert all(c in "0123456789abcdef" for c in hash1)

        # SHA-256 produces 64 character hex
        assert len(hash1) == 64

    def test_hash_secret_sha512(self):
        """Test hashing with SHA-512."""
        secret = "my_secret_value"
        hash1 = hash_secret(secret, algorithm="sha512")

        # SHA-512 produces 128 character hex
        assert len(hash1) == 128

    def test_different_inputs_different_hashes(self):
        """Test different inputs produce different hashes."""
        hash1 = hash_secret("secret1")
        hash2 = hash_secret("secret2")

        assert hash1 != hash2


class TestConstantTimeComparison:
    """Test constant-time secret comparison."""

    def test_equal_secrets(self):
        """Test comparing equal secrets."""
        secret1 = "my_secret_value"
        secret2 = "my_secret_value"

        assert compare_secrets_constant_time(secret1, secret2) is True

    def test_different_secrets(self):
        """Test comparing different secrets."""
        secret1 = "my_secret_value"
        secret2 = "different_value"

        assert compare_secrets_constant_time(secret1, secret2) is False

    def test_similar_secrets(self):
        """Test comparing similar secrets."""
        secret1 = "my_secret_value"
        secret2 = "my_secret_valu"  # Missing one character

        assert compare_secrets_constant_time(secret1, secret2) is False
