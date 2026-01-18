"""Prometheus metrics integration for K os."""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from ipaddress import ip_address, ip_network
from typing import TYPE_CHECKING, Any, Literal

try:
    # FastAPI is an OPTIONAL dependency for kagami-observability.
    # Kagami core should be installable without pulling in FastAPI; only users
    # wiring the /metrics endpoint need it.
    from fastapi import FastAPI, Request, Response, status  # type: ignore

    _FASTAPI_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    _FASTAPI_AVAILABLE = False
    if TYPE_CHECKING:  # pragma: no cover
        from fastapi import (  # type: ignore[no-redef]
            FastAPI,
            Request,
            Response,
            status,
        )
    else:
        FastAPI = Any  # type: ignore[assignment,misc]
        Request = Any  # type: ignore[assignment,misc]
        Response = Any  # type: ignore[assignment,misc]
        status = None  # type: ignore[assignment]

if TYPE_CHECKING:
    from kagami_observability.types import CounterProtocol, GaugeProtocol, HistogramProtocol

logger = logging.getLogger(__name__)

# =============================================================================
# CARDINALITY GUARD
# =============================================================================

# Global cardinality tracker
_cardinality_tracker: dict[str, set[tuple]] = defaultdict(set)
_cardinality_lock = threading.Lock()
_cardinality_warnings_sent: set[str] = set()

# Cardinality limits
CARDINALITY_LIMIT = int(os.getenv("METRICS_CARDINALITY_LIMIT", "1000"))
CARDINALITY_WARNING_THRESHOLD = int(os.getenv("METRICS_CARDINALITY_WARNING_THRESHOLD", "800"))


def check_cardinality(metric_name: str, label_values: tuple) -> bool:
    """Check if adding this label combination would exceed cardinality limit.

    Args:
        metric_name: Name of the metric
        label_values: Tuple of label values (in consistent order)

    Returns:
        True if safe to add, False if limit exceeded
    """
    with _cardinality_lock:
        current_combinations = _cardinality_tracker[metric_name]

        # If we've already seen this combination, it's safe
        if label_values in current_combinations:
            return True

        # Check if we're at the limit
        if len(current_combinations) >= CARDINALITY_LIMIT:
            logger.error(
                f"Cardinality limit exceeded for metric '{metric_name}': "
                f"{len(current_combinations)} >= {CARDINALITY_LIMIT}. "
                f"Rejecting new label combination: {label_values}"
            )
            return False

        # Add the new combination
        current_combinations.add(label_values)

        # Warn if approaching limit
        if (
            len(current_combinations) >= CARDINALITY_WARNING_THRESHOLD
            and metric_name not in _cardinality_warnings_sent
        ):
            logger.warning(
                f"Metric '{metric_name}' approaching cardinality limit: "
                f"{len(current_combinations)}/{CARDINALITY_LIMIT} unique label combinations"
            )
            _cardinality_warnings_sent.add(metric_name)

        return True


def get_cardinality_stats() -> dict[str, int]:
    """Get current cardinality statistics for all metrics.

    Returns:
        Dict mapping metric names to their unique label combination counts
    """
    with _cardinality_lock:
        return {
            metric_name: len(combinations)
            for metric_name, combinations in _cardinality_tracker.items()
        }


def reset_cardinality_tracking() -> None:
    """Reset cardinality tracking (for testing)."""
    with _cardinality_lock:
        _cardinality_tracker.clear()
        _cardinality_warnings_sent.clear()


def _get_metrics_helpers() -> None:
    """Lazy import of metrics helpers to avoid circular dependency."""
    from kagami_observability.metrics import REGISTRY, get_prometheus_metrics
    from kagami_observability.metrics.core import Counter, Gauge, Histogram

    return REGISTRY, get_prometheus_metrics, Counter, Gauge, Histogram  # type: ignore[return-value]


# Lazy initialization of module-level metrics
_METRICS_INITIALIZED = False
METRICS_SCRAPE_DURATION_SECONDS: HistogramProtocol | None = None
METRICS_SCRAPE_SIZE_BYTES: GaugeProtocol | None = None
METRICS_SCRAPE_TOTAL: CounterProtocol | None = None


def _init_module_metrics() -> None:
    """Initialize module-level metrics (called lazily)."""
    global _METRICS_INITIALIZED, METRICS_SCRAPE_DURATION_SECONDS
    global METRICS_SCRAPE_SIZE_BYTES, METRICS_SCRAPE_TOTAL

    if _METRICS_INITIALIZED:
        return

    REGISTRY, _, Counter, Gauge, Histogram = _get_metrics_helpers()  # type: ignore[func-returns-value]

    METRICS_SCRAPE_DURATION_SECONDS = Histogram(
        "kagami_metrics_scrape_duration_seconds",
        "Duration to generate /metrics response",
        registry=REGISTRY,
    )
    METRICS_SCRAPE_SIZE_BYTES = Gauge(
        "kagami_metrics_scrape_size_bytes",
        "Size of /metrics response in bytes",
        registry=REGISTRY,
    )
    METRICS_SCRAPE_TOTAL = Counter(
        "kagami_metrics_scrape_total",
        "Total /metrics endpoint scrapes",
        ["cache_status"],
        registry=REGISTRY,
    )

    _METRICS_INITIALIZED = True


CacheStatus = Literal["hit", "miss", "stale", "error"]


@dataclass(slots=True)
class _MetricsCache:
    payload: bytes = b""
    generated_at_monotonic: float = 0.0


def _parse_ttl_env() -> tuple[float, float, float]:
    """Parse cache TTL configuration (ms) with sane fallbacks."""

    def _to_float(env_key: str, default: float) -> float:
        try:
            return float(os.getenv(env_key, str(default)))
        except Exception:
            logger.debug("Invalid %s value; using default %.2f", env_key, default)
            return default

    ttl_default = 500.0
    ttl_min = _to_float("METRICS_CACHE_TTL_MIN_MS", 200.0)
    ttl_max = _to_float("METRICS_CACHE_TTL_MAX_MS", 3000.0)

    if ttl_min <= 0:
        ttl_min = 50.0
    if ttl_max < ttl_min:
        ttl_max = max(ttl_min, 1000.0)

    ttl = _to_float("METRICS_CACHE_TTL_MS", ttl_default)
    ttl = min(max(ttl, ttl_min), ttl_max)

    return ttl, ttl_min, ttl_max


def _load_allowlist() -> tuple[list[str], list[ip_network]]:  # type: ignore[valid-type]
    """Derive hostname and CIDR allow-lists for /metrics exposure."""

    raw = (os.getenv("METRICS_ALLOW_IPS") or "").replace(",", " ")
    host_tokens = [token.strip() for token in raw.split() if token.strip()]

    hostname_allow = {"localhost", "testclient"}
    network_allow: list[ip_network] = [  # type: ignore[valid-type]
        ip_network("127.0.0.1/32"),
        ip_network("::1/128"),
    ]

    for token in host_tokens:
        try:
            network_allow.append(ip_network(token, strict=False))
            continue
        except ValueError:
            pass
        try:
            network_allow.append(ip_network(f"{token}/32", strict=False))
            continue
        except ValueError:
            hostname_allow.add(token.lower())

    return sorted(hostname_allow), network_allow


def _client_allowed(
    request: Request,
    public_enabled: bool,
    allowed_hostnames: list[str],
    allowed_networks: list[ip_network],  # type: ignore[valid-type]
) -> bool:
    if public_enabled:
        return True

    client_host = getattr(request.client, "host", "") or ""
    if not client_host:
        # Internal requests (lifespan/tests) are allowed by default
        return True

    client_host_lower = client_host.lower()
    if client_host_lower in allowed_hostnames:
        return True

    forwarded = request.headers.get("X-Forwarded-For")
    forwarded_hosts = [h.strip() for h in forwarded.split(",") if h.strip()] if forwarded else []
    probe_hosts = [client_host, *forwarded_hosts]

    for host in probe_hosts:
        try:
            addr = ip_address(host.strip())
        except ValueError:
            continue
        if any(addr in network for network in allowed_networks):  # type: ignore[attr-defined]
            return True

    return False


def init_metrics(app: FastAPI) -> None:
    """Initialize Prometheus metrics endpoint with caching and guardrails."""
    if not _FASTAPI_AVAILABLE:  # pragma: no cover
        raise ImportError(
            "fastapi is required to use kagami_observability.metrics_prometheus.init_metrics(). "
            "Install FastAPI (or install Kagami with the 'api' extra)."
        )
    # Initialize module-level metrics
    _init_module_metrics()

    if getattr(app.state, "metrics_endpoint_initialized", False):
        logger.debug("/metrics endpoint already initialized; skipping duplicate wiring")
        return

    # Defensive: avoid double registration if routes already contain /metrics
    for route in app.router.routes:
        try:
            if getattr(route, "path", None) == "/metrics":
                app.state.metrics_endpoint_initialized = True
                app.state.metrics_initialized = True
                logger.debug("Existing /metrics route detected; marking as initialized")
                return
        except Exception:
            continue

    ttl_ms, ttl_min_ms, ttl_max_ms = _parse_ttl_env()
    allowed_hostnames, allowed_networks = _load_allowlist()
    public_enabled = os.getenv("METRICS_PUBLIC", "0").lower() in ("1", "true", "yes", "on")

    cache = _MetricsCache()
    lock = threading.Lock()

    def _render_metrics() -> bytes:
        """Generate Prometheus payload from registry."""
        _, get_prometheus_metrics, _, _, _ = _get_metrics_helpers()  # type: ignore[func-returns-value]

        text = get_prometheus_metrics()
        if not isinstance(text, str):
            text = str(text)
        payload = text.encode("utf-8")
        if METRICS_SCRAPE_SIZE_BYTES:
            METRICS_SCRAPE_SIZE_BYTES.set(len(payload))
        return payload

    async def _metrics_endpoint(request: Request) -> Response:
        start = time.perf_counter()
        cache_status: CacheStatus = "hit"

        if not _client_allowed(request, public_enabled, allowed_hostnames, allowed_networks):
            if METRICS_SCRAPE_TOTAL:
                METRICS_SCRAPE_TOTAL.labels("error").inc()  # type: ignore[call-arg]
            logger.warning(
                "/metrics access denied for host=%s", getattr(request.client, "host", "unknown")
            )
            return Response(status_code=status.HTTP_403_FORBIDDEN)

        try:
            with lock:
                now = time.monotonic()
                age_ms = (
                    (now - cache.generated_at_monotonic) * 1000 if cache.payload else float("inf")
                )
                need_refresh = age_ms >= ttl_ms

                if not cache.payload or need_refresh:
                    cache_status = "miss"
                    payload = _render_metrics()
                    cache.payload = payload
                    cache.generated_at_monotonic = now
                else:
                    payload = cache.payload

        except Exception as exc:
            logger.exception("Failed to generate /metrics payload: %s", exc)
            cache_status = "error"
            if METRICS_SCRAPE_TOTAL:
                METRICS_SCRAPE_TOTAL.labels(cache_status).inc()  # type: ignore[call-arg]
            if METRICS_SCRAPE_DURATION_SECONDS:
                METRICS_SCRAPE_DURATION_SECONDS.observe(time.perf_counter() - start)
            if cache.payload:
                if METRICS_SCRAPE_TOTAL:
                    METRICS_SCRAPE_TOTAL.labels("stale").inc()  # type: ignore[call-arg]
                response = Response(
                    content=cache.payload,
                    media_type="text/plain; version=0.0.4; charset=utf-8",
                )
                response.headers["X-Metrics-Cache"] = "stale"
                response.headers["X-Metrics-TTL-MS"] = f"{ttl_ms:.0f}"
                return response
            return Response(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)

        duration = time.perf_counter() - start
        if METRICS_SCRAPE_DURATION_SECONDS:
            METRICS_SCRAPE_DURATION_SECONDS.observe(duration)
        if METRICS_SCRAPE_TOTAL:
            METRICS_SCRAPE_TOTAL.labels(cache_status).inc()  # type: ignore[call-arg]

        response = Response(content=payload, media_type="text/plain; version=0.0.4; charset=utf-8")
        response.headers["X-Metrics-Cache"] = cache_status
        response.headers["X-Metrics-TTL-MS"] = f"{ttl_ms:.0f}"
        cache_visibility = "public" if public_enabled else "private"
        response.headers["Cache-Control"] = f"{cache_visibility}, max-age={int(ttl_ms / 1000)}"
        response.headers["Content-Length"] = str(len(payload))
        if cache.generated_at_monotonic:
            response.headers["X-Metrics-Generated-At-Ms"] = (
                f"{cache.generated_at_monotonic * 1000:.0f}"
            )
        return response

    app.add_api_route(
        "/metrics",
        _metrics_endpoint,
        methods=["GET"],
        include_in_schema=False,
        name="kagami_metrics",
    )

    try:
        app.state.metrics_endpoint_initialized = True
        app.state.metrics_initialized = True
        app.state.metrics_cache_ttl_ms = ttl_ms
        app.state.metrics_cache_ttl_min_ms = ttl_min_ms
        app.state.metrics_cache_ttl_max_ms = ttl_max_ms
        app.state.metrics_public = public_enabled
    except Exception:
        pass

    logger.info(
        "✓ /metrics endpoint wired (ttl_ms=%.0f, public=%s, allow_hosts=%s, allow_networks=%d)",
        ttl_ms,
        public_enabled,
        ",".join(allowed_hostnames) or "<none>",
        len(allowed_networks),
    )


def metrics_middleware(request, call_next):  # type: ignore[no-untyped-def]
    """Metrics middleware (passthrough - handled by TelemetryMiddleware)."""
    return call_next(request)


def counter(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Decorator for counter metrics (passthrough)."""
    return lambda f: f


def gauge(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Decorator for gauge metrics (passthrough)."""
    return lambda f: f


def histogram(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Decorator for histogram metrics (passthrough)."""
    return lambda f: f


def summary(*args, **kwargs):  # type: ignore[no-untyped-def]
    """Decorator for summary metrics (passthrough)."""
    return lambda f: f
