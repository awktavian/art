"""Kagami Agents Package.

Provides agent architectures for distributed cognition:
- HTML Agents: Cognitive substrate in filesystem
- Markdown Agents: Live agents defined in markdown
- Colony Agents: Specialized processing colonies
- Meta Agents: Orchestration and coordination
- Security: Input validation, rate limiting, XSS prevention
- Knowledge Graph: Property graph-based agent memory

Created: January 2026
"""

from kagami.core.agents.auth import (
    AgentEntitlement,
    AgentTier,
    AgentUser,
    require_agent_auth,
    unauthenticated_response,
    upsell_response,
)
from kagami.core.agents.html_agent import (
    AgentMessage,
    AgentType,
    HTMLAgentConfig,
    HTMLAgentGenerator,
    HTMLAgentRegistry,
    get_agent_generator,
)
from kagami.core.agents.html_agent import (
    get_agent_registry as get_html_agent_registry,
)
from kagami.core.agents.knowledge_graph import (
    Entity,
    EntityType,
    KnowledgeGraph,
    KnowledgeGraphConfig,
    Relation,
    RelationType,
    StorageScope,
)
from kagami.core.agents.markdown_loader import (
    AgentRegistry,
    AgentWatcher,
    ParsedMarkdown,
    get_agent_registry,
    get_agent_watcher,
    initialize_agents,
    load_agent,
    load_agent_from_text,
    parse_markdown,
    parse_markdown_file,
)
from kagami.core.agents.schema import (
    AgentSchema,
    AgentState,
    Colony,
    CraftLevel,
    EmbodimentSchema,
    IdentitySchema,
    LearningSchema,
    MemorySchema,
    PerceptionSchema,
    ProductionSchema,
    ReactivitySchema,
    SecretsSchema,
    StorageType,
    StructureSchema,
    VoiceSchema,
    validate_agent_schema,
)
from kagami.core.agents.security import (
    InputValidationError,
    SecurityAuditResult,
    SecurityConfig,
    check_rate_limit,
    check_websocket_connection,
    get_security_config,
    run_security_audit,
    validate_agent_id,
    validate_query,
)

__all__ = [
    # Auth
    "AgentEntitlement",
    # HTML Agents
    "AgentMessage",
    # Markdown Agents
    "AgentRegistry",
    # Schema
    "AgentSchema",
    "AgentState",
    "AgentTier",
    "AgentType",
    "AgentUser",
    "AgentWatcher",
    "Colony",
    "CraftLevel",
    "EmbodimentSchema",
    # Knowledge Graph
    "Entity",
    "EntityType",
    "HTMLAgentConfig",
    "HTMLAgentGenerator",
    "HTMLAgentRegistry",
    "IdentitySchema",
    # Security
    "InputValidationError",
    "KnowledgeGraph",
    "KnowledgeGraphConfig",
    "LearningSchema",
    "MemorySchema",
    "ParsedMarkdown",
    "PerceptionSchema",
    "ProductionSchema",
    "ReactivitySchema",
    "Relation",
    "RelationType",
    "SecretsSchema",
    "SecurityAuditResult",
    "SecurityConfig",
    "StorageScope",
    "StorageType",
    "StructureSchema",
    "VoiceSchema",
    "check_rate_limit",
    "check_websocket_connection",
    "get_agent_generator",
    "get_agent_registry",
    "get_agent_watcher",
    "get_html_agent_registry",
    "get_security_config",
    "initialize_agents",
    "load_agent",
    "load_agent_from_text",
    "parse_markdown",
    "parse_markdown_file",
    "require_agent_auth",
    "run_security_audit",
    "unauthenticated_response",
    "upsell_response",
    "validate_agent_id",
    "validate_agent_schema",
    "validate_query",
]
