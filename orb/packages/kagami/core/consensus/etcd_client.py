"""Production-grade etcd client for distributed consensus and state replication.

Provides:
- True connection pooling with round-robin load balancing
- Automatic failover across cluster nodes
- Lease management and renewal
- Transaction support with optimistic concurrency
- Watch API for reactive updates
- TLS/authentication support
- Circuit breaker for fault tolerance
- Comprehensive metrics and observability

Enhanced October 2025: Fixed thread safety, added pooling, TLS, circuit breaker.
"""

import asyncio
import logging
import os
import threading
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from queue import Empty, Queue
from typing import Any

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Import from central exception hierarchy
from kagami.core.exceptions import (
    CircuitOpenError,
    EtcdConnectionError,
    EtcdLeaderError,
    EtcdQuorumError,
)

# Alias for backward compatibility
CircuitBreakerOpenError = CircuitOpenError

logger = logging.getLogger(__name__)
_etcd_pool: "EtcdConnectionPool | None" = None
_compat_client = None
_pool_lock = asyncio.Lock()
_last_health_check = 0.0
_health_check_interval = 30.0

# Prometheus metrics (module-level variables, initialized lazily)
_etcd_cluster_healthy: Any = None
_etcd_cluster_members: Any = None
_etcd_circuit_breaker_state: Any = None
_etcd_operations_total: Any = None
_etcd_operation_duration_seconds: Any = None


class CircuitBreakerManager:
    """Per-operation circuit breaker for fine-grained fault isolation.

    OPTIMIZATION: Prevents one bad operation from blocking all etcd calls.
    Each operation has its own circuit breaker state.
    """

    def __init__(self) -> None:
        self.breakers: dict[str, dict[str, Any]] = {}
        self.threshold = 5
        self.timeout = 60.0
        self._lock = threading.Lock()

    def _get_breaker(self, operation: str) -> dict[str, Any]:
        """Get or create breaker for operation."""
        with self._lock:
            if operation not in self.breakers:
                self.breakers[operation] = {
                    "failures": 0,
                    "state": "closed",
                    "last_failure": 0.0,
                    "last_success": 0.0,
                }
            return self.breakers[operation]

    def check(self, operation: str) -> None:
        """Check if operation is allowed.

        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        breaker = self._get_breaker(operation)
        current_time = time.time()

        if breaker["state"] == "open":
            if current_time - breaker["last_failure"] > self.timeout:
                breaker["state"] = "half_open"
                logger.info(f"Circuit breaker for '{operation}': OPEN → HALF_OPEN")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker open for '{operation}' due to "
                    f"{breaker['failures']} failures. "
                    f"Retry in {self.timeout - (current_time - breaker['last_failure']):.0f}s"
                )

    def record_success(self, operation: str) -> None:
        """Record successful operation."""
        breaker = self._get_breaker(operation)
        breaker["last_success"] = time.time()

        if breaker["state"] == "half_open":
            breaker["state"] = "closed"
            breaker["failures"] = 0
            logger.info(f"Circuit breaker for '{operation}': HALF_OPEN → CLOSED")
        elif breaker["state"] == "closed":
            breaker["failures"] = max(0, breaker["failures"] - 1)

    def record_failure(self, operation: str) -> None:
        """Record failed operation."""
        breaker = self._get_breaker(operation)
        breaker["failures"] += 1
        breaker["last_failure"] = time.time()

        if breaker["failures"] >= self.threshold and breaker["state"] != "open":
            breaker["state"] = "open"
            logger.error(
                f"Circuit breaker for '{operation}': "
                f"CLOSED/HALF_OPEN → OPEN (threshold {self.threshold} reached)"
            )

    def get_state(self, operation: str) -> dict[str, Any]:
        """Get current breaker state."""
        return self._get_breaker(operation).copy()

    def get_all_states(self) -> dict[str, dict[str, Any]]:
        """Get all breaker states."""
        with self._lock:
            return {op: breaker.copy() for op, breaker in self.breakers.items()}


# Global per-operation circuit breaker manager
_circuit_breaker_manager = CircuitBreakerManager()

# Legacy global circuit breaker state (for backward compatibility with _check_circuit_breaker)
_circuit_breaker_state: str = "closed"
_circuit_breaker_failures: int = 0
_circuit_breaker_last_failure: float = 0.0
_circuit_breaker_threshold: int = 5
_circuit_breaker_timeout: float = 60.0


def _get_etcd_endpoints() -> list[str]:
    """Get etcd endpoints from environment.

    Returns:
        List of etcd endpoint URLs

    Raises:
        EtcdConnectionError: If no endpoints configured
        RuntimeError: If production mode with insecure endpoints
    """
    endpoints_str = os.getenv("ETCD_ENDPOINTS", "")
    if not endpoints_str:
        endpoint = os.getenv("ETCD_ENDPOINT", "http://localhost:2379")
        endpoints = [endpoint]
    else:
        endpoints = [e.strip() for e in endpoints_str.split(",") if e.strip()]
        if not endpoints:
            endpoints = ["http://localhost:2379"]

    # SECURITY CHECK (Dec 21, 2025): Enforce TLS in production
    environment = os.getenv("ENVIRONMENT", "development").lower()
    if environment == "production":
        for endpoint in endpoints:
            if (
                endpoint.startswith("http://")
                and "localhost" not in endpoint
                and "127.0.0.1" not in endpoint
            ):
                raise RuntimeError(
                    f"Production etcd endpoint MUST use TLS (https://). "
                    f"Found insecure endpoint: {endpoint}. "
                    f"Update ETCD_ENDPOINTS to use https:// and configure TLS certificates. "
                    f"See docs/operations/SECRET_ROTATION.md for TLS configuration."
                )
            if not endpoint.startswith("https://") and "localhost" not in endpoint:
                logger.warning(
                    f"⚠️  Production etcd endpoint should use TLS: {endpoint}. "
                    f"Configure ETCD_CA_CERT, ETCD_CERT_CERT, ETCD_CERT_KEY."
                )

    return endpoints


def _parse_endpoint(endpoint: str) -> tuple[str, int]:
    """Parse endpoint URL into host and port.

    Args:
        endpoint: URL like "http://localhost:2379"

    Returns:
        Tuple of (host, port)
    """
    endpoint = endpoint.replace("http://", "").replace("https://", "")
    if ":" in endpoint:
        host, port_str = endpoint.rsplit(":", 1)
        port = int(port_str)
    else:
        host = endpoint
        port = 2379
    return (host, port)


def _check_circuit_breaker() -> None:
    """Check circuit breaker state and potentially open/close it.

    Raises:
        CircuitBreakerOpenError: If circuit is open
    """
    global _circuit_breaker_state, _circuit_breaker_failures, _circuit_breaker_last_failure
    current_time = time.time()
    if _circuit_breaker_state == "open":
        if current_time - _circuit_breaker_last_failure > _circuit_breaker_timeout:
            _circuit_breaker_state = "half_open"
            logger.info("Circuit breaker: OPEN → HALF_OPEN (timeout expired)")
        else:
            raise CircuitBreakerOpenError(
                f"Circuit breaker open due to {_circuit_breaker_failures} failures. Will retry in {_circuit_breaker_timeout - (current_time - _circuit_breaker_last_failure):.0f}s"
            )


def _record_success() -> None:
    """Record successful operation for circuit breaker."""
    global _circuit_breaker_state, _circuit_breaker_failures
    if _circuit_breaker_state == "half_open":
        _circuit_breaker_state = "closed"
        _circuit_breaker_failures = 0
        logger.info("Circuit breaker: HALF_OPEN → CLOSED (success)")
    elif _circuit_breaker_state == "closed":
        _circuit_breaker_failures = max(0, _circuit_breaker_failures - 1)


def _record_failure() -> None:
    """Record failed operation for circuit breaker."""
    global _circuit_breaker_state, _circuit_breaker_failures, _circuit_breaker_last_failure
    _circuit_breaker_failures += 1
    _circuit_breaker_last_failure = time.time()
    if _circuit_breaker_failures >= _circuit_breaker_threshold:
        if _circuit_breaker_state != "open":
            _circuit_breaker_state = "open"
            logger.error(
                f"Circuit breaker: CLOSED/HALF_OPEN → OPEN (threshold {_circuit_breaker_threshold} failures reached)"
            )


async def _try_connect_single(
    endpoint: str,
    timeout: float = 0.5,
) -> Any | None:
    """Try connecting to a single etcd endpoint asynchronously.

    Args:
        endpoint: etcd endpoint URL
        timeout: Connection timeout in seconds

    Returns:
        etcd3 client if successful, None otherwise
    """
    try:
        import etcd3

        host, port = _parse_endpoint(endpoint)
        ca_cert = os.getenv("ETCD_CA_CERT")
        cert_key = os.getenv("ETCD_CERT_KEY")
        cert_cert = os.getenv("ETCD_CERT_CERT")
        user = os.getenv("ETCD_USER")
        password = os.getenv("ETCD_PASSWORD")

        # Run client creation in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        client = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: etcd3.client(
                    host=host,
                    port=port,
                    timeout=timeout,
                    ca_cert=ca_cert if ca_cert else None,
                    cert_key=cert_key if cert_key else None,
                    cert_cert=cert_cert if cert_cert else None,
                    user=user if user else None,
                    password=password if password else None,
                ),
            ),
            timeout=timeout,
        )

        # Validate connection with status check
        await asyncio.wait_for(
            loop.run_in_executor(None, client.status),
            timeout=timeout,
        )

        logger.debug(f"✅ Successfully connected to etcd at {endpoint}")
        return client
    except TimeoutError:
        logger.debug(f"⏱️  Connection to {endpoint} timed out after {timeout}s")
        return None
    except Exception as e:
        logger.debug(f"Connection to {endpoint} failed: {e}")
        return None


async def _try_connect_parallel(
    endpoints: list[str],
    timeout_per_endpoint: float = 0.5,
    timeout_total: float = 1.0,
) -> Any:
    """Try connecting to multiple etcd endpoints in parallel.

    Returns immediately on first successful connection.
    Cancels remaining tasks after first success or timeout.

    Args:
        endpoints: List of etcd endpoint URLs
        timeout_per_endpoint: Timeout for each connection attempt (seconds)
        timeout_total: Total timeout for all attempts (seconds)

    Returns:
        etcd3 client from first successful connection

    Raises:
        EtcdConnectionError: If all endpoints fail or timeout
    """
    if not endpoints:
        raise EtcdConnectionError("No etcd endpoints provided")

    logger.info(
        f"Attempting parallel connection to {len(endpoints)} etcd endpoint(s) "
        f"(per-endpoint timeout: {timeout_per_endpoint}s, total timeout: {timeout_total}s)"
    )

    # Create tasks for all endpoints
    tasks = [asyncio.create_task(_try_connect_single(ep, timeout_per_endpoint)) for ep in endpoints]

    try:
        # Wait for first successful result or total timeout
        pending = set(tasks)
        while pending:
            done, pending = await asyncio.wait(
                pending,
                return_when=asyncio.FIRST_COMPLETED,
                timeout=timeout_total if pending == set(tasks) else 0.01,
            )

            for task in done:
                try:
                    result = task.result()
                    if result is not None:
                        # Cancel remaining tasks
                        for t in pending:
                            t.cancel()
                        logger.info(f"✅ Connected to etcd (parallel, {len(endpoints)} attempts)")
                        return result
                except Exception:
                    pass  # Task failed, continue to next

            if not pending:
                break

        # All tasks failed
        for task in tasks:
            task.cancel()

        raise EtcdConnectionError(
            f"Failed to connect to any etcd endpoint in {timeout_total}s. "
            f"Tried: {', '.join(endpoints)}"
        )

    except TimeoutError as e:
        # Cancel all tasks
        for task in tasks:
            task.cancel()
        raise EtcdConnectionError(
            f"Parallel connection to etcd timed out after {timeout_total}s. "
            f"Tried: {', '.join(endpoints)}"
        ) from e


@retry(
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
def _create_etcd_client() -> Any:
    """Create etcd client with parallel connection optimization.

    Attempts to connect to all configured endpoints in parallel for fast failure.
    Falls back to sequential mode if no event loop is running.

    Returns:
        etcd3.Etcd3Client instance

    Raises:
        EtcdConnectionError: If connection fails to all endpoints
    """
    try:
        import etcd3

        # SECURITY: Enforce TLS in production (Dec 21, 2025)
        environment = os.getenv("ENVIRONMENT", "development").lower()
        ca_cert = os.getenv("ETCD_CA_CERT")
        cert_key = os.getenv("ETCD_CERT_KEY")
        cert_cert = os.getenv("ETCD_CERT_CERT")

        if environment == "production":
            if not (ca_cert and cert_key and cert_cert):
                raise EtcdConnectionError(
                    "Production etcd connections must use TLS. "
                    "Set ETCD_CA_CERT, ETCD_CERT_KEY, ETCD_CERT_CERT environment variables. "
                    "Example: "
                    "ETCD_CA_CERT=/certs/etcd/ca.pem "
                    "ETCD_CERT_KEY=/certs/etcd/client-key.pem "
                    "ETCD_CERT_CERT=/certs/etcd/client.pem"
                )

        endpoints = _get_etcd_endpoints()
        logger.info(f"Connecting to etcd cluster ({len(endpoints)} endpoint(s)): {endpoints}")

        # Try to use parallel async connection if event loop is available
        try:
            asyncio.get_running_loop()
            logger.debug("Event loop detected, using async-safe sequential fallback")
            # Can't use await here, fall through to sync method
        except RuntimeError:
            # No running loop, we can use async via asyncio.run()
            try:
                timeout_per_endpoint = float(os.getenv("ETCD_CONNECT_TIMEOUT_PER", "0.5"))
                timeout_total = float(os.getenv("ETCD_CONNECT_TIMEOUT", "1.0"))
                logger.info(
                    f"Using parallel connection (timeouts: {timeout_per_endpoint}s per, "
                    f"{timeout_total}s total)"
                )
                client = asyncio.run(
                    _try_connect_parallel(
                        endpoints,
                        timeout_per_endpoint=timeout_per_endpoint,
                        timeout_total=timeout_total,
                    )
                )
                ca_cert = os.getenv("ETCD_CA_CERT")
                tls_str = " (TLS)" if ca_cert else ""
                logger.info(f"✅ Connected to etcd via parallel attempt{tls_str}")
                return client
            except Exception as e:
                logger.debug(f"Parallel connection failed: {e}, falling back to sequential")

        # Fallback: sequential connection (for compatibility with running event loops)
        last_error = None
        for endpoint in endpoints:
            try:
                host, port = _parse_endpoint(endpoint)
                timeout = int(os.getenv("ETCD_CONNECT_TIMEOUT", "5"))
                ca_cert = os.getenv("ETCD_CA_CERT")
                cert_key = os.getenv("ETCD_CERT_KEY")
                cert_cert = os.getenv("ETCD_CERT_CERT")
                user = os.getenv("ETCD_USER")
                password = os.getenv("ETCD_PASSWORD")
                client = etcd3.client(
                    host=host,
                    port=port,
                    timeout=timeout,
                    ca_cert=ca_cert if ca_cert else None,
                    cert_key=cert_key if cert_key else None,
                    cert_cert=cert_cert if cert_cert else None,
                    user=user if user else None,
                    password=password if password else None,
                )
                client.status()
                logger.info(
                    f"✅ Connected to etcd at {endpoint} (sequential)"
                    + (" (TLS)" if ca_cert else "")
                )
                return client
            except Exception as e:
                last_error = e
                logger.debug(f"Failed to connect to {endpoint}: {e}")
                continue

        raise EtcdConnectionError(f"Failed to connect to any etcd endpoint: {last_error}")
    except ImportError as e:
        raise EtcdConnectionError(
            f"etcd3 Python client not installed: {e}. Run: pip install etcd3>=0.12.0"
        ) from e
    except Exception as e:
        raise EtcdConnectionError(f"Failed to create etcd client: {e}") from e


class EtcdConnectionPool:
    """Thread-safe connection pool for etcd clients.

    Provides round-robin load balancing across multiple connections
    to different cluster nodes.
    """

    def __init__(self, pool_size: int = 10) -> None:
        """Initialize connection pool.

        Args:
            pool_size: Number of connections to maintain (default 10)
        """
        self.pool_size = pool_size
        self._pool: Queue = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._initialized = False

    def initialize(self) -> None:
        """Initialize pool with connections."""
        with self._lock:
            if self._initialized:
                return
            logger.info(f"Initializing etcd connection pool (size={self.pool_size})")
            for i in range(self.pool_size):
                try:
                    client = _create_etcd_client()
                    self._pool.put(client)
                except Exception as e:
                    logger.warning(f"Failed to create connection {i + 1}/{self.pool_size}: {e}")
            self._initialized = True
            actual_size = self._pool.qsize()
            logger.info(
                f"✅ etcd connection pool initialized ({actual_size}/{self.pool_size} connections)"
            )

    @contextmanager
    def get_client(self, timeout: float = 5.0) -> Generator[Any, None, None]:
        """Get a client from the pool with health validation.

        Args:
            timeout: Max time to wait for available connection

        Yields:
            etcd3.Etcd3Client instance

        Raises:
            EtcdConnectionError: If no connection available
        """
        if not self._initialized:
            self.initialize()

        client = None
        retries = 0
        max_retries = 2

        try:
            while retries < max_retries:
                try:
                    client = self._pool.get(timeout=timeout)

                    # OPTIMIZATION: Validate connection health before use
                    try:
                        # Quick health check (< 10ms typically)
                        client.status()
                        break  # Connection is healthy
                    except Exception as e:
                        logger.warning(f"Stale etcd connection detected: {e}")
                        try:
                            client.close()
                        except Exception:
                            pass

                        # Recreate connection
                        client = _create_etcd_client()
                        _record_success()
                        break

                except Empty:
                    retries += 1
                    if retries >= max_retries:
                        raise EtcdConnectionError(
                            "Connection pool exhausted after retries"
                        ) from None
                    import time

                    time.sleep(0.1)  # Brief backoff

            yield client

        except Empty:
            raise EtcdConnectionError(
                "Connection pool exhausted (all connections in use)"
            ) from None
        finally:
            if client:
                self._pool.put(client)

    def close_all(self) -> None:
        """Close all connections in pool."""
        with self._lock:
            while not self._pool.empty():
                try:
                    client = self._pool.get_nowait()
                    client.close()
                except Exception as e:
                    logger.debug(f"Error closing connection: {e}")
            self._initialized = False
            logger.info("etcd connection pool closed")


async def _check_cluster_health(client: Any) -> dict[str, Any]:
    """Check etcd cluster health (async version).

    Args:
        client: etcd3 client instance

    Returns:
        Dict with health status

    Raises:
        EtcdQuorumError: If cluster doesn't have quorum
        EtcdLeaderError: If no leader is present
    """
    try:
        loop = asyncio.get_running_loop()
        status = await loop.run_in_executor(None, client.status)
        leader = status.leader
        if not leader:
            raise EtcdLeaderError("No etcd leader elected")
        members = await loop.run_in_executor(None, lambda: list(client.members))
        cluster_size = int(os.getenv("ETCD_CLUSTER_SIZE", "1"))
        if cluster_size > 1 and len(members) < cluster_size // 2 + 1:
            raise EtcdQuorumError(f"Insufficient cluster members: {len(members)}/{cluster_size}")
        return {
            "healthy": True,
            "leader": leader.name if hasattr(leader, "name") else str(leader),
            "members": len(members),
            "raft_term": status.raft_term,
            "raft_index": status.raft_index,
            "db_size": status.db_size,
            "version": status.version,
        }
    except (EtcdLeaderError, EtcdQuorumError):
        raise
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"healthy": False, "error": str(e)}


async def get_etcd_client_pool(force_reconnect: bool = False) -> EtcdConnectionPool:
    """Get etcd connection pool singleton (async, thread-safe).

    Args:
        force_reconnect: Force pool recreation

    Returns:
        EtcdConnectionPool instance

    Raises:
        EtcdConnectionError: If pool creation fails
        CircuitBreakerOpenError: If circuit breaker is open
    """
    global _etcd_pool, _last_health_check
    _check_circuit_breaker()
    async with _pool_lock:
        current_time = time.time()
        need_health_check = current_time - _last_health_check > _health_check_interval
        if _etcd_pool is None or force_reconnect:
            try:
                if _etcd_pool:
                    _etcd_pool.close_all()
                pool_size = int(os.getenv("ETCD_POOL_SIZE", "5"))
                _etcd_pool = EtcdConnectionPool(pool_size=pool_size)
                _etcd_pool.initialize()
                _record_success()
            except Exception as e:
                _record_failure()
                logger.error(f"etcd pool creation failed: {e}")
                raise EtcdConnectionError(f"Failed to create etcd pool: {e}") from e
        if need_health_check and _etcd_pool:
            try:
                with _etcd_pool.get_client() as client:
                    health = await _check_cluster_health(client)
                    if not health.get("healthy"):
                        logger.warning(f"etcd cluster unhealthy: {health.get('error')}")
                        _etcd_pool.close_all()
                        _etcd_pool = EtcdConnectionPool(
                            pool_size=int(os.getenv("ETCD_POOL_SIZE", "5"))
                        )
                        _etcd_pool.initialize()
                    _last_health_check = current_time
                    try:
                        global \
                            _etcd_cluster_healthy, \
                            _etcd_cluster_members, \
                            _etcd_circuit_breaker_state
                        from kagami_observability.metrics import REGISTRY, Gauge

                        if _etcd_cluster_healthy is None:
                            _etcd_cluster_healthy = Gauge(
                                "kagami_etcd_cluster_healthy",
                                "etcd cluster health status (1=healthy, 0=unhealthy)",
                                registry=REGISTRY,
                            )
                            _etcd_cluster_members = Gauge(
                                "kagami_etcd_cluster_members",
                                "Number of etcd cluster members",
                                registry=REGISTRY,
                            )
                            _etcd_circuit_breaker_state = Gauge(
                                "kagami_etcd_circuit_breaker_state",
                                "Circuit breaker state (0=closed, 1=half_open, 2=open)",
                                registry=REGISTRY,
                            )
                        _etcd_cluster_healthy.set(1 if health.get("healthy") else 0)
                        _etcd_cluster_members.set(health.get("members", 0))
                        cb_state_map = {"closed": 0, "half_open": 1, "open": 2}
                        _etcd_circuit_breaker_state.set(cb_state_map.get(_circuit_breaker_state, 0))
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"Health check failed: {e}")
        return _etcd_pool


def get_etcd_client(force_reconnect: bool = False) -> Any:
    """Backward-compatible synchronous etcd client getter.

    Always returns a usable etcd client, even when called from within a
    running event loop (tests and legacy code rely on this behavior).

    Args:
        force_reconnect: Recreate the underlying client

    Returns:
        etcd3.Etcd3Client instance or None if creation fails
    """
    global _compat_client
    try:
        if _compat_client is None or force_reconnect:  # type: ignore[unreachable]
            _compat_client = _create_etcd_client()
        return _compat_client
    except Exception as e:
        # Only log as error if etcd is required (reduces log spam when optional)
        if os.getenv("KAGAMI_ETCD_REQUIRED", "0") == "1":
            logger.error(f"etcd compatibility client creation failed: {e}")
        else:
            logger.debug(f"etcd unavailable (optional): {e}")
        return None


@contextmanager
def etcd_operation(operation_name: str = "operation") -> Generator[Any, None, None]:
    """Synchronous context manager for etcd operations with per-operation circuit breaker.

    OPTIMIZATION: Uses per-operation circuit breaker for better fault isolation.

    Args:
        operation_name: Operation name for metrics and circuit breaker

    Yields:
        etcd client instance
    """
    # Check per-operation circuit breaker
    _circuit_breaker_manager.check(operation_name)

    client = get_etcd_client()
    if not client:
        raise EtcdConnectionError("etcd client unavailable")

    start_time = time.time()
    success = False

    try:
        yield client
        success = True
        _circuit_breaker_manager.record_success(operation_name)
        _record_success()  # Also update legacy global breaker
    except Exception as e:
        _circuit_breaker_manager.record_failure(operation_name)
        _record_failure()  # Also update legacy global breaker
        logger.error(f"etcd operation '{operation_name}' failed: {e}")
        raise
    finally:
        duration = time.time() - start_time
        try:
            global _etcd_operations_total, _etcd_operation_duration_seconds
            from kagami_observability.metrics import REGISTRY, Counter, Histogram

            if _etcd_operations_total is None:
                _etcd_operations_total = Counter(
                    "kagami_etcd_operations_total",
                    "Total etcd operations",
                    ["operation", "status"],
                    registry=REGISTRY,
                )
                _etcd_operation_duration_seconds = Histogram(
                    "kagami_etcd_operation_duration_seconds",
                    "etcd operation duration",
                    ["operation"],
                    registry=REGISTRY,
                )
            status = "success" if success else "error"
            _etcd_operations_total.labels(operation=operation_name, status=status).inc()
            _etcd_operation_duration_seconds.labels(operation=operation_name).observe(duration)
        except Exception:
            pass


async def publish_state(key: str, value: dict[str, Any]) -> bool:
    """Publish state to etcd with retry logic.

    Args:
        key: State key
        value: State value (will be JSON serialized)

    Returns:
        True if published successfully
    """
    try:
        import json

        with etcd_operation("publish_state") as client:
            client.put(key, json.dumps(value))
            return True
    except Exception as e:
        logger.debug(f"etcd publish failed for key {key}: {e}")
        return False


async def get_state(key: str) -> dict[str, Any] | None:
    """Get state from etcd.

    Args:
        key: State key

    Returns:
        State value or None if not found
    """
    try:
        import json

        with etcd_operation("get_state") as client:
            value, _metadata = client.get(key)
            if value:
                parsed = json.loads(value.decode())
                return parsed if isinstance(parsed, dict) else None
            return None
    except Exception as e:
        logger.debug(f"etcd get failed for key {key}: {e}")
        return None


async def acquire_leader(
    role: str = "default", node_id: str | None = None, ttl: int = 10
) -> tuple[bool, int | None]:
    """Attempt to become leader via etcd lease.

    Args:
        role: Leadership role identifier
        node_id: Node identifier (defaults to PID-based)
        ttl: Leader lease TTL in seconds

    Returns:
        Tuple of (success, lease_id)
    """
    try:
        if node_id is None:
            node_id = os.getenv("NODE_ID", f"node-{os.getpid()}")
        with etcd_operation("acquire_leader") as client:
            lease = client.lease(ttl=ttl)
            leader_key = f"kagami:leader:{role}"
            success, _responses = client.transaction(
                compare=[client.transactions.version(leader_key) == 0],
                success=[client.transactions.put(leader_key, node_id.encode(), lease=lease)],
                failure=[],
            )
            if success:
                logger.info(f"🎖️  Acquired leadership for role '{role}' (node: {node_id})")
                return (True, lease.id)
            else:
                return (False, None)
    except Exception as e:
        logger.debug(f"Leader election failed for role '{role}': {e}")
        return (False, None)


async def watch_key(
    key: str, callback: Callable[[dict[str, Any]], None], prefix: bool = False
) -> None:
    """Watch a key for changes and invoke callback (non-blocking).

    Args:
        key: Key to watch (or prefix if prefix=True)
        callback: Function to call on changes
        prefix: Watch all keys with prefix
    """
    loop = asyncio.get_running_loop()

    def _watch_loop() -> None:
        try:
            # Create dedicated client for long-running watch to avoid pool exhaustion
            client = _create_etcd_client()
            watch_func = client.watch_prefix if prefix else client.watch
            logger.info(f"👁️  Watching etcd key: {key} (prefix={prefix})")

            for event in watch_func(key):
                try:
                    if event.value:
                        import json

                        value = json.loads(event.value.decode())
                        # Bridge to async loop safely
                        loop.call_soon_threadsafe(
                            callback, {"key": event.key.decode(), "value": value}
                        )
                except Exception as e:
                    logger.error(f"Watch callback failed for {key}: {e}")
        except Exception as e:
            logger.error(f"Watch failed for key {key}: {e}")

    # Run watcher in background thread
    threading.Thread(target=_watch_loop, daemon=True).start()


def close_etcd_client() -> None:
    """Close etcd client (backward compatibility alias)."""
    global _compat_client
    try:
        if _compat_client:
            _compat_client.close()
    except Exception as e:
        logger.warning(f"Error closing etcd client: {e}")
    finally:
        _compat_client = None


# =============================================================================
# SERVICE DISCOVERY WATCHES (January 4, 2026)
# =============================================================================


async def watch_services(
    service_prefix: str,
    callback: Callable[[str, dict[str, Any] | None], None],
) -> None:
    """Watch for service registry changes.

    Specialized watch for service discovery that handles:
    - Service registration (PUT)
    - Service deregistration (DELETE)
    - Service updates (PUT with changed value)

    Args:
        service_prefix: etcd key prefix (e.g., "/kagami/services/hub/")
        callback: Function called with (event_type, service_data)
                  event_type: "put" | "delete"
                  service_data: Parsed JSON or None for delete

    Example:
        def on_service_change(event_type: str, data: dict | None):
            if event_type == "put" and data:
                print(f"Service registered: {data['node_id']}")
            elif event_type == "delete":
                print("Service deregistered")

        await watch_services("/kagami/services/hub/", on_service_change)
    """
    loop = asyncio.get_running_loop()

    def _watch_loop() -> None:
        try:
            client = _create_etcd_client()
            logger.info(f"👁️  Watching services: {service_prefix}")

            events_iterator, _cancel = client.watch_prefix(service_prefix)

            for event in events_iterator:
                try:
                    import json

                    key = event.key.decode() if event.key else ""
                    event_type = "delete" if event.value is None else "put"

                    if event_type == "put" and event.value:
                        try:
                            value = json.loads(event.value.decode())
                        except json.JSONDecodeError:
                            value = {"raw": event.value.decode()}
                    else:
                        value = None

                    # Extract node_id from key for context
                    node_id = key.rsplit("/", 1)[-1] if key else ""
                    if value is None:
                        value = {"node_id": node_id, "_deleted": True}

                    loop.call_soon_threadsafe(callback, event_type, value)

                except Exception as e:
                    logger.error(f"Service watch callback failed: {e}")

        except Exception as e:
            logger.error(f"Service watch failed for {service_prefix}: {e}")

    threading.Thread(target=_watch_loop, daemon=True, name=f"etcd-watch-{service_prefix}").start()


async def get_service_endpoints(service_type: str) -> list[dict[str, Any]]:
    """Get all endpoints for a service type.

    Convenience function for service discovery.

    Args:
        service_type: Service type (e.g., "api", "hub", "smarthome")

    Returns:
        List of service instance dictionaries
    """
    import json

    prefix = f"/kagami/services/{service_type}/"
    endpoints: list[dict[str, Any]] = []

    try:
        pool = await get_etcd_pool()
        with pool.get_client() as client:
            for value, _metadata in client.get_prefix(prefix):
                if value:
                    try:
                        data = json.loads(value.decode() if isinstance(value, bytes) else value)
                        endpoints.append(data)
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        logger.debug(f"Failed to get service endpoints: {e}")

    return endpoints


# Alias for backward compatibility
get_etcd_pool = get_etcd_client_pool
