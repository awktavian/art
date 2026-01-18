"""K os Integrations with External Agent Ecosystems.

This package provides bidirectional integrations with popular agent frameworks:
- **Elysia**: Weaviate's agentic RAG with Fano topology routing (PRIMARY)
- LangChain: Use K os as a LangChain tool, or use LangChain tools in K os
- CrewAI: Coordinate K os agents with CrewAI crews
- AutoGen: Multi-agent conversations with K os capabilities
- Custom: Build your own integrations using the base framework

All integrations maintain K os's core guarantees:
- Safety (CBF, risk assessment, confirmations)
- Observability (receipts, correlation_id, metrics)
- Reliability (idempotency, error handling, retries)
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "BaseIntegration",
    "IntegrationRegistry",
    # Elysia exports (primary RAG integration)
    "KagamiElysia",
    "create_elysia",
    "get_integration",
]

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kagami_integrations.base import BaseIntegration
    from kagami_integrations.registry import IntegrationRegistry

logger = logging.getLogger(__name__)


def get_integration(name: str) -> BaseIntegration | None:
    """Get an integration by name.

    Args:
        name: Integration name (langchain, crewai, autogen)

    Returns:
        Integration instance or None if not available
    """
    try:
        from kagami_integrations.registry import get_integration_registry

        registry = get_integration_registry()
        return registry.get(name)
    except Exception as e:
        logger.warning(f"Failed to get integration '{name}': {e}")
        return None


# Lazy imports for optional dependencies
def __getattr__(name: str) -> Any:
    # Elysia (primary RAG integration)
    if name == "KagamiElysia":
        from kagami_integrations.elysia import KagamiElysia

        return KagamiElysia
    elif name == "create_elysia":
        from kagami_integrations.elysia import create_elysia

        return create_elysia
    # Other agent frameworks
    elif name == "LangChainIntegration":
        from kagami_integrations.langchain.integration import LangChainIntegration

        return LangChainIntegration
    elif name == "CrewAIIntegration":
        from kagami_integrations.crewai.integration import CrewAIIntegration

        return CrewAIIntegration
    elif name == "AutoGenIntegration":
        from kagami_integrations.autogen.integration import AutoGenIntegration

        return AutoGenIntegration
    elif name == "BaseIntegration":
        from kagami_integrations.base import BaseIntegration

        return BaseIntegration
    elif name == "IntegrationRegistry":
        from kagami_integrations.registry import IntegrationRegistry

        return IntegrationRegistry
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
