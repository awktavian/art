"""AutoGen Integration for K os.

Enables multi-agent conversations with K os capabilities:
1. K os as an AutoGen function/tool
2. AutoGen agents coordinating with K os
3. Conversational workflows with safety and observability

Features:
- ChronosAutoGenTool: Function for AutoGen agents
- AutoGenBridge: Import AutoGen functions into K os
- Multi-agent conversation support
- Shared context and state management
"""

from __future__ import annotations

from typing import Any

# Lazy-loaded exports via __getattr__ (pylint: disable=undefined-all-variable)
__all__ = [
    "AutoGenBridge",
    "AutoGenIntegration",
    "ChronosAutoGenTool",
]


def __getattr__(name: str) -> Any:
    if name == "AutoGenIntegration":
        from kagami_integrations.autogen.integration import AutoGenIntegration

        return AutoGenIntegration
    elif name == "ChronosAutoGenTool":
        from kagami_integrations.autogen.tools import ChronosAutoGenTool

        return ChronosAutoGenTool
    elif name == "AutoGenBridge":
        from kagami_integrations.autogen.bridge import AutoGenBridge

        return AutoGenBridge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
