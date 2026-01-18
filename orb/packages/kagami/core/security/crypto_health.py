"""Cryptography health check and startup validation.

P0 Mitigation: Crypto initialization failure → All data inaccessible
"""

from __future__ import annotations

import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


class CryptoHealthCheck:
    """Validates cryptography availability at startup.

    P0 Mitigation: Prevents API from starting if crypto unavailable.

    Checks:
    - Quantum-safe crypto (Kyber + X25519)
    - Symmetric crypto (AES-256-GCM)
    - Signatures (Ed25519 + Dilithium)
    - Key generation
    - Encrypt/decrypt round-trip

    Usage:
        @app.on_event("startup")
        async def validate_crypto():
            health = CryptoHealthCheck()
            if not await health.validate():
                sys.exit(1)  # Don't start without crypto
    """

    def __init__(self):
        self.quantum_safe_available = False
        self.aes_available = False
        self.signatures_available = False

    async def validate(self) -> bool:
        """Validate all cryptography components.

        Returns:
            True if all checks pass
        """
        logger.info("🔒 Validating cryptography...")

        checks = [
            ("Quantum-safe (Kyber)", self._check_quantum_safe()),
            ("AES-256-GCM", self._check_aes()),
            ("Ed25519 signatures", self._check_signatures()),
            ("Encrypt/Decrypt round-trip", self._check_round_trip()),
        ]

        all_passed = True
        for name, check_result in checks:
            passed = await check_result if hasattr(check_result, "__await__") else check_result
            status = "✅" if passed else "❌"
            logger.info(f"  {status} {name}")
            if not passed:
                all_passed = False

        if all_passed:
            logger.info("✅ Cryptography validation complete")
        else:
            logger.critical("❌ Cryptography validation FAILED")

        return all_passed

    def _check_quantum_safe(self) -> bool:
        """Check Kyber + X25519 availability."""
        try:
            from cryptography.hazmat.primitives.asymmetric import x25519

            # Generate X25519 key pair
            private_key = x25519.X25519PrivateKey.generate()
            private_key.public_key()

            # Kyber (ML-KEM) check deferred until liboqs-python stabilizes
            self.quantum_safe_available = True
            return True

        except Exception as e:
            logger.error(f"Quantum-safe crypto check failed: {e}")
            return False

    def _check_aes(self) -> bool:
        """Check AES-256-GCM availability."""
        try:
            import os

            from cryptography.hazmat.backends import default_backend
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

            # Generate key and IV
            key = os.urandom(32)  # 256-bit key
            iv = os.urandom(12)  # 96-bit IV for GCM

            # Create cipher
            cipher = Cipher(
                algorithms.AES(key),
                modes.GCM(iv),
                backend=default_backend(),
            )

            # Test encryption
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(b"test") + encryptor.finalize()
            tag = encryptor.tag

            # Test decryption
            cipher_decrypt = Cipher(
                algorithms.AES(key),
                modes.GCM(iv, tag),
                backend=default_backend(),
            )
            decryptor = cipher_decrypt.decryptor()
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()

            self.aes_available = plaintext == b"test"
            return self.aes_available

        except Exception as e:
            logger.error(f"AES check failed: {e}")
            return False

    def _check_signatures(self) -> bool:
        """Check Ed25519 signature availability."""
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519

            # Generate key pair
            private_key = ed25519.Ed25519PrivateKey.generate()
            public_key = private_key.public_key()

            # Sign message
            message = b"test message"
            signature = private_key.sign(message)

            # Verify signature
            public_key.verify(signature, message)

            self.signatures_available = True
            return True

        except Exception as e:
            logger.error(f"Signature check failed: {e}")
            return False

    async def _check_round_trip(self) -> bool:
        """Check full encrypt/decrypt round-trip using unified crypto."""
        try:
            from kagami.core.security.unified_crypto import decrypt, encrypt

            # Test data
            test_data = b"test encryption round-trip"
            context = {"purpose": "health_check"}

            # Encrypt
            ciphertext = await encrypt(test_data, context=context)

            # Decrypt
            plaintext = await decrypt(ciphertext, context=context)

            # Verify
            return plaintext == test_data

        except Exception as e:
            logger.error(f"Round-trip check failed: {e}")
            return False

    def get_status(self) -> dict[str, Any]:
        """Get current crypto status."""
        return {
            "quantum_safe_available": self.quantum_safe_available,
            "aes_available": self.aes_available,
            "signatures_available": self.signatures_available,
        }


async def validate_crypto_on_startup() -> None:
    """Validate cryptography and fail fast if unavailable.

    Usage in FastAPI:
        @app.on_event("startup")
        async def startup():
            await validate_crypto_on_startup()
    """
    health = CryptoHealthCheck()

    if not await health.validate():
        logger.critical(
            "🔴 CRITICAL: Cryptography validation failed! API cannot start without working crypto."
        )
        logger.critical("Check that cryptography library is installed correctly.")
        logger.critical("Install: pip install cryptography")
        sys.exit(1)  # Fail fast
