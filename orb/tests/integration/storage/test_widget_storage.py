"""Tests for WidgetStorageManager - covers 309 lines."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kagami.core.widget_storage import WidgetStorageManager

pytestmark = pytest.mark.tier2  # Integration tests with external services


class TestWidgetStorageManagerInit:
    """Test WidgetStorageManager initialization."""

    def test_init_creates_instance(self) -> None:
        """Test basic initialization."""
        with patch("kagami.core.utils.paths.get_user_kagami_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.mkdir = MagicMock()
            mock_dir.return_value = mock_path

            manager = WidgetStorageManager()
            assert manager.redis_client is None
            assert manager._widget_registry == {}
            assert manager._workspace_registry == {}

    def test_prefix_constants(self) -> None:
        """Test prefix constants are set correctly."""
        with patch("kagami.core.utils.paths.get_user_kagami_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.mkdir = MagicMock()
            mock_dir.return_value = mock_path

            manager = WidgetStorageManager()
            assert manager.WIDGET_PREFIX == "kagami:widgets:"
            assert manager.WORKSPACE_PREFIX == "kagami:workspaces:"
            assert manager.WIDGET_DATA_PREFIX == "kagami:widget_data:"


@pytest.mark.asyncio
class TestWidgetStorageManagerAsync:
    """Test async methods."""

    async def test_initialize_success(self) -> None:
        """Test successful initialization."""
        with patch("kagami.core.utils.paths.get_user_kagami_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.mkdir = MagicMock()
            mock_dir.return_value = mock_path

            manager = WidgetStorageManager()

            with patch.object(manager, "_load_registry", new_callable=AsyncMock):
                with patch.object(manager, "_sync_to_redis", new_callable=AsyncMock):
                    with patch("kagami.core.widget_storage.RedisClientFactory") as mock_factory:
                        mock_client = AsyncMock()
                        mock_factory.get_client.return_value = mock_client

                        await manager.initialize()
                        assert manager.redis_client is mock_client

    async def test_get_user_installations_empty(self) -> None:
        """Test getting installations for user with none."""
        with patch("kagami.core.utils.paths.get_user_kagami_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.mkdir = MagicMock()
            mock_dir.return_value = mock_path

            manager = WidgetStorageManager()
            installations = await manager.get_user_installations("user-123")
            assert installations == []

    async def test_get_user_installations_with_widgets(self) -> None:
        """Test getting installations for user with widgets."""
        with patch("kagami.core.utils.paths.get_user_kagami_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.mkdir = MagicMock()
            mock_dir.return_value = mock_path

            manager = WidgetStorageManager()
            manager._widget_registry = {
                "widget-1": {"user_id": "user-123", "name": "test"},
                "widget-2": {"user_id": "user-456", "name": "other"},
            }

            installations = await manager.get_user_installations("user-123")
            assert len(installations) == 1
            assert installations[0]["name"] == "test"

    async def test_get_all_widgets_from_registry(self) -> None:
        """Test getting all widgets from memory registry."""
        with patch("kagami.core.utils.paths.get_user_kagami_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.mkdir = MagicMock()
            mock_dir.return_value = mock_path

            manager = WidgetStorageManager()
            manager._widget_registry = {
                "w1": {"id": "w1"},
                "w2": {"id": "w2"},
            }

            widgets = await manager.get_all_widgets()
            assert len(widgets) == 2

    async def test_get_all_widgets_from_redis(self) -> None:
        """Test getting all widgets from Redis."""
        with patch("kagami.core.utils.paths.get_user_kagami_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.mkdir = MagicMock()
            mock_dir.return_value = mock_path

            manager = WidgetStorageManager()
            mock_redis = AsyncMock()
            mock_redis.keys.return_value = ["kagami:widgets:w1"]
            mock_redis.get.return_value = json.dumps({"id": "w1"})
            manager.redis_client = mock_redis

            widgets = await manager.get_all_widgets()
            assert len(widgets) == 1
            assert widgets[0]["id"] == "w1"

    async def test_install_widget(self) -> None:
        """Test installing a widget."""
        with patch("kagami.core.utils.paths.get_user_kagami_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.mkdir = MagicMock()
            mock_dir.return_value = mock_path

            manager = WidgetStorageManager()

            with patch.object(manager, "_save_registry", new_callable=AsyncMock):
                # Check if _sync_widget_to_redis exists before patching
                sync_exists = hasattr(manager, "_sync_widget_to_redis")
                if sync_exists:
                    with patch.object(manager, "_sync_widget_to_redis", new_callable=AsyncMock):
                        result = await manager.install_widget(
                            widget_id="my-widget",
                            widget_data={"name": "Test Widget"},
                            initial_config={"theme": "dark"},
                        )
                else:
                    result = await manager.install_widget(
                        widget_id="my-widget",
                        widget_data={"name": "Test Widget"},
                        initial_config={"theme": "dark"},
                    )

                assert "id" in result
                assert result["widget_id"] == "my-widget"
                assert result["active"] is True


class TestWidgetStorageManagerRegistries:
    """Test registry management."""

    def test_widget_registry_init_empty(self) -> None:
        """Test widget registry initializes empty."""
        with patch("kagami.core.utils.paths.get_user_kagami_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.mkdir = MagicMock()
            mock_dir.return_value = mock_path

            manager = WidgetStorageManager()
            assert isinstance(manager._widget_registry, dict)
            assert len(manager._widget_registry) == 0

    def test_workspace_registry_init_empty(self) -> None:
        """Test workspace registry initializes empty."""
        with patch("kagami.core.utils.paths.get_user_kagami_dir") as mock_dir:
            mock_path = MagicMock()
            mock_path.__truediv__ = MagicMock(return_value=mock_path)
            mock_path.mkdir = MagicMock()
            mock_dir.return_value = mock_path

            manager = WidgetStorageManager()
            assert isinstance(manager._workspace_registry, dict)
            assert len(manager._workspace_registry) == 0
