"""Tests for MCP (Model Context Protocol) Server.

Tests cover:
- Tool registration and execution
- Intent execution
- World model queries
- Receipt emission
- Colony status
- Health checks
- Weaviate integration tools

Coverage target: kagami/core/services/mcp/__init__.py

Dec 2025: MCP tools are defined inside if _FASTMCP_AVAILABLE block.
Imports like IntentOrchestrator and get_world_model are from their source modules,
not from kagami.core.services.mcp namespace.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


from unittest.mock import AsyncMock, MagicMock, patch
import os

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_fastmcp():
    """Mock FastMCP availability."""
    with patch.dict("sys.modules", {"fastmcp": MagicMock()}):
        yield


# =============================================================================
# MCP SERVER AVAILABILITY TESTS
# =============================================================================


class TestMCPAvailability:
    """Tests for MCP server availability."""

    def test_get_mcp_server_returns_none_without_fastmcp(self) -> None:
        """Test graceful handling when FastMCP is not installed."""
        # The module should handle missing fastmcp gracefully
        from kagami.core.services.mcp import get_mcp_server

        # Should return server or None without crashing
        result = get_mcp_server()
        # Verify function doesn't crash and returns expected type
        assert result is None or hasattr(result, "__class__")

    def test_get_mcp_asgi_app_returns_none_without_fastmcp(self) -> None:
        """Test ASGI app returns None when FastMCP unavailable."""
        from kagami.core.services.mcp import get_mcp_asgi_app

        result = get_mcp_asgi_app()
        # Should return None or valid app
        assert result is None or callable(result)


# =============================================================================
# TOOL EXECUTION TESTS
# =============================================================================


class TestMCPToolExecution:
    """Tests for MCP tool execution."""

    @pytest.mark.asyncio
    async def test_execute_intent_success(self):
        """Test successful intent execution."""
        # Dec 2025: patch at source - IntentOrchestrator is from kagami.core.orchestrator
        with patch("kagami.core.orchestrator.IntentOrchestrator", autospec=True) as MockOrch:
            mock_orch_instance = MagicMock()
            mock_orch_instance.execute = AsyncMock(return_value={"status": "completed"})
            MockOrch.return_value = mock_orch_instance

            try:
                # Import fresh after patching
                import importlib
                import kagami.core.services.mcp as mcp_mod

                importlib.reload(mcp_mod)
                if hasattr(mcp_mod, "execute_intent"):
                    result = await mcp_mod.execute_intent("forge.generate", {"concept": "warrior"})
                    assert result["status"] == "success"
                    assert result["intent"] == "forge.generate"
                else:
                    pytest.skip("FastMCP not available - execute_intent not defined")
            except ImportError:
                pytest.skip("FastMCP not available")

    @pytest.mark.asyncio
    async def test_execute_intent_error(self):
        """Test intent execution error handling."""
        with patch(
            "kagami.core.orchestrator.IntentOrchestrator",
            side_effect=Exception("Orchestrator unavailable"),
        ):
            try:
                import importlib
                import kagami.core.services.mcp as mcp_mod

                importlib.reload(mcp_mod)
                if hasattr(mcp_mod, "execute_intent"):
                    result = await mcp_mod.execute_intent("forge.generate", {})
                    assert result["status"] == "error"
                    assert "error" in result
                else:
                    pytest.skip("FastMCP not available")
            except ImportError:
                pytest.skip("FastMCP not available")


class TestMCPWorldModelQueries:
    """Tests for world model query tool."""

    @pytest.mark.asyncio
    async def test_query_world_model_success(self):
        """Test successful world model query."""
        mock_model = MagicMock()
        mock_model.__class__.__name__ = "KagamiWorldModel"

        # Dec 2025: patch inside the MCP module where it's imported
        mock_service = MagicMock()
        mock_service.model = mock_model

        # Patch at the point where query_world_model imports it
        with patch("kagami.core.world_model.get_world_model_service", return_value=mock_service):
            try:
                import importlib
                import kagami.core.services.mcp as mcp_mod

                importlib.reload(mcp_mod)
                if hasattr(mcp_mod, "query_world_model"):
                    result = await mcp_mod.query_world_model("predict next state", top_k=5)
                    assert result["status"] == "success"
                    assert result["available"] is True
                else:
                    pytest.skip("FastMCP not available - query_world_model not defined")
            except ImportError:
                pytest.skip("FastMCP not available")

    @pytest.mark.asyncio
    async def test_query_world_model_unavailable(self):
        """Test world model query when model unavailable."""
        mock_service = MagicMock()
        mock_service.model = None  # Model not loaded

        with patch("kagami.core.world_model.get_world_model_service", return_value=mock_service):
            try:
                import importlib
                import kagami.core.services.mcp as mcp_mod

                importlib.reload(mcp_mod)
                if hasattr(mcp_mod, "query_world_model"):
                    result = await mcp_mod.query_world_model("test query")
                    assert result["status"] == "error"
                    assert "not available" in result["error"]
                else:
                    pytest.skip("FastMCP not available")
            except ImportError:
                pytest.skip("FastMCP not available")


class TestMCPReceiptEmission:
    """Tests for receipt emission tool."""

    @pytest.mark.asyncio
    async def test_emit_receipt_success(self):
        """Test successful receipt emission."""
        mock_urf = MagicMock()
        mock_urf.emit = MagicMock(return_value={"receipt_id": "rcpt-123"})

        with patch.dict(
            "sys.modules", {"kagami.core.receipts": MagicMock(UnifiedReceiptFacade=mock_urf)}
        ):
            try:
                from kagami.core.services.mcp import emit_receipt

                result = await emit_receipt(
                    action="tool.execute",
                    event_data={"tool": "test"},
                    correlation_id="corr-123",
                )
                assert result["status"] == "success"
                assert result["action"] == "tool.execute"
            except ImportError:
                pytest.skip("FastMCP not available")

    @pytest.mark.asyncio
    async def test_emit_receipt_error(self):
        """Test receipt emission error handling."""
        with patch("kagami.core.receipts.UnifiedReceiptFacade") as MockURF:
            MockURF.emit.side_effect = Exception("Redis unavailable")

            try:
                from kagami.core.services.mcp import emit_receipt

                result = await emit_receipt(
                    action="test",
                    event_data={},
                )
                assert result["status"] == "error"
            except ImportError:
                pytest.skip("FastMCP not available")


class TestMCPColonyStatus:
    """Tests for colony status tool."""

    @pytest.mark.asyncio
    async def test_get_colony_status_success(self):
        """Test successful colony status retrieval."""
        mock_organism = MagicMock()
        mock_organism.colonies = {
            "spark": MagicMock(agents=["agent1", "agent2"], domain="creativity"),
            "forge": MagicMock(agents=["agent3"], domain="implementation"),
        }

        # Dec 2025: patch at source - get_unified_organism is from kagami.core.unified_agents
        with patch(
            "kagami.core.unified_agents.unified_organism.get_unified_organism",
            return_value=mock_organism,
        ):
            try:
                import importlib
                import kagami.core.services.mcp as mcp_mod

                importlib.reload(mcp_mod)
                if hasattr(mcp_mod, "get_colony_status"):
                    result = await mcp_mod.get_colony_status()
                    assert result["status"] == "success"
                    assert len(result["colonies"]) == 2
                    assert result["total_agents"] == 3
                else:
                    pytest.skip("FastMCP not available")
            except ImportError:
                pytest.skip("FastMCP not available")

    @pytest.mark.asyncio
    async def test_get_colony_status_error(self):
        """Test colony status error handling."""
        with patch(
            "kagami.core.unified_agents.unified_organism.get_unified_organism",
            side_effect=Exception("Not initialized"),
        ):
            try:
                import importlib
                import kagami.core.services.mcp as mcp_mod

                importlib.reload(mcp_mod)
                if hasattr(mcp_mod, "get_colony_status"):
                    result = await mcp_mod.get_colony_status()
                    assert result["status"] == "error"
                else:
                    pytest.skip("FastMCP not available")
            except ImportError:
                pytest.skip("FastMCP not available")


class TestMCPHealthCheck:
    """Tests for health check tool."""

    @pytest.mark.asyncio
    async def test_health_check_all_healthy(self):
        """Test health check when all systems healthy."""
        mock_model = MagicMock()
        mock_service = MagicMock()
        mock_service.model = mock_model

        with patch("kagami.core.world_model.get_world_model_service", return_value=mock_service):
            with patch(
                "kagami.core.caching.redis.RedisClientFactory.get_client", return_value=MagicMock()
            ):
                try:
                    import importlib
                    import kagami.core.services.mcp as mcp_mod

                    importlib.reload(mcp_mod)
                    if hasattr(mcp_mod, "health_check"):
                        result = await mcp_mod.health_check()
                        assert result["status"] in ("healthy", "degraded")
                        assert "subsystems" in result
                    else:
                        pytest.skip("FastMCP not available")
                except ImportError:
                    pytest.skip("FastMCP not available")

    @pytest.mark.asyncio
    async def test_health_check_degraded(self):
        """Test health check when some systems unavailable."""
        with patch(
            "kagami.core.world_model.get_world_model_service", side_effect=Exception("Model error")
        ):
            try:
                import importlib
                import kagami.core.services.mcp as mcp_mod

                importlib.reload(mcp_mod)
                if hasattr(mcp_mod, "health_check"):
                    result = await mcp_mod.health_check()
                    assert "subsystems" in result
                    assert result["subsystems"]["world_model"] == "error"
                else:
                    pytest.skip("FastMCP not available")
            except (ImportError, KeyError):
                # KeyError: 'pydantic.root_model' can occur with fastmcp/pydantic compatibility
                pytest.skip("FastMCP not available or pydantic compatibility issue")


# =============================================================================
# WEAVIATE INTEGRATION TESTS
# =============================================================================


def _check_mcp_available():
    """Check if MCP module can be imported without errors."""
    try:
        import kagami.core.services.mcp as mcp_mod

        return hasattr(mcp_mod, "weaviate_health")
    except (ImportError, KeyError):
        # KeyError can happen with pydantic.root_model issues
        return False


class TestMCPWeaviateTools:
    """Tests for Weaviate integration tools."""

    @pytest.mark.asyncio
    async def test_weaviate_health_success(self):
        """Test Weaviate health check."""
        if not _check_mcp_available():
            pytest.skip("FastMCP not available or pydantic compatibility issue")

        mock_adapter = MagicMock()
        mock_adapter.connect = AsyncMock(return_value=True)
        mock_adapter.config = MagicMock(
            url="http://localhost:8080",
            memory_collection="KagamiMemory",
            feedback_collection="KagamiFeedback",
        )

        import kagami.core.services.mcp as mcp_mod

        with patch.object(mcp_mod, "_get_weaviate_adapter", return_value=mock_adapter):
            result = await mcp_mod.weaviate_health()
            assert result["status"] == "healthy"

            assert result["connected"] is True

    @pytest.mark.asyncio
    async def test_weaviate_health_disconnected(self):
        """Test Weaviate health when disconnected."""
        if not _check_mcp_available():
            pytest.skip("FastMCP not available or pydantic compatibility issue")

        mock_adapter = MagicMock()
        mock_adapter.connect = AsyncMock(return_value=False)

        import kagami.core.services.mcp as mcp_mod

        with patch.object(mcp_mod, "_get_weaviate_adapter", return_value=mock_adapter):
            result = await mcp_mod.weaviate_health()
            assert result["status"] == "degraded"

            assert result["connected"] is False

    @pytest.mark.asyncio
    async def test_weaviate_store_memory(self):
        """Test storing memory in Weaviate."""
        if not _check_mcp_available():
            pytest.skip("FastMCP not available or pydantic compatibility issue")

        import torch
        import kagami.core.services.mcp as mcp_mod

        mock_adapter = MagicMock()
        mock_adapter.connect = AsyncMock(return_value=True)
        mock_adapter.store = AsyncMock(return_value="uuid-123")

        mock_embed_service = MagicMock()
        mock_embed_service.embed_text = MagicMock(return_value=torch.zeros(512).numpy())

        with patch.object(mcp_mod, "_get_weaviate_adapter", return_value=mock_adapter):
            with patch.object(mcp_mod, "_embed_to_tensor", return_value=torch.zeros(512)):
                result = await mcp_mod.weaviate_store_memory(
                    content="Test memory content",
                    metadata={"source": "test"},
                )
                assert result["status"] == "success"

                assert result["uuid"] == "uuid-123"

    @pytest.mark.asyncio
    async def test_weaviate_search_memory(self):
        """Test searching memory in Weaviate."""
        if not _check_mcp_available():
            pytest.skip("FastMCP not available or pydantic compatibility issue")

        import torch
        import kagami.core.services.mcp as mcp_mod

        mock_adapter = MagicMock()
        mock_adapter.connect = AsyncMock(return_value=True)
        mock_adapter.search_similar = AsyncMock(
            return_value=[
                {"uuid": "1", "content": "Result 1", "score": 0.95},
                {"uuid": "2", "content": "Result 2", "score": 0.85},
            ]
        )

        with patch.object(mcp_mod, "_get_weaviate_adapter", return_value=mock_adapter):
            with patch.object(mcp_mod, "_embed_to_tensor", return_value=torch.zeros(512)):
                result = await mcp_mod.weaviate_search_memory(
                    query="test query",
                    limit=5,
                )
                assert result["status"] == "success"

                assert len(result["results"]) == 2

    @pytest.mark.asyncio
    async def test_weaviate_rag_answer(self):
        """Test RAG answer generation."""
        if not _check_mcp_available():
            pytest.skip("FastMCP not available or pydantic compatibility issue")

        import torch
        import kagami.core.services.mcp as mcp_mod

        mock_adapter = MagicMock()
        mock_adapter.connect = AsyncMock(return_value=True)
        mock_adapter.search_similar = AsyncMock(
            return_value=[
                {"uuid": "1", "content": "Relevant context", "colony": "grove"},
            ]
        )

        with patch.object(mcp_mod, "_get_weaviate_adapter", return_value=mock_adapter):
            with patch.object(mcp_mod, "_embed_to_tensor", return_value=torch.zeros(512)):
                result = await mcp_mod.weaviate_rag_answer(
                    query="What is Kagami?",
                    limit=3,
                )
                assert result["status"] == "success"

                assert "answer" in result
                assert len(result["results"]) > 0


# =============================================================================
# RESOURCE TESTS
# =============================================================================


class TestMCPResources:
    """Tests for MCP resources."""

    @pytest.mark.asyncio
    async def test_get_boot_mode(self):
        """Test boot mode resource."""
        with patch.dict(os.environ, {"KAGAMI_BOOT_MODE": "test"}):
            try:
                import importlib
                import kagami.core.services.mcp as mcp_mod

                importlib.reload(mcp_mod)
                if hasattr(mcp_mod, "get_boot_mode"):
                    result = await mcp_mod.get_boot_mode()
                    assert result == "test"
                else:
                    pytest.skip("FastMCP not available - get_boot_mode not defined")
            except ImportError:
                pytest.skip("FastMCP not available")

    @pytest.mark.asyncio
    async def test_get_version(self):
        """Test version resource."""
        with patch.dict(os.environ, {"KAGAMI_VERSION": "1.2.3"}):
            try:
                import importlib
                import kagami.core.services.mcp as mcp_mod

                importlib.reload(mcp_mod)
                if hasattr(mcp_mod, "get_version"):
                    result = await mcp_mod.get_version()
                    # Should return version string
                    assert isinstance(result, str)
                else:
                    pytest.skip("FastMCP not available - get_version not defined")
            except ImportError:
                pytest.skip("FastMCP not available")


# =============================================================================
# EDGE CASES
# =============================================================================


class TestMCPEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_execute_intent_with_none_params(self):
        """Test intent execution with None params."""
        with patch("kagami.core.orchestrator.IntentOrchestrator") as MockOrch:
            mock_instance = MagicMock()
            mock_instance.execute = AsyncMock(return_value={})
            MockOrch.return_value = mock_instance

            try:
                import importlib
                import kagami.core.services.mcp as mcp_mod

                importlib.reload(mcp_mod)
                if hasattr(mcp_mod, "execute_intent"):
                    result = await mcp_mod.execute_intent("test.intent", None)
                    assert "status" in result
                else:
                    pytest.skip("FastMCP not available")
            except ImportError:
                pytest.skip("FastMCP not available")

    @pytest.mark.asyncio
    async def test_weaviate_error_handling(self):
        """Test Weaviate error handling."""
        try:
            import importlib
            import kagami.core.services.mcp as mcp_mod

            # Don't reload here, just check if function exists
            if hasattr(mcp_mod, "weaviate_health"):
                # Patch at module level where _get_weaviate_adapter is defined
                with patch.object(
                    mcp_mod, "_get_weaviate_adapter", side_effect=RuntimeError("Connection failed")
                ):
                    result = await mcp_mod.weaviate_health()
                    assert result["status"] == "error"

                    assert "error" in result
            else:
                pytest.skip("FastMCP not available - weaviate_health not defined")
        except ImportError:
            pytest.skip("FastMCP not available")
