"""Tests for the Hybrid Logical Clock implementation."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration


import time
from unittest.mock import patch

from kagami.core.hybrid_logical_clock import (
    GlobalHLC,
    HLCTimestamp,
    HybridLogicalClock,
    hlc_from_tuple,
    hlc_now,
    hlc_update,
)


class TestHLCTimestamp:
    """Test HLC timestamp functionality."""

    def test_timestamp_creation(self) -> None:
        """Test creating HLC timestamps."""
        ts = HLCTimestamp(physical=1000.0, logical=5, node_id="node1")
        assert ts.physical == 1000.0
        assert ts.logical == 5
        assert ts.node_id == "node1"

    def test_timestamp_comparison(self) -> None:
        """Test timestamp ordering."""
        # Different physical times
        ts1 = HLCTimestamp(physical=1000.0, logical=0, node_id="node1")
        ts2 = HLCTimestamp(physical=1001.0, logical=0, node_id="node1")
        assert ts1 < ts2
        assert ts2 > ts1

        # Same physical time, different logical
        ts3 = HLCTimestamp(physical=1000.0, logical=1, node_id="node1")
        ts4 = HLCTimestamp(physical=1000.0, logical=2, node_id="node1")
        assert ts3 < ts4

        # Same physical and logical, different nodes (tie-breaking)
        ts5 = HLCTimestamp(physical=1000.0, logical=0, node_id="node1")
        ts6 = HLCTimestamp(physical=1000.0, logical=0, node_id="node2")
        assert ts5 < ts6  # "node1" < "node2" lexicographically

    def test_timestamp_serialization(self) -> None:
        """Test serialization and deserialization."""
        ts1 = HLCTimestamp(physical=1234.5678, logical=42, node_id="test-node")

        # To/from bytes
        data = ts1.to_bytes()
        ts2 = HLCTimestamp.from_bytes(data)
        assert ts2.physical == pytest.approx(1234.5678)
        assert ts2.logical == 42
        assert ts2.node_id == "test-node"

        # To tuple
        tup = ts1.to_tuple()
        assert tup == (1234.5678, 42, "test-node")

    def test_timestamp_string_representation(self) -> None:
        """Test string representation."""
        ts = HLCTimestamp(physical=1000.123456, logical=5, node_id="node1")
        s = str(ts)
        assert "1000.123456" in s
        assert ":5" in s
        assert "@node1" in s


class TestHybridLogicalClock:
    """Test HLC implementation."""

    def test_clock_initialization(self) -> None:
        """Test clock initialization with auto node ID."""
        hlc = HybridLogicalClock()
        assert hlc.node_id is not None
        assert ":" in hlc.node_id  # Should be hostname:pid format

        # With explicit node ID
        hlc2 = HybridLogicalClock(node_id="custom-node")
        assert hlc2.node_id == "custom-node"

    def test_monotonic_timestamps(self) -> None:
        """Test that timestamps are monotonically increasing."""
        hlc = HybridLogicalClock(node_id="test")

        timestamps = []
        for _ in range(10):
            timestamps.append(hlc.now())

        # Each timestamp should be greater than the previous
        for i in range(1, len(timestamps)):
            assert timestamps[i] > timestamps[i - 1]

    @patch("kagami.core.hybrid_logical_clock.time.time")
    def test_logical_increment_on_time_stall(self, mock_time: Any) -> None:
        """Test logical counter increments when physical time doesn't advance."""
        mock_time.return_value = 1000.0

        hlc = HybridLogicalClock(node_id="test")

        # First call initializes the internal state
        ts1 = hlc.now()
        assert ts1.physical == 1000.0
        # First timestamp might have logical > 0 due to initialization

        # Subsequent calls should increment logical
        ts2 = hlc.now()
        assert ts2.physical == 1000.0
        assert ts2.logical > ts1.logical

        ts3 = hlc.now()
        assert ts3.physical == 1000.0
        assert ts3.logical > ts2.logical

    @patch("kagami.core.hybrid_logical_clock.time.time")
    def test_update_with_remote_timestamp(self, mock_time: Any) -> None:
        """Test updating clock with remote timestamps."""
        mock_time.return_value = 1000.0

        hlc = HybridLogicalClock(node_id="local")

        # Remote in the past - local time wins
        remote = HLCTimestamp(physical=900.0, logical=5, node_id="remote")
        result = hlc.update(remote)
        assert result.physical == 1000.0
        # Logical counter depends on internal state

        # Remote slightly ahead - remote time wins
        remote = HLCTimestamp(physical=1001.0, logical=3, node_id="remote")
        result = hlc.update(remote)
        assert result.physical == 1001.0
        assert result.logical == 4  # remote.logical + 1

        # Now local time advances
        mock_time.return_value = 1002.0
        result = hlc.now()
        assert result.physical == 1002.0
        assert result.logical == 0  # Reset on physical advance

    @patch("kagami.core.hybrid_logical_clock.time.time")
    def test_clock_skew_detection(self, mock_time: Any) -> None:
        """Test detection of excessive clock skew."""
        mock_time.return_value = 1000.0

        # The MAX_CLOCK_SKEW is set at class definition time (60 seconds default)
        hlc = HybridLogicalClock(node_id="local")

        # Remote timestamp 70 seconds in future - should fail (exceeds 60s default)
        remote = HLCTimestamp(physical=1070.0, logical=0, node_id="remote")

        with pytest.raises(ValueError) as exc_info:
            hlc.update(remote)

        assert "too far in future" in str(exc_info.value)

        # Remote timestamp 50 seconds in future - should work (within 60s default)
        remote = HLCTimestamp(physical=1050.0, logical=0, node_id="remote")
        result = hlc.update(remote)
        assert result.physical == 1050.0

    def test_send_receive_aliases(self) -> None:
        """Test send() and receive() aliases."""
        hlc = HybridLogicalClock(node_id="test")

        # send() is alias for now()
        ts1 = hlc.send()
        assert isinstance(ts1, HLCTimestamp)

        # receive() is alias for update()
        remote = HLCTimestamp(physical=time.time() + 1, logical=0, node_id="remote")
        ts2 = hlc.receive(remote)
        assert isinstance(ts2, HLCTimestamp)
        assert ts2 > ts1

    def test_happens_before_relation(self) -> None:
        """Test happens-before relationship."""
        hlc = HybridLogicalClock(node_id="test")

        ts1 = hlc.now()
        ts2 = hlc.now()

        assert hlc.happens_before(ts1, ts2)
        assert not hlc.happens_before(ts2, ts1)

    def test_concurrent_check(self) -> None:
        """Test concurrent event detection."""
        hlc = HybridLogicalClock(node_id="test")

        ts1 = HLCTimestamp(physical=1000.0, logical=0, node_id="node1")
        ts2 = HLCTimestamp(physical=1000.0, logical=0, node_id="node2")

        # Same physical and logical time but different nodes
        assert hlc.concurrent(ts1, ts2)

        # Different times are not concurrent
        ts3 = HLCTimestamp(physical=1001.0, logical=0, node_id="node1")
        assert not hlc.concurrent(ts1, ts3)


class TestGlobalHLC:
    """Test global HLC singleton."""

    def test_global_singleton(self) -> None:
        """Test that global HLC is a singleton."""
        hlc1 = GlobalHLC.get_clock()
        hlc2 = GlobalHLC.get_clock()
        assert hlc1 is hlc2

    def test_global_convenience_functions(self) -> None:
        """Test module-level convenience functions."""
        # hlc_now() should return a timestamp
        ts1 = hlc_now()
        assert isinstance(ts1, HLCTimestamp)

        # hlc_update() should update and return new timestamp
        remote = HLCTimestamp(physical=time.time() + 0.1, logical=0, node_id="remote")
        ts2 = hlc_update(remote)
        assert isinstance(ts2, HLCTimestamp)
        assert ts2 > ts1

        # hlc_from_tuple() should create timestamp
        ts3 = hlc_from_tuple(1000.0, 5, "test")
        assert ts3.physical == 1000.0
        assert ts3.logical == 5
        assert ts3.node_id == "test"

    def test_global_hlc_methods(self) -> None:
        """Test GlobalHLC class methods."""
        ts1 = GlobalHLC.now()
        assert isinstance(ts1, HLCTimestamp)

        remote = HLCTimestamp(physical=time.time() + 0.1, logical=0, node_id="remote")
        ts2 = GlobalHLC.update(remote)
        assert isinstance(ts2, HLCTimestamp)
        assert ts2 > ts1


class TestHLCIntegration:
    """Integration tests for HLC in distributed scenarios."""

    def test_three_node_scenario(self) -> None:
        """Test HLC with three nodes exchanging messages."""
        # Create three nodes
        node1 = HybridLogicalClock(node_id="node1")
        node2 = HybridLogicalClock(node_id="node2")
        node3 = HybridLogicalClock(node_id="node3")

        # Node1 sends to Node2
        msg1 = node1.send()
        recv1 = node2.receive(msg1)
        assert recv1 > msg1

        # Node2 sends to Node3
        msg2 = node2.send()
        recv2 = node3.receive(msg2)
        assert recv2 > msg2
        assert recv2 > recv1

        # Node3 sends to Node1
        msg3 = node3.send()
        recv3 = node1.receive(msg3)
        assert recv3 > msg3

        # All timestamps should be ordered
        all_timestamps = [msg1, recv1, msg2, recv2, msg3, recv3]
        sorted_timestamps = sorted(all_timestamps)
        assert sorted_timestamps == [msg1, recv1, msg2, recv2, msg3, recv3]

    @patch("kagami.core.hybrid_logical_clock.time.time")
    def test_concurrent_events_different_nodes(self, mock_time: Any) -> None:
        """Test concurrent events on different nodes."""
        mock_time.return_value = 1000.0

        node1 = HybridLogicalClock(node_id="node1")
        node2 = HybridLogicalClock(node_id="node2")

        # Both nodes generate events at same physical time
        ts1 = node1.now()
        ts2 = node2.now()

        # They should have same physical time but different node IDs
        assert ts1.physical == ts2.physical
        # Logical counters might differ due to initialization
        assert ts1.node_id != ts2.node_id

        # Total ordering still applies (tie-broken by node ID if needed)
        assert ts1 != ts2
        assert (ts1 < ts2) or (ts2 < ts1)

    def test_message_causality(self) -> None:
        """Test that message causality is preserved."""
        node1 = HybridLogicalClock(node_id="node1")
        node2 = HybridLogicalClock(node_id="node2")

        # Node1 sends message A
        msg_a = node1.send()

        # Node2 receives A and sends B
        node2.receive(msg_a)
        msg_b = node2.send()

        # B should be causally after A
        assert msg_b > msg_a

        # Node1 receives B
        recv_b = node1.receive(msg_b)

        # Receipt of B should be after B itself
        assert recv_b > msg_b

        # And transitively after A
        assert recv_b > msg_a
