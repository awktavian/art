"""Organism-Level Control Barrier Functions (Tier 1).

Created: December 14, 2025
Based on: Ames et al. (2019), Hierarchical CBF safety architecture

Tier 1 barriers are GLOBAL safety constraints that apply to the entire
KagamiOS organism (all colonies). These represent inviolable system-level
invariants that must hold for safe operation.

Tier hierarchy:
    Tier 1 (Organism) - Global constraints (this file)
    Tier 2 (Colony) - Per-colony resource limits
    Tier 3 (Agent) - Per-agent operational constraints

MATHEMATICAL FOUNDATION:
========================
Each barrier function h(x) defines a safe set[Any]:
    C = {x ∈ ℝⁿ | h(x) ≥ 0}

Where:
    h(x) > 0  : Safe with margin
    h(x) = 0  : On safety boundary
    h(x) < 0  : UNSAFE (violation)

All Tier 1 barriers must be satisfied simultaneously for the system
to be considered globally safe.

References:
- Ames et al. (2019): Control Barrier Functions: Theory and Applications
- KagamiOS Architecture: Hierarchical safety with Markov blanket integrity
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


# =============================================================================
# CONFIGURATION
# =============================================================================


@dataclass
class OrganismBarriersConfig:
    """Configuration for organism-level safety barriers.

    These thresholds define the safe operating envelope for the entire
    KagamiOS system. Violations trigger emergency safety protocols.

    Attributes:
        max_memory_gb: Maximum memory usage in GB
        max_processes: Maximum number of active processes/threads
        max_disk_usage_pct: Maximum disk usage as fraction [0,1]
        min_free_disk_gb: Minimum free disk space in GB
        rate_limits: Per-operation rate limits (requests per second)
        blanket_tolerance: Maximum mutual information I(μ; η) tolerated
        enable_blanket_check: Whether to check Markov blanket integrity
    """

    max_memory_gb: float = 16.0
    max_processes: int = 100
    max_disk_usage_pct: float = 0.9
    min_free_disk_gb: float = 5.0
    rate_limits: dict[str, float] = field(default_factory=dict[str, Any])
    blanket_tolerance: float = 0.01  # Max mutual info I(μ; η)
    enable_blanket_check: bool = (
        True  # ENABLED (Dec 23, 2025): Sparse approximation makes it tractable
    )

    def __post_init__(self) -> None:
        """Validate configuration parameters."""
        if self.max_memory_gb <= 0:
            raise ValueError(f"max_memory_gb must be positive, got {self.max_memory_gb}")
        if self.max_processes <= 0:
            raise ValueError(f"max_processes must be positive, got {self.max_processes}")
        if not 0 < self.max_disk_usage_pct <= 1:
            raise ValueError(f"max_disk_usage_pct must be in (0,1], got {self.max_disk_usage_pct}")
        if self.min_free_disk_gb <= 0:
            raise ValueError(f"min_free_disk_gb must be positive, got {self.min_free_disk_gb}")
        if self.blanket_tolerance <= 0:
            raise ValueError(f"blanket_tolerance must be positive, got {self.blanket_tolerance}")


# =============================================================================
# RATE LIMITER (TOKEN BUCKET)
# =============================================================================


class TokenBucket:
    """Token bucket rate limiter for operation throttling.

    Implements token bucket algorithm:
    - Tokens refill at constant rate
    - Each operation consumes 1 token
    - If bucket empty, operation is rate-limited

    This provides smooth rate limiting with burst tolerance.
    """

    def __init__(self, rate: float, capacity: float | None = None) -> None:
        """Initialize token bucket.

        Args:
            rate: Token refill rate (tokens per second)
            capacity: Bucket capacity (defaults to 2x rate for burst tolerance)
        """
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate * 2.0
        self.tokens = self.capacity
        self.last_update = time.monotonic()

    def consume(self, tokens: float = 1.0) -> bool:
        """Attempt to consume tokens.

        Args:
            tokens: Number of tokens to consume

        Returns:
            True if tokens were consumed (operation allowed)
            False if insufficient tokens (operation rate-limited)
        """
        now = time.monotonic()
        elapsed = now - self.last_update

        # Refill tokens based on elapsed time
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now

        # Check if we have enough tokens
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    def available(self) -> float:
        """Get current token count.

        Returns:
            Current number of tokens in bucket
        """
        now = time.monotonic()
        elapsed = now - self.last_update
        return min(self.capacity, self.tokens + elapsed * self.rate)


# =============================================================================
# ORGANISM-LEVEL BARRIERS
# =============================================================================


class OrganismBarriers:
    """Tier 1: Organism-level safety barriers.

    These are GLOBAL constraints that must hold for the entire system.
    If any Tier 1 barrier is violated (h < 0), the system is in an unsafe state.

    Barrier functions:
        h_memory: Memory usage safety
        h_process: Process count safety
        h_disk_space: Disk space safety
        h_blanket_integrity: Markov blanket integrity (internal vs external separation)
        h_rate_limit: Per-operation rate limiting

    All barrier values are normalized such that:
        h > 0.5  : GREEN zone (full autonomy)
        0 ≤ h ≤ 0.5 : YELLOW zone (caution)
        h < 0 : RED zone (BLOCKED)
    """

    def __init__(self, config: OrganismBarriersConfig | None = None) -> None:
        """Initialize organism barriers.

        Args:
            config: Barrier configuration (uses defaults if None)
        """
        self.config = config or OrganismBarriersConfig()

        # Rate limiters (one bucket per operation)
        self._rate_buckets: dict[str, TokenBucket] = {}
        for operation, rate in self.config.rate_limits.items():
            self._rate_buckets[operation] = TokenBucket(rate=rate)

        # Cache system info for efficiency
        self._psutil_available = True
        self._shutil_available = True

        # Try importing system libraries
        try:
            import psutil  # noqa: F401
        except ImportError:
            logger.warning("psutil not available, memory/process barriers will return h=1.0")
            self._psutil_available = False

        try:
            import shutil  # noqa: F401
        except ImportError:
            logger.warning("shutil not available, disk barriers will return h=1.0")
            self._shutil_available = False

        logger.info(
            f"OrganismBarriers initialized: "
            f"max_memory={self.config.max_memory_gb}GB, "
            f"max_processes={self.config.max_processes}, "
            f"rate_limits={len(self._rate_buckets)} operations"
        )

    def h_memory(self, current_state: dict[str, Any] | None = None) -> float:
        """Memory safety barrier.

        Returns:
            h >= 0: Memory is safe (h = fraction of headroom remaining)
            h < 0: Memory limit exceeded
        """
        if not self._psutil_available:
            return 1.0  # Fail open if psutil unavailable

        try:
            import psutil

            # Get current memory usage
            mem = psutil.virtual_memory()
            current_gb = mem.used / (1024**3)

            # Barrier: h = (max - current) / max
            # Normalized to [0, 1] range
            h = (self.config.max_memory_gb - current_gb) / self.config.max_memory_gb

            return float(h)

        except Exception as e:
            logger.error(f"Error computing h_memory: {e}", exc_info=True)
            return 0.0  # Fail closed on error

    def h_process(self, current_state: dict[str, Any] | None = None) -> float:
        """Process count safety barrier.

        Returns:
            h >= 0: Process count is safe
            h < 0: Too many processes
        """
        if not self._psutil_available:
            return 1.0  # Fail open if psutil unavailable

        try:
            import psutil

            # Get current process and all children (recursive)
            current_process = psutil.Process()
            children = current_process.children(recursive=True)
            process_count = 1 + len(children)  # Current + children

            # Barrier: h = (max - current) / max
            h = (self.config.max_processes - process_count) / self.config.max_processes

            return float(h)

        except Exception as e:
            logger.error(f"Error computing h_process: {e}", exc_info=True)
            return 0.0  # Fail closed on error

    def h_disk_space(self, current_state: dict[str, Any] | None = None) -> float:
        """Disk space safety barrier.

        Enforces TWO constraints:
        1. Total usage < max_disk_usage_pct
        2. Free space > min_free_disk_gb

        Returns the MINIMUM of both constraints (most restrictive).

        Returns:
            h >= 0: Sufficient disk space
            h < 0: Disk space critical
        """
        if not self._shutil_available:
            return 1.0  # Fail open if shutil unavailable

        try:
            import shutil

            # Get disk usage for current directory
            usage = shutil.disk_usage("/")

            # Constraint 1: Usage percentage
            usage_pct = usage.used / usage.total
            h1 = (self.config.max_disk_usage_pct - usage_pct) / self.config.max_disk_usage_pct

            # Constraint 2: Minimum free space
            free_gb = usage.free / (1024**3)
            h2 = (free_gb - self.config.min_free_disk_gb) / self.config.min_free_disk_gb

            # Return most restrictive constraint
            return float(min(h1, h2))

        except Exception as e:
            logger.error(f"Error computing h_disk_space: {e}", exc_info=True)
            return 0.0  # Fail closed on error

    def h_blanket_integrity(self, current_state: dict[str, Any] | None = None) -> float:
        """Markov blanket integrity barrier.

        Ensures internal state (μ) is properly separated from external state (η).
        Uses mutual information: I(μ; η) ≈ 0 for proper blanket integrity.

        In practice, this is approximated via correlation between internal
        latent states and external observations.

        Args:
            current_state: Must contain 'internal_state' and 'external_obs' if checking

        Returns:
            h >= 0: Blanket integrity maintained
            h < 0: Information leakage detected
        """
        if not self.config.enable_blanket_check:
            return 1.0  # Blanket check disabled

        if current_state is None:
            # No state provided - cannot check, fail open
            return 1.0

        internal = current_state.get("internal_state")
        external = current_state.get("external_obs")

        if internal is None or external is None:
            # Missing required state - cannot check
            logger.debug("h_blanket_integrity: missing internal_state or external_obs")
            return 1.0

        try:
            # Convert to numpy arrays
            internal_arr = np.asarray(internal).flatten()
            external_arr = np.asarray(external).flatten()

            # OPTIMIZED (Dec 27, 2025): Sparse approximation for large arrays
            # Sample 100 dimensions instead of computing full correlation
            MAX_DIMS = 100
            if len(internal_arr) > MAX_DIMS or len(external_arr) > MAX_DIMS:
                # Random sampling for efficiency
                rng = np.random.default_rng(42)  # Fixed seed for reproducibility
                if len(internal_arr) > MAX_DIMS:
                    indices = rng.choice(len(internal_arr), MAX_DIMS, replace=False)
                    internal_arr = internal_arr[indices]  # type: ignore[assignment]
                if len(external_arr) > MAX_DIMS:
                    indices = rng.choice(len(external_arr), MAX_DIMS, replace=False)
                    external_arr = external_arr[indices]  # type: ignore[assignment]

            # Approximate mutual information via normalized correlation
            # I(X;Y) ≈ -0.5 * log(1 - ρ²) where ρ is correlation
            # For small ρ: I(X;Y) ≈ ρ²/2

            # Compute correlation
            if len(internal_arr) == 0 or len(external_arr) == 0:
                return 1.0

            # Normalize
            internal_norm = (internal_arr - internal_arr.mean()) / (internal_arr.std() + 1e-8)
            external_norm = (external_arr - external_arr.mean()) / (external_arr.std() + 1e-8)

            # Correlation (taking min length if different sizes)
            min_len = min(len(internal_norm), len(external_norm))
            corr = np.abs(np.corrcoef(internal_norm[:min_len], external_norm[:min_len])[0, 1])

            # Approximate mutual information
            mutual_info = (corr**2) / 2.0

            # Barrier: h = tolerance - I(μ; η)
            h = (self.config.blanket_tolerance - mutual_info) / self.config.blanket_tolerance

            return float(h)

        except Exception as e:
            logger.error(f"Error computing h_blanket_integrity: {e}", exc_info=True)
            return 0.0  # Fail closed on error

    def h_rate_limit(
        self,
        operation: str,
        current_state: dict[str, Any] | None = None,
    ) -> float:
        """Rate limiting barrier.

        Args:
            operation: Operation name (e.g., "api.request", "websocket.message")
            current_state: Optional state (unused)

        Returns:
            h >= 0: Within rate limit (h = fraction of tokens available)
            h < 0: Rate limit exceeded
        """
        # If no rate limit configured for this operation, allow
        if operation not in self._rate_buckets:
            return 1.0

        bucket = self._rate_buckets[operation]

        # Check if operation can proceed (consume 1 token)
        can_proceed = bucket.consume(tokens=1.0)

        if can_proceed:
            # Return fraction of tokens available as safety margin
            return bucket.available() / bucket.capacity
        else:
            # Rate limited - return negative value proportional to shortage
            available = bucket.available()
            # h = (available - 1.0) means we're short by (1.0 - available)
            return available - 1.0

    def check_all(
        self,
        current_state: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """Check all Tier 1 barriers.

        Args:
            current_state: Optional system state dict[str, Any]

        Returns:
            Dict mapping barrier name to h(x) value
        """
        barriers = {
            "memory": self.h_memory(current_state),
            "process": self.h_process(current_state),
            "disk": self.h_disk_space(current_state),
        }

        # Add blanket check if enabled
        if self.config.enable_blanket_check:
            barriers["blanket"] = self.h_blanket_integrity(current_state)

        # Add rate limit checks for all configured operations
        for operation in self._rate_buckets:
            # Use a read-only check (don't consume tokens)
            bucket = self._rate_buckets[operation]
            available = bucket.available()
            h = available / bucket.capacity if bucket.capacity > 0 else 1.0
            barriers[f"rate_limit.{operation}"] = h

        return barriers

    def is_safe(self, current_state: dict[str, Any] | None = None) -> bool:
        """Check if all Tier 1 barriers are satisfied.

        Args:
            current_state: Optional system state dict[str, Any]

        Returns:
            True if all barriers h(x) >= 0, False otherwise
        """
        barriers = self.check_all(current_state)
        return all(h >= 0 for h in barriers.values())

    def min_barrier(self, current_state: dict[str, Any] | None = None) -> float:
        """Get minimum barrier value (most restrictive).

        Args:
            current_state: Optional system state dict[str, Any]

        Returns:
            Minimum h(x) across all barriers
        """
        barriers = self.check_all(current_state)
        return min(barriers.values()) if barriers else 1.0

    def get_violations(
        self,
        current_state: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """Get all barrier violations (h < 0).

        Args:
            current_state: Optional system state dict[str, Any]

        Returns:
            Dict mapping barrier name to h(x) value for violated barriers only
        """
        barriers = self.check_all(current_state)
        return {name: h for name, h in barriers.items() if h < 0}

    def get_status_zone(self, current_state: dict[str, Any] | None = None) -> str:
        """Get overall safety status zone.

        Args:
            current_state: Optional system state dict[str, Any]

        Returns:
            "GREEN" if min h > 0.5
            "YELLOW" if 0 <= min h <= 0.5
            "RED" if min h < 0
        """
        h_min = self.min_barrier(current_state)

        if h_min < 0:
            return "RED"
        elif h_min <= 0.5:
            return "YELLOW"
        else:
            return "GREEN"


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================


_organism_barriers: OrganismBarriers | None = None


def get_organism_barriers() -> OrganismBarriers:
    """Get singleton OrganismBarriers instance.

    Returns:
        Global OrganismBarriers instance
    """
    global _organism_barriers
    if _organism_barriers is None:
        _organism_barriers = OrganismBarriers()
    return _organism_barriers


__all__ = [
    "OrganismBarriers",
    "OrganismBarriersConfig",
    "TokenBucket",
    "get_organism_barriers",
]
