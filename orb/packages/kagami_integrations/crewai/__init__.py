"""CrewAI Integration for K os.

Bidirectional integration:
1. Use K os as a CrewAI tool
2. Coordinate K os agents with CrewAI crews
3. Share context and results between systems

Features:
- ChronosCrew: CrewAI-compatible tool for K os execution
- CrewBridge: Import CrewAI tools and agents into K os
- Crew coordination and task delegation
- Shared observability via receipts
"""

from __future__ import annotations

from typing import Any

# Lazy-loaded exports via __getattr__ (pylint: disable=undefined-all-variable)
__all__ = [
    "ChronosCrewTool",
    "CrewAIIntegration",
    "CrewBridge",
]


def __getattr__(name: str) -> Any:
    if name == "CrewAIIntegration":
        from kagami_integrations.crewai.integration import CrewAIIntegration

        return CrewAIIntegration
    elif name == "ChronosCrewTool":
        from kagami_integrations.crewai.tools import ChronosCrewTool

        return ChronosCrewTool
    elif name == "CrewBridge":
        from kagami_integrations.crewai.bridge import CrewBridge

        return CrewBridge
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
