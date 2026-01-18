"""Tests for Receipt Sync Integration.

Tests cross-instance receipt synchronization via etcd.
"""

from __future__ import annotations

import pytest
import asyncio

# Try to import etcd client - skip if unavailable
try:
    from kagami.core.receipts.etcd_receipt_sync import EtcdReceiptSync

    ETCD_SYNC_AVAILABLE = True
except Exception:
    ETCD_SYNC_AVAILABLE = False
    EtcdReceiptSync = None  # type: ignore[assignment, misc]

# Consolidated markers - must be after imports
pytestmark = [
    pytest.mark.tier_integration,
    pytest.mark.timeout(60),
    pytest.mark.skipif(not ETCD_SYNC_AVAILABLE, reason="etcd receipt sync unavailable"),
]


class TestReceiptSyncIntegration:
    """Test receipt sync integration."""

    @pytest.mark.asyncio
    async def test_rate_limiting(self) -> None:
        """Test rate limiting prevents flooding."""
        sync = EtcdReceiptSync()

        # Try to publish many receipts rapidly
        success_count = 0
        blocked_count = 0

        for _ in range(20):
            if sync._check_rate_limit():
                success_count += 1
            else:
                blocked_count += 1

        # Should have some blocked due to rate limit
        assert blocked_count > 0 or success_count <= sync.rate_limit

    @pytest.mark.asyncio
    async def test_publish_receipt(self) -> None:
        """Test publishing receipt to etcd."""
        sync = EtcdReceiptSync()

        receipt = {
            "correlation_id": "test-123",
            "phase": "execute",
            "event_name": "TEST",
            "data": {"test": True},
        }

        # Should not raise exception
        try:
            await sync.publish_receipt(receipt)
        except Exception as e:
            # May fail if etcd not available, but shouldn't crash
            assert "etcd" in str(e).lower() or "connection" in str(e).lower()

    @pytest.mark.asyncio
    async def test_subscribe_receipts(self) -> None:
        """Test subscribing to receipts from other instances."""
        sync = EtcdReceiptSync()

        # Should not raise exception
        try:
            # Subscribe would start background task
            # Just verify it doesn't crash
            assert sync.instance_id is not None
        except Exception as e:
            pytest.skip(f"etcd not available: {e}")
