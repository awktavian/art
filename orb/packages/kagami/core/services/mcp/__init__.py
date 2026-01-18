"""MCP (Model Context Protocol) Server for K OS.

Exposes K OS capabilities to Claude Desktop and other MCP clients:
- Intent execution (LANG/2 commands)
- World model queries
- Receipt emission
- Agent colony status

Built with FastMCP for efficient async operation.

Usage:
    # Standalone server
    python -m kagami.core.mcp

    # Mounted in API
    # Automatically mounted at /mcp when KAGAMI_MCP_ENABLED=1

Protocol: Model Context Protocol (MCP) v1.6+
Dependencies: fastmcp>=2.1.0, mcp>=1.6.0
"""

from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Check if fastmcp is available
try:
    from fastmcp import FastMCP

    _FASTMCP_AVAILABLE = True
except ImportError:
    _FASTMCP_AVAILABLE = False
    logger.warning("FastMCP not available - MCP server disabled")

if _FASTMCP_AVAILABLE:
    # Create the MCP server
    mcp = FastMCP(
        "K OS MCP Server",
        version="1.0.0",
        description="MCP server exposing K OS AI capabilities",
    )

    @mcp.tool()
    async def execute_intent(intent: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a K OS intent (LANG/2 command).

        Args:
            intent: The intent name (e.g., "forge.generate", "agent.spawn")
            params: Optional parameters for the intent

        Returns:
            Result of intent execution including status and any output
        """
        try:
            import importlib

            IntentOrchestrator = importlib.import_module(
                "kagami.core.orchestrator"
            ).IntentOrchestrator

            orch = IntentOrchestrator()
            intent_payload = {
                "intent": intent,
                **(params or {}),
            }
            result = await orch.execute(intent_payload)
            return {
                "status": "success",
                "intent": intent,
                "result": result,
            }
        except Exception as e:
            logger.error(f"Intent execution failed: {e}")
            return {
                "status": "error",
                "intent": intent,
                "error": str(e),
            }

    @mcp.tool()
    async def query_world_model(query: str, top_k: int = 5) -> dict[str, Any]:
        """Query the K OS world model for predictions or state.

        Args:
            query: Natural language query about the world model state
            top_k: Number of top predictions to return

        Returns:
            World model response with predictions and confidence scores
        """
        try:
            from kagami.core.world_model import get_world_model_service

            model = get_world_model_service().model
            if model is None:
                return {
                    "status": "error",
                    "error": "World model not available",
                }

            # Simple text embedding query
            # In practice, this would encode the query and retrieve similar states
            return {
                "status": "success",
                "query": query,
                "model_type": type(model).__name__,
                "available": True,
                "note": "Full query API coming in v1.1",
            }
        except Exception as e:
            logger.error(f"World model query failed: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    @mcp.tool()
    async def emit_receipt(
        action: str,
        event_data: dict[str, Any],
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Emit a receipt for observability and audit trail.

        Args:
            action: Action identifier (e.g., "tool.execute", "decision.made")
            event_data: Event payload data
            correlation_id: Optional correlation ID for tracing

        Returns:
            Confirmation with receipt ID
        """
        try:
            from kagami.core.receipts import UnifiedReceiptFacade as URF

            result = URF.emit(
                correlation_id=correlation_id,  # type: ignore[arg-type]
                action=action,
                event_name=f"mcp.{action}",
                event_data=event_data,
                status="success",
                app="MCP",
            )
            return {
                "status": "success",
                "action": action,
                "receipt_id": result.get("receipt_id") if isinstance(result, dict) else None,
            }
        except Exception as e:
            logger.error(f"Receipt emission failed: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    @mcp.tool()
    async def get_colony_status() -> dict[str, Any]:
        """Get current status of agent colonies.

        Returns:
            Status of all active colonies including agent counts and health
        """
        try:
            colonies = []
            from kagami.core.unified_agents.unified_organism import get_unified_organism

            organism = get_unified_organism()
            for name, colony in organism.colonies.items():
                colonies.append(
                    {
                        "name": name,
                        "agent_count": len(getattr(colony, "agents", [])),
                        "domain": str(getattr(colony, "domain", "unknown")),
                    }
                )

            return {
                "status": "success",
                "colonies": colonies,
                "total_agents": sum(c["agent_count"] for c in colonies),
            }
        except Exception as e:
            logger.error(f"Colony status failed: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    @mcp.tool()
    async def health_check() -> dict[str, Any]:
        """Check K OS system health.

        Returns:
            Health status of core subsystems
        """
        health = {
            "status": "healthy",
            "subsystems": {},
        }

        # Check world model
        try:
            from kagami.core.world_model import get_world_model_service

            model = get_world_model_service().model
            health["subsystems"]["world_model"] = "available" if model else "unavailable"  # type: ignore[index]
        except Exception:
            health["subsystems"]["world_model"] = "error"  # type: ignore[index]

        # Check Redis
        try:
            from kagami.core.caching.redis import RedisClientFactory

            RedisClientFactory.get_client(purpose="default")
            health["subsystems"]["redis"] = "available"  # type: ignore[index]
        except Exception:
            health["subsystems"]["redis"] = "unavailable"  # type: ignore[index]

        # Check orchestrator
        try:
            import importlib

            _ = importlib.import_module("kagami.core.orchestrator").IntentOrchestrator

            health["subsystems"]["orchestrator"] = "available"  # type: ignore[index]
        except Exception:
            health["subsystems"]["orchestrator"] = "unavailable"  # type: ignore[index]

        # Overall status
        if any(v == "error" for v in health["subsystems"].values()):  # type: ignore[attr-defined]
            health["status"] = "degraded"

        return health

    # =====================================================================
    # WEAVIATE TOOLS (Kagami-aligned vector storage + retrieval)
    # =====================================================================

    def _get_weaviate_adapter() -> Any:
        """Lazy-create a Weaviate adapter (optional dependency)."""
        try:
            from kagami_integrations.elysia.weaviate_e8_adapter import get_weaviate_adapter

            return get_weaviate_adapter()
        except Exception as e:
            raise RuntimeError(f"Weaviate adapter unavailable: {e}") from e

    def _embed_to_tensor(text: str, dim: int = 512) -> Any:
        """Embed text using Kagami embedding service (best-effort)."""
        try:
            import numpy as np
            import torch

            from kagami.core.services.embedding_service import get_embedding_service

            vec: np.ndarray[Any, Any] = get_embedding_service().embed_text(text, dimension=dim)  # type: ignore[assignment]
            return torch.from_numpy(vec).float()
        except Exception as e:
            raise RuntimeError(f"Embedding failed: {e}") from e

    @mcp.tool()
    async def weaviate_health() -> dict[str, Any]:
        """Check Weaviate connectivity and basic collection readiness."""
        try:
            adapter = _get_weaviate_adapter()
            ok = await adapter.connect()
            if not ok:
                return {"status": "degraded", "connected": False}
            return {
                "status": "healthy",
                "connected": True,
                "url": getattr(adapter.config, "url", None),
                "memory_collection": getattr(adapter.config, "memory_collection", None),
                "feedback_collection": getattr(adapter.config, "feedback_collection", None),
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def weaviate_store_memory(
        content: str,
        metadata: dict[str, Any] | None = None,
        embedding_dim: int = 512,
    ) -> dict[str, Any]:
        """Store a memory chunk into Weaviate with Kagami-native embeddings."""
        try:
            adapter = _get_weaviate_adapter()
            await adapter.connect()
            emb = _embed_to_tensor(content, dim=embedding_dim)
            uuid = await adapter.store(content=content, embedding=emb, metadata=metadata or {})
            return {"status": "success", "uuid": uuid}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def weaviate_search_memory(
        query: str,
        limit: int = 10,
        colony_filter: str | None = None,
        embedding_dim: int = 512,
        mode: str = "vector",
    ) -> dict[str, Any]:
        """Search Weaviate memory.

        mode:
          - 'vector': Kagami-native vector similarity (preferred)
          - 'text'  : near_text (requires server-side vectorizer modules)
        """
        try:
            adapter = _get_weaviate_adapter()
            await adapter.connect()
            if mode == "text":
                results = await adapter.search_similar(
                    query=query, limit=limit, colony_filter=colony_filter
                )
            else:
                emb = _embed_to_tensor(query, dim=embedding_dim)
                results = await adapter.search_similar(
                    query=emb, limit=limit, colony_filter=colony_filter
                )
            return {"status": "success", "results": results}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def weaviate_rag_answer(
        query: str,
        limit: int = 6,
        colony_filter: str | None = None,
        embedding_dim: int = 512,
    ) -> dict[str, Any]:
        """End-to-end text → retrieve → answer.

        This is deliberately dependency-light: it retrieves Kagami-aligned results
        from Weaviate and returns a synthesized plaintext answer *without* requiring
        an external LLM at tool-runtime.
        """
        try:
            adapter = _get_weaviate_adapter()
            await adapter.connect()

            emb = _embed_to_tensor(query, dim=embedding_dim)
            results = await adapter.search_similar(
                query=emb, limit=limit, colony_filter=colony_filter
            )

            if not results:
                return {"status": "success", "answer": "No relevant memories found.", "results": []}

            # Minimal synthesis: top snippets + provenance
            lines: list[str] = []
            lines.append("Retrieved context:")
            for i, r in enumerate(results[:limit], start=1):
                content = (r.get("content") or "").strip()
                snippet = content if len(content) <= 400 else content[:400].rstrip() + "…"
                lines.append(f"{i}. [{r.get('uuid', '')}] ({r.get('colony', '')}) {snippet}")

            answer = "\n".join(lines)
            return {"status": "success", "answer": answer, "results": results}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def weaviate_store_feedback(
        query: str,
        response: str,
        rating: int,
        colony: str,
        model: str,
    ) -> dict[str, Any]:
        """Store feedback in Weaviate (for few-shot retrieval / RAG tuning)."""
        try:
            adapter = _get_weaviate_adapter()
            await adapter.connect()
            uuid = await adapter.store_feedback(
                query=query, response=response, rating=rating, colony=colony, model=model
            )
            return {"status": "success", "uuid": uuid}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def weaviate_get_similar_feedback(
        query: str,
        min_rating: int = 4,
        limit: int = 5,
    ) -> dict[str, Any]:
        """Retrieve similar positive feedback examples."""
        try:
            adapter = _get_weaviate_adapter()
            await adapter.connect()
            examples = await adapter.get_similar_feedback(
                query=query, min_rating=min_rating, limit=limit
            )
            return {"status": "success", "examples": examples}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.tool()
    async def weaviate_analyze_collection(collection_name: str | None = None) -> dict[str, Any]:
        """Return schema + sample data + suggested display for a Weaviate collection."""
        try:
            adapter = _get_weaviate_adapter()
            await adapter.connect()
            analysis = await adapter.analyze_collection(collection_name=collection_name)
            return {"status": "success", "analysis": analysis}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @mcp.resource("kagami://config/boot_mode")
    async def get_boot_mode() -> str:
        """Get current K OS boot mode."""
        return os.getenv("KAGAMI_BOOT_MODE", "full")

    @mcp.resource("kagami://config/version")
    async def get_version() -> str:
        """Get K OS version."""
        try:
            from kagami._version import __version__

            return __version__
        except ImportError:
            return os.getenv("KAGAMI_VERSION", "0.0.0")


def get_mcp_server() -> Any:
    """Get the MCP server instance.

    Returns:
        FastMCP server instance or None if not available
    """
    if not _FASTMCP_AVAILABLE:
        return None
    return mcp


def get_mcp_asgi_app() -> None:
    """Get ASGI app for mounting in FastAPI.

    Returns:
        ASGI app for the MCP server (Starlette SSE app)
    """
    if not _FASTMCP_AVAILABLE:
        return None

    try:
        # FastMCP v1.x may not expose an ASGI app at all (stdio only).
        if hasattr(mcp, "sse_app"):
            return mcp.sse_app()  # type: ignore[no-any-return]
        if hasattr(mcp, "http_app"):
            return mcp.http_app()  # type: ignore[no-any-return]
        # No ASGI transport available in this FastMCP version.
        logger.info("FastMCP ASGI app not available (stdio-only FastMCP)")
        return None
    except Exception as e:
        logger.error(f"Failed to create MCP ASGI app: {e}")
        return None


__all__ = [
    "get_mcp_asgi_app",
    "get_mcp_server",
]


if __name__ == "__main__":
    # Run standalone MCP server
    if _FASTMCP_AVAILABLE:
        import uvicorn

        app = get_mcp_asgi_app()  # type: ignore[func-returns-value]
        if app:
            uvicorn.run(app, host="0.0.0.0", port=8002)
        else:
            print("Failed to create MCP app")
    else:
        print("FastMCP not available. Install with: pip install fastmcp")
