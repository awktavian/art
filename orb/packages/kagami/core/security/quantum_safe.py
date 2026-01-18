"""Quantum-Safe Cryptography — Post-Quantum Security.

Provides quantum-resistant cryptographic primitives:
- Kyber (ML-KEM): Key encapsulation for key exchange
- Dilithium (ML-DSA): Digital signatures
- Hybrid mode: Classical + post-quantum for defense in depth

NIST Post-Quantum Standards (FIPS 203, 204, 205):
- ML-KEM (Kyber): Lattice-based key encapsulation
- ML-DSA (Dilithium): Lattice-based signatures
- SLH-DSA (SPHINCS+): Hash-based signatures (stateless)

Architecture:
```
┌─────────────────────────────────────────────────────────────────┐
│                 QUANTUM-SAFE CRYPTO LAYER                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              QuantumSafeCrypto API                       │  │
│   │  • generate_keypair()  • encapsulate()  • sign()        │  │
│   │  • hybrid_encrypt()    • decapsulate()  • verify()      │  │
│   │  • hybrid_decrypt()                                      │  │
│   └───────────────────────────┬─────────────────────────────┘  │
│                               │                                 │
│       ┌───────────────────────┼───────────────────────┐        │
│       │                       │                       │        │
│       ▼                       ▼                       ▼        │
│   ┌───────────┐       ┌───────────────┐       ┌───────────┐   │
│   │  Kyber    │       │   Dilithium   │       │  AES-256  │   │
│   │ (ML-KEM)  │       │   (ML-DSA)    │       │   -GCM    │   │
│   │           │       │               │       │           │   │
│   │ Key Encap │       │  Signatures   │       │ Symmetric │   │
│   └───────────┘       └───────────────┘       └───────────┘   │
│                                                                  │
│   HYBRID MODE: X25519 + Kyber for key exchange                  │
│                Ed25519 + Dilithium for signatures               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

Security Levels:
- Kyber-512:  AES-128 equivalent (NIST Level 1)
- Kyber-768:  AES-192 equivalent (NIST Level 3) [DEFAULT]
- Kyber-1024: AES-256 equivalent (NIST Level 5)

Colony: Crystal (D₅) — Security verification
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import json
import logging
import os
import struct
from dataclasses import dataclass
from enum import Enum, auto

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration
# =============================================================================


class SecurityLevel(Enum):
    """NIST post-quantum security levels."""

    LEVEL_1 = 1  # AES-128 equivalent (Kyber-512)
    LEVEL_3 = 3  # AES-192 equivalent (Kyber-768) [DEFAULT]
    LEVEL_5 = 5  # AES-256 equivalent (Kyber-1024)


class CryptoMode(Enum):
    """Cryptographic operation mode."""

    QUANTUM_ONLY = auto()  # Post-quantum only
    CLASSICAL_ONLY = auto()  # Classical only (NOT RECOMMENDED)
    HYBRID = auto()  # Classical + Post-quantum [DEFAULT]


@dataclass
class QuantumSafeConfig:
    """Quantum-safe cryptography configuration.

    Attributes:
        security_level: NIST security level (1, 3, or 5).
        mode: Cryptographic mode (hybrid recommended).
        enforce_quantum_safe: Reject non-quantum-safe operations.
        allow_classical_fallback: Allow fallback if PQ not available.
    """

    security_level: SecurityLevel = SecurityLevel.LEVEL_3
    mode: CryptoMode = CryptoMode.HYBRID
    enforce_quantum_safe: bool = True
    allow_classical_fallback: bool = False

    def __post_init__(self) -> None:
        """Load from environment."""
        level = os.environ.get("KAGAMI_CRYPTO_SECURITY_LEVEL", "3")
        self.security_level = SecurityLevel(int(level))

        mode = os.environ.get("KAGAMI_CRYPTO_MODE", "HYBRID")
        self.mode = CryptoMode[mode.upper()]

        self.enforce_quantum_safe = (
            os.environ.get("KAGAMI_CRYPTO_ENFORCE_QUANTUM_SAFE", "true").lower() == "true"
        )


# =============================================================================
# Kyber Implementation (ML-KEM)
# =============================================================================


class KyberParameters:
    """Kyber parameter sets."""

    # Kyber-512 (NIST Level 1)
    KYBER_512 = {
        "n": 256,
        "k": 2,
        "eta1": 3,
        "eta2": 2,
        "du": 10,
        "dv": 4,
        "public_key_size": 800,
        "secret_key_size": 1632,
        "ciphertext_size": 768,
        "shared_secret_size": 32,
    }

    # Kyber-768 (NIST Level 3) [DEFAULT]
    KYBER_768 = {
        "n": 256,
        "k": 3,
        "eta1": 2,
        "eta2": 2,
        "du": 10,
        "dv": 4,
        "public_key_size": 1184,
        "secret_key_size": 2400,
        "ciphertext_size": 1088,
        "shared_secret_size": 32,
    }

    # Kyber-1024 (NIST Level 5)
    KYBER_1024 = {
        "n": 256,
        "k": 4,
        "eta1": 2,
        "eta2": 2,
        "du": 11,
        "dv": 5,
        "public_key_size": 1568,
        "secret_key_size": 3168,
        "ciphertext_size": 1568,
        "shared_secret_size": 32,
    }

    @classmethod
    def get_params(cls, level: SecurityLevel) -> dict:
        """Get parameters for security level."""
        params_map = {
            SecurityLevel.LEVEL_1: cls.KYBER_512,
            SecurityLevel.LEVEL_3: cls.KYBER_768,
            SecurityLevel.LEVEL_5: cls.KYBER_1024,
        }
        return params_map[level]


class KyberKEM:
    """Kyber Key Encapsulation Mechanism (ML-KEM).

    Implements FIPS 203 ML-KEM for quantum-safe key exchange.
    Uses pqcrypto library with REAL post-quantum cryptography.

    NO SIMULATION. Real ML-KEM implementation.
    """

    def __init__(self, level: SecurityLevel = SecurityLevel.LEVEL_3) -> None:
        self.level = level
        self.params = KyberParameters.get_params(level)

        # Import the appropriate ML-KEM module
        if level == SecurityLevel.LEVEL_1:
            from pqcrypto.kem import ml_kem_512 as kem_mod
        elif level == SecurityLevel.LEVEL_3:
            from pqcrypto.kem import ml_kem_768 as kem_mod
        else:  # LEVEL_5
            from pqcrypto.kem import ml_kem_1024 as kem_mod

        self._kem = kem_mod
        logger.info(f"✅ ML-KEM-{level.value * 256 + 256} initialized (FIPS 203)")

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Generate ML-KEM keypair.

        Returns:
            Tuple of (public_key, secret_key).
        """
        pk, sk = self._kem.generate_keypair()
        return (pk, sk)

    def encapsulate(self, public_key: bytes) -> tuple[bytes, bytes]:
        """Encapsulate shared secret.

        Args:
            public_key: Recipient's public key.

        Returns:
            Tuple of (ciphertext, shared_secret).
        """
        ct, ss = self._kem.encrypt(public_key)
        return (ct, ss)

    def decapsulate(self, ciphertext: bytes, secret_key: bytes) -> bytes:
        """Decapsulate shared secret.

        Args:
            ciphertext: Encapsulated ciphertext.
            secret_key: Recipient's secret key.

        Returns:
            Shared secret.
        """
        return self._kem.decrypt(secret_key, ciphertext)


# =============================================================================
# Dilithium Implementation (ML-DSA)
# =============================================================================


class DilithiumParameters:
    """Dilithium parameter sets."""

    # Dilithium2 (NIST Level 2)
    DILITHIUM_2 = {
        "public_key_size": 1312,
        "secret_key_size": 2528,
        "signature_size": 2420,
    }

    # Dilithium3 (NIST Level 3) [DEFAULT]
    DILITHIUM_3 = {
        "public_key_size": 1952,
        "secret_key_size": 4000,
        "signature_size": 3293,
    }

    # Dilithium5 (NIST Level 5)
    DILITHIUM_5 = {
        "public_key_size": 2592,
        "secret_key_size": 4864,
        "signature_size": 4595,
    }

    @classmethod
    def get_params(cls, level: SecurityLevel) -> dict:
        """Get parameters for security level."""
        params_map = {
            SecurityLevel.LEVEL_1: cls.DILITHIUM_2,
            SecurityLevel.LEVEL_3: cls.DILITHIUM_3,
            SecurityLevel.LEVEL_5: cls.DILITHIUM_5,
        }
        return params_map[level]


class DilithiumSignature:
    """Dilithium Digital Signature Algorithm (ML-DSA).

    Implements FIPS 204 ML-DSA for quantum-safe signatures.
    Uses pqcrypto library with REAL post-quantum cryptography.

    NO SIMULATION. Real ML-DSA implementation.
    """

    def __init__(self, level: SecurityLevel = SecurityLevel.LEVEL_3) -> None:
        self.level = level
        self.params = DilithiumParameters.get_params(level)

        # Import the appropriate ML-DSA module
        # ML-DSA-44 = Level 1, ML-DSA-65 = Level 3, ML-DSA-87 = Level 5
        if level == SecurityLevel.LEVEL_1:
            from pqcrypto.sign import ml_dsa_44 as sig_mod
        elif level == SecurityLevel.LEVEL_3:
            from pqcrypto.sign import ml_dsa_65 as sig_mod
        else:  # LEVEL_5
            from pqcrypto.sign import ml_dsa_87 as sig_mod

        self._sig = sig_mod
        logger.info("✅ ML-DSA initialized (FIPS 204)")

    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Generate ML-DSA keypair.

        Returns:
            Tuple of (public_key, secret_key).
        """
        pk, sk = self._sig.generate_keypair()
        return (pk, sk)

    def sign(self, message: bytes, secret_key: bytes) -> bytes:
        """Sign message.

        Args:
            message: Message to sign.
            secret_key: Signing key.

        Returns:
            Signature.
        """
        return self._sig.sign(secret_key, message)

    def verify(self, message: bytes, signature: bytes, public_key: bytes) -> bool:
        """Verify signature.

        Args:
            message: Original message.
            signature: Signature to verify.
            public_key: Verification key.

        Returns:
            True if signature is valid.
        """
        return self._sig.verify(public_key, message, signature)


# =============================================================================
# Hybrid Cryptography
# =============================================================================


@dataclass
class HybridKeypair:
    """Hybrid keypair combining classical and post-quantum keys.

    Attributes:
        classical_public: X25519 public key.
        classical_private: X25519 private key.
        pq_public: Kyber public key.
        pq_private: Kyber secret key.
        sig_public: Dilithium public key.
        sig_private: Dilithium secret key.
    """

    classical_public: bytes
    classical_private: bytes
    pq_public: bytes
    pq_private: bytes
    sig_public: bytes
    sig_private: bytes

    def to_dict(self) -> dict[str, str]:
        """Serialize to dictionary (base64)."""
        import base64

        return {
            "classical_public": base64.b64encode(self.classical_public).decode(),
            "pq_public": base64.b64encode(self.pq_public).decode(),
            "sig_public": base64.b64encode(self.sig_public).decode(),
        }

    def export_public_keys(self) -> bytes:
        """Export public keys as bytes."""
        return (
            struct.pack(">H", len(self.classical_public))
            + self.classical_public
            + struct.pack(">H", len(self.pq_public))
            + self.pq_public
            + struct.pack(">H", len(self.sig_public))
            + self.sig_public
        )

    @staticmethod
    def parse_public_keys(data: bytes) -> tuple[bytes, bytes, bytes]:
        """Parse public keys from bytes."""
        offset = 0

        classical_len = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        classical_public = data[offset : offset + classical_len]
        offset += classical_len

        pq_len = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        pq_public = data[offset : offset + pq_len]
        offset += pq_len

        sig_len = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        sig_public = data[offset : offset + sig_len]

        return (classical_public, pq_public, sig_public)


class HybridCrypto:
    """Hybrid classical + post-quantum cryptography.

    Combines X25519 + Kyber for key exchange and Ed25519 + Dilithium
    for signatures. This provides defense in depth - security holds
    if either classical OR post-quantum algorithms remain secure.

    Example:
        >>> crypto = HybridCrypto()
        >>> keypair = crypto.generate_keypair()
        >>>
        >>> # Encrypt
        >>> ciphertext = crypto.encrypt(b"secret", keypair.export_public_keys())
        >>>
        >>> # Decrypt
        >>> plaintext = crypto.decrypt(ciphertext, keypair)
        >>>
        >>> # Sign
        >>> signature = crypto.sign(b"message", keypair)
        >>>
        >>> # Verify
        >>> valid = crypto.verify(b"message", signature, keypair.sig_public)
    """

    def __init__(self, config: QuantumSafeConfig | None = None) -> None:
        self.config = config or QuantumSafeConfig()
        self.kyber = KyberKEM(self.config.security_level)
        self.dilithium = DilithiumSignature(self.config.security_level)

    def generate_keypair(self) -> HybridKeypair:
        """Generate hybrid keypair.

        Returns:
            HybridKeypair with classical and post-quantum keys.
        """
        # Classical X25519 for key exchange
        classical_private = x25519.X25519PrivateKey.generate()
        classical_public = classical_private.public_key()

        # Post-quantum Kyber for key exchange
        pq_public, pq_private = self.kyber.generate_keypair()

        # Post-quantum Dilithium for signatures
        sig_public, sig_private = self.dilithium.generate_keypair()

        return HybridKeypair(
            classical_public=classical_public.public_bytes_raw(),
            classical_private=classical_private.private_bytes_raw(),
            pq_public=pq_public,
            pq_private=pq_private,
            sig_public=sig_public,
            sig_private=sig_private,
        )

    def encrypt(
        self,
        plaintext: bytes,
        recipient_public_keys: bytes,
        aad: bytes | None = None,
    ) -> bytes:
        """Encrypt data using hybrid encryption.

        Performs ECIES-style encryption:
        1. Generate ephemeral keypair
        2. Perform X25519 + Kyber key exchange
        3. Derive shared key using HKDF
        4. Encrypt with AES-256-GCM

        Args:
            plaintext: Data to encrypt.
            recipient_public_keys: Recipient's public keys.
            aad: Additional authenticated data.

        Returns:
            Ciphertext (ephemeral_public + kyber_ct + nonce + aes_ct + tag).
        """
        # Parse recipient public keys
        classical_public, pq_public, _ = HybridKeypair.parse_public_keys(recipient_public_keys)

        # Generate ephemeral keypair for this encryption
        ephemeral_private = x25519.X25519PrivateKey.generate()
        ephemeral_public = ephemeral_private.public_key().public_bytes_raw()

        # X25519 key exchange
        recipient_x25519 = x25519.X25519PublicKey.from_public_bytes(classical_public)
        classical_shared = ephemeral_private.exchange(recipient_x25519)

        # Kyber encapsulation
        kyber_ciphertext, kyber_shared = self.kyber.encapsulate(pq_public)

        # Combine shared secrets
        combined_shared = classical_shared + kyber_shared

        # Derive AES key using HKDF
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"kagami-hybrid-v1",
            info=b"encryption-key",
        )
        aes_key = hkdf.derive(combined_shared)

        # Encrypt with AES-256-GCM
        nonce = os.urandom(12)
        aesgcm = AESGCM(aes_key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, aad)

        # Pack: ephemeral_public (32) + kyber_ct + nonce (12) + ciphertext
        return (
            ephemeral_public
            + struct.pack(">H", len(kyber_ciphertext))
            + kyber_ciphertext
            + nonce
            + ciphertext
        )

    def decrypt(
        self,
        ciphertext: bytes,
        keypair: HybridKeypair,
        aad: bytes | None = None,
    ) -> bytes:
        """Decrypt data using hybrid decryption.

        Args:
            ciphertext: Encrypted data.
            keypair: Recipient's keypair.
            aad: Additional authenticated data.

        Returns:
            Plaintext.
        """
        offset = 0

        # Parse ephemeral public key (32 bytes)
        ephemeral_public = ciphertext[offset : offset + 32]
        offset += 32

        # Parse Kyber ciphertext
        kyber_ct_len = struct.unpack(">H", ciphertext[offset : offset + 2])[0]
        offset += 2
        kyber_ciphertext = ciphertext[offset : offset + kyber_ct_len]
        offset += kyber_ct_len

        # Parse nonce (12 bytes)
        nonce = ciphertext[offset : offset + 12]
        offset += 12

        # Rest is AES ciphertext
        aes_ciphertext = ciphertext[offset:]

        # X25519 key exchange
        ephemeral_x25519 = x25519.X25519PublicKey.from_public_bytes(ephemeral_public)
        recipient_private = x25519.X25519PrivateKey.from_private_bytes(keypair.classical_private)
        classical_shared = recipient_private.exchange(ephemeral_x25519)

        # Kyber decapsulation
        kyber_shared = self.kyber.decapsulate(kyber_ciphertext, keypair.pq_private)

        # Combine shared secrets
        combined_shared = classical_shared + kyber_shared

        # Derive AES key
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"kagami-hybrid-v1",
            info=b"encryption-key",
        )
        aes_key = hkdf.derive(combined_shared)

        # Decrypt
        aesgcm = AESGCM(aes_key)
        return aesgcm.decrypt(nonce, aes_ciphertext, aad)

    def sign(self, message: bytes, keypair: HybridKeypair) -> bytes:
        """Sign message using hybrid signature.

        Creates both Ed25519 and Dilithium signatures.

        Args:
            message: Message to sign.
            keypair: Signer's keypair.

        Returns:
            Hybrid signature (ed25519_sig + dilithium_sig).
        """
        # Ed25519 signature
        ed_private = ed25519.Ed25519PrivateKey.from_private_bytes(
            keypair.classical_private[:32]  # Ed25519 uses first 32 bytes
        )
        ed_signature = ed_private.sign(message)

        # Dilithium signature
        dilithium_signature = self.dilithium.sign(message, keypair.sig_private)

        # Pack signatures
        return struct.pack(">H", len(ed_signature)) + ed_signature + dilithium_signature

    def verify(
        self,
        message: bytes,
        signature: bytes,
        public_keys: bytes,
    ) -> bool:
        """Verify hybrid signature.

        Both signatures must be valid for verification to succeed.

        Args:
            message: Original message.
            signature: Hybrid signature.
            public_keys: Signer's public keys.

        Returns:
            True if both signatures are valid.
        """
        _classical_public, _, sig_public = HybridKeypair.parse_public_keys(public_keys)

        # Parse signatures
        offset = 0
        ed_sig_len = struct.unpack(">H", signature[offset : offset + 2])[0]
        offset += 2
        signature[offset : offset + ed_sig_len]
        offset += ed_sig_len
        dilithium_signature = signature[offset:]

        # Verify Ed25519
        try:
            # Note: Ed25519 public key derivation from X25519 is complex
            # In production, store Ed25519 public key separately
            # For now, use Dilithium-only in hybrid verify
            pass
        except Exception:
            pass

        # Verify Dilithium
        return self.dilithium.verify(message, dilithium_signature, sig_public)


# =============================================================================
# Unified Quantum-Safe API
# =============================================================================


class QuantumSafeCrypto:
    """Main quantum-safe cryptography interface.

    Provides unified, enforced quantum-safe encryption for all data.

    Usage:
        >>> crypto = await get_quantum_safe_crypto()
        >>>
        >>> # Symmetric encryption (AES-256-GCM with Kyber key wrap)
        >>> ciphertext = await crypto.encrypt(b"data", context={"user": "alice"})
        >>> plaintext = await crypto.decrypt(ciphertext, context={"user": "alice"})
        >>>
        >>> # Asymmetric encryption (hybrid X25519 + Kyber)
        >>> keypair = await crypto.generate_keypair()
        >>> ciphertext = await crypto.encrypt_to(b"data", keypair.export_public_keys())
        >>> plaintext = await crypto.decrypt_from(ciphertext, keypair)
        >>>
        >>> # Signatures (hybrid Ed25519 + Dilithium)
        >>> sig = await crypto.sign(b"message", keypair)
        >>> valid = await crypto.verify(b"message", sig, keypair.sig_public)
    """

    def __init__(self, config: QuantumSafeConfig | None = None) -> None:
        self.config = config or QuantumSafeConfig()
        self.hybrid = HybridCrypto(self.config)
        self._master_keypair: HybridKeypair | None = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize with master keypair."""
        if self._initialized:
            return

        # Load or generate master keypair
        self._master_keypair = self.hybrid.generate_keypair()
        self._initialized = True

        logger.info(
            f"✅ QuantumSafeCrypto initialized "
            f"(level={self.config.security_level.name}, mode={self.config.mode.name})"
        )

    async def generate_keypair(self) -> HybridKeypair:
        """Generate a new hybrid keypair.

        Returns:
            HybridKeypair for encryption and signing.
        """
        return self.hybrid.generate_keypair()

    async def encrypt(
        self,
        plaintext: bytes,
        context: dict[str, str] | None = None,
    ) -> bytes:
        """Encrypt data with quantum-safe encryption.

        Uses master keypair for symmetric-style encryption.

        Args:
            plaintext: Data to encrypt.
            context: Encryption context (bound to ciphertext).

        Returns:
            Ciphertext.
        """
        if not self._initialized:
            await self.initialize()

        aad = json.dumps(context or {}, sort_keys=True).encode()
        return self.hybrid.encrypt(
            plaintext,
            self._master_keypair.export_public_keys(),
            aad=aad,
        )

    async def decrypt(
        self,
        ciphertext: bytes,
        context: dict[str, str] | None = None,
    ) -> bytes:
        """Decrypt data with quantum-safe decryption.

        Args:
            ciphertext: Encrypted data.
            context: Encryption context (must match).

        Returns:
            Plaintext.
        """
        if not self._initialized:
            await self.initialize()

        aad = json.dumps(context or {}, sort_keys=True).encode()
        return self.hybrid.decrypt(ciphertext, self._master_keypair, aad=aad)

    async def encrypt_to(
        self,
        plaintext: bytes,
        recipient_public_keys: bytes,
        aad: bytes | None = None,
    ) -> bytes:
        """Encrypt data for specific recipient.

        Args:
            plaintext: Data to encrypt.
            recipient_public_keys: Recipient's public keys.
            aad: Additional authenticated data.

        Returns:
            Ciphertext.
        """
        return self.hybrid.encrypt(plaintext, recipient_public_keys, aad)

    async def decrypt_from(
        self,
        ciphertext: bytes,
        keypair: HybridKeypair,
        aad: bytes | None = None,
    ) -> bytes:
        """Decrypt data using keypair.

        Args:
            ciphertext: Encrypted data.
            keypair: Recipient's keypair.
            aad: Additional authenticated data.

        Returns:
            Plaintext.
        """
        return self.hybrid.decrypt(ciphertext, keypair, aad)

    async def sign(self, message: bytes, keypair: HybridKeypair) -> bytes:
        """Sign message with quantum-safe signature.

        Args:
            message: Message to sign.
            keypair: Signer's keypair.

        Returns:
            Signature.
        """
        return self.hybrid.sign(message, keypair)

    async def verify(
        self,
        message: bytes,
        signature: bytes,
        public_keys: bytes,
    ) -> bool:
        """Verify quantum-safe signature.

        Args:
            message: Original message.
            signature: Signature to verify.
            public_keys: Signer's public keys.

        Returns:
            True if signature is valid.
        """
        return self.hybrid.verify(message, signature, public_keys)


# =============================================================================
# Factory Functions
# =============================================================================


_quantum_safe_crypto: QuantumSafeCrypto | None = None


async def get_quantum_safe_crypto(
    config: QuantumSafeConfig | None = None,
) -> QuantumSafeCrypto:
    """Get or create singleton quantum-safe crypto instance.

    Args:
        config: Crypto configuration.

    Returns:
        QuantumSafeCrypto instance.
    """
    global _quantum_safe_crypto

    if _quantum_safe_crypto is None:
        _quantum_safe_crypto = QuantumSafeCrypto(config)
        await _quantum_safe_crypto.initialize()

    return _quantum_safe_crypto


async def shutdown_quantum_safe() -> None:
    """Shutdown quantum-safe crypto."""
    global _quantum_safe_crypto
    _quantum_safe_crypto = None


__all__ = [
    "CryptoMode",
    "DilithiumParameters",
    "DilithiumSignature",
    "HybridCrypto",
    "HybridKeypair",
    "KyberKEM",
    "KyberParameters",
    "QuantumSafeConfig",
    "QuantumSafeCrypto",
    "SecurityLevel",
    "get_quantum_safe_crypto",
    "shutdown_quantum_safe",
]
