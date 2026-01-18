"""Adaptive cache configuration with environment-aware auto-tuning.

This module provides intelligent, environment-aware cache configuration that:
- Auto-detects system resources (memory, CPU, GPU)
- Adjusts cache sizes and TTLs based on available resources
- Supports runtime reconfiguration without restart
- Provides environment profiles (development, staging, production)

Environment Variables:
    KAGAMI_CACHE_PROFILE: Environment profile (dev, staging, prod, auto)
    KAGAMI_CACHE_MEMORY_FRACTION: Fraction of RAM for caching (0.0-1.0)
    KAGAMI_CACHE_ADAPTIVE_ENABLED: Enable adaptive tuning (default: true)
    KAGAMI_CACHE_MIN_FREE_MEMORY_GB: Minimum free memory threshold
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EnvironmentProfile(Enum):
    """Environment profiles with different optimization strategies."""

    DEVELOPMENT = "dev"
    STAGING = "staging"
    PRODUCTION = "prod"
    AUTO = "auto"


@dataclass
class ResourceSnapshot:
    """Snapshot of system resources for adaptive tuning."""

    total_memory_gb: float
    available_memory_gb: float
    cpu_count: int
    cpu_percent: float
    gpu_available: bool
    gpu_memory_gb: float
    timestamp: float = field(default_factory=time.time)

    @property
    def memory_pressure(self) -> float:
        """Calculate memory pressure (0.0 = no pressure, 1.0 = critical)."""
        if self.total_memory_gb == 0:
            return 1.0  # Unknown memory = assume critical
        used_fraction = 1 - (self.available_memory_gb / self.total_memory_gb)
        return min(1.0, max(0.0, used_fraction))

    @property
    def is_resource_constrained(self) -> bool:
        """Check if system is resource constrained."""
        return self.memory_pressure > 0.8 or self.cpu_percent > 90


@dataclass
class AdaptiveCacheSettings:
    """Dynamically computed cache settings based on environment."""

    # Model cache settings
    model_cache_max_size_gb: float = 50.0
    model_cache_max_models: int = 5
    model_cache_ttl_hours: int = 168

    # Response cache settings
    response_cache_max_size: int = 1000
    response_cache_ttl_seconds: float = 3600.0

    # L1 (memory) cache settings
    l1_cache_max_entries: int = 1024
    l1_cache_ttl_seconds: float = 300.0

    # Rate limiting settings
    rate_limit_requests_per_minute: int = 60
    rate_limit_burst_size: int = 20

    # Prefetch settings
    prefetch_enabled: bool = True
    prefetch_threshold_hits: int = 3

    # Environment
    profile: EnvironmentProfile = EnvironmentProfile.AUTO


class ResourceMonitor:
    """Monitor system resources for adaptive tuning."""

    def __init__(self) -> None:
        """Initialize resource monitor."""
        self._last_snapshot: ResourceSnapshot | None = None
        self._snapshot_interval = 30.0  # seconds
        self._lock = asyncio.Lock()

    def get_snapshot(self, force_refresh: bool = False) -> ResourceSnapshot:
        """Get current resource snapshot (cached for performance)."""
        now = time.time()

        if (
            not force_refresh
            and self._last_snapshot
            and now - self._last_snapshot.timestamp < self._snapshot_interval
        ):
            return self._last_snapshot

        # Collect fresh metrics
        snapshot = self._collect_metrics()
        self._last_snapshot = snapshot
        return snapshot

    def _collect_metrics(self) -> ResourceSnapshot:
        """Collect system metrics."""
        # Try psutil first
        try:
            import psutil

            mem = psutil.virtual_memory()
            total_memory_gb = mem.total / (1024**3)
            available_memory_gb = mem.available / (1024**3)
            cpu_count = psutil.cpu_count(logical=True) or 4
            cpu_percent = psutil.cpu_percent(interval=None)
        except ImportError:
            # Fallback to conservative defaults
            total_memory_gb = 8.0
            available_memory_gb = 4.0
            cpu_count = 4
            cpu_percent = 50.0

        # Check GPU availability
        gpu_available = False
        gpu_memory_gb = 0.0

        try:
            import torch

            if torch.cuda.is_available():
                gpu_available = True
                gpu_memory_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3)
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                gpu_available = True
                # MPS doesn't expose memory, estimate from system
                gpu_memory_gb = total_memory_gb * 0.75  # Shared memory
        except ImportError:
            pass

        return ResourceSnapshot(
            total_memory_gb=total_memory_gb,
            available_memory_gb=available_memory_gb,
            cpu_count=cpu_count,
            cpu_percent=cpu_percent,
            gpu_available=gpu_available,
            gpu_memory_gb=gpu_memory_gb,
        )


class AdaptiveConfigManager:
    """Manages adaptive cache configuration based on environment and resources."""

    # Profile presets
    PROFILE_PRESETS: dict[EnvironmentProfile, dict[str, Any]] = {
        EnvironmentProfile.DEVELOPMENT: {
            "model_cache_max_size_gb": 20.0,
            "model_cache_max_models": 3,
            "response_cache_max_size": 500,
            "l1_cache_max_entries": 512,
            "rate_limit_requests_per_minute": 120,
            "prefetch_enabled": False,
        },
        EnvironmentProfile.STAGING: {
            "model_cache_max_size_gb": 50.0,
            "model_cache_max_models": 5,
            "response_cache_max_size": 1000,
            "l1_cache_max_entries": 1024,
            "rate_limit_requests_per_minute": 60,
            "prefetch_enabled": True,
        },
        EnvironmentProfile.PRODUCTION: {
            "model_cache_max_size_gb": 100.0,
            "model_cache_max_models": 10,
            "response_cache_max_size": 5000,
            "l1_cache_max_entries": 2048,
            "rate_limit_requests_per_minute": 60,
            "prefetch_enabled": True,
        },
    }

    def __init__(self) -> None:
        """Initialize adaptive config manager."""
        self._resource_monitor = get_resource_monitor()
        self._current_settings: AdaptiveCacheSettings | None = None
        self._settings_lock = asyncio.Lock()
        self._reconfigure_callbacks: list[Any] = []

    def get_profile(self) -> EnvironmentProfile:
        """Determine current environment profile."""
        profile_str = os.getenv("KAGAMI_CACHE_PROFILE", "auto").lower()

        if profile_str == "dev" or profile_str == "development":
            return EnvironmentProfile.DEVELOPMENT
        elif profile_str == "staging":
            return EnvironmentProfile.STAGING
        elif profile_str == "prod" or profile_str == "production":
            return EnvironmentProfile.PRODUCTION
        else:
            return EnvironmentProfile.AUTO

    def get_settings(self, force_refresh: bool = False) -> AdaptiveCacheSettings:
        """Get current adaptive settings.

        Args:
            force_refresh: Force recalculation of settings

        Returns:
            Current adaptive cache settings
        """
        if not force_refresh and self._current_settings is not None:
            return self._current_settings

        profile = self.get_profile()
        resources = self._resource_monitor.get_snapshot()

        if profile == EnvironmentProfile.AUTO:
            settings = self._compute_auto_settings(resources)
        else:
            settings = self._apply_profile_preset(profile, resources)

        self._current_settings = settings
        return settings

    def _compute_auto_settings(self, resources: ResourceSnapshot) -> AdaptiveCacheSettings:
        """Compute settings based on detected resources."""
        # Memory-based scaling
        memory_fraction = float(os.getenv("KAGAMI_CACHE_MEMORY_FRACTION", "0.3"))
        min_free_gb = float(os.getenv("KAGAMI_CACHE_MIN_FREE_MEMORY_GB", "2.0"))

        # Calculate available memory for caching
        available_for_cache = max(0, resources.available_memory_gb - min_free_gb)
        cache_memory_budget = available_for_cache * memory_fraction

        # Scale model cache based on memory
        if resources.total_memory_gb >= 256:
            # Datacenter class
            model_cache_max_gb = min(cache_memory_budget * 0.6, 200.0)
            max_models = 20
            l1_entries = 4096
        elif resources.total_memory_gb >= 64:
            # High-end workstation
            model_cache_max_gb = min(cache_memory_budget * 0.5, 100.0)
            max_models = 10
            l1_entries = 2048
        elif resources.total_memory_gb >= 32:
            # Standard workstation
            model_cache_max_gb = min(cache_memory_budget * 0.4, 50.0)
            max_models = 5
            l1_entries = 1024
        elif resources.total_memory_gb >= 16:
            # Laptop/light workstation
            model_cache_max_gb = min(cache_memory_budget * 0.3, 20.0)
            max_models = 3
            l1_entries = 512
        else:
            # Resource constrained
            model_cache_max_gb = min(cache_memory_budget * 0.2, 5.0)
            max_models = 2
            l1_entries = 256

        # Adjust based on memory pressure
        if resources.is_resource_constrained:
            model_cache_max_gb *= 0.5
            max_models = max(1, max_models // 2)
            l1_entries = l1_entries // 2
            logger.warning(
                f"Resource constrained mode: reducing cache sizes "
                f"(memory pressure: {resources.memory_pressure:.1%})"
            )

        # Response cache scales with CPU count
        response_cache_size = min(10000, max(500, resources.cpu_count * 200))

        # Rate limiting based on capacity
        rpm = 60 if resources.is_resource_constrained else 120
        burst = min(50, max(10, rpm // 3))

        # TTL adjustments
        model_ttl = 168 if resources.gpu_available else 72  # Keep models longer with GPU
        response_ttl = 3600.0 if not resources.is_resource_constrained else 1800.0

        return AdaptiveCacheSettings(
            model_cache_max_size_gb=model_cache_max_gb,
            model_cache_max_models=max_models,
            model_cache_ttl_hours=model_ttl,
            response_cache_max_size=response_cache_size,
            response_cache_ttl_seconds=response_ttl,
            l1_cache_max_entries=l1_entries,
            l1_cache_ttl_seconds=300.0,
            rate_limit_requests_per_minute=rpm,
            rate_limit_burst_size=burst,
            prefetch_enabled=not resources.is_resource_constrained,
            prefetch_threshold_hits=3,
            profile=EnvironmentProfile.AUTO,
        )

    def _apply_profile_preset(
        self, profile: EnvironmentProfile, resources: ResourceSnapshot
    ) -> AdaptiveCacheSettings:
        """Apply profile preset with resource-aware adjustments."""
        preset = self.PROFILE_PRESETS.get(profile, self.PROFILE_PRESETS[EnvironmentProfile.STAGING])

        settings = AdaptiveCacheSettings(
            model_cache_max_size_gb=preset["model_cache_max_size_gb"],
            model_cache_max_models=preset["model_cache_max_models"],
            response_cache_max_size=preset["response_cache_max_size"],
            l1_cache_max_entries=preset["l1_cache_max_entries"],
            rate_limit_requests_per_minute=preset["rate_limit_requests_per_minute"],
            prefetch_enabled=preset["prefetch_enabled"],
            profile=profile,
        )

        # Apply resource constraints if needed
        if resources.is_resource_constrained:
            settings.model_cache_max_size_gb *= 0.5
            settings.model_cache_max_models = max(1, settings.model_cache_max_models // 2)
            settings.l1_cache_max_entries //= 2

        return settings

    def register_reconfigure_callback(self, callback: Any) -> None:
        """Register callback to be called when settings change.

        Args:
            callback: Async function to call with new settings
        """
        self._reconfigure_callbacks.append(callback)

    async def reconfigure(self) -> AdaptiveCacheSettings:
        """Force reconfiguration based on current resources.

        Returns:
            New settings after reconfiguration
        """
        async with self._settings_lock:
            old_settings = self._current_settings
            new_settings = self.get_settings(force_refresh=True)

            if old_settings != new_settings:
                logger.info(f"Reconfiguring cache settings: {new_settings}")
                for callback in self._reconfigure_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(new_settings)
                        else:
                            callback(new_settings)
                    except Exception as e:
                        logger.error(f"Reconfigure callback failed: {e}")

            return new_settings

    def get_status(self) -> dict[str, Any]:
        """Get current configuration status.

        Returns:
            Status dictionary with current settings and resources
        """
        resources = self._resource_monitor.get_snapshot()
        settings = self.get_settings()

        return {
            "profile": settings.profile.value,
            "settings": {
                "model_cache_max_size_gb": settings.model_cache_max_size_gb,
                "model_cache_max_models": settings.model_cache_max_models,
                "response_cache_max_size": settings.response_cache_max_size,
                "l1_cache_max_entries": settings.l1_cache_max_entries,
                "rate_limit_rpm": settings.rate_limit_requests_per_minute,
                "prefetch_enabled": settings.prefetch_enabled,
            },
            "resources": {
                "total_memory_gb": round(resources.total_memory_gb, 2),
                "available_memory_gb": round(resources.available_memory_gb, 2),
                "memory_pressure": round(resources.memory_pressure, 3),
                "cpu_count": resources.cpu_count,
                "cpu_percent": round(resources.cpu_percent, 1),
                "gpu_available": resources.gpu_available,
                "gpu_memory_gb": round(resources.gpu_memory_gb, 2),
                "is_constrained": resources.is_resource_constrained,
            },
        }


# =============================================================================
# SINGLETON FACTORIES (via centralized registry)
# =============================================================================

from kagami.core.shared_abstractions.singleton_consolidation import (
    get_singleton_registry,
)

_singleton_registry = get_singleton_registry()
get_resource_monitor = _singleton_registry.register_sync("resource_monitor", ResourceMonitor)
get_adaptive_config_manager = _singleton_registry.register_sync(
    "adaptive_config_manager", AdaptiveConfigManager
)


# Convenience functions
def get_adaptive_settings() -> AdaptiveCacheSettings:
    """Get current adaptive cache settings.

    Returns:
        Current adaptive settings
    """
    return get_adaptive_config_manager().get_settings()


def get_resource_snapshot() -> ResourceSnapshot:
    """Get current resource snapshot.

    Returns:
        Current resource snapshot
    """
    return get_resource_monitor().get_snapshot()


async def reconfigure_caches() -> AdaptiveCacheSettings:
    """Force reconfiguration of all caches.

    Returns:
        New settings after reconfiguration
    """
    return await get_adaptive_config_manager().reconfigure()


__all__ = [
    "AdaptiveCacheSettings",
    "AdaptiveConfigManager",
    "EnvironmentProfile",
    "ResourceMonitor",
    "ResourceSnapshot",
    "get_adaptive_settings",
    "get_resource_snapshot",
    "reconfigure_caches",
]
