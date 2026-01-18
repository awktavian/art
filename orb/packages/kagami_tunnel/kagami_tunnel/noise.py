"""Noise Protocol XX Implementation for Kagami Mesh Tunneling.

Implements the Noise Protocol Framework (revision 34) with:
- XX pattern: Mutual authentication with identity hiding
- Ed25519 for static keys (reuses mesh auth keys)
- X25519 for ephemeral DH
- ChaCha20-Poly1305 for symmetric encryption
- BLAKE2b for hashing

Protocol Flow (XX pattern):
```
    -> e                              (initiator sends ephemeral public key)
    <- e, ee, s, es                   (responder sends ephemeral, DH, static, DH)
    -> s, se                          (initiator sends static, DH)
```

After handshake, both parties derive symmetric keys for bidirectional
encrypted communication.

Colony: Crystal (D5) - Security verification
h(x) >= 0. Always.

Created: January 2026
"""

from __future__ import annotations

import hashlib
import hmac
import struct
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

if TYPE_CHECKING:
    pass


# =============================================================================
# Constants
# =============================================================================

# Noise Protocol constants
PROTOCOL_NAME = b"Noise_XX_25519_ChaChaPoly_BLAKE2b"
PROLOGUE = b"kagami-tunnel-v1"
MAX_MESSAGE_SIZE = 65535
TAG_SIZE = 16  # Poly1305 tag
DH_SIZE = 32  # X25519 public key size
HASH_SIZE = 64  # BLAKE2b-512 output
KEY_SIZE = 32  # ChaCha20 key size


class HandshakeState(Enum):
    """Noise handshake state."""

    INITIATOR_START = auto()
    INITIATOR_WAIT_RESPONSE = auto()
    INITIATOR_FINAL = auto()
    RESPONDER_START = auto()
    RESPONDER_WAIT_FINAL = auto()
    TRANSPORT = auto()
    FAILED = auto()


class NoiseError(Exception):
    """Noise Protocol error."""

    pass


class HandshakeError(NoiseError):
    """Handshake failed."""

    pass


class DecryptionError(NoiseError):
    """Decryption failed (authentication failure)."""

    pass


# =============================================================================
# Cryptographic Primitives
# =============================================================================


def blake2b_hash(data: bytes) -> bytes:
    """BLAKE2b-512 hash."""
    h = hashlib.blake2b(data, digest_size=HASH_SIZE)
    return h.digest()


def blake2b_hmac(key: bytes, data: bytes) -> bytes:
    """BLAKE2b HMAC."""
    return hmac.new(key, data, hashlib.blake2b).digest()


def hkdf_expand(chaining_key: bytes, input_key_material: bytes) -> tuple[bytes, bytes]:
    """HKDF-Expand for Noise Protocol.

    Returns two 32-byte keys derived from input.
    """
    # HKDF-Extract
    temp_key = blake2b_hmac(chaining_key, input_key_material)

    # HKDF-Expand (two outputs)
    output1 = blake2b_hmac(temp_key, b"\x01")[:KEY_SIZE]
    output2 = blake2b_hmac(temp_key, output1 + b"\x02")[:KEY_SIZE]

    return output1, output2


def hkdf_expand_3(chaining_key: bytes, input_key_material: bytes) -> tuple[bytes, bytes, bytes]:
    """HKDF-Expand for three outputs (used in final split)."""
    temp_key = blake2b_hmac(chaining_key, input_key_material)

    output1 = blake2b_hmac(temp_key, b"\x01")[:KEY_SIZE]
    output2 = blake2b_hmac(temp_key, output1 + b"\x02")[:KEY_SIZE]
    output3 = blake2b_hmac(temp_key, output2 + b"\x03")[:KEY_SIZE]

    return output1, output2, output3


def x25519_dh(private_key: x25519.X25519PrivateKey, public_key_bytes: bytes) -> bytes:
    """X25519 Diffie-Hellman key exchange."""
    peer_public = x25519.X25519PublicKey.from_public_bytes(public_key_bytes)
    return private_key.exchange(peer_public)


# =============================================================================
# Symmetric State
# =============================================================================


@dataclass
class CipherState:
    """Cipher state for symmetric encryption.

    Manages ChaCha20-Poly1305 encryption with nonce counter.
    """

    key: bytes | None = None
    nonce: int = 0

    def has_key(self) -> bool:
        """Check if key is set."""
        return self.key is not None

    def set_key(self, key: bytes) -> None:
        """Set encryption key."""
        self.key = key
        self.nonce = 0

    def encrypt(self, plaintext: bytes, associated_data: bytes = b"") -> bytes:
        """Encrypt with AEAD.

        Args:
            plaintext: Data to encrypt.
            associated_data: Additional authenticated data.

        Returns:
            Ciphertext with Poly1305 tag.
        """
        if self.key is None:
            return plaintext

        # Build 12-byte nonce (little-endian 64-bit counter + 4 zero bytes)
        nonce_bytes = struct.pack("<Q", self.nonce) + b"\x00\x00\x00\x00"
        self.nonce += 1

        cipher = ChaCha20Poly1305(self.key)
        return cipher.encrypt(nonce_bytes, plaintext, associated_data)

    def decrypt(self, ciphertext: bytes, associated_data: bytes = b"") -> bytes:
        """Decrypt with AEAD.

        Args:
            ciphertext: Data to decrypt (includes tag).
            associated_data: Additional authenticated data.

        Returns:
            Plaintext.

        Raises:
            DecryptionError: If authentication fails.
        """
        if self.key is None:
            return ciphertext

        # Build 12-byte nonce
        nonce_bytes = struct.pack("<Q", self.nonce) + b"\x00\x00\x00\x00"
        self.nonce += 1

        cipher = ChaCha20Poly1305(self.key)
        try:
            return cipher.decrypt(nonce_bytes, ciphertext, associated_data)
        except Exception as e:
            raise DecryptionError(f"AEAD decryption failed: {e}") from e


@dataclass
class SymmetricState:
    """Symmetric state for handshake.

    Manages the hash state and cipher during handshake.
    """

    h: bytes = field(default_factory=lambda: blake2b_hash(PROTOCOL_NAME))
    ck: bytes = field(default_factory=lambda: blake2b_hash(PROTOCOL_NAME)[:KEY_SIZE])
    cipher: CipherState = field(default_factory=CipherState)

    def mix_hash(self, data: bytes) -> None:
        """Mix data into hash."""
        self.h = blake2b_hash(self.h + data)

    def mix_key(self, input_key_material: bytes) -> None:
        """Mix key material into chaining key and cipher key."""
        self.ck, temp_k = hkdf_expand(self.ck, input_key_material)
        self.cipher.set_key(temp_k)

    def encrypt_and_hash(self, plaintext: bytes) -> bytes:
        """Encrypt plaintext and mix into hash."""
        ciphertext = self.cipher.encrypt(plaintext, self.h)
        self.mix_hash(ciphertext)
        return ciphertext

    def decrypt_and_hash(self, ciphertext: bytes) -> bytes:
        """Decrypt ciphertext and mix into hash."""
        plaintext = self.cipher.decrypt(ciphertext, self.h)
        self.mix_hash(ciphertext)
        return plaintext

    def split(self) -> tuple[CipherState, CipherState]:
        """Split into two cipher states for transport.

        Returns:
            Tuple of (initiator_send, initiator_recv) cipher states.
        """
        temp_k1, temp_k2 = hkdf_expand(self.ck, b"")

        c1 = CipherState()
        c1.set_key(temp_k1)

        c2 = CipherState()
        c2.set_key(temp_k2)

        return c1, c2


# =============================================================================
# Handshake State
# =============================================================================


@dataclass
class NoiseKeypair:
    """X25519 keypair for Noise Protocol."""

    private_key: x25519.X25519PrivateKey
    public_key: bytes

    @classmethod
    def generate(cls) -> NoiseKeypair:
        """Generate new keypair."""
        private = x25519.X25519PrivateKey.generate()
        public = private.public_key().public_bytes_raw()
        return cls(private_key=private, public_key=public)

    @classmethod
    def from_private_bytes(cls, private_bytes: bytes) -> NoiseKeypair:
        """Create from private key bytes."""
        private = x25519.X25519PrivateKey.from_private_bytes(private_bytes)
        public = private.public_key().public_bytes_raw()
        return cls(private_key=private, public_key=public)


@dataclass
class NoiseHandshake:
    """Noise XX pattern handshake state machine.

    Manages the handshake process between initiator and responder.
    After successful handshake, provides transport cipher states.

    Example:
        # Initiator
        initiator = NoiseHandshake.initiator(static_keypair)
        msg1 = initiator.write_message()  # -> e

        # Responder
        responder = NoiseHandshake.responder(static_keypair)
        responder.read_message(msg1)
        msg2 = responder.write_message()  # -> e, ee, s, es

        # Initiator
        initiator.read_message(msg2)
        msg3 = initiator.write_message()  # -> s, se

        # Responder
        responder.read_message(msg3)

        # Both now have transport ciphers
        send, recv = initiator.get_transport_ciphers()
    """

    # Static identity keypair (long-term)
    static: NoiseKeypair

    # Ephemeral keypair (per-session)
    ephemeral: NoiseKeypair | None = None

    # Remote keys (populated during handshake)
    remote_static: bytes | None = None
    remote_ephemeral: bytes | None = None

    # Handshake symmetric state
    symmetric: SymmetricState = field(default_factory=SymmetricState)

    # Current handshake state
    state: HandshakeState = HandshakeState.INITIATOR_START

    # Is this the initiator?
    is_initiator: bool = True

    # Transport cipher states (available after handshake)
    _send_cipher: CipherState | None = None
    _recv_cipher: CipherState | None = None

    @classmethod
    def initiator(cls, static: NoiseKeypair) -> NoiseHandshake:
        """Create initiator handshake state."""
        hs = cls(static=static, is_initiator=True, state=HandshakeState.INITIATOR_START)
        hs._initialize()
        return hs

    @classmethod
    def responder(cls, static: NoiseKeypair) -> NoiseHandshake:
        """Create responder handshake state."""
        hs = cls(static=static, is_initiator=False, state=HandshakeState.RESPONDER_START)
        hs._initialize()
        return hs

    def _initialize(self) -> None:
        """Initialize symmetric state with prologue."""
        self.symmetric = SymmetricState()
        self.symmetric.mix_hash(PROLOGUE)

    def write_message(self, payload: bytes = b"") -> bytes:
        """Generate next handshake message.

        Args:
            payload: Optional payload to include (encrypted).

        Returns:
            Handshake message bytes.

        Raises:
            HandshakeError: If called in wrong state.
        """
        if self.state == HandshakeState.INITIATOR_START:
            return self._write_initiator_1(payload)
        elif self.state == HandshakeState.RESPONDER_START:
            return self._write_responder_1(payload)
        elif self.state == HandshakeState.INITIATOR_WAIT_RESPONSE:
            raise HandshakeError("Initiator must read response first")
        elif self.state == HandshakeState.INITIATOR_FINAL:
            return self._write_initiator_2(payload)
        elif self.state == HandshakeState.RESPONDER_WAIT_FINAL:
            raise HandshakeError("Responder must read final first")
        else:
            raise HandshakeError(f"Cannot write in state {self.state}")

    def read_message(self, message: bytes) -> bytes:
        """Process received handshake message.

        Args:
            message: Received handshake message.

        Returns:
            Decrypted payload (if any).

        Raises:
            HandshakeError: If message is invalid.
        """
        if self.state == HandshakeState.INITIATOR_START:
            raise HandshakeError("Initiator must write first")
        elif self.state == HandshakeState.RESPONDER_START:
            return self._read_responder_1(message)
        elif self.state == HandshakeState.INITIATOR_WAIT_RESPONSE:
            return self._read_initiator_1(message)
        elif self.state == HandshakeState.RESPONDER_WAIT_FINAL:
            return self._read_responder_2(message)
        else:
            raise HandshakeError(f"Cannot read in state {self.state}")

    def is_complete(self) -> bool:
        """Check if handshake is complete."""
        return self.state == HandshakeState.TRANSPORT

    def get_transport_ciphers(self) -> tuple[CipherState, CipherState]:
        """Get transport cipher states after handshake.

        Returns:
            Tuple of (send_cipher, recv_cipher).

        Raises:
            HandshakeError: If handshake not complete.
        """
        if not self.is_complete():
            raise HandshakeError("Handshake not complete")

        if self._send_cipher is None or self._recv_cipher is None:
            raise HandshakeError("Transport ciphers not initialized")

        return self._send_cipher, self._recv_cipher

    def get_remote_static_key(self) -> bytes | None:
        """Get remote peer's static public key.

        Available after handshake completes.
        """
        return self.remote_static

    # =========================================================================
    # Initiator Message Handlers
    # =========================================================================

    def _write_initiator_1(self, payload: bytes) -> bytes:
        """Write first initiator message: -> e

        Sends ephemeral public key.
        """
        # Generate ephemeral keypair
        self.ephemeral = NoiseKeypair.generate()

        # e: Send ephemeral public key
        message = self.ephemeral.public_key
        self.symmetric.mix_hash(self.ephemeral.public_key)

        # Encrypt payload (no key yet, so plaintext)
        if payload:
            encrypted_payload = self.symmetric.encrypt_and_hash(payload)
            message += encrypted_payload

        self.state = HandshakeState.INITIATOR_WAIT_RESPONSE
        return message

    def _read_initiator_1(self, message: bytes) -> bytes:
        """Read responder message: <- e, ee, s, es

        Receives responder ephemeral, performs DH operations.
        """
        if self.ephemeral is None:
            raise HandshakeError("Ephemeral keypair not initialized")

        offset = 0

        # e: Read responder ephemeral public key
        if len(message) < DH_SIZE:
            raise HandshakeError("Message too short for ephemeral key")

        self.remote_ephemeral = message[offset : offset + DH_SIZE]
        offset += DH_SIZE
        self.symmetric.mix_hash(self.remote_ephemeral)

        # ee: DH(e, re)
        shared = x25519_dh(self.ephemeral.private_key, self.remote_ephemeral)
        self.symmetric.mix_key(shared)

        # s: Read encrypted static public key
        encrypted_static_len = DH_SIZE + TAG_SIZE
        if len(message) < offset + encrypted_static_len:
            raise HandshakeError("Message too short for static key")

        encrypted_static = message[offset : offset + encrypted_static_len]
        offset += encrypted_static_len

        self.remote_static = self.symmetric.decrypt_and_hash(encrypted_static)

        # es: DH(e, rs)
        shared = x25519_dh(self.ephemeral.private_key, self.remote_static)
        self.symmetric.mix_key(shared)

        # Decrypt payload
        payload = b""
        if offset < len(message):
            encrypted_payload = message[offset:]
            payload = self.symmetric.decrypt_and_hash(encrypted_payload)

        self.state = HandshakeState.INITIATOR_FINAL
        return payload

    def _write_initiator_2(self, payload: bytes) -> bytes:
        """Write final initiator message: -> s, se

        Sends static key, completes handshake.
        """
        if self.remote_ephemeral is None:
            raise HandshakeError("Remote ephemeral key not received")

        # s: Send encrypted static public key
        encrypted_static = self.symmetric.encrypt_and_hash(self.static.public_key)
        message = encrypted_static

        # se: DH(s, re)
        shared = x25519_dh(self.static.private_key, self.remote_ephemeral)
        self.symmetric.mix_key(shared)

        # Encrypt payload
        if payload:
            encrypted_payload = self.symmetric.encrypt_and_hash(payload)
            message += encrypted_payload

        # Split into transport ciphers
        c1, c2 = self.symmetric.split()
        self._send_cipher = c1
        self._recv_cipher = c2

        self.state = HandshakeState.TRANSPORT
        return message

    # =========================================================================
    # Responder Message Handlers
    # =========================================================================

    def _read_responder_1(self, message: bytes) -> bytes:
        """Read first initiator message: -> e

        Receives initiator ephemeral.
        """
        if len(message) < DH_SIZE:
            raise HandshakeError("Message too short for ephemeral key")

        # e: Read initiator ephemeral
        self.remote_ephemeral = message[:DH_SIZE]
        self.symmetric.mix_hash(self.remote_ephemeral)

        # Decrypt payload (no key yet)
        payload = b""
        if len(message) > DH_SIZE:
            payload = self.symmetric.decrypt_and_hash(message[DH_SIZE:])

        self.state = HandshakeState.RESPONDER_START
        return payload

    def _write_responder_1(self, payload: bytes) -> bytes:
        """Write responder message: <- e, ee, s, es

        Sends ephemeral, static, performs DH operations.
        """
        if self.remote_ephemeral is None:
            raise HandshakeError("Remote ephemeral key not received")

        # Generate ephemeral keypair
        self.ephemeral = NoiseKeypair.generate()

        # e: Send ephemeral public key
        message = self.ephemeral.public_key
        self.symmetric.mix_hash(self.ephemeral.public_key)

        # ee: DH(e, re)
        shared = x25519_dh(self.ephemeral.private_key, self.remote_ephemeral)
        self.symmetric.mix_key(shared)

        # s: Send encrypted static public key
        encrypted_static = self.symmetric.encrypt_and_hash(self.static.public_key)
        message += encrypted_static

        # es: DH(s, re)
        shared = x25519_dh(self.static.private_key, self.remote_ephemeral)
        self.symmetric.mix_key(shared)

        # Encrypt payload
        if payload:
            encrypted_payload = self.symmetric.encrypt_and_hash(payload)
            message += encrypted_payload

        self.state = HandshakeState.RESPONDER_WAIT_FINAL
        return message

    def _read_responder_2(self, message: bytes) -> bytes:
        """Read final initiator message: -> s, se

        Receives initiator static, completes handshake.
        """
        if self.ephemeral is None:
            raise HandshakeError("Ephemeral keypair not initialized")

        offset = 0

        # s: Read encrypted static public key
        encrypted_static_len = DH_SIZE + TAG_SIZE
        if len(message) < encrypted_static_len:
            raise HandshakeError("Message too short for static key")

        encrypted_static = message[offset : offset + encrypted_static_len]
        offset += encrypted_static_len

        self.remote_static = self.symmetric.decrypt_and_hash(encrypted_static)

        # se: DH(e, rs)
        shared = x25519_dh(self.ephemeral.private_key, self.remote_static)
        self.symmetric.mix_key(shared)

        # Decrypt payload
        payload = b""
        if offset < len(message):
            encrypted_payload = message[offset:]
            payload = self.symmetric.decrypt_and_hash(encrypted_payload)

        # Split into transport ciphers (reversed for responder)
        c1, c2 = self.symmetric.split()
        self._send_cipher = c2  # Responder sends with c2
        self._recv_cipher = c1  # Responder receives with c1

        self.state = HandshakeState.TRANSPORT
        return payload


# =============================================================================
# Transport Layer
# =============================================================================


@dataclass
class NoiseTransport:
    """Transport layer for encrypted communication after handshake.

    Provides bidirectional encrypted messaging with:
    - ChaCha20-Poly1305 AEAD encryption
    - Per-message nonce counter
    - Message framing with length prefix

    Example:
        # After handshake
        send, recv = handshake.get_transport_ciphers()
        transport = NoiseTransport(send, recv)

        # Send encrypted message
        encrypted = transport.encrypt(b"Hello, peer!")

        # Receive and decrypt
        plaintext = transport.decrypt(encrypted)
    """

    send_cipher: CipherState
    recv_cipher: CipherState

    @classmethod
    def from_handshake(cls, handshake: NoiseHandshake) -> NoiseTransport:
        """Create transport from completed handshake."""
        send, recv = handshake.get_transport_ciphers()
        return cls(send_cipher=send, recv_cipher=recv)

    def encrypt(self, plaintext: bytes) -> bytes:
        """Encrypt plaintext for sending.

        Args:
            plaintext: Data to encrypt.

        Returns:
            Length-prefixed encrypted message.
        """
        if len(plaintext) > MAX_MESSAGE_SIZE:
            raise NoiseError(f"Message too large: {len(plaintext)} > {MAX_MESSAGE_SIZE}")

        ciphertext = self.send_cipher.encrypt(plaintext)

        # Prefix with 2-byte length
        return struct.pack(">H", len(ciphertext)) + ciphertext

    def decrypt(self, message: bytes) -> bytes:
        """Decrypt received message.

        Args:
            message: Length-prefixed encrypted message.

        Returns:
            Decrypted plaintext.
        """
        if len(message) < 2:
            raise NoiseError("Message too short")

        length = struct.unpack(">H", message[:2])[0]
        ciphertext = message[2 : 2 + length]

        if len(ciphertext) != length:
            raise NoiseError(f"Message truncated: expected {length}, got {len(ciphertext)}")

        return self.recv_cipher.decrypt(ciphertext)


# =============================================================================
# Helper Functions
# =============================================================================


def create_static_keypair() -> NoiseKeypair:
    """Create a new static keypair for tunnel identity."""
    return NoiseKeypair.generate()


def keypair_from_ed25519_seed(seed: bytes) -> NoiseKeypair:
    """Derive X25519 keypair from Ed25519 seed.

    This allows reusing mesh auth Ed25519 keys for tunnel encryption.
    Uses HKDF to derive X25519 key material.

    Args:
        seed: Ed25519 seed (32 bytes).

    Returns:
        NoiseKeypair for tunnel encryption.
    """
    if len(seed) != 32:
        raise ValueError("Seed must be 32 bytes")

    # Derive X25519 private key from Ed25519 seed via HKDF
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"kagami-tunnel-x25519-v1",
        info=b"x25519-derivation",
    )
    x25519_private = hkdf.derive(seed)

    return NoiseKeypair.from_private_bytes(x25519_private)


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "CipherState",
    "DecryptionError",
    "HandshakeError",
    "HandshakeState",
    "NoiseError",
    "NoiseHandshake",
    "NoiseKeypair",
    "NoiseTransport",
    "SymmetricState",
    "create_static_keypair",
    "keypair_from_ed25519_seed",
]
