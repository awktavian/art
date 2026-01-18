"""Elysia Integration — Agentic RAG with Fano Topology.

This module integrates Weaviate's Elysia agentic RAG framework into Kagami,
providing production-ready retrieval augmented generation with:

1. **Fano-Aware Decision Trees**: Elysia's decision tree uses Kagami's
   Fano plane topology for mathematically grounded 1/3/7 colony routing.

2. **Unified Memory**: Weaviate for persistent RAG + pattern storage,
   HierarchicalMemory for consolidation. No Redis dependency for RAG.

3. **E8 Quantization**: All embeddings compressed via E8 lattice (240 roots)
   for 47× compression with semantic preservation.

4. **Stigmergic Feedback**: User ratings become receipts, feeding ACO
   probability updates for continuous improvement.

5. **DSPy Integration**: Colony-aware prompt signatures with multi-model
   routing based on query complexity.

6. **Chunk-on-Demand**: Dynamic document chunking with HierarchicalMemory
   integration for intelligent retrieval.

7. **Colony Display Types**: Each of 7 colonies maps to a display format:
   - Spark → Generic (creative)
   - Forge → Tables (structured)
   - Flow → Conversations (recovery)
   - Nexus → Documents (integration)
   - Beacon → E-commerce Cards (planning)
   - Grove → Tickets (research)
   - Crystal → Charts (verification)

Usage:
    from kagami_integrations.elysia import KagamiElysia

    elysia = KagamiElysia(
        weaviate_url=os.environ["WEAVIATE_URL"],
        weaviate_api_key=os.environ["WEAVIATE_API_KEY"],
    )

    # Analyze data collections
    await elysia.analyze_collections()

    # Query with Fano routing
    response = await elysia.query("How does E8 quantization work?")

    # Provide feedback (updates stigmergy)
    await elysia.feedback(query_id=response.id, rating=5)

References:
    - Elysia: https://github.com/weaviate/elysia
    - Fano Plane: G₂ 3-form φ encoding octonion multiplication
    - E8 Lattice: Viazovska (2016), optimal sphere packing

Created: December 7, 2025
Updated: December 7, 2025 — Added DSPy, chunking bridge, removed Redis dependency
"""

from __future__ import annotations

__all__ = [
    "COLONY_DISPLAY_MAP",
    # Chunking bridge
    "ChunkOnDemandBridge",
    # Display types
    "ColonyDisplayFormatter",
    "DisplayType",
    "ElysiaCoTBridge",
    # Configuration
    "ElysiaConfig",
    "ElysiaE8EventHandler",
    # Feedback bridge
    "ElysiaFeedbackBridge",
    "ElysiaNode",
    # Sub-adapters
    "ElysiaWorkspaceAdapter",
    # Decision tree
    "FanoDecisionTree",
    # DSPy integration
    "KagamiDSPyModule",
    # Main interface
    "KagamiElysia",
    "TreeExecutionResult",
    "UnifiedRAGConfig",
    # =====================================
    # UNIFIED INTEGRATION (Dec 7, 2025)
    # Connects Elysia to Workspace, Bus, CoT
    # =====================================
    "UnifiedRAGIntegration",
    # Weaviate adapter
    "WeaviateE8Adapter",
    "WeaviateE8Config",
    # Pattern store (replaces Redis)
    "WeaviatePatternStore",
    "create_elysia",
    "create_unified_rag_integration",
    # Tools
    "get_colony_tools",
    "get_dspy_module",
    "get_elysia_config",
    "get_unified_rag_integration",
    "get_weaviate_pattern_store",
]

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ElysiaConfig:
    """Configuration for Elysia integration."""

    # Weaviate settings
    weaviate_url: str = ""
    weaviate_api_key: str = ""
    weaviate_timeout: int = 30

    # Collections
    memory_collection: str = "KagamiMemory"
    feedback_collection: str = "ElysiaFeedback"

    # E8 quantization
    e8_training_levels: int = 8
    e8_inference_levels: int = 16
    e8_adaptive: bool = True

    # Model routing
    default_model: str = "gemini-1.5-flash"
    complex_model: str = "gemini-1.5-pro"
    embedding_model: str = "text2vec-weaviate"

    # Fano routing thresholds
    simple_threshold: float = 0.3
    complex_threshold: float = 0.7

    # Feedback settings
    feedback_min_rating: int = 4  # Store as positive example if >= this
    feedback_ttl_days: int = 90

    # Safety
    cbf_enabled: bool = True

    def __post_init__(self):
        """Load from environment if not set."""
        import os

        # Weaviate connection (prefer cloud, fallback to local Docker)
        if not self.weaviate_url:
            self.weaviate_url = os.environ.get("WEAVIATE_URL", "")
        if not self.weaviate_api_key:
            self.weaviate_api_key = os.environ.get("WEAVIATE_API_KEY", "")

        # Collections
        self.memory_collection = os.environ.get("ELYSIA_MEMORY_COLLECTION", self.memory_collection)
        self.feedback_collection = os.environ.get(
            "ELYSIA_FEEDBACK_COLLECTION", self.feedback_collection
        )

        # E8 quantization
        self.e8_training_levels = int(os.environ.get("E8_TRAINING_LEVELS", self.e8_training_levels))
        self.e8_inference_levels = int(
            os.environ.get("E8_INFERENCE_LEVELS", self.e8_inference_levels)
        )
        self.e8_adaptive = os.environ.get("E8_ADAPTIVE", "true").lower() == "true"

        # Model routing
        self.default_model = os.environ.get("ELYSIA_DEFAULT_MODEL", self.default_model)
        self.complex_model = os.environ.get("ELYSIA_COMPLEX_MODEL", self.complex_model)

        # Fano routing thresholds
        self.simple_threshold = float(
            os.environ.get("ELYSIA_SIMPLE_THRESHOLD", self.simple_threshold)
        )
        self.complex_threshold = float(
            os.environ.get("ELYSIA_COMPLEX_THRESHOLD", self.complex_threshold)
        )

        # Feedback settings
        self.feedback_min_rating = int(
            os.environ.get("ELYSIA_FEEDBACK_MIN_RATING", self.feedback_min_rating)
        )
        self.feedback_ttl_days = int(
            os.environ.get("ELYSIA_FEEDBACK_TTL_DAYS", self.feedback_ttl_days)
        )

        # Safety
        self.cbf_enabled = os.environ.get("ELYSIA_CBF_ENABLED", "true").lower() == "true"


# Global config singleton
_elysia_config: ElysiaConfig | None = None


def get_elysia_config() -> ElysiaConfig:
    """Get global Elysia configuration."""
    global _elysia_config
    if _elysia_config is None:
        _elysia_config = ElysiaConfig()
    return _elysia_config


# Colony → Display type mapping
COLONY_DISPLAY_MAP = {
    "spark": "generic",  # Creative outputs
    "forge": "table",  # Structured implementations
    "flow": "conversation",  # Recovery dialogues
    "nexus": "document",  # Integration documents
    "beacon": "ecommerce",  # Strategic plans (card format)
    "grove": "ticket",  # Research items
    "crystal": "chart",  # Verification metrics
}

# Lazy imports for heavy modules (cached globals)
_FanoDecisionTree = None
_WeaviateE8Adapter = None
_ElysiaFeedbackBridge = None
_ColonyDisplayFormatter = None
_KagamiElysia = None


# ============================================================================
# ATTRIBUTE RESOLVER REGISTRY
# ============================================================================
# Maps attribute names to (module_path, attr_name) tuples.
# This table-driven approach reduces cyclomatic complexity from 57 to <15.
# ============================================================================

_ATTR_REGISTRY = {
    # Main interface
    "create_elysia": ("kagami_integrations.elysia.kagami_elysia", "create_elysia"),
    # Decision tree
    "ElysiaNode": ("kagami_integrations.elysia.fano_decision_tree", "ElysiaNode"),
    "TreeExecutionResult": ("kagami_integrations.elysia.fano_decision_tree", "TreeExecutionResult"),
    # Display types
    "DisplayType": ("kagami_integrations.elysia.colony_displays", "DisplayType"),
    # Weaviate adapter
    "WeaviateE8Config": ("kagami_integrations.elysia.weaviate_e8_adapter", "WeaviateE8Config"),
    # Pattern store
    "WeaviatePatternStore": (
        "kagami_integrations.elysia.weaviate_pattern_store",
        "WeaviatePatternStore",
    ),
    "get_weaviate_pattern_store": (
        "kagami_integrations.elysia.weaviate_pattern_store",
        "get_weaviate_pattern_store",
    ),
    # DSPy integration
    "KagamiDSPyModule": ("kagami_integrations.elysia.dspy_integration", "KagamiDSPyModule"),
    "get_dspy_module": ("kagami_integrations.elysia.dspy_integration", "get_dspy_module"),
    # Chunking bridge
    "ChunkOnDemandBridge": ("kagami_integrations.elysia.chunking_bridge", "ChunkOnDemandBridge"),
    # Tools
    "get_colony_tools": ("kagami_integrations.elysia.tools", "get_colony_tools"),
    # Unified integration
    "UnifiedRAGIntegration": (
        "kagami_integrations.elysia.unified_rag_integration",
        "UnifiedRAGIntegration",
    ),
    "UnifiedRAGConfig": ("kagami_integrations.elysia.unified_rag_integration", "UnifiedRAGConfig"),
    "get_unified_rag_integration": (
        "kagami_integrations.elysia.unified_rag_integration",
        "get_unified_rag_integration",
    ),
    "create_unified_rag_integration": (
        "kagami_integrations.elysia.unified_rag_integration",
        "create_unified_rag_integration",
    ),
    "ElysiaWorkspaceAdapter": (
        "kagami_integrations.elysia.unified_rag_integration",
        "ElysiaWorkspaceAdapter",
    ),
    "ElysiaE8EventHandler": (
        "kagami_integrations.elysia.unified_rag_integration",
        "ElysiaE8EventHandler",
    ),
    "ElysiaCoTBridge": ("kagami_integrations.elysia.unified_rag_integration", "ElysiaCoTBridge"),
}


def _load_cached_attr(name: str, cache_var: str, module_path: str, attr_name: str) -> Any:
    """Load and cache a heavy module attribute.

    Args:
        name: Attribute name for error messages
        cache_var: Name of the global cache variable
        module_path: Module to import from
        attr_name: Attribute to extract

    Returns:
        The imported attribute
    """
    import importlib

    cached = globals().get(cache_var)
    if cached is None:
        cached = getattr(importlib.import_module(module_path), attr_name)
        globals()[cache_var] = cached
    return cached


def _resolve_common_cached_attr(name: str) -> Any | None:
    """Resolve commonly used cached attributes.

    These are the hot-path attributes that benefit from caching.
    Returns None if not a cached attribute.
    """
    if name == "KagamiElysia":
        return _load_cached_attr(
            name, "_KagamiElysia", "kagami_integrations.elysia.kagami_elysia", "KagamiElysia"
        )
    if name == "FanoDecisionTree":
        return _load_cached_attr(
            name,
            "_FanoDecisionTree",
            "kagami_integrations.elysia.fano_decision_tree",
            "FanoDecisionTree",
        )
    if name == "ColonyDisplayFormatter":
        return _load_cached_attr(
            name,
            "_ColonyDisplayFormatter",
            "kagami_integrations.elysia.colony_displays",
            "ColonyDisplayFormatter",
        )
    if name == "WeaviateE8Adapter":
        return _load_cached_attr(
            name,
            "_WeaviateE8Adapter",
            "kagami_integrations.elysia.weaviate_e8_adapter",
            "WeaviateE8Adapter",
        )
    if name == "ElysiaFeedbackBridge":
        return _load_cached_attr(
            name,
            "_ElysiaFeedbackBridge",
            "kagami_integrations.elysia.stigmergy_feedback",
            "ElysiaFeedbackBridge",
        )
    return None


def _resolve_registry_attr(name: str) -> Any:
    """Resolve attribute from registry table."""
    import importlib

    if name not in _ATTR_REGISTRY:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module_path, attr_name = _ATTR_REGISTRY[name]
    return getattr(importlib.import_module(module_path), attr_name)


def __getattr__(name: str) -> Any:
    """Lazy import heavy modules with table-driven dispatch.

    Refactored from CC=57 to CC<15 by:
    1. Extracting cached attributes to _resolve_common_cached_attr
    2. Moving registry lookups to _resolve_registry_attr
    3. Using _ATTR_REGISTRY table instead of if-elif chain
    """
    # Try cached attributes first (hot path)
    result = _resolve_common_cached_attr(name)
    if result is not None:
        return result

    # Fall back to registry table
    return _resolve_registry_attr(name)
