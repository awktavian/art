"""Tests for kagami.forge.modules.export.manager (ExportManager)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from kagami.forge.modules.export.manager import ExportManager
from kagami.forge.modules.export.base import ExportConfig, ExportFormat, ExportResult

pytestmark = pytest.mark.tier_integration


@pytest.fixture
def export_manager():
    """Create ExportManager instance."""
    return ExportManager()


class TestExportManagerInit:
    """Test ExportManager initialization."""

    def test_init_default(self):
        """Test default initialization."""
        manager = ExportManager()
        assert manager._exporters is not None
        assert len(manager._exporters) > 0

    def test_get_supported_formats(self, export_manager):
        """Test getting supported formats."""
        formats = export_manager.get_supported_formats()
        assert ExportFormat.FBX in formats
        assert ExportFormat.GLTF in formats
        assert ExportFormat.USD in formats


class TestExport:
    """Test export operations."""

    @pytest.mark.asyncio
    async def test_export_glb(self, export_manager):
        """Test exporting to GLB format."""
        data = {"mesh": "test_data"}
        config = ExportConfig(format=ExportFormat.GLB)

        with patch.object(export_manager, "_exporters") as mock_exporters:
            mock_exporter = MagicMock()
            mock_exporter.get_supported_formats = MagicMock(return_value=[ExportFormat.GLB])
            mock_exporter.export = AsyncMock(
                return_value=ExportResult(success=True, file_path="/tmp/test.glb")
            )
            mock_exporters.get = MagicMock(return_value=lambda c: mock_exporter)

            result = await export_manager.export(data, config)

            assert result.success is True

    @pytest.mark.asyncio
    async def test_export_unsupported_format(self, export_manager):
        """Test exporting to unsupported format."""
        data = {"mesh": "test_data"}

        with patch.object(export_manager, "_exporters", {}):
            config = ExportConfig(format=ExportFormat.FBX)
            result = await export_manager.export(data, config)

            assert result.success is False


class TestBatchExport:
    """Test batch export operations."""

    @pytest.mark.asyncio
    async def test_export_multiple(self, export_manager):
        """Test exporting to multiple formats."""
        data = {"mesh": "test_data"}
        configs = [
            ExportConfig(format=ExportFormat.GLB),
            ExportConfig(format=ExportFormat.FBX),
        ]

        with patch.object(export_manager, "export") as mock_export:
            mock_export.return_value = ExportResult(success=True)

            results = await export_manager.export_multiple(data, configs)

            assert len(results) == 2
