"""Widget storage management for Kagami.

Provides persistent storage and management for UI widgets.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class RedisClientFactory:
    """Factory for Redis client connections."""

    _client: Any = None

    @classmethod
    async def get_client(cls) -> Any:
        """Get or create a Redis client."""
        if cls._client is None:
            try:
                import redis.asyncio as aioredis

                cls._client = await aioredis.from_url(
                    "redis://localhost:6379", decode_responses=True
                )
            except Exception as e:
                logger.warning(f"Failed to create Redis client: {e}")
                cls._client = None
        return cls._client


class WidgetStorageManager:
    """Manages persistent storage for UI widgets.

    Supports:
    - Widget registration and installation
    - User-specific widget configurations
    - Workspace management
    - Redis and local file fallback storage
    """

    WIDGET_PREFIX = "kagami:widgets:"
    WORKSPACE_PREFIX = "kagami:workspaces:"
    WIDGET_DATA_PREFIX = "kagami:widget_data:"

    def __init__(self) -> None:
        """Initialize widget storage manager."""
        try:
            from kagami.core.utils.paths import get_user_kagami_dir

            self._storage_dir = get_user_kagami_dir() / "widgets"
        except ImportError:
            self._storage_dir = Path.home() / ".kagami" / "widgets"

        self._storage_dir.mkdir(parents=True, exist_ok=True)

        self.redis_client: Any = None
        self._widget_registry: dict[str, dict[str, Any]] = {}
        self._workspace_registry: dict[str, dict[str, Any]] = {}

    async def initialize(self) -> None:
        """Initialize storage connections."""
        try:
            self.redis_client = await RedisClientFactory.get_client()
            await self._load_registry()
            await self._sync_to_redis()
        except Exception as e:
            logger.warning(f"Widget storage initialization failed: {e}")

    async def _load_registry(self) -> None:
        """Load widget registry from disk."""
        registry_file = self._storage_dir / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file) as f:
                    data = json.load(f)
                    self._widget_registry = data.get("widgets", {})
                    self._workspace_registry = data.get("workspaces", {})
            except Exception as e:
                logger.warning(f"Failed to load widget registry: {e}")

    async def _save_registry(self) -> None:
        """Save widget registry to disk."""
        registry_file = self._storage_dir / "registry.json"
        try:
            with open(registry_file, "w") as f:
                json.dump(
                    {
                        "widgets": self._widget_registry,
                        "workspaces": self._workspace_registry,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.warning(f"Failed to save widget registry: {e}")

    async def _sync_to_redis(self) -> None:
        """Sync local registry to Redis."""
        if not self.redis_client:
            return

        try:
            for widget_id, widget_data in self._widget_registry.items():
                key = f"{self.WIDGET_PREFIX}{widget_id}"
                await self.redis_client.set(key, json.dumps(widget_data))
        except Exception as e:
            logger.warning(f"Failed to sync to Redis: {e}")

    async def _sync_widget_to_redis(self, widget_id: str, widget_data: dict[str, Any]) -> None:
        """Sync a single widget to Redis."""
        if not self.redis_client:
            return

        try:
            key = f"{self.WIDGET_PREFIX}{widget_id}"
            await self.redis_client.set(key, json.dumps(widget_data))
        except Exception as e:
            logger.warning(f"Failed to sync widget to Redis: {e}")

    async def get_user_installations(self, user_id: str) -> list[dict[str, Any]]:
        """Get all widget installations for a user.

        Args:
            user_id: User identifier

        Returns:
            List of installed widget configurations
        """
        installations = []
        for _widget_id, widget_data in self._widget_registry.items():
            if widget_data.get("user_id") == user_id:
                installations.append(widget_data)
        return installations

    async def get_all_widgets(self) -> list[dict[str, Any]]:
        """Get all registered widgets.

        Returns:
            List of all widget configurations
        """
        # First try Redis if available
        if self.redis_client:
            try:
                keys = await self.redis_client.keys(f"{self.WIDGET_PREFIX}*")
                widgets = []
                for key in keys:
                    data = await self.redis_client.get(key)
                    if data:
                        widgets.append(json.loads(data))
                return widgets
            except Exception as e:
                logger.warning(f"Failed to get widgets from Redis: {e}")

        # Fall back to in-memory registry
        return list(self._widget_registry.values())

    async def install_widget(
        self,
        widget_id: str,
        widget_data: dict[str, Any],
        initial_config: dict[str, Any] | None = None,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        """Install a widget.

        Args:
            widget_id: Widget identifier
            widget_data: Widget metadata
            initial_config: Initial configuration
            user_id: Optional user ID

        Returns:
            Installation record
        """
        installation_id = str(uuid.uuid4())
        installation = {
            "id": installation_id,
            "widget_id": widget_id,
            "active": True,
            "installed_at": datetime.now().isoformat(),
            "config": initial_config or {},
            "user_id": user_id,
            **widget_data,
        }

        self._widget_registry[installation_id] = installation
        await self._save_registry()

        if hasattr(self, "_sync_widget_to_redis"):
            await self._sync_widget_to_redis(installation_id, installation)

        return installation

    async def uninstall_widget(self, installation_id: str) -> bool:
        """Uninstall a widget.

        Args:
            installation_id: Installation identifier

        Returns:
            True if uninstalled successfully
        """
        if installation_id in self._widget_registry:
            del self._widget_registry[installation_id]
            await self._save_registry()

            if self.redis_client:
                try:
                    key = f"{self.WIDGET_PREFIX}{installation_id}"
                    await self.redis_client.delete(key)
                except Exception as e:
                    logger.warning(f"Failed to delete widget from Redis: {e}")

            return True
        return False

    async def update_widget_config(
        self,
        installation_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Update widget configuration.

        Args:
            installation_id: Installation identifier
            config: New configuration

        Returns:
            Updated installation record or None if not found
        """
        if installation_id in self._widget_registry:
            self._widget_registry[installation_id]["config"] = config
            self._widget_registry[installation_id]["updated_at"] = datetime.now().isoformat()
            await self._save_registry()

            if hasattr(self, "_sync_widget_to_redis"):
                await self._sync_widget_to_redis(
                    installation_id, self._widget_registry[installation_id]
                )

            return self._widget_registry[installation_id]
        return None

    async def get_widget(self, installation_id: str) -> dict[str, Any] | None:
        """Get a specific widget installation.

        Args:
            installation_id: Installation identifier

        Returns:
            Widget installation record or None
        """
        return self._widget_registry.get(installation_id)


__all__ = ["RedisClientFactory", "WidgetStorageManager"]
