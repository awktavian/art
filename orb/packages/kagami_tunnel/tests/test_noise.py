"""Tests for Noise Protocol implementation.

Tests the XX handshake pattern and transport encryption.
"""

import pytest

from kagami_tunnel.noise import (
    CipherState,
    DecryptionError,
    HandshakeError,
    NoiseHandshake,
    NoiseKeypair,
    NoiseTransport,
    SymmetricState,
    blake2b_hash,
    create_static_keypair,
    hkdf_expand,
    keypair_from_ed25519_seed,
)


class TestNoiseKeypair:
    """Tests for NoiseKeypair."""

    def test_generate_keypair(self):
        """Test keypair generation."""
        keypair = NoiseKeypair.generate()

        assert keypair.private_key is not None
        assert keypair.public_key is not None
        assert len(keypair.public_key) == 32

    def test_keypair_from_bytes(self):
        """Test keypair creation from bytes."""
        # Generate and export
        keypair1 = NoiseKeypair.generate()
        private_bytes = keypair1.private_key.private_bytes_raw()

        # Recreate from bytes
        keypair2 = NoiseKeypair.from_private_bytes(private_bytes)

        assert keypair2.public_key == keypair1.public_key

    def test_create_static_keypair(self):
        """Test helper function for static keypair."""
        keypair = create_static_keypair()
        assert len(keypair.public_key) == 32

    def test_keypair_from_ed25519_seed(self):
        """Test X25519 derivation from Ed25519 seed."""
        seed = b"0" * 32  # Deterministic seed

        keypair1 = keypair_from_ed25519_seed(seed)
        keypair2 = keypair_from_ed25519_seed(seed)

        # Same seed should produce same keypair
        assert keypair1.public_key == keypair2.public_key

        # Different seed should produce different keypair
        keypair3 = keypair_from_ed25519_seed(b"1" * 32)
        assert keypair3.public_key != keypair1.public_key


class TestCryptoPrimitives:
    """Tests for cryptographic primitives."""

    def test_blake2b_hash(self):
        """Test BLAKE2b hashing."""
        data = b"test data"
        hash1 = blake2b_hash(data)
        hash2 = blake2b_hash(data)

        assert len(hash1) == 64  # BLAKE2b-512
        assert hash1 == hash2  # Deterministic

        # Different data produces different hash
        hash3 = blake2b_hash(b"other data")
        assert hash3 != hash1

    def test_hkdf_expand(self):
        """Test HKDF key derivation."""
        key = b"0" * 32
        ikm = b"input key material"

        k1, k2 = hkdf_expand(key, ikm)

        assert len(k1) == 32
        assert len(k2) == 32
        assert k1 != k2  # Different outputs


class TestCipherState:
    """Tests for CipherState."""

    def test_no_key_passthrough(self):
        """Test passthrough when no key set."""
        cipher = CipherState()

        plaintext = b"hello world"
        ciphertext = cipher.encrypt(plaintext)
        decrypted = cipher.decrypt(ciphertext)

        # Without key, data passes through unchanged
        assert ciphertext == plaintext
        assert decrypted == plaintext

    def test_encryption_decryption(self):
        """Test encryption and decryption with key."""
        cipher = CipherState()
        cipher.set_key(b"0" * 32)

        plaintext = b"secret message"
        ciphertext = cipher.encrypt(plaintext)

        # Ciphertext should be different from plaintext
        assert ciphertext != plaintext

        # Create new cipher with same key for decryption
        cipher2 = CipherState()
        cipher2.set_key(b"0" * 32)
        decrypted = cipher2.decrypt(ciphertext)

        assert decrypted == plaintext

    def test_aad(self):
        """Test additional authenticated data."""
        cipher = CipherState()
        cipher.set_key(b"0" * 32)

        plaintext = b"message"
        aad = b"additional data"

        ciphertext = cipher.encrypt(plaintext, aad)

        cipher2 = CipherState()
        cipher2.set_key(b"0" * 32)

        # Correct AAD should work
        decrypted = cipher2.decrypt(ciphertext, aad)
        assert decrypted == plaintext

    def test_tamper_detection(self):
        """Test tampering is detected."""
        cipher = CipherState()
        cipher.set_key(b"0" * 32)

        ciphertext = cipher.encrypt(b"message")

        # Tamper with ciphertext
        tampered = bytearray(ciphertext)
        tampered[0] ^= 0xFF
        tampered = bytes(tampered)

        cipher2 = CipherState()
        cipher2.set_key(b"0" * 32)

        with pytest.raises(DecryptionError):
            cipher2.decrypt(tampered)

    def test_nonce_increment(self):
        """Test nonce increments on each operation."""
        cipher = CipherState()
        cipher.set_key(b"0" * 32)

        assert cipher.nonce == 0

        cipher.encrypt(b"msg1")
        assert cipher.nonce == 1

        cipher.encrypt(b"msg2")
        assert cipher.nonce == 2


class TestSymmetricState:
    """Tests for SymmetricState."""

    def test_mix_hash(self):
        """Test hash mixing."""
        state = SymmetricState()
        h1 = state.h

        state.mix_hash(b"data")
        h2 = state.h

        assert h2 != h1
        assert len(h2) == 64

    def test_mix_key(self):
        """Test key mixing."""
        state = SymmetricState()

        assert not state.cipher.has_key()

        state.mix_key(b"key material")

        assert state.cipher.has_key()

    def test_encrypt_and_hash(self):
        """Test encrypt with hash update."""
        state = SymmetricState()
        state.mix_key(b"key")

        h_before = state.h
        plaintext = b"message"

        ciphertext = state.encrypt_and_hash(plaintext)

        assert state.h != h_before
        assert ciphertext != plaintext

    def test_split(self):
        """Test symmetric state split."""
        state = SymmetricState()
        state.mix_key(b"key")

        c1, c2 = state.split()

        assert c1.has_key()
        assert c2.has_key()
        # Different keys for each direction
        assert c1.key != c2.key


class TestNoiseHandshake:
    """Tests for Noise XX handshake."""

    def test_full_handshake(self):
        """Test complete XX handshake."""
        # Create keypairs
        initiator_keypair = NoiseKeypair.generate()
        responder_keypair = NoiseKeypair.generate()

        # Create handshake states
        initiator = NoiseHandshake.initiator(initiator_keypair)
        responder = NoiseHandshake.responder(responder_keypair)

        # Step 1: Initiator -> e
        msg1 = initiator.write_message()
        assert len(msg1) == 32  # Just ephemeral public key

        # Step 2: Responder reads e, sends e, ee, s, es
        responder.read_message(msg1)
        msg2 = responder.write_message()
        assert len(msg2) > 32  # Ephemeral + encrypted static + tag

        # Step 3: Initiator reads response
        initiator.read_message(msg2)

        # Step 4: Initiator sends s, se
        msg3 = initiator.write_message()
        assert len(msg3) > 0

        # Step 5: Responder reads final
        responder.read_message(msg3)

        # Both should be complete
        assert initiator.is_complete()
        assert responder.is_complete()

        # Verify peer keys
        assert initiator.get_remote_static_key() == responder_keypair.public_key
        assert responder.get_remote_static_key() == initiator_keypair.public_key

    def test_transport_after_handshake(self):
        """Test transport encryption after handshake."""
        # Complete handshake
        initiator_keypair = NoiseKeypair.generate()
        responder_keypair = NoiseKeypair.generate()

        initiator = NoiseHandshake.initiator(initiator_keypair)
        responder = NoiseHandshake.responder(responder_keypair)

        msg1 = initiator.write_message()
        responder.read_message(msg1)
        msg2 = responder.write_message()
        initiator.read_message(msg2)
        msg3 = initiator.write_message()
        responder.read_message(msg3)

        # Get transport ciphers
        init_send, init_recv = initiator.get_transport_ciphers()
        resp_send, resp_recv = responder.get_transport_ciphers()

        # Initiator -> Responder
        plaintext = b"Hello from initiator"
        encrypted = init_send.encrypt(plaintext)
        decrypted = resp_recv.decrypt(encrypted)
        assert decrypted == plaintext

        # Responder -> Initiator
        plaintext = b"Hello from responder"
        encrypted = resp_send.encrypt(plaintext)
        decrypted = init_recv.decrypt(encrypted)
        assert decrypted == plaintext

    def test_handshake_with_payload(self):
        """Test handshake with payload in messages."""
        initiator_keypair = NoiseKeypair.generate()
        responder_keypair = NoiseKeypair.generate()

        initiator = NoiseHandshake.initiator(initiator_keypair)
        responder = NoiseHandshake.responder(responder_keypair)

        # First message can have payload (unencrypted in XX)
        msg1 = initiator.write_message(b"init payload")
        responder.read_message(msg1)
        # Note: First message payload is not encrypted in XX

        # Second message has encrypted payload
        msg2 = responder.write_message(b"resp payload")
        payload2 = initiator.read_message(msg2)
        assert payload2 == b"resp payload"

        # Third message has encrypted payload
        msg3 = initiator.write_message(b"final payload")
        payload3 = responder.read_message(msg3)
        assert payload3 == b"final payload"

    def test_handshake_state_errors(self):
        """Test handshake state machine errors."""
        keypair = NoiseKeypair.generate()

        # Initiator must write first, not read
        initiator = NoiseHandshake.initiator(keypair)
        with pytest.raises(HandshakeError):
            initiator.read_message(b"x" * 32)  # Valid length but wrong state

        # Initiator in wait state cannot write
        initiator2 = NoiseHandshake.initiator(keypair)
        initiator2.write_message()  # First write
        with pytest.raises(HandshakeError):
            initiator2.write_message()  # Can't write again, must read

    def test_get_transport_before_complete(self):
        """Test error when getting transport before handshake completes."""
        keypair = NoiseKeypair.generate()
        initiator = NoiseHandshake.initiator(keypair)

        with pytest.raises(HandshakeError):
            initiator.get_transport_ciphers()


class TestNoiseTransport:
    """Tests for NoiseTransport."""

    def test_bidirectional_encryption(self):
        """Test bidirectional message encryption."""
        # Complete handshake
        initiator_keypair = NoiseKeypair.generate()
        responder_keypair = NoiseKeypair.generate()

        initiator = NoiseHandshake.initiator(initiator_keypair)
        responder = NoiseHandshake.responder(responder_keypair)

        msg1 = initiator.write_message()
        responder.read_message(msg1)
        msg2 = responder.write_message()
        initiator.read_message(msg2)
        msg3 = initiator.write_message()
        responder.read_message(msg3)

        # Create transports
        init_transport = NoiseTransport.from_handshake(initiator)
        resp_transport = NoiseTransport.from_handshake(responder)

        # Test multiple messages in each direction
        for i in range(5):
            # Initiator -> Responder
            msg = f"Message {i} from initiator".encode()
            encrypted = init_transport.encrypt(msg)
            decrypted = resp_transport.decrypt(encrypted)
            assert decrypted == msg

            # Responder -> Initiator
            msg = f"Message {i} from responder".encode()
            encrypted = resp_transport.encrypt(msg)
            decrypted = init_transport.decrypt(encrypted)
            assert decrypted == msg

    def test_message_framing(self):
        """Test length-prefixed message framing."""
        initiator_keypair = NoiseKeypair.generate()
        responder_keypair = NoiseKeypair.generate()

        initiator = NoiseHandshake.initiator(initiator_keypair)
        responder = NoiseHandshake.responder(responder_keypair)

        msg1 = initiator.write_message()
        responder.read_message(msg1)
        msg2 = responder.write_message()
        initiator.read_message(msg2)
        msg3 = initiator.write_message()
        responder.read_message(msg3)

        init_transport = NoiseTransport.from_handshake(initiator)
        NoiseTransport.from_handshake(responder)

        # Encrypt includes length prefix
        encrypted = init_transport.encrypt(b"test")

        # First 2 bytes are length
        import struct

        length = struct.unpack(">H", encrypted[:2])[0]
        assert length == len(encrypted) - 2

    def test_large_message(self):
        """Test large message handling."""
        initiator_keypair = NoiseKeypair.generate()
        responder_keypair = NoiseKeypair.generate()

        initiator = NoiseHandshake.initiator(initiator_keypair)
        responder = NoiseHandshake.responder(responder_keypair)

        msg1 = initiator.write_message()
        responder.read_message(msg1)
        msg2 = responder.write_message()
        initiator.read_message(msg2)
        msg3 = initiator.write_message()
        responder.read_message(msg3)

        init_transport = NoiseTransport.from_handshake(initiator)
        resp_transport = NoiseTransport.from_handshake(responder)

        # Test with ~60KB message
        large_msg = b"x" * 60000
        encrypted = init_transport.encrypt(large_msg)
        decrypted = resp_transport.decrypt(encrypted)
        assert decrypted == large_msg


class TestInteroperability:
    """Tests for protocol interoperability scenarios."""

    def test_multiple_sessions_same_keys(self):
        """Test multiple sessions with same static keys."""
        initiator_keypair = NoiseKeypair.generate()
        responder_keypair = NoiseKeypair.generate()

        for _ in range(3):
            # Each session should use different ephemeral keys
            initiator = NoiseHandshake.initiator(initiator_keypair)
            responder = NoiseHandshake.responder(responder_keypair)

            msg1 = initiator.write_message()
            responder.read_message(msg1)
            msg2 = responder.write_message()
            initiator.read_message(msg2)
            msg3 = initiator.write_message()
            responder.read_message(msg3)

            assert initiator.is_complete()
            assert responder.is_complete()

    def test_failed_handshake_recovery(self):
        """Test recovery after failed handshake."""
        initiator_keypair = NoiseKeypair.generate()
        responder_keypair = NoiseKeypair.generate()

        # First attempt - corrupt message
        initiator1 = NoiseHandshake.initiator(initiator_keypair)
        responder1 = NoiseHandshake.responder(responder_keypair)

        msg1 = initiator1.write_message()
        responder1.read_message(msg1)
        msg2 = responder1.write_message()

        # Corrupt message
        corrupted = bytes([b ^ 0xFF for b in msg2])
        try:
            initiator1.read_message(corrupted)
        except (HandshakeError, DecryptionError):
            pass

        # Second attempt - should succeed
        initiator2 = NoiseHandshake.initiator(initiator_keypair)
        responder2 = NoiseHandshake.responder(responder_keypair)

        msg1 = initiator2.write_message()
        responder2.read_message(msg1)
        msg2 = responder2.write_message()
        initiator2.read_message(msg2)
        msg3 = initiator2.write_message()
        responder2.read_message(msg3)

        assert initiator2.is_complete()
        assert responder2.is_complete()
