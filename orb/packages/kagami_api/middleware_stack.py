from __future__ import annotations

import graphlib
import importlib
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

MiddlewareKind = Literal["http", "add"]

_TRUTHY = ("1", "true", "yes", "on")


def _always_enabled() -> bool:
    return True


def _tracing_enabled() -> bool:
    return os.getenv("ENABLE_TRACING", "0").lower() in ("1", "true", "yes")


def _lightweight_startup() -> bool:
    """Lightweight startup mode should minimize per-request overhead."""
    return os.getenv("LIGHTWEIGHT_STARTUP", "0").lower() in _TRUTHY


def _not_lightweight_startup() -> bool:
    return not _lightweight_startup()


def _feature_gates_enabled() -> bool:
    return os.getenv("ENABLE_FEATURE_GATES", "0").lower() in ("1", "true", "yes")


@dataclass(frozen=True)
class MiddlewareSpec:
    """Declarative description for middleware registration with dependency tracking."""

    name: str
    target: str  # e.g. "kagami.api.idempotency:idempotency_middleware"
    kind: MiddlewareKind
    enabled: Callable[[], bool] = _always_enabled
    success_log: str | None = None
    failure_log_level: int = logging.WARNING
    # Dependencies: names of middlewares that must be added BEFORE this one.
    # (i.e., this middleware wraps the dependencies, making it Outer)
    depends_on: frozenset[str] = field(default_factory=frozenset)


# Dependency Graph Definition
# Add Order: Inner -> Outer
# Request Flow: Outer -> Inner
STACK: tuple[MiddlewareSpec, ...] = (
    MiddlewareSpec(
        name="Correlation ID",
        target="kagami_api.correlation:correlation_middleware",
        kind="http",
        success_log="✓ Correlation ID middleware enabled (X-Request-ID, X-Correlation-ID)",
        depends_on=frozenset(),  # Innermost - first to run, adds IDs to all requests
    ),
    MiddlewareSpec(
        name="Feature gates",
        target="kagami_api.feature_gate:feature_gate_middleware",
        kind="http",
        enabled=_feature_gates_enabled,
        success_log="✓ Feature gate middleware enabled",
        failure_log_level=logging.DEBUG,
        depends_on=frozenset({"Correlation ID"}),
    ),
    MiddlewareSpec(
        name="Tenant quota",
        target="kagami_api.tenant_quota:tenant_quota_middleware",
        kind="http",
        success_log="✓ Tenant quota middleware enabled (X-Quota-Policy headers)",
        depends_on=frozenset({"Feature gates", "Correlation ID"}),
    ),
    MiddlewareSpec(
        name="Idempotency",
        target="kagami_api.idempotency:idempotency_middleware",
        kind="http",
        success_log="✓ Idempotency middleware enabled",
        depends_on=frozenset({"Tenant quota"}),
    ),
    MiddlewareSpec(
        name="Rate limiting",
        target="kagami_api.rate_limiter:rate_limit_middleware",
        kind="http",
        success_log="✓ Rate limiting middleware enabled",
        depends_on=frozenset({"Idempotency"}),
    ),
    MiddlewareSpec(
        name="Telemetry",
        target="kagami_api.middleware.telemetry:TelemetryMiddleware",
        kind="add",
        enabled=_not_lightweight_startup,
        success_log="✓ Telemetry middleware enabled (request tracing)",
        depends_on=frozenset({"Rate limiting"}),
    ),
    MiddlewareSpec(
        name="Tracing",
        target="kagami_api.middleware.telemetry:TracingMiddleware",
        kind="add",
        enabled=_tracing_enabled,
        success_log="✓ Distributed tracing middleware enabled",
        failure_log_level=logging.DEBUG,
        depends_on=frozenset({"Telemetry"}),
    ),
    # Response Caching (Dec 4, 2025) - ETag and Cache-Control headers
    MiddlewareSpec(
        name="Response Cache",
        target="kagami_api.response_cache:response_cache_middleware",
        kind="http",
        enabled=_not_lightweight_startup,
        success_log="✓ Response cache middleware enabled (ETags, Cache-Control)",
        depends_on=frozenset({"Tracing"}),  # Outermost - wraps all
    ),
)


def configure_gateway_middlewares(app: Any, *, logger: logging.Logger | None = None) -> None:
    """Install the canonical middleware stack using topological sort.

    Ensures deterministic ordering: Inner (App) -> ... -> Outer (Security)
    """

    log = logger or logging.getLogger(__name__)

    # Build dependency graph
    graph = {spec.name: spec.depends_on for spec in STACK}

    # Map names to specs
    spec_map = {spec.name: spec for spec in STACK}

    try:
        sorter = graphlib.TopologicalSorter(graph)
        # Prepare static order list (consumed in order)
        ordered_names = list(sorter.static_order())
    except graphlib.CycleError as e:
        log.error(f"Middleware dependency cycle detected: {e}")
        # Fallback to linear order (risky but prevents crash)
        ordered_names = [s.name for s in STACK]

    log.debug(f"Middleware add order: {ordered_names}")

    for name in ordered_names:
        if name not in spec_map:
            # Might happen if we have deps on non-existent nodes (shouldn't in static tuple)
            continue

        spec = spec_map[name]

        if not spec.enabled():
            log.debug("Skipped %s middleware (feature disabled)", spec.name)
            continue

        module_name, attr_name = spec.target.split(":")
        try:
            module = importlib.import_module(module_name)
            target = getattr(module, attr_name)

            if spec.kind == "http":
                app.middleware("http")(target)
            elif spec.kind == "add":
                app.add_middleware(target)
            else:
                raise ValueError(f"Unknown middleware kind '{spec.kind}' for {spec.name}")

            if spec.success_log:
                log.info(spec.success_log)
        except Exception as exc:
            log.log(
                spec.failure_log_level,
                "Failed to enable %s middleware: %s",
                spec.name,
                exc,
            )


__all__ = ["STACK", "MiddlewareSpec", "configure_gateway_middlewares"]
