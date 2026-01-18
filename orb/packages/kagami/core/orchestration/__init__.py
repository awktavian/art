"""Orchestration System — Unified Cross-Domain Coordination.

This module provides high-level orchestration across all integrated services,
enabling the ecosystem to operate as a coherent, self-improving whole.

Key Components:
    - EcosystemOrchestrator: Unified state and cross-domain triggers
    - GitHubDevelopmentFlow: Automated branch/PR management
    - LinearSprintSync: Sprint and cycle synchronization
    - NotionKnowledgeBase: Structured knowledge persistence

Usage:
    from kagami.core.orchestration import get_ecosystem_orchestrator

    orchestrator = await get_ecosystem_orchestrator()
    state = await orchestrator.get_ecosystem_state()

    # Enable automatic cross-domain triggers
    await orchestrator.enable_cross_domain_triggers()

    # GitHub flow
    from kagami.core.orchestration import get_github_flow
    flow = await get_github_flow()
    await flow.create_branch_from_issue("KAG-123")

    # Linear sync
    from kagami.core.orchestration import get_linear_sync
    sync = await get_linear_sync()
    report = await sync.generate_sprint_report()

    # Notion KB
    from kagami.core.orchestration import get_notion_kb
    kb = await get_notion_kb()
    await kb.store_research("Topic", "Findings...")
"""

from kagami.core.orchestration.ecosystem_orchestrator import (
    AttentionPriority,
    EcosystemOrchestrator,
    EcosystemState,
    ServiceState,
    ServiceTriggerRule,
    ServiceType,
    get_ecosystem_orchestrator,
    initialize_ecosystem_orchestrator,
)
from kagami.core.orchestration.github_flow import (
    BranchInfo,
    CIConclusion,
    CIStatus,
    GitHubDevelopmentFlow,
    PRInfo,
    PRStatus,
    WorkflowRun,
    get_github_flow,
    initialize_github_flow,
)
from kagami.core.orchestration.learning_pipeline import (
    ActionRecord,
    LearningMetrics,
    LearningPipeline,
    RoutingSuggestion,
    get_learning_pipeline,
    initialize_learning_pipeline,
)
from kagami.core.orchestration.linear_sync import (
    CycleInfo,
    IssueInfo,
    IssuePriority,
    IssueState,
    LinearSprintSync,
    SprintReport,
    VelocityMetrics,
    get_linear_sync,
    initialize_linear_sync,
)
from kagami.core.orchestration.notion_kb import (
    ChangelogEntry,
    DecisionEntry,
    DecisionStatus,
    KBEntryType,
    NotionKnowledgeBase,
    PatternCategory,
    PatternEntry,
    ResearchEntry,
    get_notion_kb,
    initialize_notion_kb,
)

__all__ = [
    # Learning Pipeline
    "ActionRecord",
    # Ecosystem Orchestrator
    "AttentionPriority",
    # GitHub Flow
    "BranchInfo",
    "CIConclusion",
    "CIStatus",
    # Notion KB
    "ChangelogEntry",
    # Linear Sync
    "CycleInfo",
    "DecisionEntry",
    "DecisionStatus",
    "EcosystemOrchestrator",
    "EcosystemState",
    "GitHubDevelopmentFlow",
    "IssueInfo",
    "IssuePriority",
    "IssueState",
    "KBEntryType",
    "LearningMetrics",
    "LearningPipeline",
    "LinearSprintSync",
    "NotionKnowledgeBase",
    "PRInfo",
    "PRStatus",
    "PatternCategory",
    "PatternEntry",
    "ResearchEntry",
    "RoutingSuggestion",
    "ServiceState",
    "ServiceTriggerRule",
    "ServiceType",
    "SprintReport",
    "VelocityMetrics",
    "WorkflowRun",
    "get_ecosystem_orchestrator",
    "get_github_flow",
    "get_learning_pipeline",
    "get_linear_sync",
    "get_notion_kb",
    "initialize_ecosystem_orchestrator",
    "initialize_github_flow",
    "initialize_learning_pipeline",
    "initialize_linear_sync",
    "initialize_notion_kb",
]
