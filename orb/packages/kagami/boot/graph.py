from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI


# OPTIMIZED (Dec 28, 2025): Define BootGraphError locally to avoid importing
# kagami.core.exceptions which triggers heavy kagami.core imports (583ms saved)
class BootGraphError(Exception):
    """Boot graph execution error (lightweight local definition)."""

    pass


# Use Any for FastAPI parameter to avoid type conflicts with imports
BootCallable = Callable[[Any], Awaitable[None]]
HealthCallable = Callable[[Any], Mapping[str, Any] | Awaitable[Mapping[str, Any]]]


class BootGraphExecutionError(BootGraphError):
    """Raised when a boot node fails to start."""

    def __init__(self, node: str, error: Exception, report: BootGraphReport):
        self.node = node
        self.original = error
        self.report = report
        super().__init__(f"Boot graph node '{node}' failed: {error}")


@dataclass(frozen=True)
class BootNode:
    """Declarative definition of an initialization step."""

    name: str
    start: BootCallable
    stop: BootCallable | None = None
    dependencies: Sequence[str] = field(default_factory=tuple[Any, ...])
    health_check: HealthCallable | None = None
    # Reliability knobs (optional; keep defaults non-invasive)
    #
    # - timeout_s: hard cap for a node's start() coroutine (prevents hangs)
    # - retries: number of retry attempts after the first failure
    # - retry_backoff_s: base backoff between retries (exponential, best-effort)
    timeout_s: float | None = None
    retries: int = 0
    retry_backoff_s: float = 0.5


@dataclass
class BootNodeStatus:
    """Execution metadata for a boot node."""

    success: bool
    started_at: float
    duration_ms: float
    error: str | None = None
    attempts: int = 1
    timed_out: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "started_at": self.started_at,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "attempts": self.attempts,
            "timed_out": self.timed_out,
        }


@dataclass
class BootGraphReport:
    """Aggregated execution report for a boot graph run."""

    statuses: dict[str, BootNodeStatus] = field(default_factory=dict[str, Any])

    @property
    def success(self) -> bool:
        return all(status.success for status in self.statuses.values())

    def as_dict(self) -> dict[str, dict[str, Any]]:
        return {name: status.as_dict() for name, status in self.statuses.items()}


class BootGraph:
    """Declarative boot graph orchestrating K os subsystem startup.

    The boot graph executes nodes concurrently while respecting dependency order.
    Each node can define start/stop actions and health checks.

    API Surface:
        - Constructor requires at least one BootNode
        - Use ``.start(app)`` to execute the boot sequence
        - Use ``.stop(app)`` to shutdown in reverse order
        - Use ``.health(app)`` to run health checks

    Example:
        >>> async def start_db(app): ...
        >>> async def start_cache(app): ...
        >>> graph = BootGraph([
        ...     BootNode(name="database", start=start_db),
        ...     BootNode(name="cache", start=start_cache, dependencies=["database"]),
        ... ])
        >>> report = await graph.start(app)
        >>> assert report.success

    Note:
        The constructor requires an iterable of BootNode instances.
        An empty graph will raise ValueError.
    """

    def __init__(self, nodes: Iterable[BootNode]) -> None:
        """Initialize the boot graph.

        Args:
            nodes: Iterable of BootNode instances defining the boot sequence.
                   Must contain at least one node.

        Raises:
            ValueError: If nodes is empty or contains duplicates.
        """
        node_list = list(nodes)
        if not node_list:
            raise ValueError("BootGraph requires at least one node.")
        self._nodes: dict[str, BootNode] = {}
        for node in node_list:
            if node.name in self._nodes:
                raise ValueError(f"Duplicate boot node: {node.name}")
            self._nodes[node.name] = node
        self._started_order: list[str] = []

    def _topological_order(self) -> list[str]:
        incoming: dict[str, set[str]] = {
            name: set(node.dependencies) for name, node in self._nodes.items()
        }
        for name, deps in incoming.items():
            unknown = deps - self._nodes.keys()
            if unknown:
                raise ValueError(f"Boot node '{name}' depends on unknown nodes: {sorted(unknown)}")
        ready = [name for name, deps in incoming.items() if not deps]
        order: list[str] = []
        while ready:
            node = ready.pop()
            order.append(node)
            for target, deps in incoming.items():
                if node in deps:
                    deps.remove(node)
                    if not deps:
                        ready.append(target)
        if len(order) != len(self._nodes):
            unresolved = [name for name, deps in incoming.items() if deps]
            raise ValueError(f"Boot graph contains cycles: {unresolved}")
        return order

    async def start(self, app: FastAPI) -> BootGraphReport:
        """Execute nodes concurrently respecting declared dependencies."""
        report = BootGraphReport()

        # Verify graph validity first (cycle detection)
        self._topological_order()

        completed: set[str] = set()
        remaining = set(self._nodes.keys())

        while remaining:
            # Identify ready nodes (dependencies met)
            ready_nodes: list[str] = []
            for name in remaining:
                node = self._nodes[name]
                if all(dep in completed for dep in node.dependencies):
                    ready_nodes.append(name)

            if not ready_nodes:
                # Should be caught by _topological_order check, but as a safety:
                raise RuntimeError(f"Boot graph stuck. Remaining: {remaining}")

            # Execute batch concurrently
            async def _run_node(name: str) -> tuple[str, BootNodeStatus]:
                node = self._nodes[name]
                started_at = time.perf_counter()
                attempts = 0
                timed_out = False
                last_exc: Exception | None = None

                # Validate retry configuration defensively
                retries = max(0, int(node.retries))
                backoff = max(0.0, float(node.retry_backoff_s))

                while True:
                    attempts += 1
                    try:
                        if node.timeout_s is not None:
                            await asyncio.wait_for(node.start(app), timeout=float(node.timeout_s))
                        else:
                            await node.start(app)
                        duration = (time.perf_counter() - started_at) * 1000
                        return name, BootNodeStatus(
                            True, started_at, duration, attempts=attempts, timed_out=False
                        )
                    except TimeoutError as exc:
                        timed_out = True
                        last_exc = exc
                    except Exception as exc:
                        last_exc = exc

                    # retries = number of retries after the first attempt
                    # total_attempts_allowed = 1 + retries
                    if attempts >= retries + 1:
                        duration = (time.perf_counter() - started_at) * 1000
                        error_msg = str(last_exc) if last_exc else "boot_node_failed"
                        if timed_out and not error_msg:
                            # asyncio.TimeoutError string is often empty; include a useful message.
                            error_msg = (
                                f"timeout after {float(node.timeout_s):g}s"
                                if node.timeout_s is not None
                                else "timeout"
                            )
                        status = BootNodeStatus(
                            False,
                            started_at,
                            duration,
                            error=error_msg,
                            attempts=attempts,
                            timed_out=timed_out,
                        )
                        # Persist the failure status so the report is useful even on exceptions.
                        report.statuses[name] = status
                        raise BootGraphExecutionError(
                            name, last_exc or RuntimeError(status.error), report
                        )

                    # Exponential backoff between retries (best-effort; keeps boot responsive).
                    if backoff > 0:
                        await asyncio.sleep(backoff * (2 ** (attempts - 1)))

            # Run the batch
            try:
                results = await asyncio.gather(
                    *[_run_node(name) for name in ready_nodes], return_exceptions=True
                )
            except Exception:
                # Should be handled by return_exceptions=True, but just in case
                raise

            # Process results
            batch_failed = False
            first_error = None

            for result in results:
                if isinstance(result, Exception):
                    batch_failed = True
                    # If it's our custom error, unwrap or use as is
                    if isinstance(result, BootGraphExecutionError):
                        # Update report with what we have
                        # The error already has the node name and report ref
                        first_error = result
                    else:
                        # Unexpected error
                        first_error = result  # type: ignore[assignment]
                else:
                    name, status = result  # type: ignore[misc]
                    report.statuses[name] = status
                    self._started_order.append(name)
                    completed.add(name)
                    remaining.remove(name)

            if batch_failed and first_error:
                if isinstance(first_error, BootGraphExecutionError):
                    # Update the report in the exception with current statuses
                    first_error.report = report
                    raise first_error
                raise first_error

        return report

    async def stop(self, app: FastAPI) -> None:
        """Run registered stop hooks in reverse order."""
        while self._started_order:
            name = self._started_order.pop()
            node = self._nodes[name]
            if node.stop is None:
                continue
            try:
                if node.timeout_s is not None:
                    await asyncio.wait_for(node.stop(app), timeout=float(node.timeout_s))
                else:
                    await node.stop(app)
            except Exception:  # pragma: no cover - best effort teardown
                # Errors during shutdown are logged by the caller; keep graph resilient.
                continue

    async def health(self, app: FastAPI) -> dict[str, Mapping[str, Any]]:
        """Collect health snapshots from nodes that expose a health check."""
        snapshots: dict[str, Mapping[str, Any]] = {}
        for name, node in self._nodes.items():
            if node.health_check is None:
                continue
            try:
                result = node.health_check(app)
                if asyncio.iscoroutine(result):
                    result = await result
                snapshots[name] = dict(result)  # type: ignore[arg-type]
            except Exception:
                snapshots[name] = {"healthy": False, "error": "health_check_failed"}
        return snapshots


__all__ = [
    "BootGraph",
    "BootGraphExecutionError",
    "BootGraphReport",
    "BootNode",
    "BootNodeStatus",
]
