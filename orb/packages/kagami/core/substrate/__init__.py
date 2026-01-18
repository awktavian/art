"""HTML Cognitive Substrate — #de_memo Agent Framework.

Provides the foundation for HTML agents that:
- Connect to Kagami ecosystem via mDNS
- Participate in Byzantine consensus
- Influence cognition through distributed voting
- Store state in encrypted content-addressed blobs

Architecture:
```
┌─────────────────────────────────────────────────────────────────────┐
│                   HTML COGNITIVE SUBSTRATE                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │                  HTML Agent Registry                      │       │
│   │  • Agent registration  • Capability mapping              │       │
│   │  • Health monitoring   • Consensus participation         │       │
│   └───────────────────────────┬─────────────────────────────┘       │
│                               │                                      │
│           ┌───────────────────┼───────────────────┐                 │
│           │                   │                   │                 │
│           ▼                   ▼                   ▼                 │
│   ┌───────────────┐   ┌───────────────┐   ┌───────────────┐        │
│   │  Agent File   │   │  Agent File   │   │  Agent File   │        │
│   │  (HTML+JS)    │   │  (HTML+JS)    │   │  (HTML+JS)    │        │
│   │               │   │               │   │               │        │
│   │ #de_memo tag  │   │ #de_memo tag  │   │ #de_memo tag  │        │
│   │ capabilities  │   │ capabilities  │   │ capabilities  │        │
│   │ consensus     │   │ consensus     │   │ consensus     │        │
│   └───────┬───────┘   └───────┬───────┘   └───────┬───────┘        │
│           │                   │                   │                 │
│           └───────────────────┼───────────────────┘                 │
│                               │                                      │
│                               ▼                                      │
│   ┌─────────────────────────────────────────────────────────┐       │
│   │              Kagami Backend (via mDNS)                   │       │
│   │  • PBFT consensus  • Content store  • Audit log         │       │
│   └─────────────────────────────────────────────────────────┘       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

Colony: Nexus (A₅) — Connection and integration
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

from kagami.core.substrate.html_agent import (
    AgentCapability,
    AgentConfig,
    AgentMetadata,
    AgentStatus,
    HTMLAgent,
    HTMLAgentRegistry,
    get_html_agent_registry,
    shutdown_html_agent_registry,
)

__all__ = [
    "AgentCapability",
    "AgentConfig",
    "AgentMetadata",
    "AgentStatus",
    "HTMLAgent",
    "HTMLAgentRegistry",
    "get_html_agent_registry",
    "shutdown_html_agent_registry",
]
