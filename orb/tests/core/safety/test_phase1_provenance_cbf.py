"""Tests for Phase 1 Provenance Chain CBF Protection.

Tests CBF monitoring on provenance chain etcd writes.

CREATED: December 21, 2025
AUTHOR: Forge (e₂)
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock, Mock

import pytest


@pytest.mark.asyncio
class TestProvenanceChainCBF:
    """Test CBF protection on provenance chain etcd writes."""

    async def test_rate_limit_check_safe(self) -> None:
        """Test that rate limit barrier returns positive value when safe."""
        from kagami.core.safety.provenance_chain import EtcdProvenanceStorage

        storage = EtcdProvenanceStorage()
        storage._max_writes_per_window = 100
        storage._write_count = 0
        storage._last_write = time.time()

        # First check should show 99 remaining (100 - 1)
        h_value = storage._check_rate_limit()
        assert h_value == 99.0

    async def test_rate_limit_check_violation(self) -> None:
        """Test that rate limit barrier returns negative value when violated."""
        from kagami.core.safety.provenance_chain import EtcdProvenanceStorage

        storage = EtcdProvenanceStorage()
        storage._max_writes_per_window = 5
        storage._write_count = 4  # Already at limit
        storage._last_write = time.time()

        # Next check should increment to 5 and show 0 remaining
        h_value = storage._check_rate_limit()
        assert h_value == 0.0

        # One more should be negative
        h_value2 = storage._check_rate_limit()
        assert h_value2 == -1.0

    async def test_cbf_protected_put_safe(self) -> None:
        """Test that CBF-protected PUT succeeds when within rate limit."""
        from kagami.core.safety.provenance_chain import EtcdProvenanceStorage

        storage = EtcdProvenanceStorage()
        storage._enabled = True
        storage._client = MagicMock()
        storage._client.put = Mock()
        storage._max_writes_per_window = 10
        storage._write_count = 0
        storage._last_write = time.time()

        # Should succeed
        result = await storage._cbf_protected_put(b"test_key", b"test_value")  # type: ignore[arg-type]
        assert result is True
        assert storage._client.put.called

    async def test_cbf_protected_put_violation(self) -> None:
        """Test that CBF-protected PUT raises RuntimeError when rate exceeded."""
        from kagami.core.safety.provenance_chain import EtcdProvenanceStorage

        storage = EtcdProvenanceStorage()
        storage._enabled = True
        storage._client = MagicMock()
        storage._client.put = Mock()
        storage._max_writes_per_window = 2
        storage._write_count = 2  # Already at limit
        storage._last_write = time.time()

        # Should raise RuntimeError due to CBF violation
        with pytest.raises(RuntimeError, match="rate limit exceeded"):
            await storage._cbf_protected_put(b"test_key", b"test_value")  # type: ignore[arg-type]

        # PUT should not have been called
        assert not storage._client.put.called

    async def test_store_record_uses_cbf_protection(self) -> None:
        """Test that store_record uses CBF-protected PUT."""
        from kagami.core.safety.provenance_chain import (
            EtcdProvenanceStorage,
            ProvenanceRecord,
        )

        storage = EtcdProvenanceStorage()
        storage._enabled = True
        storage._client = MagicMock()
        storage._client.lease = Mock(return_value=MagicMock(id=1))
        storage._client.put = Mock()
        storage._max_writes_per_window = 10
        storage._write_count = 0
        storage._last_write = time.time()

        record = ProvenanceRecord(
            record_hash="abc123",
            previous_hash=None,
            correlation_id="test",
            instance_id="test-instance",
            timestamp=time.time(),
            action="test_action",
            context={},
            output_hash=None,
            signature="sig",
            scheme="ed25519",
        )

        # Should succeed and increment write counter
        result = await storage.store_record(record)
        assert result is True
        # Should have made 2 PUTs (record + chain head)
        assert storage._write_count == 2

    async def test_store_record_respects_rate_limit(self) -> None:
        """Test that store_record respects CBF rate limit."""
        from kagami.core.safety.provenance_chain import (
            EtcdProvenanceStorage,
            ProvenanceRecord,
        )

        storage = EtcdProvenanceStorage()
        storage._enabled = True
        storage._client = MagicMock()
        storage._client.lease = Mock(return_value=MagicMock(id=1))
        storage._client.put = Mock()
        # Set limit to 3 writes total
        storage._max_writes_per_window = 3
        storage._write_count = 0
        storage._last_write = time.time()

        record = ProvenanceRecord(
            record_hash="abc123",
            previous_hash=None,
            correlation_id="test",
            instance_id="test-instance",
            timestamp=time.time(),
            action="test_action",
            context={},
            output_hash=None,
            signature="sig",
            scheme="ed25519",
        )

        # First record should succeed (writes 1 and 2)
        result1 = await storage.store_record(record)
        assert result1 is True

        # Second record would need writes 3 and 4, but limit is 3
        # CBF violations are safety-critical and raise RuntimeError
        with pytest.raises(RuntimeError, match="rate limit exceeded"):
            await storage.store_record(record)

    async def test_rate_limit_window_reset(self) -> None:
        """Test that rate limit window resets after timeout."""
        from kagami.core.safety.provenance_chain import EtcdProvenanceStorage

        storage = EtcdProvenanceStorage()
        storage._max_writes_per_window = 2
        storage._rate_limit_window = 0.1  # 100ms window
        storage._write_count = 2  # At limit
        storage._last_write = time.time()

        # Should be at limit
        h_value1 = storage._check_rate_limit()
        assert h_value1 < 0  # Exceeded

        # Wait for window to expire
        await asyncio.sleep(0.15)

        # Should reset
        h_value2 = storage._check_rate_limit()
        assert h_value2 > 0  # Back to safe

    async def test_store_public_key_cbf_protected(self) -> None:
        """Test that store_public_key uses CBF protection."""
        from kagami.core.safety.provenance_chain import EtcdProvenanceStorage

        storage = EtcdProvenanceStorage()
        storage._enabled = True
        storage._client = MagicMock()
        storage._client.put = Mock()
        storage._max_writes_per_window = 2
        storage._write_count = 0
        storage._last_write = time.time()

        # First write should succeed
        result1 = await storage.store_public_key("inst1", "key1", "ed25519")
        assert result1 is True
        assert storage._write_count == 1

        # Second write should succeed
        result2 = await storage.store_public_key("inst2", "key2", "ed25519")
        assert result2 is True
        assert storage._write_count == 2

        # Third write should raise RuntimeError (CBF violation is safety-critical)
        with pytest.raises(RuntimeError, match="rate limit exceeded"):
            await storage.store_public_key("inst3", "key3", "ed25519")

    async def test_add_witness_cbf_protected(self) -> None:
        """Test that add_witness uses CBF protection."""
        from kagami.core.safety.provenance_chain import EtcdProvenanceStorage

        storage = EtcdProvenanceStorage()
        storage._enabled = True
        storage._client = MagicMock()
        storage._client.lease = Mock(return_value=MagicMock(id=1))
        storage._client.put = Mock()
        storage._max_writes_per_window = 2
        storage._write_count = 0
        storage._last_write = time.time()

        # First two witnesses should succeed
        result1 = await storage.add_witness("record1", "witness1", "sig1")
        assert result1 is True

        result2 = await storage.add_witness("record1", "witness2", "sig2")
        assert result2 is True

        # Third witness should raise RuntimeError (CBF violation is safety-critical)
        with pytest.raises(RuntimeError, match="rate limit exceeded"):
            await storage.add_witness("record1", "witness3", "sig3")
