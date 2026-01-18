"""K OS API Schemas — Pydantic Models for API Endpoints.

This module provides strongly-typed request/response models for:
- Command/Intent execution
- Colonies/Agents
- Vitals/Health
- Receipts
- Forge

Note: Mind API schemas (thoughts, learning, dynamics, goals) are defined
inline in their respective route files for tighter coupling with endpoints.
See: routes/mind/thoughts.py, routes/mind/goals.py, routes/mind/dynamics/core.py

Created: December 6, 2025
Updated: December 30, 2025 - Removed unused mind schemas
"""

# Mind schemas removed (Dec 30, 2025) - routes define their own schemas inline
# See: routes/mind/thoughts.py, routes/mind/goals.py, routes/mind/dynamics/core.py
from kagami_api.schemas.colonies import (
    AgentsListResponse,
    AgentsStatusResponse,
    AgentState,
    AgentStatus,
    AgentSummary,
    ColonyActivityEvent,
)
from kagami_api.schemas.command import (
    # Core command endpoint responses
    CommandBlockedResponse,
    CommandFallbackResponse,
    CommandResponse,
    CommandSuccessResponse,
    # Request models
    ExecuteRequest,
    # Response models
    ExecuteResponse,
    IntentData,
    NaturalLanguageRequest,
    NaturalLanguageResponse,
    ParseRequest,
    ParseResponse,
    ParsingQualityMetrics,
    SuggestionItem,
    SuggestResponse,
    VirtualActionPlan,
)
from kagami_api.schemas.forge_dtos import (
    ForgeGenerateRequest,
)
from kagami_api.schemas.receipts import (
    ReceiptRecord,
    ReceiptSearchParams,
    ReceiptSearchResponse,
    ReceiptsListResponse,
)
from kagami_api.schemas.vitals import (
    ClusterHealthResponse,
    DeepHealthResponse,
    DependencyCheck,
    FanoVitals,
    HardwareStatus,
    LivenessResponse,
    MLHealthStatus,
    OrganismVitals,
    ReadinessResponse,
    VitalsSummary,
)

__all__ = [
    # Colonies
    "AgentState",
    "AgentStatus",
    "AgentSummary",
    "AgentsListResponse",
    "AgentsStatusResponse",
    "ColonyActivityEvent",
    # Command
    "CommandBlockedResponse",
    "CommandFallbackResponse",
    "CommandResponse",
    "CommandSuccessResponse",
    "ExecuteRequest",
    "ExecuteResponse",
    "IntentData",
    "NaturalLanguageRequest",
    "NaturalLanguageResponse",
    "ParseRequest",
    "ParseResponse",
    "ParsingQualityMetrics",
    "SuggestResponse",
    "SuggestionItem",
    "VirtualActionPlan",
    # Forge
    "ForgeGenerateRequest",
    # Receipts
    "ReceiptRecord",
    "ReceiptSearchParams",
    "ReceiptSearchResponse",
    "ReceiptsListResponse",
    # Vitals
    "ClusterHealthResponse",
    "DeepHealthResponse",
    "DependencyCheck",
    "FanoVitals",
    "HardwareStatus",
    "LivenessResponse",
    "MLHealthStatus",
    "OrganismVitals",
    "ReadinessResponse",
    "VitalsSummary",
]
