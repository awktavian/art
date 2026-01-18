"""Mixin for adding cleanup to singleton classes.

CRITICAL FIX: All 15+ global singletons need periodic cleanup to prevent memory leaks.

Apply this mixin to all singleton classes with internal state.
"""

import atexit
import logging
import time
from abc import abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class SingletonRegistry:
    """Central registry of all singleton instances."""

    _registry: dict[str, Any] = {}

    @classmethod
    def register(cls, name: str, instance: Any) -> None:
        """Register a singleton instance."""
        cls._registry[name] = instance
        logger.debug(f"Registered singleton: {name}")

    @classmethod
    def get_all(cls) -> dict[str, Any]:
        """Get all registered singletons."""
        return cls._registry.copy()

    @classmethod
    def get(cls, name: str) -> Any | None:
        """Get singleton by name."""
        return cls._registry.get(name)

    @classmethod
    def cleanup_all(cls, force: bool = False) -> dict[str, Any]:
        """Cleanup all registered singletons."""
        results = {}
        for name, instance in cls._registry.items():
            if hasattr(instance, "cleanup"):
                try:
                    result = instance.cleanup(force=force)
                    results[name] = result
                    logger.debug(f"Cleaned up {name}: {result}")
                except Exception as e:
                    results[name] = {"status": "error", "error": str(e)}
                    logger.error(f"Failed to cleanup {name}: {e}")
        return results

    @classmethod
    def count(cls) -> int:
        """Number of registered singletons."""
        return len(cls._registry)


class SingletonCleanupMixin:
    """Mixin to add automatic cleanup to singleton classes."""

    # Class-level tracking
    _cleanup_interval: float = 3600.0  # 1 hour default
    _last_cleanup: float = 0.0
    _cleanup_enabled: bool = True

    def _should_cleanup(self) -> bool:
        """Check if cleanup should run."""
        if not self._cleanup_enabled:
            return False

        now = time.time()
        if now - self._last_cleanup >= self._cleanup_interval:
            self.__class__._last_cleanup = now
            return True
        return False

    @abstractmethod
    def _cleanup_internal_state(self) -> dict[str, int]:
        """Override this to implement cleanup logic.

        Returns:
            Dict with cleanup stats (e.g., {'items_removed': 10})
        """
        ...

    def cleanup(self, force: bool = False) -> dict[str, Any]:
        """Public cleanup method.

        Args:
            force: Force cleanup regardless of interval

        Returns:
            Cleanup statistics
        """
        if force or self._should_cleanup():
            try:
                stats = self._cleanup_internal_state()
                logger.debug(f"{self.__class__.__name__} cleanup: {stats}")
                return {"status": "success", "stats": stats}
            except Exception as e:
                logger.error(f"{self.__class__.__name__} cleanup failed: {e}")
                return {"status": "error", "error": str(e)}
        return {"status": "skipped", "reason": "cleanup_interval_not_reached"}

    def _register_cleanup_on_exit(self) -> None:
        """Register cleanup to run on process exit AND in registry."""
        atexit.register(lambda: self.cleanup(force=True))
        # Auto-register in SingletonRegistry
        SingletonRegistry.register(self.__class__.__name__, self)
