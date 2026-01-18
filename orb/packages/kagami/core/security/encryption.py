"""Encryption utilities for secrets at rest.

Provides Fernet-based encryption with key derivation using PBKDF2.
Used by local encrypted backend and for general secret protection.
"""

import base64
import hashlib
import logging
import os
import secrets

logger = logging.getLogger(__name__)


class SecretEncryption:
    """Handles encryption and decryption of secrets at rest."""

    def __init__(self, master_key: bytes | None = None, salt: bytes | None = None):
        """Initialize secret encryption.

        Args:
            master_key: Optional master key (will be generated if not provided)
            salt: Optional salt for key derivation
        """
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

            self.Fernet = Fernet
            self.PBKDF2HMAC = PBKDF2HMAC
            self.hashes = hashes

        except ImportError:
            logger.error("cryptography not installed. Install with: pip install cryptography")
            raise

        self.master_key = master_key
        self.salt = salt or os.urandom(16)

        # Derive encryption key if master key provided
        if self.master_key:
            self.encryption_key = self._derive_key(self.master_key, self.salt)
            self.cipher = self.Fernet(self.encryption_key)
        else:
            self.cipher = None

    def _derive_key(self, password: bytes, salt: bytes) -> bytes:
        """Derive encryption key from password using PBKDF2.

        Args:
            password: Master password/key
            salt: Salt for key derivation

        Returns:
            Derived key suitable for Fernet
        """
        kdf = self.PBKDF2HMAC(
            algorithm=self.hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100_000,  # OWASP recommended minimum
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key

    def encrypt(self, plaintext: str) -> tuple[bytes, bytes]:
        """Encrypt plaintext secret.

        Args:
            plaintext: Secret value to encrypt

        Returns:
            Tuple of (ciphertext, salt)

        Raises:
            RuntimeError: If encryption is not initialized
        """
        if not self.cipher:
            raise RuntimeError("Encryption not initialized with master key")

        plaintext_bytes = plaintext.encode("utf-8")
        ciphertext = self.cipher.encrypt(plaintext_bytes)

        return ciphertext, self.salt

    def decrypt(self, ciphertext: bytes, salt: bytes | None = None) -> str:
        """Decrypt ciphertext secret.

        Args:
            ciphertext: Encrypted secret
            salt: Optional salt (uses instance salt if not provided)

        Returns:
            Decrypted plaintext

        Raises:
            RuntimeError: If decryption fails
        """
        if not self.cipher:
            raise RuntimeError("Encryption not initialized with master key")

        # Re-derive key if different salt provided
        if salt and salt != self.salt:
            key = self._derive_key(self.master_key, salt)
            cipher = self.Fernet(key)
        else:
            cipher = self.cipher

        try:
            plaintext_bytes = cipher.decrypt(ciphertext)
            return plaintext_bytes.decode("utf-8")
        except Exception as e:
            logger.error("Failed to decrypt secret")
            raise RuntimeError("Decryption failed - invalid key or corrupted data") from e

    def rotate_key(
        self, new_master_key: bytes, new_salt: bytes | None = None
    ) -> "SecretEncryption":
        """Create new encryption instance with rotated key.

        Args:
            new_master_key: New master key
            new_salt: Optional new salt

        Returns:
            New SecretEncryption instance with new key
        """
        return SecretEncryption(master_key=new_master_key, salt=new_salt)

    def re_encrypt(
        self, ciphertext: bytes, old_salt: bytes, new_encryption: "SecretEncryption"
    ) -> tuple[bytes, bytes]:
        """Re-encrypt data with new key.

        Args:
            ciphertext: Existing ciphertext
            old_salt: Salt used for original encryption
            new_encryption: New encryption instance

        Returns:
            Tuple of (new_ciphertext, new_salt)
        """
        # Decrypt with old key
        plaintext = self.decrypt(ciphertext, old_salt)

        # Encrypt with new key
        return new_encryption.encrypt(plaintext)


def generate_master_key() -> bytes:
    """Generate a cryptographically secure master key.

    Returns:
        Random 32-byte master key
    """
    return secrets.token_bytes(32)


def generate_secret(length: int = 32, use_symbols: bool = True) -> str:
    """Generate a cryptographically secure random secret.

    Args:
        length: Length of secret in characters
        use_symbols: Include symbols in secret

    Returns:
        Random secret string
    """
    if use_symbols:
        # Use URL-safe base64 for easy copy-paste
        return secrets.token_urlsafe(length)
    else:
        # Use hex for simpler character set[Any]
        return secrets.token_hex(length // 2)


def validate_secret_strength(secret: str, min_length: int = 16) -> tuple[bool, str | None]:
    """Validate secret strength.

    Args:
        secret: Secret to validate
        min_length: Minimum required length

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check length
    if len(secret) < min_length:
        return False, f"Secret too short (minimum {min_length} characters)"

    # Check entropy - count unique characters
    unique_chars = len(set(secret))
    if unique_chars < 8:
        return False, "Secret has low entropy (too few unique characters)"

    # Check for common weak patterns
    weak_patterns = [
        "password",
        "admin",
        "secret",
        "changeme",
        "default",
        "test",
        "demo",
        "12345",
        "qwerty",
    ]

    secret_lower = secret.lower()
    for pattern in weak_patterns:
        if pattern in secret_lower:
            return False, f"Secret contains weak pattern: {pattern}"

    # Check character variety
    has_lower = any(c.islower() for c in secret)
    has_upper = any(c.isupper() for c in secret)
    has_digit = any(c.isdigit() for c in secret)
    has_special = any(not c.isalnum() for c in secret)

    variety_count = sum([has_lower, has_upper, has_digit, has_special])
    if variety_count < 3:
        return (
            False,
            "Secret should contain at least 3 character types (lower, upper, digit, special)",
        )

    return True, None


def hash_secret(secret: str, algorithm: str = "sha256") -> str:
    """Hash a secret for storage/comparison.

    Args:
        secret: Secret to hash
        algorithm: Hash algorithm (sha256, sha512)

    Returns:
        Hex digest of hashed secret
    """
    if algorithm == "sha256":
        return hashlib.sha256(secret.encode()).hexdigest()
    elif algorithm == "sha512":
        return hashlib.sha512(secret.encode()).hexdigest()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")


def compare_secrets_constant_time(secret1: str, secret2: str) -> bool:
    """Compare two secrets in constant time to prevent timing attacks.

    Args:
        secret1: First secret
        secret2: Second secret

    Returns:
        True if secrets match
    """
    return secrets.compare_digest(secret1, secret2)


class SecretValidator:
    """Validates secrets against security policies."""

    def __init__(
        self,
        min_length: int = 16,
        require_variety: bool = True,
        check_common_patterns: bool = True,
        min_entropy_bits: int = 60,
    ):
        """Initialize secret validator.

        Args:
            min_length: Minimum secret length
            require_variety: Require character variety
            check_common_patterns: Check for common weak patterns
            min_entropy_bits: Minimum entropy in bits
        """
        self.min_length = min_length
        self.require_variety = require_variety
        self.check_common_patterns = check_common_patterns
        self.min_entropy_bits = min_entropy_bits

    def validate(self, secret: str, secret_name: str = "secret") -> tuple[bool, str | None]:  # noqa: S107
        """Validate secret against policy.

        Args:
            secret: Secret to validate
            secret_name: Name of secret (for error messages)

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Basic strength check
        is_valid, error = validate_secret_strength(secret, self.min_length)
        if not is_valid:
            return False, f"{secret_name}: {error}"

        # Entropy check
        if self.min_entropy_bits > 0:
            entropy = self._calculate_entropy(secret)
            if entropy < self.min_entropy_bits:
                return (
                    False,
                    f"{secret_name}: Insufficient entropy "
                    f"({entropy:.1f} bits, minimum {self.min_entropy_bits})",
                )

        return True, None

    def _calculate_entropy(self, secret: str) -> float:
        """Calculate Shannon entropy of secret.

        Args:
            secret: Secret to analyze

        Returns:
            Entropy in bits
        """
        import math

        if not secret:
            return 0.0

        # Count character frequencies
        freq = {}
        for char in secret:
            freq[char] = freq.get(char, 0) + 1

        # Calculate Shannon entropy per character
        entropy = 0.0
        length = len(secret)

        for count in freq.values():
            probability = count / length
            if probability > 0:
                entropy -= probability * math.log2(probability)

        # Total entropy in bits = entropy per char * length
        return entropy * length


# Global validator instance with default policy
default_validator = SecretValidator()


def validate_secret(secret: str, secret_name: str = "secret") -> None:  # noqa: S107
    """Validate secret using default policy.

    Args:
        secret: Secret to validate
        secret_name: Name of secret

    Raises:
        ValueError: If validation fails
    """
    is_valid, error = default_validator.validate(secret, secret_name)
    if not is_valid:
        raise ValueError(error)
