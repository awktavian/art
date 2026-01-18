"""LangChain Integration for K os.

Bidirectional integration:
1. Use K os as a LangChain tool
2. Import LangChain tools into K os

Features:
- ChronosTool: Execute K os intents from LangChain agents
- LangChainBridge: Import LangChain tools into K os tool registry
- Full support for async operations
- Receipts and correlation tracking
- Automatic retry and error handling
"""

from __future__ import annotations

from typing import Any

# Lazy-loaded exports via __getattr__ (pylint: disable=undefined-all-variable)
__all__ = [
    "ChronosTool",
    "ChronosToolkit",
    "LangChainBridge",
    "LangChainIntegration",
]


def __getattr__(name: str) -> Any:
    if name == "LangChainIntegration":
        from kagami_integrations.langchain.integration import LangChainIntegration

        return LangChainIntegration
    elif name == "ChronosTool":
        from kagami_integrations.langchain.tools import ChronosTool

        return ChronosTool
    elif name == "ChronosToolkit":
        from kagami_integrations.langchain.tools import ChronosToolkit

        return ChronosToolkit
    elif name == "LangChainBridge":
        from kagami_integrations.langchain.bridge import LangChainBridge

        return LangChainBridge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
