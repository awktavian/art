"""Kagami Shared Abstractions Layer — Reduce Duplication by 10-15%.

This module consolidates common patterns identified across the codebase:

1. CachedRepository[T] — Generic caching wrapper for repositories
2. CoordinationStrategy — Base coordination pattern for MetaOrchestrator & SwarmCoordinator
3. ErrorContextBuilder — Unified error context across all services
4. FactoryRegistry — Central factory discovery (451 factory functions)
5. SemanticRouter — Configurable E8 routing (100-200 topics)
6. RetryPolicy — Unified retry logic with configurable backoff strategies

Created: December 30, 2025
Updated: January 12, 2026 (added RetryPolicy)
Optimizes: ~10-15% codebase duplication reduction
"""

from .action_result import (
    ActionError,
    ActionErrorType,
    ActionMetadata,
    ActionResult,
    ActionStatus,
    BatchActionResult,
    aggregate_results,
    from_exception,
    to_action_result,
)
from .action_result_adapter import (
    ActionResultAdapter,
    BatchActionAdapter,
    SmartHomeFunctionAdapter,
    migrate_smart_home_function,
)
from .cached_repository import (
    CachedRepository,
    CacheStrategy,
    RepositoryCache,
    get_cached_repository,
)
from .coordination_strategy import (
    AdaptiveStrategy,
    BaseCoordinator,
    CoordinationMode,
    CoordinationResult,
    CoordinationStrategy,
    ParallelStrategy,
    SequentialStrategy,
)
from .efe_optimization import (
    EFEComputationConfig,
    OptimizedEFECalculator,
    create_fast_efe_config,
    create_memory_efficient_efe_config,
    get_optimized_efe_calculator,
)
from .error_context import (
    ErrorContext,
    ErrorContextBuilder,
    ServiceContext,
    get_error_context_builder,
)
from .factory_registry import (
    FactoryFunction,
    FactoryInfo,
    FactoryRegistry,
    discover_factory,
    get_factory_registry,
    register_factory,
)
from .markov_blanket_enforcement import (
    BoundaryDescriptor,
    BoundaryMetrics,
    BoundaryState,
    BoundaryType,
    BoundaryViolation,
    InformationFlow,
    UnifiedMarkovBlanketEnforcer,
    create_colony_boundary,
    create_digital_boundary,
    create_memory_boundary,
    create_physical_boundary,
    get_unified_markov_enforcer,
)
from .retry_policy import (
    RETRY_AGGRESSIVE,
    RETRY_CONSERVATIVE,
    RETRY_DATABASE,
    RETRY_NETWORK,
    RETRY_QUICK,
    BackoffStrategy,
    RetryContext,
    RetryPolicy,
    execute_with_retry,
    is_retryable,
    retry_with_policy,
)
from .semantic_router import (
    RoutingCache,
    RoutingRule,
    SemanticRouter,
    configure_e8_routing,
    get_semantic_router,
)
from .singleton_consolidation import (
    SingletonRegistry,
    async_singleton_factory,
    get_singleton_registry,
    get_singleton_status,
    reset_all_singletons,
    singleton_factory,
)
from .smart_defaults import (
    ContextType,
    SmartDefault,
    SmartDefaultsRegistry,
    ToolCategory,
    ToolDefaults,
    get_smart_defaults,
    get_smart_defaults_registry,
    validate_tool_parameters,
)
from .tool_composition_framework import (
    CompositionPlan,
    CompositionResult,
    CompositionStrategy,
    OptimizedToolComposer,
    ToolDescriptor,
    ToolType,
    create_fast_composer_config,
    create_reliable_composer_config,
    get_optimized_tool_composer,
)

__all__ = [
    "RETRY_AGGRESSIVE",
    "RETRY_CONSERVATIVE",
    "RETRY_DATABASE",
    "RETRY_NETWORK",
    "RETRY_QUICK",
    "ActionError",
    "ActionErrorType",
    "ActionMetadata",
    # Action Result Pattern
    "ActionResult",
    # Action Result Adapters
    "ActionResultAdapter",
    "ActionStatus",
    "AdaptiveStrategy",
    # Retry Policy
    "BackoffStrategy",
    "BaseCoordinator",
    "BatchActionAdapter",
    "BatchActionResult",
    "BoundaryDescriptor",
    "BoundaryMetrics",
    "BoundaryState",
    # Markov Blanket Enforcement
    "BoundaryType",
    "BoundaryViolation",
    "CacheStrategy",
    # Cached Repository Pattern
    "CachedRepository",
    "CompositionPlan",
    "CompositionResult",
    # Tool Composition Framework
    "CompositionStrategy",
    "ContextType",
    "CoordinationMode",
    "CoordinationResult",
    # Coordination Strategies
    "CoordinationStrategy",
    # EFE Optimization
    "EFEComputationConfig",
    "ErrorContext",
    # Error Context Building
    "ErrorContextBuilder",
    "FactoryFunction",
    "FactoryInfo",
    # Factory Registry
    "FactoryRegistry",
    "InformationFlow",
    "OptimizedEFECalculator",
    "OptimizedToolComposer",
    "ParallelStrategy",
    "RepositoryCache",
    "RetryContext",
    "RetryPolicy",
    "RoutingCache",
    "RoutingRule",
    # Semantic Routing
    "SemanticRouter",
    "SequentialStrategy",
    "ServiceContext",
    # Singleton Consolidation
    "SingletonRegistry",
    "SmartDefault",
    # Smart Defaults
    "SmartDefaultsRegistry",
    "SmartHomeFunctionAdapter",
    "ToolCategory",
    "ToolDefaults",
    "ToolDescriptor",
    "ToolType",
    "UnifiedMarkovBlanketEnforcer",
    "aggregate_results",
    "async_singleton_factory",
    "configure_e8_routing",
    "create_colony_boundary",
    "create_digital_boundary",
    "create_fast_composer_config",
    "create_fast_efe_config",
    "create_memory_boundary",
    "create_memory_efficient_efe_config",
    "create_physical_boundary",
    "create_reliable_composer_config",
    "discover_factory",
    "execute_with_retry",
    "from_exception",
    "get_cached_repository",
    "get_error_context_builder",
    "get_factory_registry",
    "get_optimized_efe_calculator",
    "get_optimized_tool_composer",
    "get_semantic_router",
    "get_singleton_registry",
    "get_singleton_status",
    "get_smart_defaults",
    "get_smart_defaults_registry",
    "get_unified_markov_enforcer",
    "is_retryable",
    "migrate_smart_home_function",
    "register_factory",
    "reset_all_singletons",
    "retry_with_policy",
    "singleton_factory",
    "to_action_result",
    "validate_tool_parameters",
]
