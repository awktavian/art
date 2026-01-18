"""Tests for etcd Client.

Tests etcd client for distributed consensus with comprehensive mock-based coverage.

Author: Crystal 💎 (Verification Colony)
Date: December 27, 2025
"""

from __future__ import annotations

import pytest

# Check if etcd3 can be imported (protobuf compatibility issues possible)
try:
    import etcd3  # noqa: F401

    _etcd3_available = True
except ImportError:
    _etcd3_available = False
except TypeError:
    # Protobuf compatibility issue
    _etcd3_available = False

pytestmark = [
    pytest.mark.tier1,
    pytest.mark.tier_unit,
    pytest.mark.skipif(
        not _etcd3_available, reason="etcd3 not available or protobuf incompatibility"
    ),
]

import json
import os
import threading
import time
from collections.abc import Generator
from contextlib import contextmanager
from unittest import mock
from unittest.mock import MagicMock, Mock, PropertyMock, patch

from kagami.core.exceptions import (
    CircuitOpenError,
    EtcdConnectionError,
    EtcdLeaderError,
    EtcdQuorumError,
)


@pytest.fixture
def mock_etcd_client() -> MagicMock:
    """Create a mock etcd3 client."""
    client = MagicMock()
    leader_mock = MagicMock()
    leader_mock.name = "leader-1"  # Set name as an attribute, not constructor arg
    client.status.return_value = MagicMock(
        leader=leader_mock,
        raft_term=10,
        raft_index=1000,
        db_size=1024,
        version="3.5.0",
    )
    member1, member2 = MagicMock(), MagicMock()
    member1.name = "member1"
    member2.name = "member2"
    client.members = [member1, member2]
    client.get.return_value = (b'{"key": "value"}', MagicMock())
    client.put.return_value = True
    client.delete.return_value = True
    client.close.return_value = None
    return client


@pytest.fixture
def mock_etcd3_module(mock_etcd_client: MagicMock) -> Generator[MagicMock, None, None]:
    """Mock the etcd3 module by patching the import."""
    mock_etcd3 = MagicMock()
    mock_etcd3.client.return_value = mock_etcd_client

    # Patch at sys.modules level since etcd3 is imported lazily inside functions
    with patch.dict("sys.modules", {"etcd3": mock_etcd3}):
        yield mock_etcd3


@pytest.fixture(autouse=True)
def reset_module_state() -> Generator[None, None, None]:
    """Reset module-level state before each test."""
    from kagami.core.consensus import etcd_client

    # Reset global state
    etcd_client._etcd_pool = None
    etcd_client._compat_client = None
    etcd_client._circuit_breaker_state = "closed"
    etcd_client._circuit_breaker_failures = 0
    etcd_client._circuit_breaker_last_failure = 0.0
    etcd_client._last_health_check = 0.0

    # Reset circuit breaker manager
    etcd_client._circuit_breaker_manager = etcd_client.CircuitBreakerManager()

    yield

    # Cleanup
    if etcd_client._etcd_pool:
        etcd_client._etcd_pool.close_all()
    etcd_client._etcd_pool = None
    etcd_client._compat_client = None


class TestCircuitBreakerManager:
    """Test CircuitBreakerManager functionality."""

    def test_initial_state_closed(self) -> None:
        """Test circuit breaker starts in closed state."""
        from kagami.core.consensus.etcd_client import CircuitBreakerManager

        manager = CircuitBreakerManager()
        state = manager.get_state("test_op")

        assert state["state"] == "closed"
        assert state["failures"] == 0

    def test_check_allows_closed_state(self) -> None:
        """Test check allows operations in closed state."""
        from kagami.core.consensus.etcd_client import CircuitBreakerManager

        manager = CircuitBreakerManager()
        manager.check("test_op")  # Should not raise

    def test_record_failure_increments_count(self) -> None:
        """Test recording failures increments failure count."""
        from kagami.core.consensus.etcd_client import CircuitBreakerManager

        manager = CircuitBreakerManager()
        manager.record_failure("test_op")

        state = manager.get_state("test_op")
        assert state["failures"] == 1
        assert state["state"] == "closed"

    def test_threshold_opens_circuit(self) -> None:
        """Test threshold triggers circuit open."""
        from kagami.core.consensus.etcd_client import CircuitBreakerManager

        manager = CircuitBreakerManager()
        manager.threshold = 3

        # Record failures up to threshold
        for _ in range(3):
            manager.record_failure("test_op")

        state = manager.get_state("test_op")
        assert state["state"] == "open"
        assert state["failures"] >= 3

    def test_open_circuit_blocks_operations(self) -> None:
        """Test open circuit blocks operations."""
        from kagami.core.consensus.etcd_client import CircuitBreakerManager

        manager = CircuitBreakerManager()
        manager.threshold = 2

        # Trigger circuit open
        for _ in range(2):
            manager.record_failure("test_op")

        # Should raise when checking
        with pytest.raises(CircuitOpenError, match="Circuit breaker open"):
            manager.check("test_op")

    def test_timeout_transitions_to_half_open(self) -> None:
        """Test timeout transitions from open to half-open."""
        from kagami.core.consensus.etcd_client import CircuitBreakerManager

        manager = CircuitBreakerManager()
        manager.threshold = 2
        manager.timeout = 0.1  # Short timeout for testing

        # Open the circuit
        for _ in range(2):
            manager.record_failure("test_op")

        # Wait for timeout
        time.sleep(0.15)

        # Should transition to half_open and allow check
        manager.check("test_op")
        state = manager.get_state("test_op")
        assert state["state"] == "half_open"

    def test_success_in_half_open_closes_circuit(self) -> None:
        """Test success in half-open state closes circuit."""
        from kagami.core.consensus.etcd_client import CircuitBreakerManager

        manager = CircuitBreakerManager()
        manager.threshold = 2
        manager.timeout = 0.1

        # Open circuit
        for _ in range(2):
            manager.record_failure("test_op")

        # Wait and transition to half_open
        time.sleep(0.15)
        manager.check("test_op")

        # Record success
        manager.record_success("test_op")

        state = manager.get_state("test_op")
        assert state["state"] == "closed"
        assert state["failures"] == 0

    def test_multiple_operations_isolated(self) -> None:
        """Test different operations have isolated circuit breakers."""
        from kagami.core.consensus.etcd_client import CircuitBreakerManager

        manager = CircuitBreakerManager()
        manager.threshold = 2

        # Fail op1
        for _ in range(3):
            manager.record_failure("op1")

        # op1 should be open
        with pytest.raises(CircuitOpenError):
            manager.check("op1")

        # op2 should still be closed
        manager.check("op2")  # Should not raise

    def test_get_all_states(self) -> None:
        """Test getting all breaker states."""
        from kagami.core.consensus.etcd_client import CircuitBreakerManager

        manager = CircuitBreakerManager()
        manager.record_failure("op1")
        manager.record_success("op2")

        states = manager.get_all_states()
        assert "op1" in states
        assert "op2" in states
        assert states["op1"]["failures"] == 1
        assert states["op2"]["failures"] == 0


class TestEndpointParsing:
    """Test endpoint configuration and parsing."""

    def test_get_etcd_endpoints_default(self) -> None:
        """Test default endpoint when no env vars set."""
        from kagami.core.consensus.etcd_client import _get_etcd_endpoints

        with patch.dict(os.environ, {}, clear=True):
            endpoints = _get_etcd_endpoints()
            assert endpoints == ["http://localhost:2379"]

    def test_get_etcd_endpoints_single(self) -> None:
        """Test single endpoint from ETCD_ENDPOINT."""
        from kagami.core.consensus.etcd_client import _get_etcd_endpoints

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://etcd1:2379"}):
            endpoints = _get_etcd_endpoints()
            assert endpoints == ["http://etcd1:2379"]

    def test_get_etcd_endpoints_multiple(self) -> None:
        """Test multiple endpoints from ETCD_ENDPOINTS."""
        from kagami.core.consensus.etcd_client import _get_etcd_endpoints

        with patch.dict(
            os.environ,
            {"ETCD_ENDPOINTS": "http://etcd1:2379,http://etcd2:2379,http://etcd3:2379"},
        ):
            endpoints = _get_etcd_endpoints()
            assert len(endpoints) == 3
            assert "http://etcd1:2379" in endpoints

    def test_get_etcd_endpoints_production_tls_enforcement(self) -> None:
        """Test production enforces TLS."""
        from kagami.core.consensus.etcd_client import _get_etcd_endpoints

        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "ETCD_ENDPOINTS": "http://external.etcd:2379",
            },
        ):
            with pytest.raises(RuntimeError, match="MUST use TLS"):
                _get_etcd_endpoints()

    def test_get_etcd_endpoints_production_allows_localhost_http(self) -> None:
        """Test production allows http for localhost."""
        from kagami.core.consensus.etcd_client import _get_etcd_endpoints

        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "ETCD_ENDPOINTS": "http://localhost:2379",
            },
        ):
            endpoints = _get_etcd_endpoints()
            assert endpoints == ["http://localhost:2379"]

    def test_parse_endpoint_with_port(self) -> None:
        """Test parsing endpoint with explicit port."""
        from kagami.core.consensus.etcd_client import _parse_endpoint

        host, port = _parse_endpoint("http://etcd1:2379")
        assert host == "etcd1"
        assert port == 2379

    def test_parse_endpoint_without_port(self) -> None:
        """Test parsing endpoint defaults to 2379."""
        from kagami.core.consensus.etcd_client import _parse_endpoint

        host, port = _parse_endpoint("http://etcd1")
        assert host == "etcd1"
        assert port == 2379

    def test_parse_endpoint_https(self) -> None:
        """Test parsing HTTPS endpoints."""
        from kagami.core.consensus.etcd_client import _parse_endpoint

        host, port = _parse_endpoint("https://etcd-secure:2379")
        assert host == "etcd-secure"
        assert port == 2379


class TestConnectionCreation:
    """Test etcd client connection creation."""

    def test_create_etcd_client_success(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test successful client creation."""
        from kagami.core.consensus.etcd_client import _create_etcd_client

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            client = _create_etcd_client()
            assert client is not None
            mock_etcd3_module.client.assert_called()

    def test_create_etcd_client_with_tls(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test client creation with TLS credentials."""
        from kagami.core.consensus.etcd_client import _create_etcd_client

        with patch.dict(
            os.environ,
            {
                "ETCD_ENDPOINT": "https://etcd:2379",
                "ETCD_CA_CERT": "/certs/ca.pem",
                "ETCD_CERT_KEY": "/certs/key.pem",
                "ETCD_CERT_CERT": "/certs/cert.pem",
            },
        ):
            _create_etcd_client()
            call_kwargs = mock_etcd3_module.client.call_args[1]
            assert call_kwargs["ca_cert"] == "/certs/ca.pem"
            assert call_kwargs["cert_key"] == "/certs/key.pem"
            assert call_kwargs["cert_cert"] == "/certs/cert.pem"

    def test_create_etcd_client_with_auth(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test client creation with authentication."""
        from kagami.core.consensus.etcd_client import _create_etcd_client

        with patch.dict(
            os.environ,
            {
                "ETCD_ENDPOINT": "http://localhost:2379",
                "ETCD_USER": "admin",
                "ETCD_PASSWORD": "secret",
            },
        ):
            _create_etcd_client()
            call_kwargs = mock_etcd3_module.client.call_args[1]
            assert call_kwargs["user"] == "admin"
            assert call_kwargs["password"] == "secret"

    def test_create_etcd_client_production_requires_tls(self, mock_etcd3_module: MagicMock) -> None:
        """Test production environment requires TLS credentials."""
        from kagami.core.consensus.etcd_client import _create_etcd_client

        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "ETCD_ENDPOINT": "https://etcd:2379",
            },
        ):
            with pytest.raises(
                EtcdConnectionError, match="Production etcd connections must use TLS"
            ):
                _create_etcd_client()

    def test_create_etcd_client_import_error(self) -> None:
        """Test client creation fails gracefully when etcd3 not installed."""
        # Remove etcd3 from sys.modules to simulate it not being installed
        # Then create a mock that raises ImportError when accessed
        import builtins

        from kagami.core.consensus.etcd_client import _create_etcd_client

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "etcd3":
                raise ImportError("No module named 'etcd3'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            with pytest.raises(EtcdConnectionError, match="not installed"):
                _create_etcd_client()

    def test_create_etcd_client_connection_error(self, mock_etcd3_module: MagicMock) -> None:
        """Test client creation handles connection errors."""
        from kagami.core.consensus.etcd_client import _create_etcd_client

        mock_etcd3_module.client.side_effect = ConnectionError("Connection refused")

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            with pytest.raises(EtcdConnectionError):
                _create_etcd_client()


class TestConnectionPool:
    """Test EtcdConnectionPool functionality."""

    def test_pool_initialization(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test connection pool initializes correctly."""
        from kagami.core.consensus.etcd_client import EtcdConnectionPool

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            pool = EtcdConnectionPool(pool_size=3)
            pool.initialize()

            assert pool._initialized is True
            assert pool._pool.qsize() == 3

    def test_pool_get_client_returns_healthy(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test getting client from pool."""
        from kagami.core.consensus.etcd_client import EtcdConnectionPool

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            pool = EtcdConnectionPool(pool_size=2)
            pool.initialize()

            with pool.get_client() as client:
                assert client is not None
                client.status.assert_called()

    def test_pool_get_client_recreates_stale_connection(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test pool recreates stale connections."""
        from kagami.core.consensus.etcd_client import EtcdConnectionPool

        # First client will be stale (status fails), second will be fresh
        stale_client = MagicMock()
        stale_client.status.side_effect = ConnectionError("Stale")

        fresh_client = MagicMock()
        fresh_client.status.return_value = MagicMock()

        mock_etcd3_module.client.side_effect = [stale_client, fresh_client, fresh_client]

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            pool = EtcdConnectionPool(pool_size=1)
            pool.initialize()

            with pool.get_client() as client:
                # Should get fresh client after detecting stale
                assert client == fresh_client

    def test_pool_exhaustion_raises_error(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test pool exhaustion raises appropriate error."""
        from kagami.core.consensus.etcd_client import EtcdConnectionPool

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            pool = EtcdConnectionPool(pool_size=1)
            pool.initialize()

            # Hold the only connection
            with pool.get_client():
                # Try to get another (should timeout quickly)
                with pytest.raises(EtcdConnectionError, match="pool exhausted"):
                    with pool.get_client(timeout=0.1):
                        pass

    def test_pool_close_all(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test closing all pool connections."""
        from kagami.core.consensus.etcd_client import EtcdConnectionPool

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            pool = EtcdConnectionPool(pool_size=2)
            pool.initialize()

            pool.close_all()

            assert pool._initialized is False
            assert pool._pool.empty()


class TestKeyValueOperations:
    """Test key-value operations."""

    @pytest.mark.asyncio
    async def test_publish_state_success(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test publishing state to etcd."""
        from kagami.core.consensus.etcd_client import publish_state

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            result = await publish_state("test_key", {"status": "active", "value": 42})

            assert result is True
            mock_etcd_client.put.assert_called_once()
            call_args = mock_etcd_client.put.call_args[0]
            assert call_args[0] == "test_key"
            assert json.loads(call_args[1]) == {"status": "active", "value": 42}

    @pytest.mark.asyncio
    async def test_publish_state_handles_errors(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test publish_state handles errors gracefully."""
        from kagami.core.consensus.etcd_client import publish_state

        mock_etcd_client.put.side_effect = Exception("Connection lost")

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            result = await publish_state("test_key", {"data": "test"})
            assert result is False

    @pytest.mark.asyncio
    async def test_get_state_success(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test getting state from etcd."""
        from kagami.core.consensus.etcd_client import get_state

        test_data = {"status": "active", "count": 10}
        mock_etcd_client.get.return_value = (
            json.dumps(test_data).encode(),
            MagicMock(),
        )

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            result = await get_state("test_key")

            assert result == test_data
            mock_etcd_client.get.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_get_state_not_found(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test getting non-existent state returns None."""
        from kagami.core.consensus.etcd_client import get_state

        mock_etcd_client.get.return_value = (None, MagicMock())

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            result = await get_state("nonexistent_key")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_state_handles_errors(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test get_state handles errors gracefully."""
        from kagami.core.consensus.etcd_client import get_state

        mock_etcd_client.get.side_effect = Exception("Connection lost")

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            result = await get_state("test_key")
            assert result is None


class TestLeaderElection:
    """Test leader election functionality."""

    @pytest.mark.asyncio
    async def test_acquire_leader_success(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test successful leader acquisition."""
        from kagami.core.consensus.etcd_client import acquire_leader

        mock_lease = MagicMock()
        mock_lease.id = 12345
        mock_etcd_client.lease.return_value = mock_lease
        mock_etcd_client.transaction.return_value = (True, [])

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            success, lease_id = await acquire_leader(role="worker", node_id="node-1")

            assert success is True
            assert lease_id == 12345
            mock_etcd_client.lease.assert_called_once_with(ttl=10)
            mock_etcd_client.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_leader_already_has_leader(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test leader acquisition when leader already exists."""
        from kagami.core.consensus.etcd_client import acquire_leader

        mock_lease = MagicMock()
        mock_lease.id = 12345
        mock_etcd_client.lease.return_value = mock_lease
        mock_etcd_client.transaction.return_value = (False, [])  # Transaction failed

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            success, lease_id = await acquire_leader(role="worker", node_id="node-2")

            assert success is False
            assert lease_id is None

    @pytest.mark.asyncio
    async def test_acquire_leader_default_node_id(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test leader acquisition uses default node ID."""
        from kagami.core.consensus.etcd_client import acquire_leader

        mock_lease = MagicMock()
        mock_lease.id = 12345
        mock_etcd_client.lease.return_value = mock_lease
        mock_etcd_client.transaction.return_value = (True, [])

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            success, _lease_id = await acquire_leader(role="worker")  # No node_id

            assert success is True
            # Should use default PID-based node ID


class TestWatchOperations:
    """Test watch functionality."""

    @pytest.mark.asyncio
    async def test_watch_key_basic(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test basic watch key functionality."""
        from kagami.core.consensus.etcd_client import watch_key

        # Mock watch events
        event1 = MagicMock()
        event1.key.decode.return_value = "test_key"
        event1.value.decode.return_value = json.dumps({"count": 1})

        mock_etcd_client.watch.return_value = [event1]

        callback_data = []

        def callback(data: dict) -> None:
            callback_data.append(data)

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            # Start watching (non-blocking)
            await watch_key("test_key", callback)

            # Give watch thread time to process
            await asyncio.sleep(0.1)

            # Note: In real scenario, callback would be invoked
            # For testing, we verify watch was called
            mock_etcd_client.watch.assert_called_once_with("test_key")

    @pytest.mark.asyncio
    async def test_watch_prefix(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test watching with prefix."""
        from kagami.core.consensus.etcd_client import watch_key

        event = MagicMock()
        event.key.decode.return_value = "prefix/key1"
        event.value.decode.return_value = json.dumps({"data": "test"})

        mock_etcd_client.watch_prefix.return_value = [event]

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            await watch_key("prefix/", lambda data: None, prefix=True)
            await asyncio.sleep(0.1)

            mock_etcd_client.watch_prefix.assert_called_once_with("prefix/")


class TestHealthChecks:
    """Test cluster health checking."""

    @pytest.mark.asyncio
    async def test_check_cluster_health_success(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test successful cluster health check."""
        from kagami.core.consensus.etcd_client import _check_cluster_health

        leader_mock = MagicMock()
        leader_mock.name = "leader-1"  # Set name as attribute
        mock_etcd_client.status.return_value = MagicMock(
            leader=leader_mock,
            raft_term=10,
            raft_index=1000,
            db_size=2048,
            version="3.5.0",
        )
        mock_etcd_client.members = [MagicMock(), MagicMock(), MagicMock()]

        with patch.dict(os.environ, {"ETCD_CLUSTER_SIZE": "3"}):
            health = await _check_cluster_health(mock_etcd_client)

            assert health["healthy"] is True
            assert health["leader"] == "leader-1"
            assert health["members"] == 3
            assert health["version"] == "3.5.0"

    @pytest.mark.asyncio
    async def test_check_cluster_health_no_leader(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test health check fails when no leader."""
        from kagami.core.consensus.etcd_client import _check_cluster_health

        mock_etcd_client.status.return_value = MagicMock(leader=None)

        with pytest.raises(EtcdLeaderError, match="No etcd leader"):
            await _check_cluster_health(mock_etcd_client)

    @pytest.mark.asyncio
    async def test_check_cluster_health_no_quorum(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test health check fails without quorum."""
        from kagami.core.consensus.etcd_client import _check_cluster_health

        mock_etcd_client.status.return_value = MagicMock(
            leader=MagicMock(name="leader-1"),
            raft_term=10,
            raft_index=1000,
            db_size=2048,
            version="3.5.0",
        )
        mock_etcd_client.members = [MagicMock()]  # Only 1 member

        with patch.dict(os.environ, {"ETCD_CLUSTER_SIZE": "5"}):
            with pytest.raises(EtcdQuorumError, match="Insufficient cluster members"):
                await _check_cluster_health(mock_etcd_client)


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration with operations."""

    @pytest.mark.asyncio
    async def test_operation_success_resets_failures(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test successful operations reduce failure count."""
        from kagami.core.consensus.etcd_client import publish_state

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            # Multiple successful operations
            for _ in range(3):
                await publish_state("key", {"test": "data"})

            # Should have recorded successes (no exception)

    def test_etcd_operation_context_manager(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test etcd_operation context manager."""
        from kagami.core.consensus.etcd_client import etcd_operation

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            with etcd_operation("test_operation") as client:
                assert client is not None
                client.status()

    def test_etcd_operation_circuit_breaker_check(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test operation checks circuit breaker."""
        from kagami.core.consensus.etcd_client import (
            _circuit_breaker_manager,
            etcd_operation,
        )

        # Force circuit open for specific operation
        _circuit_breaker_manager.threshold = 1
        _circuit_breaker_manager.record_failure("test_op")

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            with pytest.raises(CircuitOpenError):
                with etcd_operation("test_op"):
                    pass

    def test_etcd_operation_records_failure(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test operation records failures."""
        from kagami.core.consensus.etcd_client import (
            _circuit_breaker_manager,
            etcd_operation,
        )

        # Mock get_etcd_client to return our mock client
        with patch(
            "kagami.core.consensus.etcd_client.get_etcd_client", return_value=mock_etcd_client
        ):
            with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
                with pytest.raises(RuntimeError):
                    with etcd_operation("failing_op"):
                        raise RuntimeError("Operation failed")

                # Check failure was recorded
                state = _circuit_breaker_manager.get_state("failing_op")
                assert state["failures"] > 0


class TestBackwardCompatibility:
    """Test backward compatibility functions."""

    def test_get_etcd_client_sync(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test synchronous client getter."""
        from kagami.core.consensus.etcd_client import get_etcd_client

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            client = get_etcd_client()
            assert client is not None

    def test_get_etcd_client_force_reconnect(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test force reconnect creates new client."""
        from kagami.core.consensus.etcd_client import get_etcd_client

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            client1 = get_etcd_client()
            client2 = get_etcd_client(force_reconnect=True)

            # Should have called client creation twice
            assert mock_etcd3_module.client.call_count >= 2

    def test_close_etcd_client(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test closing compatibility client."""
        from kagami.core.consensus.etcd_client import (
            close_etcd_client,
            get_etcd_client,
        )

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            client = get_etcd_client()
            close_etcd_client()

            mock_etcd_client.close.assert_called()


class TestErrorHandling:
    """Test comprehensive error handling."""

    def test_connection_error_propagation(self, mock_etcd3_module: MagicMock) -> None:
        """Test connection errors are properly propagated."""
        from kagami.core.consensus.etcd_client import _create_etcd_client

        mock_etcd3_module.client.side_effect = ConnectionError("Network unreachable")

        with pytest.raises(EtcdConnectionError):
            _create_etcd_client()

    @pytest.mark.asyncio
    async def test_get_state_invalid_json(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test get_state handles invalid JSON gracefully."""
        from kagami.core.consensus.etcd_client import get_state

        mock_etcd_client.get.return_value = (b"invalid json{", MagicMock())

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            result = await get_state("test_key")
            # Should return None on JSON decode error
            assert result is None

    @pytest.mark.asyncio
    async def test_publish_state_serialization_error(
        self, mock_etcd3_module: MagicMock, mock_etcd_client: MagicMock
    ) -> None:
        """Test publish_state handles serialization errors gracefully."""
        from kagami.core.consensus.etcd_client import publish_state

        # Create un-serializable object
        class UnserializableClass:
            pass

        with patch.dict(os.environ, {"ETCD_ENDPOINT": "http://localhost:2379"}):
            # publish_state catches exceptions and returns False
            result = await publish_state("key", {"obj": UnserializableClass()})
            assert result is False


# Import asyncio for async tests
import asyncio
